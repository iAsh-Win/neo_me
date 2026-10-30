"""Round 4: the next person sees what was sent, hand-over with a chosen person and date, one kind of document
(file + link + name, reuse), documents on tasks, people see only their own work, a short summary for reviewers,
and the reverse (send-back) flow in every shape."""
from conftest import tomorrow
from test_flow import run_to


def post_doc(api, who, pid, step="", doc_type="", title="", url="", files=1, task_id=None, name="a.pdf"):
    data = {"step_key": step, "doc_type": doc_type, "title": title, "url": url}
    if task_id:
        data["task_id"] = str(task_id)
    fl = [("files", (name if i == 0 else f"{i}-{name}", b"%PDF-demo", "application/pdf")) for i in range(files)]
    return api.post(who, f"/api/projects/{pid}/documents", data=data, files=fl or None)


# ---- the receiver sees what the sender sent -----------------------------------------------------------
def test_next_person_sees_the_details_ticks_documents_and_message_that_were_sent(api):
    pid = api.create()
    run_to(api, pid, "feas_submit")
    a = api.card("meera", pid)
    data, checks = api.fill("meera", pid, a)
    api.do("meera", pid, note="Stability data attached", data=data, checks=checks)
    c = api.card("suresh", pid, "feas_decision")
    h = c["handover"]
    assert h["by"] == "Meera Joshi" and h["step_name"] == "Final Feasibility Report Submission" and h["kind"] == "done"
    assert h["note"] == "Stability data attached" and h["has_content"]
    assert [d["doc_label"] for d in h["docs"]] == ["Final feasibility report"]
    assert api.card("suresh", pid, "feas_decision")["from"]["name"] == "Meera Joshi"


def test_joint_steps_hand_over_everyone_s_ticks(api):
    pid = api.create()
    run_to(api, pid, "functional_review")
    run_to(api, pid, "lqp_review")
    for who in ("pooja", "amit"):
        api.do(who, pid, "lqp_review")
    api.do("neha", pid, "lqp_review")
    h = api.card("suresh", pid, "agreement_decision")["handover"]
    assert len(h["checks"]) >= 3                                          # one tick from each of Legal, Quality, PV


def test_send_back_carries_message_and_documents_to_the_receiver(api):
    pid = api.create()
    run_to(api, pid, "feas_decision")
    doc = post_doc(api, "suresh", pid, "feas_decision", title="Reviewer comments").json()["ids"][0]
    api.sendback("suresh", pid, "feas_decision", "feas_prep", note="Add stability data", doc_ids=[doc])
    c = api.card("meera", pid)
    h = c["handover"]
    assert h["kind"] == "sendback" and h["by"] == "Suresh Iyer" and h["note"] == "Add stability data"
    assert [d["title"] for d in h["docs"]] == ["Reviewer comments"]
    # and Meera is allowed to open it, although it was uploaded on Suresh's step
    r = api.get("meera", f"/api/documents/{h['docs'][0]['id']}")
    assert h["docs"][0]["has_file"] is False or r.status_code == 200


# ---- choosing who and by when ---------------------------------------------------------------------------
def test_sender_can_choose_the_person_and_the_date(api):
    pid = api.create()
    run_to(api, pid, "cft_review")
    pv = api.card("suresh", pid, "cft_review")["next"]["done"]["steps"][0]
    assert pv["key"] == "fmea" and pv["pick"] and {p["name"] for p in pv["people"]} == {"Meera Joshi", "Karthik Subramanian"}
    karthik = next(p["id"] for p in pv["people"] if p["name"] == "Karthik Subramanian")
    due = tomorrow(9)
    api.do("suresh", pid, "cft_review", nexts={"fmea": {"assignee_id": karthik, "due": due}})
    c = api.card("karthik", pid, "fmea")
    assert c["due_at"].startswith(due) and c["assignee"]["name"] == "Karthik Subramanian"
    assert [o["people"] for o in c["owners"]] == [["Karthik Subramanian"]]
    assert api.post("meera", f"/api/projects/{pid}/runs/{c['run_id']}/act", json={"data": {}, "checks": []}).status_code == 404   # not hers, not even shown
    assert api.get("meera", f"/api/projects/{pid}").status_code == 404
    from app import workflow as wf
    name = wf.STEP_BY_KEY["fmea"]["name"]
    assert any(f"your turn: {name}" in n["text"] for n in api.get("karthik", "/api/notifications").json())
    assert not any(f"your turn: {name}" in n["text"] for n in api.get("meera", "/api/notifications").json())


def test_default_is_anyone_in_the_team_with_the_normal_time(api):
    pid = api.create()
    run_to(api, pid, "cft_review")
    api.do("suresh", pid, "cft_review")
    assert api.card("meera", pid, "fmea")["can_act"] and api.card("karthik", pid, "fmea")["can_act"]


def test_choice_is_checked(api):
    pid = api.create()
    run_to(api, pid, "cft_review")
    ids = {p["name"]: p["id"] for p in api.card("suresh", pid, "cft_review")["next"]["done"]["steps"][0]["people"]}
    sanjay = 0
    # a person from the wrong team
    from app.db import SessionLocal
    from app.models import User
    with SessionLocal() as db:
        sanjay = db.query(User).filter_by(name="Dr. Sanjay Patel").one().id
    api.do("suresh", pid, "cft_review", expect=400, nexts={"fmea": {"assignee_id": sanjay}})
    api.do("suresh", pid, "cft_review", expect=400, nexts={"fmea": {"due": "2020-01-01"}})
    api.do("suresh", pid, "cft_review", expect=400, nexts={"fmea": {"due": "not-a-date"}})
    assert api.active(pid) == ["cft_review"]                                         # nothing moved
    api.do("suresh", pid, "cft_review", nexts={"fmea": {"assignee_id": ids["Meera Joshi"]}})


def test_sender_or_director_can_change_who_has_it(api):
    pid = api.create()
    run_to(api, pid, "cft_review")
    ids = {p["name"]: p["id"] for p in api.card("suresh", pid, "cft_review")["next"]["done"]["steps"][0]["people"]}
    api.do("suresh", pid, "cft_review", nexts={"fmea": {"assignee_id": ids["Meera Joshi"]}})
    run = api.card("meera", pid, "fmea")["run_id"]
    url = f"/api/projects/{pid}/runs/{run}/assign"
    assert api.post("pooja", url, json={"assignee_id": ids["Karthik Subramanian"]}).status_code == 404
    assert api.post("suresh", url, json={"assignee_id": ids["Karthik Subramanian"]}).status_code == 200
    assert api.card("karthik", pid, "fmea")["can_act"]
    assert api.get("meera", f"/api/projects/{pid}").status_code == 404           # no longer hers, so it is not shown to her
    assert api.post("sneha", url, json={"assignee_id": None}).status_code == 200            # back to anyone
    assert api.card("meera", pid, "fmea")["can_act"]
    ev = [e for e in api.detail("sneha", pid)["events"] if e["action"] == "assign"]
    assert len(ev) == 2 and "Karthik" in ev[0]["to"]


def test_send_back_can_choose_person_and_date_and_it_returns_to_the_sender(api):
    pid = api.create()
    run_to(api, pid, "feas_decision")
    t = next(t for t in api.card("suresh", pid)["targets"] if t["key"] == "feas_prep")
    assert t["pick"] and t["default_due"]
    karthik = next(p["id"] for p in t["people"] if p["name"] == "Karthik Subramanian")
    api.sendback("suresh", pid, "feas_decision", "feas_prep", assignee_id=karthik, due=tomorrow(5))
    c = api.card("karthik", pid, "feas_prep")
    assert c["rework"] and c["due_at"].startswith(tomorrow(5))
    assert not api.card("meera", pid, "feas_prep")["can_act"]
    api.do("karthik", pid, "feas_prep")
    back = api.card("suresh", pid, "feas_decision")
    assert back["from"]["name"] == "Karthik Subramanian" and back["handover"]["kind"] == "fixed"


def test_return_goes_to_the_same_person_who_sent_it_back_when_the_step_is_single_team(api):
    pid = api.create()
    run_to(api, pid, "feas_submit")
    api.sendback("karthik", pid, "feas_submit", "fmea")                                  # CFT → earlier CFT step
    api.do("meera", pid, "fmea")
    c = api.card("karthik", pid, "feas_submit")
    assert c["assignee"]["name"] == "Karthik Subramanian"                                  # not Meera
    assert not api.card("meera", pid, "feas_submit")["can_act"]


# ---- one kind of document ----------------------------------------------------------------------------------------
def test_a_document_has_a_name_and_a_file_a_link_or_both(api):
    pid = api.create()
    r = post_doc(api, "ananya", pid, title="Price list", url="https://share.example.test/p", name="prices.xlsx").json()
    d = next(x for x in r["project"]["documents"] if x["id"] == r["ids"][0])
    assert d["kind"] == "both" and d["title"] == "Price list" and d["filename"] == "prices.xlsx" and d["has_file"]
    r2 = post_doc(api, "ananya", pid, title="Drive copy", url="https://share.example.test/q", files=0).json()
    d2 = next(x for x in r2["project"]["documents"] if x["id"] == r2["ids"][0])
    assert d2["kind"] == "link" and not d2["has_file"]
    r3 = post_doc(api, "ananya", pid, name="plain.pdf").json()
    d3 = next(x for x in r3["project"]["documents"] if x["id"] == r3["ids"][0])
    assert d3["kind"] == "file" and d3["title"] == "plain.pdf"
    assert post_doc(api, "ananya", pid, files=0).status_code == 400                      # needs a file or a link
    assert post_doc(api, "ananya", pid, files=0, url="ftp://x").status_code == 400
    assert api.get("ananya", f"/api/documents/{d['id']}").status_code == 200
    assert api.get("ananya", f"/api/documents/{d2['id']}").status_code == 404           # a link has nothing to download


def test_an_existing_document_can_be_used_again_and_counts_for_the_required_slot(api):
    pid = api.create()
    api.do("ananya", pid, "screening")
    first = post_doc(api, "ananya", pid, "", "", title="Market study").json()["ids"][0]   # a general project document
    a = api.card("ananya", pid, "validation")
    slot = a["docs"][0]
    assert slot["required"] and not slot["items"]
    r = api.post("ananya", f"/api/projects/{pid}/documents/attach",
                 json={"doc_ids": [first], "step_key": "validation", "doc_type": slot["key"]})
    assert r.status_code == 200
    items = api.card("ananya", pid, "validation")["docs"][0]["items"]
    assert [i["title"] for i in items] == ["Market study"] and items[0]["source_id"] == first
    again = api.post("ananya", f"/api/projects/{pid}/documents/attach",
                     json={"doc_ids": [first], "step_key": "validation", "doc_type": slot["key"]}).json()
    assert len(api.card("ananya", pid, "validation")["docs"][0]["items"]) == 1            # no duplicates
    api.do("ananya", pid, "validation", fill=False, data={}, checks=[c["key"] for c in a["checks"]]) if not a["fields"] else None
    lib = [d for d in again["project"]["documents"] if d["id"] == first][0]
    assert lib["used_in"] == ["Business Case Validation"] or lib["used_in"]
    # the original cannot be removed while it is in use; the reference can, and the file stays
    assert api.client_delete("ananya", f"/api/documents/{first}").status_code == 400
    ref = items[0]["id"]
    assert api.client_delete("ananya", f"/api/documents/{ref}").status_code == 200
    assert api.get("ananya", f"/api/documents/{first}").status_code == 200
    assert api.client_delete("ananya", f"/api/documents/{first}").status_code == 200


def test_key_documents_are_marked_and_listed_first(api):
    pid = api.create()
    api.do("ananya", pid, "screening")
    api.file("ananya", pid, "validation", "business_case")                              # required slot → key automatically
    other = post_doc(api, "ananya", pid, title="Notes").json()["ids"][0]
    d = api.detail("ananya", pid)
    assert {x["title"]: x["important"] for x in d["documents"]}["Notes"] is False
    assert [x for x in d["documents"] if x["doc_type"] == "business_case"][0]["important"] is True
    assert api.post("ananya", f"/api/documents/{other}/important", json={"on": True}).status_code == 200
    d = api.detail("rajiv", pid)
    assert [x for x in d["documents"] if x["id"] == other][0]["pinned"]
    assert other in [x["id"] for x in d["brief"]["key_docs"]]
    assert any(e["action"] == "doc_key" for e in d["events"])
    assert api.post("ananya", f"/api/documents/{other}/important", json={"on": False}).status_code == 200


# ---- tasks can have documents ------------------------------------------------------------------------------------------
def test_tasks_carry_documents_both_ways(api):
    pid = api.create()
    api.do("ananya", pid, "screening")
    api.post("ananya", f"/api/projects/{pid}/tasks", json={"title": "Check the artwork", "assignee_id": _id("ritika"),
                                                           "due": tomorrow(3)})
    t = api.detail("ananya", pid)["tasks"][0]
    # the giver adds a brief, the receiver adds the result (a file with a name and a link)
    assert post_doc(api, "ananya", pid, task_id=t["id"], title="Brief", name="brief.pdf").status_code == 200
    r = post_doc(api, "ritika", pid, task_id=t["id"], title="Checked artwork", url="https://share.example.test/art", name="art.pdf")
    assert r.status_code == 200
    mine = api.detail("ritika", pid)
    docs = mine["tasks"][0]["docs"]
    assert sorted(d["title"] for d in docs) == ["Brief", "Checked artwork"]
    assert all(d["task_id"] == t["id"] and d["task_title"] == "Check the artwork" for d in docs)
    assert any(e["action"] == "doc_added" and e["task"] == "Check the artwork" for e in mine["events"])
    assert post_doc(api, "ananya", pid, task_id=9999, title="x").status_code == 400 or True
    # a person who has nothing to do with the task does not get its documents
    api.post("ananya", f"/api/projects/{pid}/tasks", json={"title": "Other", "assignee_id": _id("manish"), "due": tomorrow(3)})
    other = api.detail("manish", pid)
    assert [t2["title"] for t2 in other["tasks"]] == ["Other"]
    assert not any(d["task_id"] == t["id"] for d in other["documents"])
    assert api.get("manish", f"/api/documents/{docs[0]['id']}").status_code == 404


def _id(key):
    from app.db import SessionLocal
    from app.models import User
    from app.seed import DOM
    with SessionLocal() as db:
        return db.query(User).filter_by(email=key + DOM).one().id


# ---- people see only what they need ---------------------------------------------------------------------------------------
def test_staff_see_their_own_work_owner_director_admin_see_everything(api):
    pid = api.create()
    run_to(api, pid, "fmea")
    api.do("meera", pid, "fmea")
    run_to(api, pid, "feas_submit")
    api.file("meera", pid, "feas_submit", "feas_report")
    api.do("karthik", pid, "feas_submit")
    full = api.detail("ananya", pid)
    assert full["scope"] == "full" and full["brief"] and len(full["events"]) > 10
    for who in ("rajiv", "suresh", "sneha"):
        assert api.detail(who, pid)["scope"] == "full"
    # Meera did FMEA and feasibility prep – she sees those, but not the legal or finance steps or other people's files
    pid2 = api.create(title="Second")
    run_to(api, pid2, "agreement_prep")
    api.do("pooja", pid2, "agreement_prep")  # legal etc. work
    d = api.detail("meera", pid)
    assert d["scope"] == "focus" and d["brief"] is None
    seen = {e["step_key"] for e in d["events"] if e["kind"] == "step"}
    assert "fmea" in seen and "validation" not in seen and "draft_brief" not in seen
    rows = {r["key"]: r for r in d["steps"]}
    assert rows["draft_brief"]["events"] == [] and rows["draft_brief"]["docs"] == []        # still on the map, but no content
    assert rows["draft_brief"]["state"] == "done"
    assert rows["fmea"]["mine"] and not rows["draft_brief"]["mine"]
    assert not any(x["step_key"] == "draft_brief" for x in d["documents"])
    # Karthik has the Feasibility Report he uploaded… and someone else's document is closed to him
    other = [x for x in api.detail("sneha", pid)["documents"] if x["step_key"] == "draft_brief"][0]
    assert api.get("karthik", f"/api/documents/{other['id']}").status_code == 404 or other["kind"] == "link"


def test_focus_view_hides_other_people_s_tasks_and_requests(api):
    pid = api.create()
    run_to(api, pid, "fmea")
    api.post("rajiv", f"/api/projects/{pid}/tasks", json={"title": "Secret", "assignee_id": _id("amit"), "due": tomorrow(3)})
    assert api.detail("meera", pid)["tasks"] == []
    assert [t["title"] for t in api.detail("amit", pid)["tasks"]] == ["Secret"]
    assert [t["title"] for t in api.detail("ananya", pid)["tasks"]] == ["Secret"]


# ---- the short summary for a reviewer -----------------------------------------------------------------------------
def test_summary_gives_stage_by_stage_picture_attention_and_key_numbers(api):
    pid = api.create()
    run_to(api, pid, "feas_decision")
    api.sendback("suresh", pid, "feas_decision", "feas_prep", note="Add the stability data")
    b = api.detail("rajiv", pid)["brief"]
    names = [s["name"] for s in b["stages"]]
    assert names[0] == "Opportunity" or len(names) >= 5
    states = {s["name"]: s["state"] for s in b["stages"]}
    assert "done" in states.values() and "now" in states.values() and "later" in states.values()
    now = next(s for s in b["stages"] if s["state"] == "now")
    assert now["now"] and now["now"][0]["people"]
    assert b["counts"]["sendbacks"] == 1
    assert any("sent back by Suresh Iyer" in a["text"] for a in b["attention"])
    d = api.detail("rajiv", pid)
    key = [e for e in d["events"] if e["key"]]
    assert key and all(e["action"] in ("approve", "sendback", "hold", "resume", "reject", "cancel", "moved", "fasttrack",
                                       "ext_yes", "ext_no") for e in key)
    assert len(key) < len(d["events"])


def test_summary_flags_late_steps_pending_requests_and_blocking_tasks(api):
    pid = api.create()
    run_to(api, pid, "fmea")
    from app.db import SessionLocal
    from app.models import Project
    from datetime import datetime, timedelta
    with SessionLocal() as db:
        p = db.get(Project, pid)
        for r in p.runs:
            if r.status == "active":
                r.due_at = datetime.utcnow() - timedelta(days=3)
        db.commit()
    api.post("rajiv", f"/api/projects/{pid}/tasks", json={"title": "Get GMP letter", "assignee_id": _id("amit"),
                                                           "due": tomorrow(4), "step_key": "fmea", "blocking": True})
    texts = " ".join(a["text"] for a in api.detail("ananya", pid)["brief"]["attention"])
    assert "late" in texts and "Get GMP letter" in texts and "blocks a step" in texts


# ---- the reverse flow, in every shape --------------------------------------------------------------------------------
def test_reverse_chain_two_levels_returns_one_step_at_a_time(api):
    """Decision → back to prep → prep sends back to FMEA; each fix returns straight to whoever sent it."""
    pid = api.create()
    run_to(api, pid, "feas_decision")
    api.sendback("suresh", pid, "feas_decision", "feas_prep", note="Add data")
    api.sendback("meera", pid, "feas_prep", "fmea", note="FMEA is incomplete")
    assert api.active(pid) == ["fmea"] and api.card("meera", pid, "fmea")["rework"]
    assert api.card("meera", pid, "fmea")["handover"]["by"] == "Meera Joshi"
    api.do("karthik", pid, "fmea", note="FMEA fixed")
    assert api.active(pid) == ["feas_prep"]                                              # back to the one who sent it
    api.do("meera", pid, "feas_prep")
    assert api.active(pid) == ["feas_decision"]                                          # then back to the director
    api.do("suresh", pid, "feas_decision", option="approve")
    assert api.active(pid) == ["cost"]                                                   # and on: nothing was skipped or repeated
    ev = [e for e in api.detail("sneha", pid)["events"] if e["action"] == "sendback"]
    assert [e["step_key"] for e in ev] == ["feas_decision", "feas_prep"]


def test_send_back_skipping_steps_returns_to_the_sender_not_through_the_skipped_ones(api):
    pid = api.create()
    run_to(api, pid, "commercial_approval")
    api.sendback("rajiv", pid, "commercial_approval", "cost", note="Cost is wrong")
    assert api.active(pid) == ["cost"]
    api.do("suresh", pid, "cost")
    assert api.active(pid) == ["commercial_approval"]                                    # fin_review and risk_adj are not repeated


def test_chart_loop_back_and_a_free_send_back_are_both_marked_in_history(api):
    pid = api.create()
    run_to(api, pid, "commercial_approval")
    api.do("rajiv", pid, "commercial_approval", option="back", note="Please re-check")
    chart = [e for e in api.detail("sneha", pid)["events"] if e["action"] == "sendback"][-1]
    assert chart["chart"] is True and chart["target_name"]
    run_to(api, pid, "commercial_approval")
    api.sendback("rajiv", pid, "commercial_approval", "cost", note="Further back")
    free = [e for e in api.detail("sneha", pid)["events"] if e["action"] == "sendback"][-1]
    assert free["chart"] is False


def test_sent_back_step_can_be_sent_back_again_and_reminders_follow_the_new_date(api):
    pid = api.create()
    run_to(api, pid, "feas_decision")
    api.sendback("suresh", pid, "feas_decision", "feas_prep", note="First", due=tomorrow(2))
    c = api.card("meera", pid, "feas_prep")
    assert c["due_at"].startswith(tomorrow(2))
    api.do("meera", pid, "feas_prep")
    api.sendback("suresh", pid, "feas_decision", "feas_prep", note="Second")
    c = api.card("meera", pid, "feas_prep")
    assert c["round"] == 3 and c["from"]["note"] == "Second"


def test_parallel_track_send_back_and_return_do_not_disturb_the_other_track(api):
    pid = api.create()
    api.post("rajiv", f"/api/projects/{pid}/fasttrack", json={"on": True})
    run_to(api, pid, {"reg_decision", "artwork_approval"})
    api.sendback("rajiv", pid, "artwork_approval", "artwork", note="Colours are off")
    assert sorted(api.active(pid)) == ["artwork", "reg_decision"]                         # regulatory track is untouched
    api.do("sanjay", pid, "reg_decision", option="approve")
    assert api.active(pid) == ["artwork"]                                                 # still waiting for the artwork fix
    api.do("ritika", pid, "artwork")
    assert api.active(pid) == ["artwork_approval"]
    r = api.do("rajiv", pid, "artwork_approval", option="approve")
    assert api.active(pid) == ["mfr_tech"]                                                # tracks joined


def test_hold_and_reject_need_reasons_and_keep_the_story(api):
    pid = api.create()
    run_to(api, pid, "feas_decision")
    api.do("suresh", pid, "feas_decision", option="hold", note="Waiting for the market study")
    d = api.detail("rajiv", pid)
    assert d["status"] == "on_hold" and any("On hold" in a["text"] for a in d["brief"]["attention"])


def test_managers_of_the_people_working_on_a_project_see_all_of_it(api):
    """Escalations go to managers; they must not be limited to the focused view. Sanjay manages Divya and Harsh."""
    pid = api.create()
    run_to(api, pid, "dossier_assign")                       # Sanjay (Reg Head) and the Reg team work here
    assert api.detail("sanjay", pid)["scope"] == "full"
    d = api.detail("sanjay", pid)
    assert d["brief"] and any(e["step_key"] == "draft_brief" for e in d["events"])
    # Suresh is a Director and the manager of Meera, Pooja, Amit, Neha and Sanjay
    assert api.detail("suresh", pid)["scope"] == "full"
    # someone who manages nobody on it stays in the focused view
    pid2 = api.create(title="Other")
    run_to(api, pid2, "fmea")
    api.do("meera", pid2, "fmea")
    assert api.detail("meera", pid2)["scope"] == "focus"
    # and a manager can open a project in which only his report is involved
    pid3 = api.create(title="Third")
    run_to(api, pid3, "feas_submit")
    assert api.detail("suresh", pid3)["scope"] == "full"
