'use client';

import { useEffect, useMemo, useState } from 'react';

import { getGraph } from '@/lib/api';
import type { DocumentSummary, GraphEdge, GraphNode, GraphResponse, HealthResponse } from '@/lib/types';

import { ArrowRightIcon, SearchIcon } from './ForgeIcons';
import { GraphCanvas } from './GraphCanvas';

type GraphWorkspaceProps = {
  documents: DocumentSummary[];
  health: HealthResponse | null;
};

type NodeKind = GraphNode['kind'];

const defaultVisibility: Record<NodeKind, boolean> = { source: true, chunk: true, concept: true };

function nodeTypeLabel(kind: NodeKind) {
  return kind === 'source' ? 'SOURCES' : kind === 'chunk' ? 'CHUNKS' : 'CONCEPTS';
}

function GraphDetails({ node, edges, nodes, onSelect }: {
  node: GraphNode | null;
  edges: GraphEdge[];
  nodes: GraphNode[];
  onSelect: (node: GraphNode) => void;
}) {
  if (!node) {
    return <aside className='graph-details' role='status'><p>Select a node to inspect its relationships.</p></aside>;
  }
  const nodeById = new Map(nodes.map((item) => [item.id, item]));
  const related = edges
    .filter((edge) => edge.source === node.id || edge.target === node.id)
    .map((edge) => ({ edge, node: nodeById.get(edge.source === node.id ? edge.target : edge.source) }))
    .filter((item): item is { edge: GraphEdge; node: GraphNode } => Boolean(item.node));

  return (
    <aside className='graph-details' aria-live='polite'>
      <div className='forge-side-card-heading'>
        <p className='forge-eyebrow'>NODE DETAILS</p>
        <span className='graph-detail-pill'>{node.kind.toUpperCase()}</span>
      </div>
      <h2>{node.label}</h2>
      <p>{node.subtitle}</p>
      <dl className='graph-detail-meta'>
        {node.source_name && <div><dt>SOURCE</dt><dd>{node.source_name}</dd></div>}
        {node.page !== null && node.page !== undefined && <div><dt>PAGE</dt><dd>{node.page || '—'}</dd></div>}
        {node.region && <div><dt>REGION</dt><dd>{node.region}</dd></div>}
        {node.region_type && <div><dt>TYPE</dt><dd>{node.region_type}</dd></div>}
        {node.status && <div><dt>STATUS</dt><dd>{node.status}</dd></div>}
      </dl>
      {node.preview && <p className='graph-node-preview'>{node.preview}</p>}
      <div className='forge-relationship-list'>
        <h3>RELATIONSHIPS · {related.length}</h3>
        {related.length ? related.map(({ edge, node: relatedNode }) => (
          <button key={edge.id} type='button' className='forge-relationship' onClick={() => onSelect(relatedNode)}>
            <span>{relatedNode.label}<small>{edge.relation}{edge.provenance_ref ? ` · ${edge.provenance_ref}` : ''}</small></span>
            <strong>{edge.confidence.toFixed(2)}</strong>
          </button>
        )) : <p className='forge-empty-copy'>No linked evidence in this view.</p>}
      </div>
      {node.provenance.length > 0 && <p className='graph-provenance-note'>Exact source provenance is attached to this node.</p>}
    </aside>
  );
}

export function GraphWorkspace({ documents, health }: GraphWorkspaceProps) {
  const [graph, setGraph] = useState<GraphResponse | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [visibility, setVisibility] = useState(defaultVisibility);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const firstSourceId = documents[0] ? `source:${documents[0].doc_id}` : undefined;

  async function loadGraph(params: { nodeId?: string; search?: string }, fallbackId?: string) {
    setIsLoading(true);
    setError(null);
    try {
      const next = await getGraph({ ...params, depth: 2, limit: 60 });
      setGraph(next);
      setSelectedNodeId(next.selected_node ?? fallbackId ?? next.nodes.find((node) => node.kind === 'source')?.id ?? null);
    } catch (loadError: unknown) {
      setError(loadError instanceof Error ? loadError.message : 'The graph could not be loaded.');
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    if (!firstSourceId || graph) return;
    const timer = window.setTimeout(() => void loadGraph({ nodeId: firstSourceId }, firstSourceId), 0);
    return () => window.clearTimeout(timer);
  }, [firstSourceId, graph]);

  const visibleNodes = useMemo(
    () => graph?.nodes.filter((node) => visibility[node.kind]) ?? [],
    [graph, visibility],
  );
  const visibleEdges = useMemo(
    () => graph?.edges.filter((edge) => visibleNodes.some((node) => node.id === edge.source) && visibleNodes.some((node) => node.id === edge.target)) ?? [],
    [graph, visibleNodes],
  );
  const selectedNode = visibleNodes.find((node) => node.id === selectedNodeId) ?? graph?.nodes.find((node) => node.id === selectedNodeId) ?? null;

  function selectNode(node: GraphNode) {
    setSelectedNodeId(node.id);
    void loadGraph({ nodeId: node.id }, node.id);
  }

  function submitSearch(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const value = search.trim();
    void loadGraph(value ? { search: value } : { nodeId: firstSourceId }, firstSourceId);
  }

  return (
    <div className='forge-workspace graph-workspace'>
      <div className='forge-workspace-heading graph-heading'>
        <div>
          <p className='forge-eyebrow'>GRAPH</p>
          <h1>Corpus graph</h1>
          <p className='forge-workspace-helper'>Explore live relationships between indexed sources, evidence chunks, and factory concepts.</p>
        </div>
        <div className='forge-corpus-summary'><strong>{graph?.total_nodes ?? health?.graph?.nodes_count ?? '—'}</strong><span>GRAPH NODES</span></div>
      </div>

      <form className='forge-search-bar graph-search-bar' onSubmit={submitSearch}>
        <SearchIcon />
        <label className='forge-sr-only' htmlFor='graph-search'>Search the corpus graph</label>
        <input id='graph-search' value={search} onChange={(event) => setSearch(event.target.value)} placeholder='Search sources, chunks, or concepts...' />
        <button type='submit' className='forge-search-submit' aria-label='Search graph'><ArrowRightIcon /></button>
      </form>

      <div className='graph-filter-row'>
        <span className='graph-filter-label'>FILTER BY TYPE</span>
        <div className='graph-filter-group'>
          {(Object.keys(defaultVisibility) as NodeKind[]).map((kind) => (
            <label key={kind} className={`forge-filter-chip graph-layer-filter ${visibility[kind] ? 'is-active' : ''}`}>
              <input type='checkbox' checked={visibility[kind]} onChange={() => setVisibility((current) => ({ ...current, [kind]: !current[kind] }))} />
              {nodeTypeLabel(kind)}
            </label>
          ))}
        </div>
        <span className='graph-result-count'>{visibleNodes.length} visible · {visibleEdges.length} links</span>
      </div>

      {error && <div className='forge-connection-alert' role='alert'>{error}</div>}
      <div className='graph-layout'>
        <section aria-label='Live corpus graph'>
          {isLoading && !graph ? <div className='forge-placeholder-card graph-loading-card' role='status'>Loading live graph…</div> : graph ? <GraphCanvas nodes={visibleNodes} edges={visibleEdges} selectedNodeId={selectedNodeId} onSelect={selectNode} /> : <div className='forge-placeholder-card' role='status'>No graph data is available yet.</div>}
          {isLoading && graph && <p className='graph-loading-label' role='status'>Updating neighborhood…</p>}
        </section>
        <GraphDetails node={selectedNode} edges={visibleEdges} nodes={visibleNodes} onSelect={selectNode} />
      </div>
    </div>
  );
}

export function GraphWorkspaceRail({ documents, health }: GraphWorkspaceProps) {
  const nodeCount = health?.graph?.nodes_count ?? '—';
  const edgeCount = health?.graph?.edges_count ?? '—';
  return (
    <div className='forge-rail-content forge-graph-rail'>
      <p className='forge-eyebrow'>GRAPH VIEW</p>
      <p className='forge-rail-helper'>Explore indexed relationships.</p>
      <div className='forge-rail-stat-grid'><div><strong>{health?.documents_count ?? documents.length}</strong><span>SOURCES</span></div><div><strong>{health?.chunks_count ?? '—'}</strong><span>CHUNKS</span></div></div>
      <div className='forge-rail-section'><p className='forge-eyebrow'>LIVE GRAPH</p><div className='forge-rail-filter-stack'><div className='forge-rail-filter is-active'><i /><span>GRAPH NODES</span><small>{nodeCount}</small></div><div className='forge-rail-filter'><i className='chunk' /><span>GRAPH LINKS</span><small>{edgeCount}</small></div></div></div>
      <div className='graph-rail-legend'><div><i />Sources</div><div><i className='chunk' />Chunks</div><div><i className='concept' />Concepts</div></div>
      <p className='forge-rail-scroll-hint'>CLICK A NODE TO EXPAND ITS EVIDENCE</p>
    </div>
  );
}
