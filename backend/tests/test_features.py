"""Send-back to a chosen person, documents and links, structured details, parallel tracks, time requests,
tasks and the history – the things a pharma project needs beyond plain notes."""
from datetime import datetime, timedelta

from app import engine as eng
from app.db import SessionLocal
from app.models import Project

from conftest import tomorrow
from test_flow import run_to


def notes(api, who):
    return [n["text"] for n in api.get(who, "/api/notifications").json()]


# ---- send back --------------------------------------------------------------------
def test_send_back_to_a_chosen_earlier_step_and_it_comes_straight_back(api):
    pid = api.create()
    run_to(api, pid, "feas_decision")
    a = api.card("suresh", pid)
    keys = [t["key"] for t in a["targets"]]
    assert keys[0] == "feas_submit" and "feas_prep" in keys and "fmea" in keys          # nearest first
    target = next(t for t in a["targets"] if t["key"] == "feas_prep")
    assert [p["name"] for p in target["people"]] == ["Karthik Subramanian", "Meera Joshi"]   # who it will go to
    api.sendback("suresh", pid, "feas_decision", "feas_prep", note="", expect=400)        # a reason is required
    run = a["run_id"]
    assert api.post("pooja", f"/api/projects/{pid}/runs/{run}/sendback",
                    json={"target": "feas_prep", "note": "x"}).status_code == 404            # outsiders cannot
    api.sendback("suresh", pid, "feas_decision", "cost", expect=400)                      # only steps already done
    api.sendback("suresh", pid, "feas_decision", "feas_prep", note="Add the stability data")
    c = api.card("meera", pid)
    assert c["key"] == "feas_prep" and c["rework"] and c["from"]["name"] == "Suresh Iyer"
    assert c["from"]["note"] == "Add the stability data" and c["return_to_name"] == "Feasibility Decision"
    text = " ".join(notes(api, "meera"))
    assert "sent back to you by Suresh Iyer (India Director)" in text                    # the receiver knows who sent it
    assert "sent back" in " ".join(notes(api, "ananya"))
    api.do("meera", pid)                                                                  # fix → straight back to the sender
    assert api.active(pid) == ["feas_decision"]
    back = api.card("suresh", pid)
    assert back["from"]["name"] == "Meera Joshi"
    ev = [e for e in api.detail("sneha", pid)["events"] if e["action"] == "sendback"][0]
    assert ev["user"]["name"] == "Suresh Iyer" and "Meera Joshi" in ev["to"] and ev["target_name"]


def test_send_back_carries_documents(api):
    pid = api.create()
    run_to(api, pid, "feas_decision")
    doc = api.file("suresh", pid, "feas_decision", "", name="comments.pdf")[0]
    api.sendback("suresh", pid, "feas_decision", "feas_prep", doc_ids=[doc])
    ev = [e for e in api.detail("sneha", pid)["events"] if e["action"] == "sendback"][0]
    assert [d["title"] for d in ev["docs"]] == ["comments.pdf"]


def test_decision_can_also_send_further_back_than_the_chart_loop(api):
    pid = api.create()
    run_to(api, pid, "commercial_approval")
    a = api.card("rajiv", pid)
    assert "cost" in [t["key"] for t in a["targets"]]
    api.sendback("rajiv", pid, "commercial_approval", "cost", note="The unit cost looks wrong")
    api.do("suresh", pid)                                                                 # cost fixed → back to the approval
    assert api.active(pid) == ["commercial_approval"]


# ---- parallel tracks -----------------------------------------------------------------
def test_fast_track_needs_a_director(api):
    pid = api.create()
    assert api.post("ananya", f"/api/projects/{pid}/fasttrack", json={"on": True}).status_code == 403
    assert api.post("rajiv", f"/api/projects/{pid}/fasttrack", json={"on": True}).status_code == 200
    assert api.detail("ananya", pid)["fast_track"] is True


def test_without_fast_track_the_tracks_follow_the_chart_order(api):
    pid = api.create()
    run_to(api, pid, "handover")
    assert api.active(pid) == ["handover"]
    run_to(api, pid, "concept")                           # artwork track only starts after the regulatory decision
    assert api.active(pid) == ["concept"]
    assert api.detail("sneha", pid)["groups"][0]["mode"] == "seq"


def test_fast_track_runs_regulatory_and_artwork_side_by_side_and_joins(api):
    pid = api.create()
    api.post("rajiv", f"/api/projects/{pid}/fasttrack", json={"on": True})
    run_to(api, pid, {"handover", "concept"})
    assert sorted(api.active(pid)) == ["concept", "handover"]                              # both at once
    d = api.detail("sneha", pid)
    assert d["groups"][0]["mode"] == "fast" and d["health"] in ("ok", "risk")
    run_to(api, pid, {"reg_decision", "artwork_approval"})
    api.do("rajiv", pid, "artwork_approval", option="approve")
    assert api.active(pid) == ["reg_decision"]                                             # waits for the other track
    r = api.do("sanjay", pid, "reg_decision", option="approve")
    assert r["moved"] and api.active(pid) == ["mfr_tech"]                                  # joined
    api.do("rakesh", pid)
    assert sorted(api.active(pid)) == ["comm_ready", "print_proof", "ra_reviewer"]         # three tracks at once
    run_to(api, pid, {"manufacturing"})
    assert api.active(pid) == ["manufacturing"]


def test_send_back_inside_a_fast_track_stays_in_its_own_track(api):
    pid = api.create()
    api.post("rajiv", f"/api/projects/{pid}/fasttrack", json={"on": True})
    run_to(api, pid, {"reg_decision", "artwork_approval"})
    keys = [t["key"] for t in api.card("rajiv", pid, "artwork_approval")["targets"]]
    assert keys == ["artwork", "concept"]
    keys = [t["key"] for t in api.card("sanjay", pid, "reg_decision")["targets"]]
    assert keys == ["dossier_assign", "handover"]


def test_group_mode_is_decided_when_the_group_starts(api):
    pid = api.create()
    run_to(api, pid, {"handover"})
    api.post("rajiv", f"/api/projects/{pid}/fasttrack", json={"on": True})                 # switched on too late for g1
    run_to(api, pid, {"concept"})
    assert api.active(pid) == ["concept"]
    assert api.detail("sneha", pid)["groups"][0]["mode"] == "seq"


# ---- time requests ----------------------------------------------------------------------
def test_time_request_goes_to_whoever_gave_the_date_and_the_answer_comes_back(api):
    pid = api.create()
    run_to(api, pid, "fmea")                                                  # handed over by Suresh (cft_review)
    a = api.card("meera", pid)
    assert a["from"]["name"] == "Suresh Iyer" and a["can_set_due"] is False
    new = (datetime.fromisoformat(a["due_at"].rstrip("Z")) + timedelta(days=4)).date().isoformat()
    run = a["run_id"]
    url = f"/api/projects/{pid}/runs/{run}/extend"
    assert api.post("meera", url, json={"new_due": new, "reason": ""}).status_code == 400          # reason needed
    assert api.post("meera", url, json={"new_due": "2000-01-01", "reason": "x"}).status_code == 400  # must be later
    assert api.post("rajiv", url, json={"new_due": new, "reason": "x"}).status_code == 403          # only who must act
    r = api.post("meera", url, json={"new_due": new, "reason": "Plant data arrives next week"})
    assert r.status_code == 200 and "Suresh Iyer" in r.json()["message"]                           # says who it goes to
    assert api.post("meera", url, json={"new_due": new, "reason": "again"}).status_code == 400      # one at a time
    assert any("asks for more time" in t and "Meera Joshi" in t for t in notes(api, "suresh"))
    pending = api.card("suresh", pid, "fmea")["pending_request"]
    assert pending["can_decide"] and pending["requested_by"]["name"] == "Meera Joshi" and pending["approver"]["name"] == "Suresh Iyer"
    assert api.card("meera", pid)["pending_request"]["can_decide"] is False
    qid = pending["id"]
    assert api.post("meera", f"/api/projects/{pid}/requests/{qid}/decide", json={"approve": True}).status_code == 403
    assert api.post("suresh", f"/api/projects/{pid}/requests/{qid}/decide", json={"approve": False, "note": ""}).status_code == 400
    assert api.post("suresh", f"/api/projects/{pid}/requests/{qid}/decide", json={"approve": False, "note": "Too late"}).status_code == 200
    assert any("declined" in t and "Too late" in t for t in notes(api, "meera"))
    r2 = api.post("meera", url, json={"new_due": new, "reason": "Please, it is really needed"})
    assert r2.status_code == 200
    qid2 = api.card("suresh", pid, "fmea")["pending_request"]["id"]
    api.post("suresh", f"/api/projects/{pid}/requests/{qid2}/decide", json={"approve": True})
    assert api.card("meera", pid)["due_at"].startswith(new)
    assert any("approved your request" in t for t in notes(api, "meera"))
    ev = [e["action"] for e in api.detail("sneha", pid)["events"] if e["kind"] == "request"]
    assert ev == ["ext_ask", "ext_no", "ext_ask", "ext_yes"]


def test_first_step_time_request_goes_to_the_manager(api):
    pid = api.create()                                    # Ananya gave herself the first date → her manager decides
    a = api.card("ananya", pid)
    r = api.post("ananya", f"/api/projects/{pid}/runs/{a['run_id']}/extend",
                 json={"new_due": tomorrow(9), "reason": "On leave"})
    assert r.status_code == 200 and "Rajiv Khanna" in r.json()["message"]


def test_whoever_gave_the_date_or_a_director_can_change_it(api):
    pid = api.create()
    run_to(api, pid, "fmea")
    run = api.card("meera", pid)["run_id"]
    assert api.post("meera", f"/api/projects/{pid}/runs/{run}/due", json={"due": tomorrow(20)}).status_code == 403
    assert api.post("suresh", f"/api/projects/{pid}/runs/{run}/due", json={"due": tomorrow(20)}).status_code == 200
    assert api.card("meera", pid)["due_at"].startswith(tomorrow(20))
    assert any("changed the date" in t for t in notes(api, "meera"))


# ---- tasks ---------------------------------------------------------------------------------
def test_tasks_are_given_seen_extended_and_can_block_a_step(api):
    pid = api.create()
    pooja = next(p for p in api.get("ananya", "/api/people").json() if p["name"] == "Pooja Bansal")["id"]
    assert api.get("pooja", f"/api/projects/{pid}").status_code == 404
    r = api.post("ananya", f"/api/projects/{pid}/tasks", json={"title": "Check the claim wording", "assignee_id": pooja,
                                                              "due": tomorrow(3), "step_key": "screening", "blocking": True})
    assert r.status_code == 200
    task = r.json()["tasks"][0]
    assert task["assignee"]["name"] == "Pooja Bansal" and task["creator"]["name"] == "Ananya Reddy"
    assert api.get("pooja", f"/api/projects/{pid}").status_code == 200                 # the assignee now sees the project
    assert any("New task from Ananya Reddy (Initiator)" in t for t in notes(api, "pooja"))
    api.do("ananya", pid, expect=400)                                                      # blocked until the task is done
    tid = task["id"]
    # more time → goes to whoever gave the task
    url = f"/api/projects/{pid}/tasks/{tid}/extend"
    r = api.post("pooja", url, json={"new_due": tomorrow(8), "reason": "Waiting for counsel"})
    assert r.status_code == 200 and "Ananya Reddy" in r.json()["message"]
    q = api.detail("ananya", pid)["requests"][-1]
    assert q["can_decide"]
    api.post("ananya", f"/api/projects/{pid}/requests/{q['id']}/decide", json={"approve": True})
    assert api.detail("pooja", pid)["tasks"][0]["due_at"].startswith(tomorrow(8))
    assert api.post("ananya", f"/api/projects/{pid}/tasks/{tid}/done", json={"note": ""}).status_code == 403
    assert api.post("pooja", f"/api/projects/{pid}/tasks/{tid}/done", json={"note": "Checked, fine"}).status_code == 200
    assert any("finished the task" in t for t in notes(api, "ananya"))
    api.do("ananya", pid)                                                                  # unblocked
    assert api.active(pid) == ["validation"]


def test_only_people_working_on_the_project_can_give_tasks_and_creator_can_cancel(api):
    pid = api.create()
    sakshi = next(p for p in api.get("ananya", "/api/people").json() if p["name"] == "Sakshi Agarwal")["id"]
    assert api.post("sakshi", f"/api/projects/{pid}/tasks", json={"title": "x", "assignee_id": sakshi, "due": tomorrow()}).status_code == 404
    r = api.post("ananya", f"/api/projects/{pid}/tasks", json={"title": "Find samples", "assignee_id": sakshi, "due": tomorrow(2)})
    tid = r.json()["tasks"][0]["id"]
    assert api.post("sakshi", f"/api/projects/{pid}/tasks/{tid}/cancel", json={}).status_code == 403
    assert api.post("ananya", f"/api/projects/{pid}/tasks/{tid}/cancel", json={}).status_code == 200
    assert api.detail("ananya", pid)["tasks"][0]["status"] == "cancelled"


def test_overdue_task_reminds_assignee_and_tells_the_giver(api):
    pid = api.create()
    sakshi = next(p for p in api.get("ananya", "/api/people").json() if p["name"] == "Sakshi Agarwal")["id"]
    api.post("ananya", f"/api/projects/{pid}/tasks", json={"title": "Find samples", "assignee_id": sakshi, "due": tomorrow(1)})
    with SessionLocal() as db:
        eng.run_reminders(db, datetime.utcnow() + timedelta(days=5))
    assert any("Overdue task" in t for t in notes(api, "sakshi"))
    assert any("late on the task" in t for t in notes(api, "ananya"))


# ---- documents and links ---------------------------------------------------------------
def test_files_and_links_both_count_and_several_files_can_be_added(api):
    pid = api.create()
    run_to(api, pid, "validation")
    r = api.post("ananya", f"/api/projects/{pid}/runs/{api.card('ananya', pid)['run_id']}/act",
                 json={"data": {"est_value": "5"}, "checks": []})
    assert r.status_code == 400 and "Business case" in r.json()["detail"]
    bad = api.post("ananya", f"/api/projects/{pid}/links", json={"title": "x", "url": "ftp://nope", "step_key": "validation",
                                                                "doc_type": "business_case"})
    assert bad.status_code == 400
    api.link("ananya", pid, "validation", "business_case", url="https://share.example.test/case")    # a link is enough
    api.do("ananya", pid, "validation", fill=False, data={"est_value": "5"})
    ids = api.file("ananya", pid, "validation", "business_case", n=3)                              # several files at once
    assert len(ids) == 3
    docs = api.detail("ananya", pid)["documents"]
    assert {d["kind"] for d in docs} == {"link", "file"} and all(d["doc_label"] == "Business case" for d in docs)
    link = next(d for d in docs if d["kind"] == "link")
    assert api.get("ananya", f"/api/documents/{link['id']}").status_code == 404                      # links open elsewhere
    assert api.get("ananya", f"/api/documents/{ids[0]}").status_code == 200


def test_each_team_adds_its_own_agreement_and_signs_for_it(api):
    """Agreement Preparation is joint: Legal, Quality and PV each add their own document and sign."""
    pid = api.create()
    run_to(api, pid, "agreement_prep")
    a = api.card("pooja", pid)
    assert {d["key"]: d["editable"] for d in a["docs"]} == {"supplier_agreement": True, "quality_agreement": False,
                                                            "pv_agreement": False}
    run = a["run_id"]
    act = lambda who: api.post(who, f"/api/projects/{pid}/runs/{run}/act", json={"data": {}, "checks": []})
    assert act("pooja").status_code == 400                                       # her own document is missing
    r = api.post("pooja", f"/api/projects/{pid}/documents", data={"step_key": "agreement_prep", "doc_type": "quality_agreement"},
                 files=[("files", ("q.pdf", b"%PDF", "application/pdf"))])
    assert r.status_code == 403                                                  # another team's slot
    api.file("pooja", pid, "agreement_prep", "supplier_agreement")
    assert act("pooja").status_code == 200 and api.active(pid) == ["agreement_prep"]   # signed, waiting for the others
    api.file("amit", pid, "agreement_prep", "quality_agreement")
    assert act("amit").status_code == 200
    assert not api.card("neha", pid)["docs"][2]["items"]
    api.file("neha", pid, "agreement_prep", "pv_agreement")
    assert act("neha").status_code == 200 and api.active(pid) == ["functional_review"]
    h = api.card("suresh", pid, "functional_review")["handover"]
    assert len(h["docs"]) == 3                                                   # all three agreements reach the next step


def test_documents_can_be_removed_only_by_their_owner(api):
    pid = api.create()
    doc = api.file("ananya", pid, "screening", "")[0]
    assert api.detail("rajiv", pid)["documents"]
    from fastapi.testclient import TestClient
    from app.main import app
    c = TestClient(app)
    assert c.delete(f"/api/documents/{doc}", headers=api.as_("rajiv")).status_code == 403
    assert c.delete(f"/api/documents/{doc}", headers=api.as_("ananya")).status_code == 200
    ev = [e["action"] for e in api.detail("ananya", pid)["events"] if e["kind"] == "doc"]
    assert ev == ["doc_added", "doc_removed"]


# ---- structured details and checks ----------------------------------------------------------
def test_details_and_ticks_are_checked(api):
    pid = api.create()
    run_to(api, pid, "validation")
    api.file("ananya", pid, "validation", "business_case")
    run = api.card("ananya", pid)["run_id"]
    url = f"/api/projects/{pid}/runs/{run}/act"
    assert "Estimated yearly sales" in api.post("ananya", url, json={"data": {}}).json()["detail"]
    assert "must be a number" in api.post("ananya", url, json={"data": {"est_value": "abc"}}).json()["detail"]
    run_to(api, pid, "screening")                                                    # (no-op: already past)


def test_screening_checks_and_select_and_date_fields(api):
    pid = api.create()
    run = api.card("ananya", pid)["run_id"]
    url = f"/api/projects/{pid}/runs/{run}/act"
    r = api.post("ananya", url, json={"checks": ["fit"]})
    assert r.status_code == 400 and "Market and competitors" in r.json()["detail"]
    assert api.post("ananya", url, json={"checks": ["fit", "market", "ip"]}).status_code == 200
    run_to(api, pid, "fmea")
    api.file("meera", pid, "fmea", "fmea")
    a = api.card("meera", pid)
    url = f"/api/projects/{pid}/runs/{a['run_id']}/act"
    assert "Highest risk" in api.post("meera", url, json={"data": {"risk_level": "Extreme"}}).json()["detail"]
    run_to(api, pid, "draft_brief") if False else None


# ---- what the buttons promise, and the history --------------------------------------------
def test_the_button_says_who_gets_it_next_and_history_remembers(api):
    pid = api.create()
    run_to(api, pid, "cost")
    a = api.card("suresh", pid)
    nxt = a["next"]["done"]
    assert nxt["steps"][0]["key"] == "fin_review"
    assert {p["name"] for p in nxt["steps"][0]["people"]} == {"Suresh Iyer", "Ananya Reddy"}
    api.do("suresh", pid, note="Quotation attached")
    ev = [e for e in api.detail("sneha", pid)["events"] if e["step_key"] == "cost" and e["action"] == "done"][0]
    assert ev["user"]["name"] == "Suresh Iyer" and "Ananya Reddy" in ev["to"]
    assert [d["label"] for d in ev["data"]][:2] == ["Cost per unit", "Minimum order quantity"] and ev["note"] == "Quotation attached"
    # the receiver sees who handed it over, and the message
    got = api.card("ananya", pid, "fin_review")
    assert got["from"]["name"] == "Suresh Iyer" and got["from"]["note"] == "Quotation attached"


def test_every_kind_of_event_is_in_the_history(api):
    pid = api.create()
    api.post("ananya", f"/api/projects/{pid}/comments", json={"note": "Kick-off note"})
    api.file("ananya", pid, "screening", "")
    run_to(api, pid, "feas_decision")
    api.sendback("suresh", pid, "feas_decision", "feas_prep", note="More data please")
    kinds = {(e["kind"], e["action"]) for e in api.detail("sneha", pid)["events"]}
    for want in (("step", "done"), ("step", "approve"), ("step", "sendback"), ("comment", "comment"), ("doc", "doc_added")):
        assert want in kinds, want


def test_project_health_and_summary_fields(api):
    pid = api.create()
    d = api.detail("ananya", pid)
    assert d["health"] == "ok" and d["steps_total"] > 40 and d["phase"] == "opportunity"
    with SessionLocal() as db:
        p = db.get(Project, pid)
        run = eng.active_runs(p)[0]
        run.due_at = datetime.utcnow() - timedelta(hours=3)
        db.commit()
    assert api.detail("ananya", pid)["health"] == "late"
    assert api.detail("ananya", pid)["latest_note"] is None
    api.post("ananya", f"/api/projects/{pid}/comments", json={"note": "Hello team"})
    assert api.detail("rajiv", pid)["latest_note"]["text"] == "Hello team"
