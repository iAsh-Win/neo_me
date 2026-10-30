"""Checks the system against the client's flow chart (AD001-F01-00), page by page."""
from app import workflow as wf

# Who acts for each role in the tests
WHO = {"initiator": "ananya", "otc_director": "rajiv", "india_director": "suresh", "cft": "meera",
       "legal": "pooja", "quality": "amit", "pv": "neha", "reg_head": "sanjay", "reg_team": "divya",
       "artwork": "ritika", "commercial": "arjun", "cmo": "rakesh"}

# The flow chart, typed in from the Word file (page order). Development projects.
DOC_ORDER_DEV = [
    "opportunity", "screening", "validation", "approval_decision", "otc_decision", "code", "draft_brief",
    "internal_review", "final_internal", "submission", "india_review", "updated_brief",
    "feas_review_done", "brief_approved", "cft_review", "fmea", "feas_prep", "feas_submit", "feas_decision",
    "cost", "fin_review", "risk_adj", "commercial_approval",
    "agreement_prep", "functional_review", "lqp_review", "agreement_decision",
    "cdmo", "handover", "dossier_assign", "reg_decision",
    "concept", "artwork", "artwork_approval",
    "mfr_tech", "ra_reviewer", "reg_submission", "comm_ready", "print_proof", "tech_review", "mfr_approval",
    "final_print", "shade_card", "manufacturing", "presample", "sample_review", "dispatch", "completion",
]


def run_to(api, pid, target, ptype="development", overrides=None):
    """Drive a project forward as the right people until it reaches `target`."""
    overrides = {k: list(v) for k, v in (overrides or {}).items()}
    for _ in range(300):
        d = api.get("sneha", f"/api/projects/{pid}").json()
        if d["current_step"] == target or d["status"] != "active":
            return d
        step = wf.STEP_BY_KEY[d["current_step"]]
        if step.get("needs_file") and not d["action"]["has_file"]:
            api.upload(WHO[step["roles"][0]], pid, step["key"])
        queue = overrides.get(step["key"])
        option, note = (queue.pop(0) if queue else (None, ""))
        if step["mode"] == "decision" and not option:
            option = "complete" if step["key"] == "india_review" else "approve"
        if step.get("needs_note") and not note:
            note = "please clarify"
        for role in [r["role"] for r in d["waiting"]]:
            api.act(WHO[role], pid, option=option, note=note or "ok",
                    text="Sunrise Pharma" if step.get("needs_text") else None)
            break
    raise AssertionError("did not reach " + target)


def visited(api, pid):
    ev = api.get("sneha", f"/api/projects/{pid}").json()["events"]
    return [e["step_key"] for e in ev if e["kind"] == "step" and e["action"] in ("done", "approve")]


# ---------------------------------------------------------------------------
def test_flow_definition_matches_document():
    # "Clarification Request Raised" is a side branch: defined in the flow, visited only when asked for
    defined = DOC_ORDER_DEV[:]
    defined.insert(defined.index("updated_brief"), "clarification")
    assert [s["key"] for s in wf.steps_for("development")] == defined
    inl = [s["key"] for s in wf.steps_for("in_licence")]
    assert "reg_review" in inl and "cdmo" not in inl
    # every approve/back target exists
    for s in wf.STEPS:
        for o in s.get("options", {}).values():
            assert o.get("to") is None or o["to"] in wf.STEP_BY_KEY


def test_full_development_flow_in_document_order(api):
    pid = api.create(ptype="development")
    d = run_to(api, pid, "nothing-ever")
    assert d["status"] == "completed" and d["progress"] == 100
    assert visited(api, pid) == DOC_ORDER_DEV
    assert d["code"].startswith("NHO-DEV-")
    assert d["manufacturer"] == "Sunrise Pharma"


def test_in_licence_uses_regulatory_review_not_cdmo(api):
    pid = api.create(ptype="in_licence")
    run_to(api, pid, "nothing-ever", ptype="in_licence")
    seq = visited(api, pid)
    assert "reg_review" in seq and "cdmo" not in seq
    assert seq.index("agreement_decision") + 1 == seq.index("reg_review")
    assert api.get("sneha", f"/api/projects/{pid}").json()["code"].startswith("NHO-INL-")


def test_only_responsible_people_can_act(api):
    pid = api.create()                                   # waiting: initiator (Priya) on Screening
    api.act("suresh", pid, expect=403)                   # a Director cannot do screening
    api.act("rohit", pid, expect=404)                   # another initiator cannot even see Ananya's project
    api.act("sneha", pid, expect=403)                    # admin manages, but does not approve
    api.act("ananya", pid)
    assert api.step("ananya", pid) == "validation"


def test_only_initiators_can_create(api):
    r = api.post("suresh", "/api/projects", json={"title": "x", "ptype": "development"})
    assert r.status_code == 403


def test_director_decision_reject_closes_and_needs_reason(api):
    pid = api.create()
    run_to(api, pid, "otc_decision")
    api.act("rajiv", pid, option="reject", note="", expect=400)
    api.act("rajiv", pid, option="reject", note="Not a fit")
    d = api.get("ananya", f"/api/projects/{pid}").json()
    assert d["status"] == "rejected" and d["code"] is None
    api.act("ananya", pid, expect=400)                    # nothing can be done on a closed project


def test_project_code_only_after_director_approval(api):
    pid = api.create()
    d = run_to(api, pid, "otc_decision")
    assert d["code"] is None
    api.act("rajiv", pid, option="approve")
    assert api.step("rajiv", pid) == "code"
    api.act("ananya", pid)
    assert api.get("ananya", f"/api/projects/{pid}").json()["code"]


def test_india_review_reject_loops_to_internal_review(api):
    pid = api.create()
    run_to(api, pid, "india_review")
    api.act("suresh", pid, option="reject", note="", expect=400)
    api.act("suresh", pid, option="reject", note="Add stability data")
    assert api.step("ananya", pid) == "internal_review"
    run_to(api, pid, "india_review")                     # goes through final approval + submission again
    assert api.step("ananya", pid) == "india_review"


def test_clarification_loop_returns_to_updated_brief(api):
    pid = api.create()
    run_to(api, pid, "india_review")
    api.act("suresh", pid, option="incomplete")
    assert api.step("ananya", pid) == "clarification"
    api.act("suresh", pid, note="", expect=400)          # must say what is missing
    api.act("suresh", pid, note="Confirm shelf life")
    assert api.step("ananya", pid) == "internal_review"   # arrow goes back to Internal Review
    run_to(api, pid, "updated_brief")                    # re-submission lands on Updated Brief Received
    assert api.step("ananya", pid) == "updated_brief"
    api.act("suresh", pid)
    assert api.step("ananya", pid) == "feas_review_done"


def test_complete_information_skips_clarification(api):
    pid = api.create()
    run_to(api, pid, "india_review")
    api.act("suresh", pid, option="complete")
    assert api.step("ananya", pid) == "updated_brief"


def test_feasibility_hold_then_resume(api):
    pid = api.create()
    run_to(api, pid, "feas_decision")
    api.act("suresh", pid, option="hold", note="Waiting for supplier price")
    d = api.get("ananya", f"/api/projects/{pid}").json()
    assert d["status"] == "on_hold" and d["current_step"] == "feas_decision"
    api.act("suresh", pid, option="approve", expect=400)              # frozen while on hold
    assert api.post("ananya", f"/api/projects/{pid}/resume", json={}).status_code == 403
    assert api.post("suresh", f"/api/projects/{pid}/resume", json={}).status_code == 200
    api.act("suresh", pid, option="approve")
    assert api.step("ananya", pid) == "cost"


def test_final_commercial_approval_needs_both_directors(api):
    pid = api.create()
    run_to(api, pid, "commercial_approval")
    r = api.act("suresh", pid, option="approve")
    assert not r["moved"]
    assert api.step("ananya", pid) == "commercial_approval"
    api.act("suresh", pid, option="approve", expect=403)              # cannot sign twice
    r = api.act("rajiv", pid, option="approve")
    assert r["moved"] and api.step("ananya", pid) == "agreement_prep"


def test_final_commercial_hold_reject_loops_to_financial_review(api):
    pid = api.create()
    run_to(api, pid, "commercial_approval")
    api.act("rajiv", pid, option="back", note="Margin too thin")
    assert api.step("ananya", pid) == "fin_review"
    # Financial Review needs the India Director and the Initiator
    assert not api.act("suresh", pid)["moved"]
    assert api.act("ananya", pid)["moved"]


def test_agreement_review_needs_legal_quality_and_pv(api):
    pid = api.create()
    run_to(api, pid, "lqp_review")
    assert not api.act("pooja", pid)["moved"]
    assert not api.act("amit", pid)["moved"]
    assert api.act("neha", pid)["moved"]
    assert api.step("ananya", pid) == "agreement_decision"


def test_regulatory_and_artwork_loops(api):
    pid = api.create()
    run_to(api, pid, "reg_decision")
    api.act("sanjay", pid, option="back", note="Dossier incomplete")
    assert api.step("ananya", pid) == "dossier_assign"
    run_to(api, pid, "artwork_approval")
    api.act("rajiv", pid, option="back", note="Fix the logo")
    assert api.step("ananya", pid) == "concept"
    run_to(api, pid, "artwork_approval")
    api.act("rajiv", pid, option="approve")
    assert api.step("ananya", pid) == "mfr_tech"


def test_required_files_and_text_are_enforced(api):
    pid = api.create()
    run_to(api, pid, "draft_brief")
    api.act("ananya", pid, expect=400)                                # Master Excel missing
    api.upload("ananya", pid, "draft_brief")
    api.act("ananya", pid)
    run_to(api, pid, "cdmo")
    api.act("suresh", pid, text="", expect=400)


def test_sample_review_quality_coordinator_can_act(api):
    pid = api.create()
    run_to(api, pid, "sample_review")
    api.act("amit", pid)
    assert api.step("ananya", pid) == "dispatch"


def test_director_can_cancel_and_admin_can_correct(api):
    pid = api.create()
    assert api.post("ananya", f"/api/projects/{pid}/cancel", json={"note": "x"}).status_code == 403
    run_to(api, pid, "validation")
    assert api.post("sneha", f"/api/projects/{pid}/move", json={"step_key": "screening", "note": "fix"}).status_code == 200
    assert api.step("ananya", pid) == "screening"
    assert api.post("rajiv", f"/api/projects/{pid}/cancel", json={"note": "Priorities changed"}).status_code == 200
    assert api.get("ananya", f"/api/projects/{pid}").json()["status"] == "cancelled"


def test_notifications_and_dashboard(api):
    pid = api.create()
    run_to(api, pid, "otc_decision")
    notes = api.get("rajiv", "/api/notifications").json()
    assert any("your turn" in n["text"] for n in notes)
    dash = api.get("rajiv", "/api/dashboard").json()
    assert dash["counts"]["waiting_me"] == 1 and dash["mine"][0]["id"] == pid


def test_excel_export_import_and_auth(api):
    api.create(title="Alpha")
    r = api.get("ananya", "/api/projects/export.xlsx")
    assert r.status_code == 200 and r.content[:2] == b"PK"
    tpl = api.get("ananya", "/api/projects/import-template.xlsx").content
    from io import BytesIO
    from openpyxl import load_workbook
    wb = load_workbook(BytesIO(tpl))
    wb.active.append(["Beta Product", "In-Licence", "Australia", "desc", 1000])
    bio = BytesIO()
    wb.save(bio)
    r = api.post("ananya", "/api/projects/import", files={"file": ("t.xlsx", bio.getvalue())})
    assert r.status_code == 200 and r.json()["created"] == 1
    titles = [p["title"] for p in api.get("ananya", "/api/projects").json()]
    assert "Beta Product" in titles
    from fastapi.testclient import TestClient
    from app.main import app
    assert TestClient(app).get("/api/projects").status_code == 401
