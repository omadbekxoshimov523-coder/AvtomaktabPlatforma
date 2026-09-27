"""CSV / XLSX / PDF-chop eksporti (faqat stdlib).
- CSV: to'liq yaroqli fayl
- XLSX: zipfile + minimal XML orqali haqiqiy Excel fayli
- PDF: chop-uchun HTML ko'rinish (brauzer orqali PDF qilish mumkin)
"""
import csv
import io
import json
import zipfile

from .db import now


def to_csv(rows: list, filename: str = "export.csv") -> dict:
    buf = io.StringIO()
    if rows:
        writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()), delimiter=";")
        writer.writeheader()
        writer.writerows(rows)
    data = buf.getvalue().encode("utf-8-sig")
    return {"filename": filename, "mime": "text/csv; charset=utf-8", "data": data}


def _xl_col(n: int) -> str:
    s = ""
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def to_xlsx(rows: list, sheet: str = "Hisobot") -> dict:
    headers = list(rows[0].keys()) if rows else []
    body = []
    for r in rows:
        body.append([str(r[h]) if r.get(h) is not None else "" for h in headers])
    max_col = max(1, len(headers))
    col_letters = [_xl_col(i) for i in range(1, max_col + 1)]
    cols_xml = "\n".join(
        f'<col min="{i}" max="{i}" width="22" customWidth="1"/>' for i in range(1, max_col + 1)
    )
    sheet_rows = []
    if headers:
        sheet_rows.append(
            "<row>" + "".join(f'<c r="{c}1" t="inlineStr"><is><t>{_esc(h)}</t></is></c>' for c, h in zip(col_letters, headers)) + "</row>"
        )
    for ri, row in enumerate(body, start=2):
        cells = "".join(
            f'<c r="{c}{ri}" t="inlineStr"><is><t>{_esc(v)}</t></is></c>' for c, v in zip(col_letters, row)
        )
        sheet_rows.append(f"<row>{cells}</row>")
    sheet_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"<cols>{cols_xml}</cols><sheetData>{''.join(sheet_rows)}</sheetData></worksheet>"
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        "</Types>"
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        "</Relationships>"
    )
    workbook = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="S" sheetId="1" r:id="rId1"/></sheets></workbook>'
    )
    workbook_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
        "</Relationships>"
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", rels)
        z.writestr("xl/workbook.xml", workbook.replace('name="S"', f'name="{_esc(sheet[:31])}"'))
        z.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        z.writestr("xl/worksheets/sheet1.xml", sheet_xml)
    return {"filename": "hisobot.xlsx", "mime": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "data": buf.getvalue()}


def to_pdf_html(rows: list, title: str = "Hisobot") -> dict:
    head = "".join(f"<th>{_esc(h)}</th>" for h in (list(rows[0].keys()) if rows else []))
    trs = ""
    for r in rows:
        trs += "<tr>" + "".join(f"<td>{_esc(str(r.get(h) or ''))}</td>" for h in (list(rows[0].keys()) if rows else [])) + "</tr>"
    html = (
        "<!DOCTYPE html><html><head><meta charset='utf-8'><style>"
        "body{font-family:Arial,sans-serif;margin:24px}h1{font-size:20px}"
        "table{border-collapse:collapse;width:100%;font-size:13px;margin-top:12px}"
        "th,td{border:1px solid #c9d4e8;padding:8px;text-align:left}th{background:#0f2b5b;color:#fff}@media print{body{print-color-adjust:exact}}"
        "</style></head><body>"
        f"<h1>{_esc(title)}</h1><p>{_esc(now())}</p><table><thead><tr>{head}</tr></thead><tbody>{trs}</tbody></table>"
        "<script>window.print()</script></body></html>"
    )
    return {"filename": "hisobot.html", "mime": "text/html; charset=utf-8", "data": html.encode("utf-8")}


def _esc(v: str) -> str:
    return (v.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;").replace("'", "&apos;"))


def export_table(rows: list, fmt: str, sheet: str = "Hisobot") -> dict:
    if fmt == "xlsx":
        return to_xlsx(rows, sheet)
    if fmt == "pdf":
        return to_pdf_html(rows, sheet)
    return to_csv(rows, sheet.replace(" ", "_") + ".csv")