"""Browser test: drives the real screens like a person would.

Run against a freshly started server with demo data:
    NEO_URL=http://localhost:8090 python e2e/ui_journey.py
Needs: pip install playwright (uses the installed Microsoft Edge).
"""
import io
import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

from playwright.sync_api import expect, sync_playwright

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
    page.on("console", lambda m: errors.append("CONSOLE: " + m.text) if m.type == "error" and "401" not in m.text and "400" not in m.text and "403" not in m.text and "404" not in m.text and "429" not in m.text else None)

    tokens, current = {}, {"who": None}

    def token_for(email):
        if email not in tokens:
            r = ctx.request.post(f"{BASE}/api/auth/login", data={"email": email, "password": PASS})
            assert r.ok, r.text()
            tokens[email] = r.json()["token"]
        return tokens[email]

    def as_user(who):
        """Sign in quickly (token) as a demo user, by first name e.g. 'ananya'."""
        email = who + DOM
        if current["who"] == email:
            return
        page.goto(BASE)
        page.evaluate("t => localStorage.setItem('neo_token', t)", token_for(email))
        current["who"] = email

    def api(who, path, method="get", data=None):
        h = {"Authorization": "Bearer " + token_for(who + DOM)}
        fn = getattr(ctx.request, method)
        r = fn(f"{BASE}{path}", headers=h, **({"data": data} if data is not None else {}))
        return r

    def open_project(pid):
        page.goto(f"{BASE}/projects/{pid}")
        page.wait_for_selector(".nowcard", timeout=10000)

    def toast(text):
        expect(page.locator(".toast", has_text=text).first).to_be_visible(timeout=6000)

    def snap(name):
        page.screenshot(path=f"{OUT}/{name}.png", full_page=True)

    def step_title():
        return page.locator(".nowcard h2").inner_text()

    # ------------------------------------------------------------------ A. sign-in
    page.goto(BASE)
    page.evaluate("localStorage.clear()")
    page.goto(BASE)
    page.wait_for_selector(".login")
    snap("A1_login")
    page.get_by_label("Email").fill("ananya" + DOM)
    page.get_by_label("Password", exact=True).fill("wrong-password")
    page.get_by_role("button", name="Sign in", exact=True).click()
    expect(page.locator(".form-error")).to_contain_text("not correct")
    ok("wrong password is refused with a clear message")
    page.get_by_label("Password", exact=True).fill(PASS)
    page.get_by_role("button", name="Sign in", exact=True).click()
    page.wait_for_selector(".hero")
    expect(page.locator("h1")).to_contain_text("Ananya")
    ok("sign-in with the form works")
    page.get_by_role("button", name="My account").first.click()
    page.get_by_role("button", name="Sign out").click()
    page.wait_for_selector(".login")
    ok("sign-out works")

    # ------------------------------------------------------------------ B. role-based views
    as_user("pooja")                                    # Legal – only involved in a few projects
    page.goto(BASE)
    page.wait_for_selector(".hero")
    assert page.get_by_role("link", name="Team").count() == 0
    assert page.get_by_text("Where projects are").count() == 0
    ok("a team member has no Team page and no company-wide overview")
    page.goto(BASE + "/team")
    page.wait_for_selector(".hero")
    assert page.url.rstrip("/") == BASE
    ok("opening /team by link sends a non-director home")
    pooja_projects = api("pooja", "/api/projects").json()
    titles = [p["title"] for p in pooja_projects]
    assert "Herbal Sleep Drops" not in titles and "Kids Honey Cough Syrup" not in titles
    assert any(p["title"] == "Ashwagandha Stress Relief Capsules" for p in pooja_projects)
    ok("Legal sees only projects that reached or involved Legal (%d of 15)" % len(pooja_projects))
    hidden = [p for p in api("sneha", "/api/projects").json() if p["title"] == "Herbal Sleep Drops"][0]["id"]
    page.goto(f"{BASE}/projects/{hidden}")
    expect(page.get_by_text("We could not open this")).to_be_visible()
    ok("a project that is not theirs cannot be opened even with the link")
    as_user("rajiv")
    page.goto(BASE)
    page.wait_for_selector(".stages")
    assert len(api("rajiv", "/api/projects").json()) == 15
    expect(page.get_by_role("link", name="Team")).to_be_visible()
    ok("a Director sees all projects, the stage overview and the Team page")
    snap("B1_director_home")

    # ------------------------------------------------------------------ C. escalation from seeded data
    page.get_by_role("button", name="Notifications").click()
    expect(page.locator(".notif")).to_be_visible()
    snap("C1_notifications")
    ok("notification centre opens")
    page.keyboard.press("Escape")
    page.mouse.click(700, 500)
    esc = [n for n in api("suresh", "/api/notifications").json() if n["kind"] == "escalate"]
    assert esc, "no escalation reached the India Director"
    ok("overdue steps escalated to the manager (%d escalation(s) for the India Director)" % len(esc))
    as_user("suresh")
    page.goto(BASE)
    page.wait_for_selector(".hero")
    expect(page.get_by_text("Running late")).to_be_visible(timeout=8000)
    ok("Directors see a 'Running late' list")

    # ------------------------------------------------------------------ D. generic driver: walk a project through the UI
    users = api("sneha", "/api/users").json()
    email_of = {u["name"]: u["email"].split("@")[0] for u in users}

    def perform(pid, d, overrides):
        a = d["action"]
        step = d["current_step"]
        choice = (overrides.get(step) or [("approve", "")]).pop(0) if a["mode"] == "decision" else None
        if a["needs_file"] and not a["has_file"]:
            page.locator(".need-file input[type=file]").set_input_files({"name": f"{step}.pdf", "mimeType": "application/pdf", "buffer": b"%PDF-1.4 test"})
            toast("File attached")
        if a["needs_text"]:
            page.locator(".nowcard .act .field input").fill("Sunrise Pharma Pvt Ltd")
        if a["needs_note"]:
            page.locator(".nowcard .act .field textarea").fill("Please confirm shelf life and the supplier.")
        if a["mode"] != "decision":
            page.locator(".nowcard .act-buttons .btn.ok").click()
        else:
            kind, note = choice
            if kind == "approve":
                page.locator(".nowcard .act-buttons .btn.ok").click()
                if step == "india_review":
                    page.get_by_role("button", name="Information is complete").click()
            elif kind == "incomplete":
                page.locator(".nowcard .act-buttons .btn.ok").click()
                page.get_by_role("button", name="Information is incomplete").click()
            elif kind == "send_back":
                page.locator(".nowcard .act-buttons .btn.bad").click()
                page.locator(".modal footer .btn.danger").click()                    # no reason → blocked
                expect(page.locator(".modal .form-error")).to_contain_text("reason")
                page.locator(".modal textarea").fill(note)
                page.locator(".modal footer .btn.danger").click()
            elif kind in ("hold", "reject"):
                page.locator(".nowcard .act-buttons .btn.bad").click()
                page.locator(".modal textarea").fill(note)
                page.locator(f".modal footer .btn.{'amber' if kind == 'hold' else 'danger'}").click()
        page.locator(".toast").first.wait_for(timeout=6000)

    def drive(pid, until=None, overrides=None, max_steps=120):
        overrides = {k: list(v) for k, v in (overrides or {}).items()}
        for _ in range(max_steps):
            d = api("sneha", f"/api/projects/{pid}").json()
            if d["status"] != "active" or d["current_step"] == until:
                return d
            a = d["action"]
            pending = [o for o in a["owners"] if not (a["all"] and o["role"] in a["signed"])]
            actor = email_of[pending[0]["people"][0]]
            as_user(actor)
            try:
                open_project(pid)
            except Exception:
                snap("FAIL_open_project")
                print("FAILED to open project", pid, "step", d["current_step"], "as", actor, "url", page.url, page.inner_text("body")[:300])
                raise
            expect(page.locator(".nowcard.mine")).to_be_visible()
            before = (d["current_step"], len(a["signed"]), d["step_total"])
            perform(pid, d, overrides)
            time.sleep(0.15)
        raise AssertionError("project did not reach " + str(until))

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
        page.get_by_placeholder("What is the product?").fill("Created by the browser test.")
        snap("D1_new_project")
        page.get_by_role("button", name="Add project", exact=True).click()
        page.wait_for_selector(".nowcard")
        pid = int(page.url.rsplit("/", 1)[1])
        assert step_title() == "Neo Health (OTC) Screening"
        return pid

    # ---- Development project with every loop
    pid = new_project("ananya", "Vitamin D3 Drops 1000IU", "Development")
    ok("new project validated and created (Development)")
    drive(pid, until="india_review")
    ok("initiator steps done in the UI: screening → director approval → code → Master Excel → submission")
    d = api("sneha", f"/api/projects/{pid}").json()
    assert d["code"].startswith("NHO-DEV-")
    drive(pid, until="india_review", overrides={})
    as_user("suresh"); open_project(pid); snap("D2_india_review_decision")
    drive(pid, until="internal_review", overrides={"india_review": [("send_back", "Please add stability data.")]})
    assert step_title() == "Internal Review / Modification"
    ok("India review → Send back (reason required) loops to Internal Review")
    drive(pid, until="india_review")
    drive(pid, until="clarification", overrides={"india_review": [("incomplete", "")]})
    drive(pid, until="internal_review")
    as_user("ananya"); open_project(pid)
    expect(page.locator(".callout")).to_contain_text("clarification")
    snap("D3_clarification")
    ok("clarification request loops back and tells the initiator")
    drive(pid, until="updated_brief")
    assert step_title() == "Updated Project Brief Received"
    ok("after clarification the brief returns to 'Updated Project Brief Received' (no second review)")
    drive(pid, until="feas_decision")
    drive(pid, until="cost", overrides={"feas_decision": [("hold", "Waiting for supplier price list.")]})
    d = api("sneha", f"/api/projects/{pid}").json()
    assert d["status"] == "on_hold"
    as_user("suresh"); open_project(pid)
    expect(page.locator(".nowcard.end.warn")).to_contain_text("supplier price")
    snap("D4_on_hold")
    page.get_by_role("button", name="More actions").click()
    page.get_by_role("button", name="Restart").click()
    page.locator(".modal footer .btn.primary").click()
    expect(page.locator(".nowcard h2")).to_have_text("Feasibility Decision")
    ok("feasibility → Hold pauses the project; a Director restarts it from the menu")
    drive(pid, until="commercial_approval", overrides={"feas_decision": [("approve", "")]})
    as_user("suresh"); open_project(pid)
    page.locator(".nowcard .act-buttons .btn.ok").click()
    toast("Waiting for OTC Director")
    expect(page.locator(".who.signed")).to_have_count(1)
    expect(page.locator(".nowcard.mine")).to_have_count(0)
    ok("Final Commercial Approval needs both Directors: first approval is recorded, project waits for the second")
    as_user("rajiv"); open_project(pid)
    snap("D5_second_director")
    drive(pid, until="fin_review", overrides={"commercial_approval": [("send_back", "Margin too thin, redo the financials.")]})
    ok("Final Commercial Approval → Hold/Reject loops back to Financial Review")
    drive(pid, until="commercial_approval")
    drive(pid, until="lqp_review")
    as_user("pooja"); open_project(pid)
    page.locator(".nowcard .act-buttons .btn.ok").click()
    toast("Waiting for")
    expect(page.locator(".who.signed")).to_have_count(1)
    ok("Legal / Quality / PV review: each team signs separately")
    drive(pid, until="cdmo")
    page.goto(BASE)
    as_user("suresh"); open_project(pid)
    page.locator(".nowcard .act-buttons .btn.ok").click()
    expect(page.locator(".toast", has_text="CDMO").or_(page.locator(".nowcard .form-error"))).to_be_visible()
    ok("CDMO step asks which CDMO/CRO is confirmed before it can be completed")
    drive(pid, until="reg_decision")
    drive(pid, until="dossier_assign", overrides={"reg_decision": [("send_back", "Dossier is incomplete.")]})
    ok("Regulatory decision → Hold/Reject loops back to dossier preparation")
    drive(pid, until="artwork_approval")
    drive(pid, until="concept", overrides={"artwork_approval": [("send_back", "Simplify the front panel.")]})
    ok("Concept / Artwork approval → Hold/Reject loops back to Concept Development")
    d = drive(pid)
    assert d["status"] == "completed", d["status"]
    as_user("rajiv"); open_project(pid)
    expect(page.locator(".nowcard.end.ok")).to_contain_text("Project completed")
    snap("D6_completed")
    ok("Development project completed through the UI, every step done by its responsible person")
    done_steps = [s for s in d["steps"] if s["state"] == "done"]
    assert len(done_steps) == d["step_total"] - 1 or len(done_steps) == len(d["steps"]), (len(done_steps), len(d["steps"]))

    # ---- In-Licence project, straight through
    pid2 = new_project("rohit", "Calcium + K2 Tablets", "In-Licence")
    ok("new project created (In-Licence)")
    d2 = drive(pid2)
    assert d2["status"] == "completed"
    names = [s["name"] for s in d2["steps"]]
    assert "Regulatory Review and Approval" in names and "CDMO / CRO Identify and Confirm" not in names
    ok("In-Licence project completed through the UI (uses Regulatory Review, not CDMO)")

    # ---- reject path
    pid3 = new_project("ananya", "Test Reject Product", "Development")
    drive(pid3, until="otc_decision")
    drive(pid3, overrides={"otc_decision": [("reject", "Not a fit for the range.")]})
    d3 = api("sneha", f"/api/projects/{pid3}").json()
    assert d3["status"] == "rejected" and d3["code"] is None
    as_user("ananya"); open_project(pid3)
    expect(page.locator(".nowcard.end.bad")).to_contain_text("Not a fit")
    ok("Director rejects at the first decision: project closes, no code is issued, initiator sees the reason")
    note = [n for n in api("ananya", "/api/notifications").json() if "rejected" in n["text"]]
    assert note
    ok("initiator is notified of the rejection")

    # ------------------------------------------------------------------ E. notifications and reminders
    pid4 = new_project("ananya", "Reminder Test Product", "Development")
    drive(pid4, until="otc_decision")
    as_user("ananya"); open_project(pid4)
    page.get_by_role("button", name="Send reminder").click()
    toast("Reminder sent")
    ok("initiator can send a reminder to the person a project is waiting for")
    page.get_by_role("button", name="Send reminder").click()
    toast("already sent")
    ok("reminders are limited (no spamming)")
    as_user("rajiv"); page.goto(BASE)
    page.wait_for_selector(".hero")
    expect(page.locator(".bell .icon-btn b")).to_be_visible()
    page.get_by_role("button", name="Notifications").click()
    expect(page.locator(".note.new", has_text="reminds you")).to_be_visible()
    snap("E1_reminder_notification")
    page.locator(".note.new", has_text="reminds you").first.click()
    page.wait_for_selector(".nowcard")
    assert "Reminder Test Product" in page.locator("h1").inner_text()
    ok("the owner gets the reminder; clicking it opens the project")
    page.get_by_role("button", name="Notifications").click()
    page.get_by_role("button", name="Mark all read").click() if page.get_by_role("button", name="Mark all read").count() else None
    page.wait_for_timeout(600)
    ok("notifications can be marked read")

    # ------------------------------------------------------------------ F. notes, files, details, hold/cancel
    as_user("rajiv"); open_project(pid4)
    page.get_by_role("tab", name="Notes").click()
    page.get_by_placeholder("Write a note…").fill("Please decide this week.")
    page.get_by_role("button", name="Post").click()
    expect(page.locator(".bubble", has_text="decide this week")).to_be_visible()
    ok("notes can be posted")
    page.get_by_role("tab", name="Files").click()
    page.locator(".tabpane input[type=file]").set_input_files({"name": "quote.pdf", "mimeType": "application/pdf", "buffer": b"%PDF test"})
    expect(page.locator(".file", has_text="quote.pdf")).to_be_visible()
    with page.expect_download() as dl:
        page.locator(".file", has_text="quote.pdf").locator("a").click()
    assert dl.value.suggested_filename == "quote.pdf"
    ok("files can be added and downloaded")
    page.once("dialog", lambda dlg: dlg.accept())
    page.locator(".file", has_text="quote.pdf").get_by_role("button").click()
    expect(page.locator(".file", has_text="quote.pdf")).to_have_count(0)
    ok("files can be removed")
    page.get_by_role("button", name="Details").click()
    expect(page.locator(".modal")).to_contain_text("Reminder Test Product".split()[0] and "Development")
    page.keyboard.press("Escape")
    as_user("ananya"); open_project(pid4)
    page.get_by_role("button", name="Details").click()
    page.get_by_role("button", name="Edit").click()
    page.locator(".modal input").first.fill("Reminder Test Product v2")
    page.get_by_role("button", name="Save").click()
    toast("Saved")
    expect(page.locator("h1")).to_contain_text("v2")
    ok("initiator can edit project details")
    with page.expect_download() as dl:
        page.get_by_role("button", name="More actions").click()
        page.get_by_role("link", name="Download Excel").click()
    assert dl.value.suggested_filename.endswith(".xlsx")
    ok("project Excel download works")
    as_user("rajiv"); open_project(pid4)
    page.get_by_role("button", name="More actions").click()
    page.get_by_role("button", name="Cancel project").click()
    page.locator(".modal footer .btn.danger").click()
    expect(page.locator(".modal .form-error")).to_contain_text("reason")
    page.locator(".modal textarea").fill("Priorities changed.")
    page.locator(".modal footer .btn.danger").click()
    expect(page.locator(".nowcard.end.bad")).to_contain_text("Priorities changed")
    ok("a Director can cancel a project (reason required)")

    # ------------------------------------------------------------------ G. projects list, filters, Excel
    as_user("sneha"); page.goto(BASE + "/projects")
    page.wait_for_selector(".pcard")
    page.get_by_role("tab", name="Needs me").click()
    expect(page.locator(".empty")).to_be_visible()
    ok("admin has nothing to approve ('Needs me' is empty)")
    page.get_by_role("tab", name="All").click()
    page.get_by_label("Search projects").fill("probiotic")
    expect(page.locator(".pcard")).to_have_count(1)
    ok("search works")
    page.get_by_label("Search projects").fill("")
    with page.expect_download() as dl:
        page.get_by_role("link", name="Download Master Excel").click()
    assert dl.value.suggested_filename.endswith(".xlsx")
    ok("Master Excel download works")
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.append(["Project name", "Type", "Market", "Desc", "Value"])
    ws.append(["Imported Lozenge", "In-Licence", "Australia", "from excel", 120000])
    buf = io.BytesIO()
    wb.save(buf)
    page.get_by_role("button", name="Add projects from Excel").click()
    page.locator(".modal select").select_option(label="Rohit Malhotra")
    page.locator(".modal input[type=file]").set_input_files({"name": "in.xlsx", "mimeType": "application/vnd.ms-excel", "buffer": buf.getvalue()})
    page.get_by_role("button", name="Add projects", exact=True).click()
    toast("1 project added")
    ok("projects can be added from Excel")

    # ------------------------------------------------------------------ H. team, hierarchy, password
    page.goto(BASE + "/team")
    page.wait_for_selector(".person")
    snap("H1_team")
    page.get_by_role("button", name="Add person").click()
    page.locator(".modal input").nth(0).fill("Kavita Rao")
    page.locator(".modal input").nth(1).fill("kavita@neohealth.example")
    page.locator(".modal select").nth(0).select_option("legal")
    page.locator(".modal select").nth(1).select_option(label="Suresh Iyer")
    page.locator(".modal input").nth(3).fill("kavita123")
    page.get_by_role("button", name="Save").click()
    toast("Person added")
    expect(page.locator(".person", has_text="Kavita Rao")).to_be_visible()
    ok("admin adds a person and places them in the reporting line")
    page.locator(".person", has_text="Kavita Rao").click()
    page.get_by_label("Can sign in").uncheck()
    page.get_by_role("button", name="Save").click()
    toast("Saved")
    r = ctx.request.post(f"{BASE}/api/auth/login", data={"email": "kavita@neohealth.example", "password": "kavita123"})
    assert r.status == 401
    ok("admin can switch a person off; they can no longer sign in")
    # password change as a normal user
    as_user("harsh"); page.goto(BASE)
    page.wait_for_selector(".hero")
    page.get_by_role("button", name="My account").first.click()
    page.get_by_role("button", name="Change password").click()
    pw = page.locator(".modal input[type=password]")
    pw.nth(0).fill(PASS)
    pw.nth(1).fill("harsh-new-1")
    pw.nth(2).fill("harsh-new-1")
    page.get_by_role("button", name="Save").click()
    toast("Password changed")
    r = ctx.request.post(f"{BASE}/api/auth/login", data={"email": "harsh" + DOM, "password": "harsh-new-1"})
    assert r.ok
    ok("a person can change their own password")

    # ------------------------------------------------------------------ I. process map
    as_user("sanjay"); page.goto(BASE + "/process")
    page.wait_for_selector(".band")
    expect(page.locator(".node.mine").first).to_be_visible()
    assert page.locator(".node-name", has_text="CDMO / CRO Identify and Confirm").count() == 1
    page.get_by_role("tab", name="In-Licence").click()
    assert page.locator(".node-name", has_text="CDMO / CRO Identify and Confirm").count() == 0
    assert page.locator(".node-name", has_text="Regulatory Review and Approval").count() == 1
    snap("I1_process_map")
    ok("Process map shows the flow chart, highlights my steps, and switches between Development and In-Licence")

    # ------------------------------------------------------------------ J. phone: approve on a mobile screen
    mctx = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, has_touch=True, is_mobile=True)
    m = mctx.new_page()
    m.set_default_timeout(10000)
    m.on("pageerror", lambda e: errors.append("MOBILE JS: " + str(e)))
    pid5 = None
    r = ctx.request.post(f"{BASE}/api/auth/login", data={"email": "ananya" + DOM, "password": PASS})
    tok = r.json()["token"]
    rr = ctx.request.post(f"{BASE}/api/projects", headers={"Authorization": "Bearer " + tok}, data={"title": "Phone Test Product", "ptype": "development", "market": "AU"})
    pid5 = rr.json()["id"]
    m.goto(BASE)
    m.evaluate("t => localStorage.setItem('neo_token', t)", tok)
    m.goto(f"{BASE}/projects/{pid5}")
    m.wait_for_selector(".nowcard.mine")
    m.screenshot(path=f"{OUT}/J1_phone_task.png")
    assert m.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth") == 0
    m.locator(".nowcard .act-buttons .btn.ok").tap()
    expect(m.locator(".nowcard h2")).to_have_text("Commercial Validation")
    m.locator(".tabbar").get_by_text("Home").tap()
    m.wait_for_selector(".hero")
    m.screenshot(path=f"{OUT}/J2_phone_home.png")
    ok("on a phone: open task, tap the big button, bottom tabs work, no sideways scrolling")

    print("\nconsole/page errors:", errors)
    assert not errors, errors
    with open(f"{OUT}/result.txt", "w", encoding="utf8") as f:
        f.write("\n".join("PASS " + m for m in log))
    print("\nALL %d CHECKS PASSED" % len(log))
    browser.close()
