"""Checks the system against the client's flow chart (AD001-F01-00), page by page."""
from app import workflow as wf
from conftest import WHO

# The chart, typed in from the Word file (page order). Development projects.
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


def run_to(api, pid, target, overrides=None, max_steps=200):
    """Drive a project as the right people until `target` is waiting (or it finishes)."""
    script = {k: list(v) for k, v in (overrides or {}).items()}
    targets = {target} if isinstance(target, str) else set(target)
    for _ in range(max_steps):
        d = api.detail("sneha", pid)
        acts = d["actions"]
        if d["status"] != "active" or (acts and all(a["key"] in targets for a in acts)):
            return d
        a = next(x for x in acts if x["key"] not in targets)
        owner = next(o for o in a["owners"] if not o["signed"])
        who = WHO[owner["role"]]
        item = script[a["key"]].pop(0) if script.get(a["key"]) else None
        if item and item[0] == "sendback":
            api.sendback(who, pid, a["key"], item[1], item[2])
            continue
        option, note = item if item else (None, "")
        if a["mode"] == "decision":
            option = option or ("complete" if a["key"] == "india_review" else "approve")
            if option in ("back", "reject", "hold"):
                note = note or "Needs more work."
        api.do(who, pid, a["key"], option=option, note=note)
    raise AssertionError(f"did not reach {target}")


def done_order(api, pid):
    ev = api.detail("sneha", pid)["events"]
    return [e["step_key"] for e in ev if e["kind"] == "step" and e["action"] in ("done", "approve")]


# ---------------------------------------------------------------------------
def test_flow_definition_matches_document():
    defined = DOC_ORDER_DEV[:]
    defined.insert(defined.index("updated_brief"), "clarification")   # side branch, visited only when asked for
    assert wf.flat_order("development") == defined
    inl = wf.flat_order("in_licence")
    assert "reg_review" in inl and "cdmo" not in inl
    assert inl.index("reg_review") == inl.index("agreement_decision") + 1
    for s in wf.STEPS:
        assert wf.PHASE_BY_KEY[s["phase"]]
        for o in s.get("options", {}).values():
            assert o.get("to") is None or o["to"] in wf.STEP_BY_KEY
    assert len(wf.PHASES) == 7


def test_full_development_flow_in_document_order(api):
    pid = api.create(ptype="development")
    d = run_to(api, pid, "nothing-ever")
    assert d["status"] == "completed" and d["progress"] == 100
    assert done_order(api, pid) == DOC_ORDER_DEV
    assert d["code"].startswith("NHO-DEV-") and d["manufacturer"] == "Sunrise Pharma"
    assert d["est_value"] == 5 and d["target_date"]                        # details flow into the project


def test_in_licence_uses_regulatory_review_not_cdmo(api):
    pid = api.create(ptype="in_licence")
    run_to(api, pid, "nothing-ever")
    seq = done_order(api, pid)
    assert "reg_review" in seq and "cdmo" not in seq
    assert seq.index("agreement_decision") + 1 == seq.index("reg_review")
    assert api.detail("sneha", pid)["code"].startswith("NHO-INL-")


def test_only_responsible_people_can_act(api):
    pid = api.create()
    run = api.detail("ananya", pid)["actions"][0]["run_id"]
    for who, expect in (("suresh", 403), ("sneha", 403), ("rohit", 404)):
        r = api.post(who, f"/api/projects/{pid}/runs/{run}/act", json={"option": None})
        assert r.status_code == expect, who
    api.do("ananya", pid)
    assert api.active(pid) == ["validation"]


def test_only_initiators_can_create(api):
    assert api.post("suresh", "/api/projects", json={"title": "x", "ptype": "development"}).status_code == 403


def test_director_decision_reject_closes_and_needs_reason(api):
    pid = api.create()
    run_to(api, pid, "otc_decision")
    api.do("rajiv", pid, option="reject", note="", expect=400)
    api.do("rajiv", pid, option="reject", note="Not a fit")
    d = api.detail("ananya", pid)
    assert d["status"] == "rejected" and d["code"] is None and d["health"] == "stopped"


def test_project_code_only_after_director_approval(api):
    pid = api.create()
    run_to(api, pid, "otc_decision")
    assert api.detail("rajiv", pid)["code"] is None
    api.do("rajiv", pid, option="approve")
    assert api.active(pid) == ["code"]
    api.do("ananya", pid)
    assert api.detail("ananya", pid)["code"]


def test_india_review_send_back_loops_to_internal_review(api):
    pid = api.create()
    run_to(api, pid, "india_review")
    api.do("suresh", pid, option="reject", note="", expect=400)
    api.do("suresh", pid, option="reject", note="Add stability data")
    assert api.active(pid) == ["internal_review"]
    run_to(api, pid, "india_review")


def test_clarification_loop_returns_to_updated_brief(api):
    pid = api.create()
    run_to(api, pid, "india_review")
    api.do("suresh", pid, option="incomplete")
    assert api.active(pid) == ["clarification"]
    api.do("suresh", pid, data={"question": ""}, expect=400, fill=False)        # the question is required
    api.do("suresh", pid, data={"question": "Confirm shelf life"})
    assert api.active(pid) == ["internal_review"]                              # arrow goes back to Internal Review
    d = api.detail("ananya", pid)
    assert d["clarification_pending"] and d["actions"][0]["from"]["name"] == "Suresh Iyer"
    run_to(api, pid, "updated_brief")                                           # resubmission skips a second review
    api.do("suresh", pid)
    assert api.active(pid) == ["feas_review_done"]


def test_complete_information_skips_clarification(api):
    pid = api.create()
    run_to(api, pid, "india_review")
    api.do("suresh", pid, option="complete")
    assert api.active(pid) == ["updated_brief"]


def test_feasibility_hold_then_restart(api):
    pid = api.create()
    run_to(api, pid, "feas_decision")
    api.do("suresh", pid, option="hold", note="Waiting for supplier price")
    d = api.detail("ananya", pid)
    assert d["status"] == "on_hold" and d["health"] == "hold" and d["actions"][0]["key"] == "feas_decision"
    api.post("suresh", f"/api/projects/{pid}/runs/{d['actions'][0]['run_id']}/act", json={"option": "approve"})
    assert api.active(pid) == ["feas_decision"]                                 # frozen while on hold
    assert api.post("ananya", f"/api/projects/{pid}/resume", json={}).status_code == 403
    assert api.post("suresh", f"/api/projects/{pid}/resume", json={}).status_code == 200
    api.do("suresh", pid, option="approve")
    assert api.active(pid) == ["cost"]


def test_final_commercial_approval_needs_both_directors(api):
    pid = api.create()
    run_to(api, pid, "commercial_approval")
    r = api.do("suresh", pid, option="approve")
    assert not r["moved"] and api.active(pid) == ["commercial_approval"]
    a = api.card("suresh", pid, "commercial_approval")
    assert not a["can_act"] and [o["signed"] for o in a["owners"]] == [True, False]
    r = api.do("rajiv", pid, option="approve")
    assert r["moved"] and api.active(pid) == ["agreement_prep"]


def test_final_commercial_back_loops_to_financial_review_and_needs_both_again(api):
    pid = api.create()
    run_to(api, pid, "commercial_approval")
    api.do("rajiv", pid, option="back", note="Margin too thin")
    assert api.active(pid) == ["fin_review"]
    assert not api.do("suresh", pid)["moved"]                                   # both must sign again
    assert api.do("ananya", pid)["moved"]


def test_agreement_review_needs_legal_quality_and_pv_each_with_own_tick(api):
    pid = api.create()
    run_to(api, pid, "lqp_review")
    a = api.card("pooja", pid)
    assert [c["key"] for c in a["checks"]] == ["legal"]                         # each team ticks only its own point
    api.do("pooja", pid, checks=[], expect=400, fill=False)
    assert not api.do("pooja", pid)["moved"]
    assert not api.do("amit", pid)["moved"]
    assert api.do("neha", pid)["moved"]
    assert api.active(pid) == ["agreement_decision"]


def test_regulatory_and_artwork_loops_follow_the_chart(api):
    pid = api.create()
    run_to(api, pid, "reg_decision")
    api.do("sanjay", pid, option="back", note="Dossier incomplete")
    assert api.active(pid) == ["dossier_assign"]
    run_to(api, pid, "artwork_approval")
    api.do("rajiv", pid, option="back", note="Fix the logo")
    assert api.active(pid) == ["concept"]
    run_to(api, pid, "artwork_approval")
    api.do("rajiv", pid, option="approve")
    assert api.active(pid) == ["mfr_tech"]


def test_sample_review_quality_coordinator_can_act(api):
    pid = api.create()
    run_to(api, pid, "sample_review")
    api.do("amit", pid)
    assert api.active(pid) == ["dispatch"]


def test_director_can_cancel_and_admin_can_correct(api):
    pid = api.create()
    assert api.post("ananya", f"/api/projects/{pid}/cancel", json={"note": "x"}).status_code == 403
    run_to(api, pid, "validation")
    r = api.post("sneha", f"/api/projects/{pid}/move", json={"step_key": "screening", "note": "fix"})
    assert r.status_code == 200 and api.active(pid) == ["screening"]
    assert api.post("rajiv", f"/api/projects/{pid}/cancel", json={"note": "Priorities changed"}).status_code == 200
    assert api.detail("ananya", pid)["status"] == "cancelled"


def test_excel_downloads_are_gone(api):
    api.create()
    for url in ("/api/projects/export.xlsx", "/api/projects/import-template.xlsx"):
        assert api.get("ananya", url).status_code in (404, 405, 422)
    assert api.post("ananya", "/api/projects/import", files={"file": ("x.xlsx", b"x")}).status_code in (404, 405, 422)
