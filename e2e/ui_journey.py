"""Browser test: drives the real screens like a person would.

Run against a freshly started server with the demo data:
    NEO_URL=http://localhost:8090 python e2e/ui_journey.py
Needs: pip install playwright (uses the installed Microsoft Edge).
"""
import os
import re
import sys
import time

from playwright.sync_api import expect, sync_playwright

sys.stdout.reconfigure(encoding="utf-8")
BASE = os.environ.get("NEO_URL", "http://localhost:8090")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "screenshots")
os.makedirs(OUT, exist_ok=True)
PASS = "neo@123"
DOM = "@neohealth.example"
log, errors = [], []


def ok(msg):
    log.append(msg)
    print("PASS", msg, flush=True)


with sync_playwright() as pw:
    browser = pw.chromium.launch(channel="msedge")
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, accept_downloads=True)
    page = ctx.new_page()
    page.set_default_timeout(10000)
    page.on("pageerror", lambda e: errors.append("JS: " + str(e)))
    page.on("console", lambda m: errors.append("CONSOLE: " + m.text) if m.type == "error" and not any(c in m.text for c in ("401", "400", "403", "404", "429")) else None)
    tokens, current = {}, {"who": None}

    # ------------------------------------------------------------------ helpers
    def token_for(who):
        if who not in tokens:
            r = ctx.request.post(f"{BASE}/api/auth/login", data={"email": who + DOM, "password": PASS})
            assert r.ok, r.text()
            tokens[who] = r.json()["token"]
        return tokens[who]

    def as_user(who):
        if current["who"] == who:
            return
        page.goto(BASE)
        page.evaluate("t => localStorage.setItem('neo_token', t)", token_for(who))
        current["who"] = who

    def api(who, path, method="get", data=None):
        fn = getattr(ctx.request, method)
        kw = {"data": data} if data is not None else {}
        return fn(f"{BASE}{path}", headers={"Authorization": "Bearer " + token_for(who)}, **kw)

    def detail(pid):
        return api("sneha", f"/api/projects/{pid}").json()

    def open_project(pid):
        page.goto(f"{BASE}/projects/{pid}")
        try:
            page.wait_for_selector(".strip")
        except Exception:
            snap("FAIL_open_project")
            print("FAILED to open project", pid, "as", current["who"], "->", page.inner_text("body")[:300])
            raise
        page.wait_for_timeout(250)

    def toast(text):
        expect(page.locator(".toast", has_text=text).first).to_be_visible(timeout=7000)

    def snap(name):
        page.screenshot(path=f"{OUT}/{name}.png", full_page=True)

    def card(name):
        return page.locator(".nowcard.mine", has=page.locator("h2", has_text=name))

    # ---- fill a card like a person: documents (file / link alternately), details, ticks
    def satisfy(c):
        n = 0
        while c.locator(".slot.need").count():
            before = c.locator(".slot.need").count()
            slot = c.locator(".slot.need").first
            slot.get_by_role("button", name="Add document").click()
            if n % 2 == 0:
                page.locator(".modal input[type=file]").set_input_files({"name": f"doc{n}.pdf", "mimeType": "application/pdf", "buffer": b"%PDF-1.4 test"})
            else:
                page.locator(".modal input[placeholder='https://']").fill(f"https://share.example.test/doc{n}")
            page.locator(".modal footer .btn.primary").click()
            expect(c.locator(".slot.need")).to_have_count(before - 1)
            n += 1
        for i in range(c.locator(".fields .field").count()):
            f = c.locator(".fields .field").nth(i)
            if f.locator("select").count():
                f.locator("select").select_option(index=1)
            elif f.locator("textarea").count():
                f.locator("textarea").fill("Please confirm the shelf life and the supplier.")
            else:
                inp = f.locator("input")
                t = inp.get_attribute("type")
                if not inp.input_value():
                    inp.fill("5" if t == "number" else "2027-03-15" if t == "date" else "Sunrise Pharma")
        for i in range(c.locator(".tick:not(.on)").count()):
            c.locator(".tick:not(.on)").first.click()

    def finish(name, action="approve", note="", target=None):
        c = card(name)
        expect(c).to_be_visible()
        if action in ("approve", "done"):
            satisfy(c)
            c.locator(".act-buttons .btn.ok").click()
            if name == "Neo India Lifeline Review":
                page.get_by_role("button", name="Information is complete").click()
                page.locator(".modal footer .btn.ok").click()
        elif action == "incomplete":
            c.locator(".act-buttons .btn.ok").click()
            page.get_by_role("button", name="Information is incomplete").click()
            page.locator(".modal footer .btn.ok").click()
        elif action == "sendback":
            c.locator(".act-buttons .btn.bad").click()
            page.wait_for_selector(".targets")
            if target:
                page.locator(".target", has_text=target).click()
            page.locator(".modal footer .btn.danger").click()
            expect(page.locator(".modal .form-error")).to_contain_text(re.compile("why|reason"))          # a reason is required
            page.locator(".modal textarea").fill(note or "Please fix this.")
            page.locator(".modal footer .btn.danger").click()
        elif action in ("hold", "reject"):
            c.locator(".act-buttons .btn.ghost").click()
            page.locator(".modal textarea").fill(note or "Not now.")
            page.locator(f".modal footer .btn.{'amber' if action == 'hold' else 'danger'}").click()
        page.locator(".toast").first.wait_for(timeout=8000)

    emails = {u["name"]: u["email"].split("@")[0] for u in api("sneha", "/api/users").json()}

    def drive(pid, hold=(), script=None, max_steps=150):
        script = {k: list(v) for k, v in (script or {}).items()}
        hold = set([hold] if isinstance(hold, str) else hold)
        for _ in range(max_steps):
            d = detail(pid)
            acts = d["actions"]
            if d["status"] != "active" or (acts and all(a["key"] in hold for a in acts)):
                return d
            a = next(x for x in acts if x["key"] not in hold)
            owner = next(o for o in a["owners"] if not o["signed"])
            as_user(emails[owner["people"][0]])
            open_project(pid)
            item = script[a["key"]].pop(0) if script.get(a["key"]) else None
            kind, note, target = (tuple(item) + (None, None))[:3] if item else ("approve", "", None)
            finish(a["name"], kind, note, target)
            time.sleep(0.1)
        raise AssertionError("did not settle on " + str(hold))

    def new_project(who, title, kind):
        as_user(who)
        page.goto(BASE)
        page.wait_for_selector(".hero")
        page.get_by_role("button", name="New project").click()
        page.get_by_role("button", name="Add project", exact=True).click()
        expect(page.locator(".modal .form-error")).to_contain_text("name")
        page.get_by_placeholder("e.g. Vitamin C").fill(title)
        page.get_by_role("button", name="Add project", exact=True).click()
        expect(page.locator(".modal .form-error")).to_contain_text("Development or In-Licence")
        page.locator(".choice button", has_text=kind).click()
        page.get_by_placeholder("optional").fill("350000")
        page.get_by_role("button", name="Add project", exact=True).click()
        page.wait_for_selector(".nowcard")
        return int(page.url.rsplit("/", 1)[1])

    # ------------------------------------------------------------------ A. sign-in and role views
    page.goto(BASE)
    page.evaluate("localStorage.clear()")
    page.goto(BASE)
    page.wait_for_selector(".login")
    snap("A1_login")
    page.get_by_label("Email").fill("ananya" + DOM)
    page.get_by_label("Password", exact=True).fill("wrong")
    page.get_by_role("button", name="Sign in", exact=True).click()
    expect(page.locator(".form-error")).to_contain_text("not correct")
    page.get_by_label("Password", exact=True).fill(PASS)
    page.get_by_role("button", name="Sign in", exact=True).click()
    page.wait_for_selector(".hero")
    ok("sign-in: wrong password refused, right one works")
    page.get_by_role("button", name="My account").first.click()
    page.get_by_role("button", name="Sign out").click()
    page.wait_for_selector(".login")
    ok("sign-out works")

    as_user("pooja")
    page.goto(BASE)
    page.wait_for_selector(".hero")
    assert page.get_by_role("link", name="Team").count() == 0 and page.get_by_text("Where projects are").count() == 0
    titles = [p["title"] for p in api("pooja", "/api/projects").json()]
    assert "Herbal Sleep Drops" not in titles and any("Ashwagandha" in t for t in titles)
    hidden = [p for p in api("sneha", "/api/projects").json() if p["title"] == "Herbal Sleep Drops"][0]["id"]
    page.goto(f"{BASE}/projects/{hidden}")
    expect(page.get_by_text("We could not open this")).to_be_visible()
    ok("a team member sees only their projects; others cannot be opened even by link")
    page.goto(BASE + "/projects")
    page.wait_for_selector(".pcard")
    assert page.get_by_role("link", name="Download Master Excel").count() == 0 and page.get_by_text("From Excel").count() == 0
    ok("the Excel download / import buttons are gone")
    as_user("suresh")
    page.goto(BASE)
    page.wait_for_selector(".stages")
    expect(page.get_by_text("Running late")).to_be_visible()
    esc = [n for n in api("suresh", "/api/notifications").json() if n["kind"] == "escalate"]
    assert esc
    ok("Director sees all, a 'Running late' list and the escalations that reached them")

    # ------------------------------------------------------------------ B. the demo's special cases, as the right person
    ids = {p["title"]: p["id"] for p in api("sneha", "/api/projects").json()}
    as_user("meera")
    open_project(ids["Biotin Hair & Nails Gummies"])
    c = page.locator(".nowcard.rework")
    expect(c).to_contain_text("Sent back to you")
    expect(c.locator(".received")).to_contain_text("Suresh Iyer")
    expect(c.locator(".received")).to_contain_text("returns to Suresh Iyer")
    snap("B1_rework_banner")
    ok("a sent-back step shows who sent it, why, and where it returns")
    as_user("suresh")
    open_project(ids["Ibuprofen 5% Pain Relief Gel"])
    expect(page.locator(".reqbox")).to_contain_text("Meera Joshi")
    ok("the approver sees the request for more time with the reason")
    as_user("ritika")
    open_project(ids["C-Boost Vitamin C Effervescent 1000mg"])
    expect(page.locator(".pgroup.fast")).to_be_visible()
    expect(page.locator(".pg-track")).to_have_count(3)
    snap("B2_parallel_tracks")
    ok("Fast track: the print/readiness/submission tracks run side by side")

    # ------------------------------------------------------------------ C. a Development project, all the way, by clicking
    pid = new_project("ananya", "Vitamin D3 Drops 1000IU", "Development")
    ok("new project validated and created")
    snap("C1_new_project")
    drive(pid, hold="validation")
    as_user("ananya")
    open_project(pid)
    c = card("Commercial Validation")
    c.locator(".act-buttons .btn.ok").click()
    expect(c.locator(".form-error")).to_contain_text("Business case")
    ok("a step cannot be completed without its required document (file or link)")
    drive(pid, hold="india_review")
    assert detail(pid)["code"].startswith("NHO-DEV-")
    ok("opportunity → brief done with files, links, details and ticks; code issued after Director approval")
    drive(pid, hold="internal_review", script={"india_review": [("sendback", "Please add stability data.")]})
    as_user("ananya")
    open_project(pid)
    expect(page.locator(".received.bad")).to_contain_text("Suresh Iyer")
    ok("India review → Send back (reason required); initiator sees who sent it")
    drive(pid, hold="clarification", script={"india_review": [("incomplete",)]})
    drive(pid, hold="internal_review")
    as_user("ananya")
    open_project(pid)
    expect(page.locator(".received")).to_contain_text("Suresh Iyer")
    drive(pid, hold="updated_brief")
    ok("clarification question loops to the initiator and comes back to 'Updated Project Brief Received'")
    drive(pid, hold="feas_decision")

    # generic send back chosen from a list, to a specific earlier step
    as_user("suresh")
    open_project(pid)
    c = card("Feasibility Decision")
    c.locator(".act-buttons .btn.bad").click()
    page.wait_for_selector(".targets")
    snap("C2_send_back_picker")
    page.locator(".target", has_text="Final Feasibility Report Preparation").click()
    expect(page.locator(".modal .goes")).to_contain_text("Meera Joshi")
    expect(page.locator(".modal .goes")).to_contain_text("comes straight back to you")
    page.locator(".modal textarea").fill("Add the stability data first.")
    page.locator(".modal footer .btn.danger").click()
    toast("Sent back")
    as_user("meera")
    open_project(pid)
    expect(page.locator(".nowcard.rework")).to_contain_text("Sent back to you")
    finish("Final Feasibility Report Preparation")
    as_user("suresh")
    open_project(pid)
    expect(card("Feasibility Decision")).to_be_visible()
    ok("send back to a chosen step: recipients shown, receiver notified, and it returns straight to the sender")
    finish("Feasibility Decision", "hold", "Waiting for supplier price list.")
    expect(page.locator(".nowcard.end.warn")).to_contain_text("supplier price")
    page.get_by_role("button", name="More actions").click()
    page.get_by_role("button", name="Restart").click()
    page.locator(".modal footer .btn.primary").click()
    expect(page.locator(".nowcard.mine h2")).to_have_text("Feasibility Decision")
    ok("feasibility → Hold pauses; a Director restarts it")
    drive(pid, hold="commercial_approval")
    as_user("suresh")
    open_project(pid)
    card("Final Commercial Approval").locator(".act-buttons .btn.ok").click()
    toast("Waiting for")
    expect(page.locator(".waitcard .who.signed, .nowcard .who.signed")).to_have_count(1)
    ok("Final Commercial Approval needs both Directors: first approval recorded, project waits")
    as_user("rajiv")
    open_project(pid)
    finish("Final Commercial Approval", "sendback", "Margin too thin.", "Financial Review")
    drive(pid, hold="commercial_approval")
    drive(pid, hold="agreement_prep")
    as_user("pooja")
    open_project(pid)
    c = card("Agreement Preparation")
    expect(c.locator(".slot-btn")).to_have_count(1)                                   # only Legal's own agreement
    expect(c.locator(".slot", has_text="Quality agreement")).to_contain_text("Quality")
    snap("L0_joint_documents")
    ok("joint step: each team adds only its own agreement (Legal sees only the supplier agreement slot)")
    drive(pid, hold="lqp_review")
    as_user("pooja")
    open_project(pid)
    c = card("Legal / Quality / Pharmacovigilance Review")
    expect(c.locator(".tick")).to_have_count(1)
    c.locator(".tick").click()
    c.locator(".act-buttons .btn.ok").click()
    toast("Waiting for")
    ok("Legal / Quality / PV review: each team ticks its own point and signs separately")
    drive(pid, hold="agreement_decision")

    # Fast track on for the next stretch
    as_user("rajiv")
    open_project(pid)
    page.get_by_role("button", name="More actions").click()
    page.get_by_role("button", name="Fast track").click()
    expect(page.locator(".modal")).to_contain_text("side by side")
    page.locator(".modal footer .btn.primary").click()
    toast("Fast track is on")
    page.keyboard.press("Escape")
    drive(pid, hold="agreement_decision")
    drive(pid, hold={"handover", "concept"})
    assert sorted(a["key"] for a in detail(pid)["actions"]) == ["concept", "handover"]
    as_user("sanjay")
    open_project(pid)
    expect(page.locator(".waitcard")).to_have_count(1)
    expect(card("Handover to the Regulatory")).to_be_visible()
    snap("C3_two_tracks_side_by_side")
    ok("Fast track: Regulatory and Concept & artwork are both active at once, each for its own team")
    drive(pid, hold="mfr_tech")
    assert detail(pid)["actions"][0]["key"] == "mfr_tech"
    ok("each track worked through its own steps; the project waited for both, then moved on together")
    d = drive(pid, hold=(), script={"mfr_approval": [("sendback", "The proof colour is off.", "Manufacturer Print Proof")]})
    assert d["status"] == "completed", d["status"]
    as_user("rajiv")
    open_project(pid)
    expect(page.locator(".nowcard.end.ok")).to_contain_text("Project completed")
    snap("C4_completed")
    ok("Development project completed through the UI: files, links, details, ticks, loops, Fast track, send-backs")

    # ------------------------------------------------------------------ D. In-Licence project straight through
    pid2 = new_project("rohit", "Calcium + K2 Tablets", "In-Licence")
    d2 = drive(pid2)
    names = [s["name"] for s in d2["steps"]]
    assert d2["status"] == "completed" and "Regulatory Review and Approval" in names and "CDMO / CRO Identify and Confirm" not in names
    ok("In-Licence project completed through the UI (Regulatory Review instead of CDMO)")

    # ------------------------------------------------------------------ E. reject
    pid3 = new_project("ananya", "Test Reject Product", "Development")
    drive(pid3, hold="otc_decision")
    as_user("rajiv")
    open_project(pid3)
    finish("Director Decision", "reject", "Not a fit for the range.")
    assert detail(pid3)["code"] is None
    as_user("ananya")
    open_project(pid3)
    expect(page.locator(".nowcard.end.bad")).to_contain_text("Not a fit")
    ok("Director rejects: project closes, no code, initiator sees the reason")

    # ------------------------------------------------------------------ F. more time
    pid4 = new_project("ananya", "Time Request Product", "Development")
    drive(pid4, hold="fmea")
    as_user("meera")
    open_project(pid4)
    c = card("Risk Analysis (FMEA)")
    c.get_by_role("button", name="More").click()
    page.get_by_role("button", name="Ask for more time").click()
    expect(page.locator(".modal .goes")).to_contain_text("Suresh Iyer")
    page.locator(".modal footer .btn.primary").click()
    expect(page.locator(".modal .form-error")).to_contain_text("why")
    page.locator(".modal textarea").fill("The plant data arrives next week.")
    snap("F1_ask_more_time")
    page.locator(".modal footer .btn.primary").click()
    toast("Request sent to Suresh Iyer")
    ok("asking for more time shows who it goes to; it needs a reason")
    as_user("suresh")
    page.goto(BASE)
    page.wait_for_selector(".hero")
    expect(page.locator(".task.request").filter(has_text="Meera Joshi asks for more time").first).to_be_visible()
    ok("the approver gets it on Home and as a notification")
    open_project(pid4)
    page.locator(".reqbox .btn.bad").click()
    page.locator(".reqbox input").fill("We cannot move this one.")
    page.locator(".reqbox .btn.danger").click()
    toast("Declined")
    notes = " ".join(n["text"] for n in api("meera", "/api/notifications").json())
    assert "declined" in notes and "We cannot move this one" in notes
    as_user("meera")
    open_project(pid4)
    c = card("Risk Analysis (FMEA)")
    c.get_by_role("button", name="More").click()
    page.get_by_role("button", name="Ask for more time").click()
    page.locator(".modal textarea").fill("Please, it is really needed.")
    page.locator(".modal footer .btn.primary").click()
    toast("Request sent")
    as_user("suresh")
    open_project(pid4)
    page.locator(".reqbox .btn.ok").click()
    toast("Approved")
    notes = " ".join(n["text"] for n in api("meera", "/api/notifications").json())
    assert "approved your request" in notes
    ok("decline needs a reason and the requester is told; a second request can be approved")
    page.get_by_role("tab", name="History").click()
    page.get_by_role("button", name="Everything").click()
    expect(page.locator(".h-item", has_text="asked for more time").first).to_be_visible()
    expect(page.locator(".h-item", has_text="declined more time").first).to_be_visible()
    ok("requests and answers are in the history")

    # ------------------------------------------------------------------ G. tasks
    as_user("ananya")
    open_project(pid4)
    page.get_by_role("tab", name="Tasks").click()
    page.get_by_role("button", name="Give a task").click()
    page.get_by_placeholder("e.g. Get the GMP clearance letter").fill("Check the claim wording")
    page.locator(".modal select").first.select_option(label="Pooja Bansal · Legal")
    expect(page.locator(".modal .goes")).to_contain_text("Pooja Bansal")
    page.locator(".modal footer .btn.primary").click()
    toast("Task given")
    as_user("pooja")
    page.goto(BASE)
    page.wait_for_selector(".hero")
    expect(page.locator(".task.task", has_text="Check the claim wording")).to_be_visible()
    page.locator(".task.task", has_text="Check the claim wording").click()
    page.wait_for_selector(".strip")
    page.get_by_role("tab", name="Tasks").click()
    page.get_by_role("button", name="More time").click()
    expect(page.locator(".modal .goes")).to_contain_text("Ananya Reddy")
    page.locator(".modal textarea").fill("Waiting for counsel.")
    page.locator(".modal footer .btn.primary").click()
    toast("Request sent to Ananya Reddy")
    page.get_by_role("button", name="Done").first.click()
    page.locator(".modal footer .btn.primary").click()
    toast("Done")
    ok("a task is given (shows who gets it), appears on their Home, can ask for time (goes to the giver) and be finished")

    # ------------------------------------------------------------------ H. documents (one dialog: name + file(s) + link)
    as_user("ananya")
    open_project(pid4)
    page.get_by_role("tab", name="Files").click()
    page.get_by_role("button", name="Add document").first.click()
    page.locator(".modal input[type=file]").set_input_files([{"name": "a.pdf", "mimeType": "application/pdf", "buffer": b"%PDF a"}])
    page.locator(".modal input[placeholder='https://']").fill("https://share.example.test/folder")
    page.get_by_placeholder("a.pdf").fill("Price list")
    page.locator(".modal footer .btn.primary").click()
    toast("Document added")
    chip = page.locator(".fitem .docchip", has_text="Price list")
    expect(chip).to_have_count(1)
    expect(chip.locator("a.also")).to_have_count(1)                                    # one document: file and link together
    with page.expect_download() as dl:
        chip.locator("a").first.click()
    assert dl.value.suggested_filename == "a.pdf"
    page.get_by_role("button", name="Add document").first.click()
    page.locator(".modal input[placeholder='https://']").fill("https://share.example.test/only-link")
    page.locator(".modal footer .btn.primary").click()
    toast("Document added")
    page.get_by_role("button", name="Add document").first.click()
    page.locator(".modal footer .btn.primary").click()
    expect(page.locator(".modal .form-error")).to_contain_text("file or paste a link")
    page.locator(".modal footer .btn", has_text="Cancel").click()
    page.get_by_role("button", name="Mark Price list as key").click()
    expect(page.locator(".fgroup.keys")).to_contain_text("Price list")
    page.once("dialog", lambda dlg: dlg.accept())
    page.locator(".fitem .docchip", has_text="only-link").first.locator(".x").last.click()
    expect(page.locator(".fitem .docchip", has_text="only-link")).to_have_count(0)
    ok("one document dialog: name + file + link together, link-only, download, key document, search, removal")

    # ------------------------------------------------------------------ I. history and status
    as_user("rajiv")
    open_project(pid)
    page.get_by_role("tab", name="History").click()
    expect(page.locator(".chip.on")).to_have_text("Key moments")
    expect(page.locator(".h-item", has_text="sent Feasibility Decision back").first).to_be_visible()
    page.get_by_role("button", name="Everything").click()
    expect(page.locator(".h-to", has_text="Goes to").first).to_be_visible()
    expect(page.locator(".h-data").first).to_be_visible()
    page.get_by_placeholder("Write a note for the team…").fill("Great work everyone.")
    page.get_by_role("button", name="Post").click()
    expect(page.locator(".bubble", has_text="Great work")).to_be_visible()
    snap("I1_history")
    ok("the history shows who sent what to whom, details, files and notes")
    open_project(pid)
    expect(page.locator(".strip")).to_contain_text("Status")
    expect(page.locator(".strip")).to_contain_text("Great work everyone.")
    ok("every project shows its status, progress, who it is with and the latest note")

    # ------------------------------------------------------------------ J. process map, team, password
    as_user("sanjay")
    page.goto(BASE + "/process")
    page.wait_for_selector(".band")
    expect(page.locator(".pgroup").first).to_contain_text("Can run side by side")
    expect(page.locator(".node.mine").first).to_be_visible()
    page.get_by_role("tab", name="In-Licence").click()
    assert page.locator(".node-name", has_text="CDMO / CRO Identify and Confirm").count() == 0
    snap("J1_process_map")
    ok("Process map: 7 stages, parallel tracks marked, my steps highlighted, both project types")
    as_user("sneha")
    page.goto(BASE + "/team")
    page.wait_for_selector(".person")
    page.get_by_role("button", name="Add person").click()
    page.locator(".modal input").nth(0).fill("Kavita Rao")
    page.locator(".modal input").nth(1).fill("kavita@neohealth.example")
    page.locator(".modal select").nth(0).select_option("legal")
    page.locator(".modal select").nth(1).select_option(label="Suresh Iyer")
    page.locator(".modal input").nth(3).fill("kavita123")
    page.get_by_role("button", name="Save").click()
    toast("Person added")
    expect(page.locator(".person", has_text="Kavita Rao")).to_be_visible()
    ok("admin adds a person into the reporting line")
    as_user("harsh")
    page.goto(BASE)
    page.wait_for_selector(".hero")
    page.get_by_role("button", name="My account").first.click()
    page.get_by_role("button", name="Change password").click()
    pw_ = page.locator(".modal input[type=password]")
    pw_.nth(0).fill(PASS)
    pw_.nth(1).fill("harsh-new-1")
    pw_.nth(2).fill("harsh-new-1")
    page.get_by_role("button", name="Save").click()
    toast("Password changed")
    ok("a person can change their own password")

    # ------------------------------------------------------------------ L. round 4
    pid6 = new_project("ananya", "Reverse Flow Product", "Development")
    drive(pid6, hold="cft_review")
    as_user("suresh")
    open_project(pid6)
    cr = card("Cross-Functional Review")
    expect(cr.locator(".handover")).to_contain_text("Risk Analysis (FMEA)")
    cr.locator(".handover select").select_option(label="Karthik Subramanian (CFT)")
    cr.locator(".handover input[type=date]").fill(time.strftime("%Y-%m-%d", time.localtime(time.time() + 9 * 86400)))
    snap("L1_handover_picker")
    cr.locator(".act-buttons .btn.ok").click()
    toast("Done")
    as_user("karthik")
    open_project(pid6)
    fm = card("Risk Analysis (FMEA)")
    expect(fm.locator(".received")).to_contain_text("Suresh Iyer")
    expect(fm.locator(".now-top")).to_contain_text("left")
    ok("hand over: the sender chose the person and the date; the receiver sees who sent it and what came with it")
    as_user("meera")
    page.goto(f"{BASE}/projects/{pid6}")
    expect(page.get_by_text("We could not open this")).to_be_visible()
    ok("the other team member (not chosen) does not see the project")

    # fix chain: FMEA → feasibility prep → feasibility submit → decision, with docs, then reverse two levels
    as_user("karthik")
    open_project(pid6)
    finish("Risk Analysis (FMEA)")
    drive(pid6, hold="feas_decision")
    as_user("suresh")
    open_project(pid6)
    d = card("Feasibility Decision")
    expect(d.locator(".received")).to_contain_text("Final Feasibility Report Submission")
    expect(d.locator(".received .docrow")).to_have_count(1)                              # the report that was attached
    expect(d.locator(".received .rec-facts")).to_be_visible()                             # and the details that were filled in
    d.locator(".act-buttons .btn.bad").click()
    page.wait_for_selector(".targets")
    page.locator(".target", has_text="Final Feasibility Report Preparation").click()
    page.locator(".modal .field", has_text="Send it to").locator("select").select_option(label="Karthik Subramanian (CFT)")
    page.locator(".modal textarea").fill("Add the stability data first.")
    page.locator(".modal .slot-btn").click()
    page.locator(".modal .modal input[type=file]").set_input_files({"name": "comments.pdf", "mimeType": "application/pdf", "buffer": b"%PDF c"})
    page.locator(".modal .modal footer .btn.primary").click()
    expect(page.locator(".modal .docchip", has_text="comments.pdf")).to_be_visible()
    page.locator(".modal footer .btn.danger").last.click()
    toast("Sent back")
    as_user("karthik")
    open_project(pid6)
    rw = page.locator(".nowcard.rework")
    expect(rw.locator(".received.bad")).to_contain_text("Add the stability data first.")
    expect(rw.locator(".received .docrow", has_text="comments.pdf")).to_be_visible()   # the sender's file is visible to the receiver
    expect(rw.locator(".received")).to_contain_text("returns to Suresh Iyer")
    snap("L2_received_sendback")
    ok("send back with a chosen person, a date and a document: the receiver sees the reason, the file and where it returns")
    # reverse a second level: preparation sends back to the FMEA step, the fix returns step by step
    rw.locator(".act-buttons .btn.bad").click()
    page.wait_for_selector(".targets")
    page.locator(".target", has_text="Risk Analysis (FMEA)").click()
    page.locator(".modal textarea").fill("The risk table is incomplete.")
    page.locator(".modal footer .btn.danger").click()
    toast("Sent back")
    as_user("meera")
    open_project(pid6)
    expect(card("Risk Analysis (FMEA)").locator(".received.bad")).to_contain_text("Karthik Subramanian")
    finish("Risk Analysis (FMEA)")
    as_user("karthik")
    open_project(pid6)
    expect(card("Final Feasibility Report Preparation").locator(".received")).to_contain_text("Meera Joshi")
    finish("Final Feasibility Report Preparation")
    as_user("suresh")
    open_project(pid6)
    expect(card("Feasibility Decision")).to_be_visible()
    ok("reverse flow, two levels: each fix returns to whoever sent it, one step at a time, back to the decision")

    # reuse an existing document in another step's slot
    as_user("suresh")
    finish("Feasibility Decision")
    as_user("suresh")
    open_project(pid6)
    cost = card("Cost Finalization")
    cost.locator(".slot", has_text="Quotation").get_by_role("button", name="Add document").click()
    page.get_by_role("tab", name="Already in this project").click()
    first = page.locator(".picklist label").first
    first.click()
    page.locator(".modal footer .btn.primary").click()
    toast("Document added here")
    expect(cost.locator(".slot.ok", has_text="Quotation")).to_be_visible()
    ok("an existing project document can be used in a step slot (no re-upload) and counts as submitted")

    # task documents
    as_user("ananya")
    open_project(pid6)
    page.get_by_role("tab", name="Tasks").click()
    page.get_by_role("button", name="Give a task").click()
    page.get_by_placeholder("e.g. Get the GMP clearance letter").fill("Check the pack artwork")
    page.locator(".modal select").first.select_option(label="Ritika Sen · Artwork")
    page.locator(".modal .task-docs .link").click()
    page.locator(".modal .modal input[type=file]").set_input_files({"name": "pack-brief.pdf", "mimeType": "application/pdf", "buffer": b"%PDF b"})
    page.locator(".modal .modal footer .btn.primary").click()
    page.locator(".modal footer .btn.primary").last.click()
    toast("Task given")
    expect(page.locator(".trow .docchip", has_text="pack-brief.pdf")).to_be_visible()
    as_user("ritika")
    open_project(pid6)
    page.get_by_role("tab", name="Tasks").click()
    expect(page.locator(".trow .docchip", has_text="pack-brief.pdf")).to_be_visible()
    page.locator(".trow").get_by_role("button", name="Add document").click()
    page.locator(".modal input[type=file]").set_input_files({"name": "checked.pdf", "mimeType": "application/pdf", "buffer": b"%PDF r"})
    page.locator(".modal footer .btn.primary").click()
    expect(page.locator(".trow .docchip", has_text="checked.pdf")).to_be_visible()
    expect(page.locator(".scope-note")).to_be_visible()
    assert page.get_by_role("tab", name="Summary").count() == 0
    ok("tasks carry documents both ways; a team member sees a focused view without the owner's summary")

    # the short version for a reviewer
    as_user("rajiv")
    open_project(pid6)
    expect(page.get_by_role("tab", name="Summary")).to_have_attribute("aria-selected", "true")
    expect(page.locator(".stage")).to_have_count(7)
    expect(page.locator(".stage.done").first).to_be_visible()
    expect(page.locator(".nums")).to_contain_text("send-backs")
    snap("L3_summary")
    page.get_by_role("tab", name="History").click()
    expect(page.locator(".chip.on")).to_have_text("Key moments")
    n_key = page.locator(".h-item").count()
    page.get_by_role("button", name="Everything").click()
    assert page.locator(".h-item").count() > n_key
    ok("a reviewer gets a Summary (stages, attention, numbers) and a History that starts with the key moments only")

    # ------------------------------------------------------------------ K. phone
    mctx = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, has_touch=True, is_mobile=True)
    m = mctx.new_page()
    m.set_default_timeout(10000)
    m.on("pageerror", lambda e: errors.append("MOBILE JS: " + str(e)))
    tok = token_for("ananya")
    pid5 = ctx.request.post(f"{BASE}/api/projects", headers={"Authorization": "Bearer " + tok},
                            data={"title": "Phone Test Product", "ptype": "development", "market": "AU"}).json()["id"]
    m.goto(BASE)
    m.evaluate("t => localStorage.setItem('neo_token', t)", tok)
    m.goto(f"{BASE}/projects/{pid5}")
    m.wait_for_selector(".nowcard.mine")
    m.screenshot(path=f"{OUT}/K1_phone_task.png")
    assert m.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth") <= 0
    for _ in range(3):
        m.locator(".tick:not(.on)").first.tap()
    m.locator(".nowcard .act-buttons .btn.ok").tap()
    expect(m.locator(".nowcard.mine h2")).to_have_text("Commercial Validation")
    m.locator(".tabbar").get_by_text("Home").tap()
    m.wait_for_selector(".hero")
    m.screenshot(path=f"{OUT}/K2_phone_home.png")
    ok("on a phone: tick, tap the big button, bottom tabs, no sideways scrolling")

    print("\nconsole/page errors:", errors)
    assert not errors, errors
    with open(f"{OUT}/result.txt", "w", encoding="utf8") as f:
        f.write("\n".join("PASS " + x for x in log))
    print("\nALL %d CHECKS PASSED" % len(log))
    browser.close()
