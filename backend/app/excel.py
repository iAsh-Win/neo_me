"""Excel in / out – the team already lives in Excel, so the system speaks it too."""
from io import BytesIO

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from . import workflow as wf

HEAD_FILL = PatternFill("solid", fgColor="5B2C83")
HEAD_FONT = Font(bold=True, color="FFFFFF")


def _sheet(ws, headers, rows, widths=None):
    ws.append(headers)
    for c in ws[1]:
        c.fill, c.font = HEAD_FILL, HEAD_FONT
        c.alignment = Alignment(vertical="center")
    for r in rows:
        ws.append(r)
    for i, h in enumerate(headers, 1):
        w = (widths or {}).get(h) or max(len(str(h)) + 4, 14)
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "A2"


def _out(wb) -> bytes:
    bio = BytesIO()
    wb.save(bio)
    return bio.getvalue()


def master_workbook(summaries: list) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Master"
    rows = [[s["code"] or "", s["title"], s["ptype_label"], s["market"], s["initiator"]["name"],
             s["status"].replace("_", " ").title(), s["phase_name"], s["step_name"],
             " + ".join(w["label"] for w in s["waiting"]), s["days_in_step"],
             s["est_value"] or "", s["manufacturer"], s["created_at"][:10]] for s in summaries]
    _sheet(ws, ["Project code", "Project", "Type", "Market", "Initiator", "Status", "Phase", "Current step",
                "Waiting on", "Days in step", "Est. yearly sales (AUD)", "CDMO / Manufacturer", "Created"],
           rows, {"Project": 34, "Current step": 38, "Waiting on": 34, "Phase": 22})
    return _out(wb)


def brief_workbook(d: dict) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Project Brief"
    facts = [("Project code", d["code"] or "Not generated yet"), ("Project", d["title"]),
             ("Type", d["ptype_label"]), ("Market", d["market"]), ("Initiator", d["initiator"]["name"]),
             ("Status", d["status"].replace("_", " ").title()), ("Current step", d["step_name"]),
             ("Est. yearly sales (AUD)", d["est_value"] or ""), ("Target date", d["target_date"]),
             ("CDMO / Manufacturer", d["manufacturer"]), ("Description", d["description"])]
    _sheet(ws, ["Field", "Detail"], facts, {"Field": 28, "Detail": 70})
    ws2 = wb.create_sheet("Steps")
    state = {"done": "Done", "current": "In progress", "upcoming": "To do", "skipped": "Not needed",
             "hold": "On hold", "stopped": "Stopped"}
    rows = [[i + 1, s["name"], " / ".join(o["label"] for o in s["owners"]), state[s["state"]],
             s["last"]["user"]["name"] if s["last"] and s["last"]["user"] else "",
             s["last"]["at"][:10] if s["last"] else "", s["last"]["note"] if s["last"] else ""]
            for i, s in enumerate(d["steps"])]
    _sheet(ws2, ["#", "Step", "Responsible", "Status", "Done by", "Date", "Note"], rows,
           {"Step": 46, "Responsible": 40, "Note": 50})
    return _out(wb)


def import_template() -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Opportunities"
    _sheet(ws, ["Project name", "Type (Development / In-Licence)", "Market", "Short description",
                "Est. yearly sales (AUD)"],
           [["Example: Vitamin C 1000mg Effervescent", "Development", "Australia",
             "Orange flavour, 20 tablets", 450000]],
           {"Project name": 38, "Type (Development / In-Licence)": 30, "Short description": 46})
    return _out(wb)


def parse_import(data: bytes) -> list:
    wb = load_workbook(BytesIO(data), data_only=True)
    ws = wb.active
    out = []
    for i, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        if not row or not row[0] or str(row[0]).lower().startswith("example"):
            continue
        t = str(row[1] or "").strip().lower().replace("-", "").replace(" ", "")
        ptype = {"development": "development", "inlicence": "in_licence", "inlicense": "in_licence",
                 "inlicencing": "in_licence"}.get(t)
        if not ptype:
            raise ValueError(f"Row {i}: Type must be Development or In-Licence.")
        val = row[4] if len(row) > 4 else None
        try:
            val = float(val) if val not in (None, "") else None
        except (TypeError, ValueError):
            raise ValueError(f"Row {i}: yearly sales must be a number.")
        out.append({"title": str(row[0]).strip(), "ptype": ptype,
                    "market": str(row[2] or "").strip(), "description": str(row[3] or "").strip(),
                    "est_value": val})
    return out
