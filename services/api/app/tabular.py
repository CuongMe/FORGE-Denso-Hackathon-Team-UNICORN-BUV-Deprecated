from __future__ import annotations

import csv
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree

import xlrd


PREVIEW_MAX_ROWS = 200
PREVIEW_MAX_COLUMNS = 40


def read_table_sheets(
    source: Path,
    *,
    max_rows: int | None = PREVIEW_MAX_ROWS,
    max_columns: int | None = PREVIEW_MAX_COLUMNS,
) -> list[tuple[str, list[list[object]]]]:
    if source.suffix.casefold() == '.csv':
        with source.open(encoding='utf-8-sig', newline='') as stream:
            rows = list(csv.reader(stream))
            return [('CSV', rows if max_rows is None else rows[:max_rows])]
    if source.suffix.casefold() == '.xls':
        try:
            workbook = xlrd.open_workbook(filename=str(source), on_demand=True)
            try:
                tables = []
                for sheet in workbook.sheets():
                    width = sheet.ncols if max_columns is None else min(sheet.ncols, max_columns)
                    height = sheet.nrows if max_rows is None else min(sheet.nrows, max_rows)
                    tables.append((sheet.name, [
                        [sheet.cell_value(row, column) for column in range(width)]
                        for row in range(height)
                    ]))
                return tables
            finally:
                workbook.release_resources()
        except (xlrd.XLRDError, OSError, ValueError) as exc:
            raise ValueError('Could not read legacy Excel workbook.') from exc
    if source.suffix.casefold() != '.xlsx':
        return []

    namespace = {'main': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    relationship_namespace = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
    package_namespace = 'http://schemas.openxmlformats.org/package/2006/relationships'
    with zipfile.ZipFile(source) as archive:
        shared_strings: list[str] = []
        if 'xl/sharedStrings.xml' in archive.namelist():
            shared_root = ElementTree.fromstring(archive.read('xl/sharedStrings.xml'))
            shared_strings = [
                ''.join(item.text or '' for item in node.findall('.//main:t', namespace))
                for node in shared_root.findall('main:si', namespace)
            ]
        workbook = ElementTree.fromstring(archive.read('xl/workbook.xml'))
        relationships = ElementTree.fromstring(archive.read('xl/_rels/workbook.xml.rels'))
        relationship_map = {
            rel.attrib.get('Id', ''): rel.attrib.get('Target', '')
            for rel in relationships.findall(f'.//{{{package_namespace}}}Relationship')
        }
        tables: list[tuple[str, list[list[object]]]] = []
        for sheet in workbook.findall('.//main:sheet', namespace):
            relation_id = sheet.attrib.get(f'{{{relationship_namespace}}}id', '')
            target = relationship_map.get(relation_id, '')
            if not target:
                continue
            sheet_path = target.lstrip('/') if target.startswith('/') else target
            if not sheet_path.startswith('xl/'):
                sheet_path = f'xl/{sheet_path}'
            if sheet_path not in archive.namelist():
                continue
            root = ElementTree.fromstring(archive.read(sheet_path))
            rows: list[list[object]] = []
            for row_node in root.findall('.//main:sheetData/main:row', namespace):
                values: dict[int, object] = {}
                for cell in row_node.findall('main:c', namespace):
                    match = re.match(r'([A-Za-z]+)', cell.attrib.get('r', ''))
                    if not match:
                        continue
                    column = 0
                    for letter in match.group(1).upper():
                        column = column * 26 + ord(letter) - ord('A') + 1
                    column -= 1
                    if max_columns is not None and column >= max_columns:
                        continue
                    cell_type = cell.attrib.get('t', '')
                    if cell_type == 'inlineStr':
                        value = ''.join(item.text or '' for item in cell.findall('.//main:t', namespace))
                    else:
                        value_node = cell.find('main:v', namespace)
                        value = value_node.text if value_node is not None else ''
                        if cell_type == 's' and value:
                            value = shared_strings[int(value)] if int(value) < len(shared_strings) else value
                        elif cell_type == 'b':
                            value = 'TRUE' if value == '1' else 'FALSE'
                    values[column] = value
                width = max(values.keys(), default=-1) + 1
                rows.append([values.get(index, '') for index in range(width)])
                if max_rows is not None and len(rows) >= max_rows:
                    break
            tables.append((str(sheet.attrib.get('name') or 'Sheet'), rows))
        return tables


def read_table_rows(source: Path) -> list[dict[str, object]]:
    tables = read_table_sheets(source, max_rows=None, max_columns=None)
    if not tables:
        return []
    header, *body = tables[0][1]
    names = [str(value or f'column_{index + 1}') for index, value in enumerate(header)]
    return [
        {names[index]: row[index] if index < len(row) else '' for index in range(len(names))}
        for row in body
    ]
