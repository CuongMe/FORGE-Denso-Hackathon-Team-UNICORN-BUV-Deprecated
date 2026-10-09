from __future__ import annotations

import csv
import re
import zipfile
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree

import xlrd

from app.models import Chunk


def _unique_pages(chunks: Iterable[Chunk]) -> tuple[int, ...]:
    return tuple(sorted({page for chunk in chunks for page in chunk.pages}))


def _csv_shape(source: Path) -> tuple[int, int]:
    try:
        with source.open(encoding='utf-8-sig', newline='') as stream:
            rows = list(csv.reader(stream))
    except (OSError, UnicodeError, csv.Error):
        return 0, 0
    if not rows:
        return 0, 0
    return max(0, len(rows) - 1), len(rows[0])


def _cell_column(value: str) -> int:
    letters = re.match(r'[A-Za-z]+', value)
    if not letters:
        return 0
    total = 0
    for letter in letters.group(0).upper():
        total = total * 26 + ord(letter) - ord('A') + 1
    return total


def _xlsx_sheet_count(source: Path) -> int:
    namespace = {'main': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    try:
        with zipfile.ZipFile(source) as archive:
            workbook = ElementTree.fromstring(archive.read('xl/workbook.xml'))
            return len(workbook.findall('.//main:sheet', namespace))
    except (OSError, KeyError, ValueError, ElementTree.ParseError, zipfile.BadZipFile):
        return 0


def _xlsx_shape(source: Path) -> tuple[int, int]:
    namespace = {'main': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    relationship_namespace = (
        'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
    )
    package_namespace = 'http://schemas.openxmlformats.org/package/2006/relationships'
    try:
        with zipfile.ZipFile(source) as archive:
            workbook = ElementTree.fromstring(archive.read('xl/workbook.xml'))
            relationships = ElementTree.fromstring(
                archive.read('xl/_rels/workbook.xml.rels')
            )
            relationship_map = {
                rel.attrib.get('Id', ''): rel.attrib.get('Target', '')
                for rel in relationships.findall(f'.//{{{package_namespace}}}Relationship')
            }
            rows = 0
            columns = 0
            for sheet in workbook.findall('.//main:sheet', namespace):
                rel_id = sheet.attrib.get(f'{{{relationship_namespace}}}id', '')
                target = relationship_map.get(rel_id, '')
                if not target:
                    continue
                sheet_path = Path('xl') / target.lstrip('/')
                if target.startswith('/xl/'):
                    sheet_path = Path(target.lstrip('/'))
                xml = ElementTree.fromstring(archive.read(sheet_path.as_posix()))
                dimension = xml.find('.//main:dimension', namespace)
                reference = dimension.attrib.get('ref', '') if dimension is not None else ''
                end = reference.split(':')[-1] if reference else ''
                row_match = re.search(r'(\d+)$', end)
                if row_match:
                    rows = max(rows, int(row_match.group(1)))
                columns = max(columns, _cell_column(end))
            return rows, columns
    except (OSError, KeyError, ValueError, ElementTree.ParseError, zipfile.BadZipFile):
        return 0, 0


def _xls_shape(source: Path) -> tuple[int, int, int]:
    try:
        workbook = xlrd.open_workbook(filename=str(source), on_demand=True)
        try:
            sheets = workbook.sheets()
            return (
                len(workbook.sheet_names()),
                max((sheet.nrows for sheet in sheets), default=0),
                max((sheet.ncols for sheet in sheets), default=0),
            )
        finally:
            workbook.release_resources()
    except (xlrd.XLRDError, OSError, ValueError):
        return 0, 0, 0


def summarize_document(
    *,
    source: Path,
    doc_id: str,
    source_name: str,
    source_path: str,
    file_format: str,
    modality: str,
    language: str,
    factory_topic: str,
    chunks: Iterable[Chunk],
    status: str = 'ready',
) -> dict[str, object]:
    chunk_list = list(chunks)
    suffix = source.suffix.casefold()
    pages = _unique_pages(chunk_list)
    image_refs = {
        item.ref
        for chunk in chunk_list
        for item in chunk.provenance
        if item.kind == 'image'
    }
    region_types = sorted({item.kind for chunk in chunk_list for item in chunk.provenance})
    summary: dict[str, object] = {
        'doc_id': doc_id,
        'source_name': source_name,
        'source_path': source_path,
        'format': file_format.upper(),
        'modality': modality,
        'language': language,
        'factory_topic': factory_topic,
        'status': status,
        'chunk_count': len(chunk_list),
        'page_count': len(pages) if suffix == '.pdf' else 0,
        'sheet_count': 0,
        'row_count': 0,
        'column_count': 0,
        'image_count': (
            max(1, len(image_refs))
            if suffix in {'.png', '.jpg', '.jpeg', '.webp', '.bmp'}
            else len(image_refs)
        ),
        'region_types': region_types,
    }
    if suffix == '.xlsx':
        summary['sheet_count'] = _xlsx_sheet_count(source)
        summary['row_count'], summary['column_count'] = _xlsx_shape(source)
    elif suffix == '.xls':
        summary['sheet_count'], summary['row_count'], summary['column_count'] = _xls_shape(source)
    elif suffix == '.csv':
        summary['row_count'], summary['column_count'] = _csv_shape(source)
    return summary
