"""Open an .xlsx with openpyxl and print the sheet names and sizes (checks the stdlib writer).
Run: uv run --with openpyxl python -I -X utf8 tests/check_xlsx.py <file.xlsx>"""
import sys

import openpyxl

wb = openpyxl.load_workbook(sys.argv[1])
for ws in wb.worksheets:
    print(f"sheet {ws.title}: {ws.max_row} rows x {ws.max_column} cols; A1={ws['A1'].value!r} D2={ws['D2'].value!r}")
