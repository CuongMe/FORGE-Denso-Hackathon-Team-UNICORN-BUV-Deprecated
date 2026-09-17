from __future__ import annotations

from collections import defaultdict
import json
from pathlib import Path
import re
from threading import RLock
from typing import Any, Iterable, Mapping, Sequence

from app.models import Chunk


class GraphStoreUnavailable(RuntimeError):
    """Raised when the optional Kùzu graph runtime is not installed."""


_DOMAIN_TERMS = {
    'assembly', 'bolt', 'calibration', 'checklist', 'concept', 'ecu', 'ehs',
    'energy', 'fixture', 'inspection', 'machine', 'maintenance', 'operator',
    'procedure', 'quality', 'safety', 'torque', 'tool', 'work',
}
_STOP_WORDS = {
    'and', 'are', 'before', 'confirm', 'document', 'for', 'from', 'is', 'of',
    'the', 'this', 'use', 'verify', 'with',
}


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'))


def _loads(value: str, default: object) -> object:
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return default


def _slug(value: str) -> str:
    return re.sub(r'[^a-z0-9]+', '-', value.casefold()).strip('-')


def _concept_labels(chunk: Chunk, document: Mapping[str, object] | None) -> list[str]:
    text = ' '.join(
        value
        for value in (
            chunk.region,
            str(document.get('factory_topic') or '') if document else '',
            chunk.content[:2400],
        )
        if value
    )
    labels: dict[str, str] = {}
    for phrase in re.findall(r'\b[a-z][a-z]+(?:\s+[a-z][a-z]+){1,2}\b', text.casefold()):
        if phrase in {'document evidence', 'factory source'}:
            continue
        if any(word in _DOMAIN_TERMS for word in phrase.split()):
            labels.setdefault(_slug(phrase), phrase)
    for token in re.findall(r'\b[A-Za-z][A-Za-z0-9/-]{2,}\b', text):
        normalized = token.casefold()
        if normalized in _STOP_WORDS:
            continue
        if normalized in _DOMAIN_TERMS or token.isupper() or any(char.isdigit() for char in token):
            labels.setdefault(_slug(token), token)
    return list(labels.values())[:12]


def _page(value: object) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


class KuzuGraphStore:
    """Small Kùzu adapter for provenance-aware graph storage and exploration."""

    def __init__(self, database_path: Path) -> None:
        try:
            import kuzu
        except ImportError as exc:
            raise GraphStoreUnavailable(
                'Kùzu is not installed. Install services/api/requirements-production.txt.'
            ) from exc

        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._database = kuzu.Database(str(self.database_path))
        self._connection = kuzu.Connection(self._database)
        self._initialize_schema()

    def close(self) -> None:
        with self._lock:
            close_connection = getattr(self._connection, 'close', None)
            if callable(close_connection):
                close_connection()
            close_database = getattr(self._database, 'close', None)
            if callable(close_database):
                close_database()

    def _execute(self, query: str, parameters: Mapping[str, object] | None = None) -> Any:
        with self._lock:
            if parameters:
                return self._connection.execute(query, parameters=dict(parameters))
            return self._connection.execute(query)

    @staticmethod
    def _rows(result: Any) -> Iterable[list[object]]:
        while result.has_next():
            yield result.get_next()

    def _initialize_schema(self) -> None:
        statements = (
            '''CREATE NODE TABLE IF NOT EXISTS Source(
                id STRING PRIMARY KEY, label STRING, source_name STRING,
                source_path STRING, format STRING, status STRING,
                factory_topic STRING)''',
            '''CREATE NODE TABLE IF NOT EXISTS Chunk(
                id STRING PRIMARY KEY, label STRING, doc_id STRING,
                source_name STRING, source_path STRING, page INT64,
                pages STRING, region STRING, region_type STRING,
                preview STRING, provenance STRING)''',
            'CREATE NODE TABLE IF NOT EXISTS Concept(id STRING PRIMARY KEY, label STRING)',
            '''CREATE REL TABLE IF NOT EXISTS Contains(
                FROM Source TO Chunk, edge_id STRING, relation STRING,
                page INT64, region STRING, provenance_ref STRING,
                confidence DOUBLE)''',
            '''CREATE REL TABLE IF NOT EXISTS Mentions(
                FROM Chunk TO Concept, edge_id STRING, relation STRING,
                page INT64, region STRING, provenance_ref STRING,
                confidence DOUBLE)''',
            '''CREATE REL TABLE IF NOT EXISTS Related(
                FROM Source TO Source, edge_id STRING, relation STRING,
                page INT64, region STRING, provenance_ref STRING,
                confidence DOUBLE)''',
        )
        for statement in statements:
            self._execute(statement)

    def sync_documents(
        self,
        documents: Sequence[Mapping[str, object]],
        chunks: Sequence[Chunk],
    ) -> None:
        document_by_id = {str(document['doc_id']): document for document in documents}
        concepts_by_source: dict[str, set[str]] = defaultdict(set)

        for document_id, document in document_by_id.items():
            self._execute(
                '''MERGE (source:Source {id: $id})
                SET source.label = $label, source.source_name = $source_name,
                    source.source_path = $source_path, source.format = $format,
                    source.status = $status, source.factory_topic = $factory_topic''',
                {
                    'id': document_id,
                    'label': str(document.get('source_name') or document_id),
                    'source_name': str(document.get('source_name') or document_id),
                    'source_path': str(document.get('source_path') or ''),
                    'format': str(document.get('format') or 'DOCUMENT').upper(),
                    'status': str(document.get('status') or 'indexed'),
                    'factory_topic': str(document.get('factory_topic') or 'factory source'),
                },
            )

        for chunk in chunks:
            document = document_by_id.get(chunk.doc_id)
            self._execute(
                '''MERGE (item:Chunk {id: $id})
                SET item.label = $label, item.doc_id = $doc_id,
                    item.source_name = $source_name, item.source_path = $source_path,
                    item.page = $page, item.pages = $pages, item.region = $region,
                    item.region_type = $region_type, item.preview = $preview,
                    item.provenance = $provenance''',
                {
                    'id': chunk.chunk_id,
                    'label': chunk.region or chunk.chunk_id,
                    'doc_id': chunk.doc_id,
                    'source_name': chunk.source_name,
                    'source_path': chunk.source_path,
                    'page': _page(chunk.page),
                    'pages': _json(list(chunk.pages)),
                    'region': chunk.region,
                    'region_type': chunk.region_type,
                    'preview': chunk.content[:280],
                    'provenance': _json([item.model_dump(mode='json') for item in chunk.provenance]),
                },
            )
            provenance_ref = chunk.provenance[0].ref if chunk.provenance else ''
            self._execute(
                '''MATCH (source:Source {id: $source_id}), (item:Chunk {id: $chunk_id})
                MERGE (source)-[edge:Contains {edge_id: $edge_id}]->(item)
                SET edge.relation = $relation, edge.page = $page,
                    edge.region = $region, edge.provenance_ref = $provenance_ref,
                    edge.confidence = $confidence''',
                {
                    'source_id': chunk.doc_id,
                    'chunk_id': chunk.chunk_id,
                    'edge_id': f'contains:{chunk.doc_id}:{chunk.chunk_id}',
                    'relation': 'contains',
                    'page': _page(chunk.page),
                    'region': chunk.region,
                    'provenance_ref': provenance_ref,
                    'confidence': 1.0,
                },
            )

            for label in _concept_labels(chunk, document):
                concept_id = _slug(label)
                concepts_by_source[chunk.doc_id].add(concept_id)
                self._execute(
                    'MERGE (concept:Concept {id: $id}) SET concept.label = $label',
                    {'id': concept_id, 'label': label},
                )
                self._execute(
                    '''MATCH (item:Chunk {id: $chunk_id}), (concept:Concept {id: $concept_id})
                    MERGE (item)-[edge:Mentions {edge_id: $edge_id}]->(concept)
                    SET edge.relation = $relation, edge.page = $page,
                        edge.region = $region, edge.provenance_ref = $provenance_ref,
                        edge.confidence = $confidence''',
                    {
                        'chunk_id': chunk.chunk_id,
                        'concept_id': concept_id,
                        'edge_id': f'mentions:{chunk.chunk_id}:{concept_id}',
                        'relation': 'mentions',
                        'page': _page(chunk.page),
                        'region': chunk.region,
                        'provenance_ref': provenance_ref,
                        'confidence': 0.85,
                    },
                )

        source_ids = sorted(concepts_by_source)
        for index, left_id in enumerate(source_ids):
            for right_id in source_ids[index + 1:]:
                shared = concepts_by_source[left_id] & concepts_by_source[right_id]
                if not shared:
                    continue
                self._execute(
                    '''MATCH (left:Source {id: $left_id}), (right:Source {id: $right_id})
                    MERGE (left)-[edge:Related {edge_id: $edge_id}]->(right)
                    SET edge.relation = $relation, edge.page = $page,
                        edge.region = $region, edge.provenance_ref = $provenance_ref,
                        edge.confidence = $confidence''',
                    {
                        'left_id': left_id,
                        'right_id': right_id,
                        'edge_id': f'related:{left_id}:{right_id}',
                        'relation': 'related',
                        'page': 0,
                        'region': '',
                        'provenance_ref': ','.join(sorted(shared)[:3]),
                        'confidence': min(1.0, 0.55 + (0.08 * len(shared))),
                    },
                )

    def snapshot(
        self,
        *,
        seed_id: str | None = None,
        search: str | None = None,
        depth: int = 1,
        limit: int = 100,
        kinds: set[str] | None = None,
    ) -> dict[str, object]:
        nodes = self._read_nodes()
        edges = self._read_edges()
        by_id = {node['id']: node for node in nodes}
        matching = {
            node['id']
            for node in nodes
            if search and search.casefold() in (
                f"{node['id']} {node['label']} {node.get('source_name', '')}"
            ).casefold()
        }
        selected_seed = seed_id if seed_id in by_id else None
        if selected_seed is None and matching:
            selected_seed = sorted(matching)[0]
        adjacency: dict[str, set[str]] = defaultdict(set)
        for edge in edges:
            adjacency[edge['source']].add(edge['target'])
            adjacency[edge['target']].add(edge['source'])

        if selected_seed is not None:
            selected = {selected_seed}
            frontier = {selected_seed}
            for _ in range(max(0, min(depth, 3))):
                frontier = {
                    neighbor
                    for node_id in frontier
                    for neighbor in adjacency[node_id]
                    if neighbor not in selected
                }
                selected.update(frontier)
        elif matching:
            selected = set(matching)
        else:
            selected = set(by_id)
        if kinds:
            selected = {node_id for node_id in selected if by_id[node_id]['kind'] in kinds}
        ordered_ids = sorted(
            selected,
            key=lambda node_id: (0 if node_id == selected_seed else 1, node_id),
        )[:max(1, min(limit, 500))]
        selected_set = set(ordered_ids)
        return {
            'backend': 'kuzu',
            'selected_node': selected_seed,
            'nodes': [by_id[node_id] for node_id in ordered_ids],
            'edges': [
                edge for edge in edges
                if edge['source'] in selected_set and edge['target'] in selected_set
            ],
            'total_nodes': len(nodes),
            'total_edges': len(edges),
        }

    def status(self) -> dict[str, object]:
        graph = self.snapshot(limit=500)
        return {
            'backend': 'kuzu',
            'available': True,
            'nodes_count': graph['total_nodes'],
            'edges_count': graph['total_edges'],
            'database_path': str(self.database_path),
        }

    def _read_nodes(self) -> list[dict[str, object]]:
        nodes: list[dict[str, object]] = []
        for row in self._rows(self._execute(
            'MATCH (node:Source) RETURN node.id, node.label, node.source_name, '
            'node.source_path, node.format, node.status, node.factory_topic'
        )):
            nodes.append({
                'id': f'source:{row[0]}', 'kind': 'source', 'label': row[1],
                'subtitle': f'{row[4]} · {row[5]}', 'doc_id': row[0],
                'source_name': row[2], 'source_path': row[3], 'format': row[4],
                'status': row[5], 'factory_topic': row[6],
            })
        for row in self._rows(self._execute(
            'MATCH (node:Chunk) RETURN node.id, node.label, node.doc_id, '
            'node.source_name, node.source_path, node.page, node.pages, '
            'node.region, node.region_type, node.preview, node.provenance'
        )):
            nodes.append({
                'id': f'chunk:{row[0]}', 'kind': 'chunk', 'label': row[1],
                'subtitle': f'Chunk · page {row[5] or "—"}', 'doc_id': row[2],
                'source_name': row[3], 'source_path': row[4], 'page': row[5] or None,
                'pages': _loads(row[6], []), 'region': row[7],
                'region_type': row[8], 'preview': row[9], 'provenance': _loads(row[10], []),
            })
        for row in self._rows(self._execute('MATCH (node:Concept) RETURN node.id, node.label')):
            nodes.append({
                'id': f'concept:{row[0]}', 'kind': 'concept', 'label': row[1],
                'subtitle': 'Concept',
            })
        return nodes

    def _read_edges(self) -> list[dict[str, object]]:
        edges: list[dict[str, object]] = []
        queries = (
            ('source', 'chunk', 'MATCH (left:Source)-[edge:Contains]->(right:Chunk) '),
            ('chunk', 'concept', 'MATCH (left:Chunk)-[edge:Mentions]->(right:Concept) '),
            ('source', 'source', 'MATCH (left:Source)-[edge:Related]->(right:Source) '),
        )
        for source_kind, target_kind, prefix in queries:
            rows = self._rows(self._execute(
                prefix + 'RETURN left.id, right.id, edge.edge_id, edge.relation, '
                'edge.page, edge.region, edge.provenance_ref, edge.confidence'
            ))
            for row in rows:
                edges.append({
                    'id': row[2], 'source': f'{source_kind}:{row[0]}',
                    'target': f'{target_kind}:{row[1]}', 'relation': row[3],
                    'page': row[4] or None, 'region': row[5] or None,
                    'provenance_ref': row[6] or None,
                    'confidence': float(row[7] or 0.0),
                })
        return edges
