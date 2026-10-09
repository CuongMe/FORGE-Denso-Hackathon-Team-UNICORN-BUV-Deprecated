from app import tabular


class Sheet:
    name = 'Inspection'
    rows = [['part', 'status'], ['M6 bolt', 'ok'], ['M8 nut', 'hold']]
    nrows = len(rows)
    ncols = len(rows[0])

    def cell_value(self, row, column):
        return self.rows[row][column]


class Workbook:
    def __init__(self):
        self.released = False

    def sheets(self):
        return [Sheet()]

    def release_resources(self):
        self.released = True


def test_xls_reader_preserves_sheets_and_applies_preview_limits(tmp_path, monkeypatch):
    source = tmp_path / 'inspection.xls'
    source.write_bytes(b'xls fixture')
    workbook = Workbook()
    monkeypatch.setattr(tabular.xlrd, 'open_workbook', lambda **_: workbook)

    sheets = tabular.read_table_sheets(source, max_rows=2, max_columns=1)

    assert sheets == [('Inspection', [['part'], ['M6 bolt']])]
    assert workbook.released
