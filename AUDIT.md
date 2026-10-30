# AUDIT – Neo Project Flow (version 2)

Maintained as required by `RULEBOOK.md`. Last updated: 2026-10-30.

## 1. Feedback on version 1 and what was done

| Client feedback | What was wrong | Fix in version 2 | Verified by |
|---|---|---|---|
| "Very confusing and cluttered" | Too many panels and sentences per screen | One idea per screen. Project page = journey line → **one big "Your turn" card** → three tabs (Flow / Files / Notes). Details moved into a pop-up. Almost all explanatory text removed | Screenshots, browser journey |
| "No visual understanding of the actual flow" | Flow was a plain checklist | **Live flow diagram** of the client's chart (`FlowMap`): 10 coloured phases, steps joined by a line, done / current / waiting states, decision branches, loop-back arrows, "who did it and when". Same diagram on the **Process map** page for both project types | UI journey I |
| "5-year-old can use it" | Many buttons, long labels | A person only ever sees **green Approve** and **red Send back** (or one green *Done*). India review asks one plain question ("Is the information complete?"). Reasons are asked only when needed | UI journey D |
| "Person should only see what he works on" | Everybody saw everything | **Role-based visibility** (section 3). Staff see only tasks that need them and projects they work or worked on; Directors/Office Admin see all. Applies to lists, project pages, files, downloads, Excel export, notifications, dashboard | 10 backend + 5 UI checks |
| "Proper approval, hierarchy, flow, notifications" | No reporting line, basic alerts | **Reporting lines + org chart**, step deadlines, overdue **reminders**, **escalation** to the manager, "send reminder" button, notification centre with kinds, e-mail copy (SMTP) | 12 backend + 8 UI checks |
| "Indian names in demo data" | Mixed names | All 17 people have Indian names; 15 demo projects (e.g. Ashwagandha capsules) | Seed |
| "Demo system, I want fully functional and fully tested" | Few tests, no real lifecycle test | 38 backend tests + 47 browser checks that **complete whole projects by clicking** as each responsible person, including every loop, both project types, reject, hold, cancel, phone | Section 8 |
| "Professional, production-grade, visually powerful" | Plain styling | New design system: brand colours from the Neo logo, phase icons/colours, large type, soft depth, animated "you are here", responsive to 320 px, accessibility labels | Screenshots |

## 2. Research behind the redesign

See `docs/WORKFLOW_RESEARCH.md` (company, process, industry practice) and section 9 of that file (UX research). Key points used:
* Task inbox shows the *current* task and next action, hides the rest (progressive disclosure).
* Role-based views are a UX feature, not just security – they cut noise.
* Progress display: current step must stand out from done/upcoming; use icon + label, not colour alone; overdue shown clearly.
* Many approvals happen on phones → big tap targets (56 px primary buttons), bottom navigation.

## 3. Who sees what

| Person | Sees |
|---|---|
| **Director – Neo Health OTC / Director – Neo India Lifeline** | All projects, stage overview ("Where projects are"), "Running late" list, Team/org chart. Can hold, restart, cancel any project |
| **Office Admin** | All projects (read), people management, correct a wrong step. **Cannot approve** anything |
| **Project Initiator** | Own projects (any stage) |
| **Every other role** (CFT, Legal, Quality, PV, Regulatory Head/Team, Artwork, Commercial, CMO) | Only projects that are **waiting on their role** now, or where they already **acted/commented**. A team that has not yet been reached sees nothing and cannot open the project even with a link (shown as "not found") |

Notifications, files, downloads, Excel export, dashboard and project pages all follow the same rule (`engine.can_see`). Staff do not get the Team page (the menu item is hidden and `/team` redirects home; `/api/users` is refused).

## 4. Hierarchy, deadlines, escalation

```
Director – Neo Health OTC ── Initiators, Commercial, Artwork
Director – Neo India Lifeline ── CFT, Legal, Quality, PV, Regulatory Head ── Regulatory Team
CMO (external manufacturer)       Office Admin
```
Reporting lines are editable by the Office Admin (loops are refused).

Every step has a deadline (SLA): 3 days for an action, 2 days for a decision, longer for heavy steps (e.g. manufacturing 21 days, dossier 14) – `workflow.SLA_OVERRIDES`. Shown as "2 days left / Due today / 1 day late".
1. Past due → the people who must act get an **"Overdue"** reminder.
2. Still waiting one more full period → their **manager** (or both Directors if none) gets an **"Escalation"**.
3. Anyone involved can press **Send reminder** (max once per 12 hours).
4. Checks run at start-up and every hour, and reset when the step moves. Held projects are not chased.

## 5. Notifications

In-app bell with unread count, pop-up for new items, "Mark all read", click opens the project, browser tab shows `(3)`. Kinds: your turn, approved, sent back, on hold, rejected, completed, new note, reminder, escalation.
E-mail copy: set `NEO_SMTP_HOST` (+ `NEO_SMTP_PORT/USER/PASSWORD/FROM/TLS`, `NEO_BASE_URL`); a background job sends queued mails and marks them sent/failed. **Verified against a simulated SMTP server only** (no real mailbox was available) – please test once with the company's mail account.

## 6. Flow chart → system (unchanged rules, simpler screens)

Page numbers are the Word file's. ✔ = covered by backend test and by the browser journey.

| Chart box | System |
|---|---|
| Opportunity Identification, Screening, Commercial Validation (Initiator) | Created with the project; initiator completes the next two | ✔ |
| Approval Decision (Initiator; consult OTC Director) | "Send to Director" step; consult shown | ✔ |
| Approved / **Reject** (OTC Director) | Approve → code step; **Reject needs a reason and closes** | ✔ |
| Project Code Generated | Initiator presses *Done*; code `NHO-DEV/INL-year-nnn` issued only now | ✔ |
| Drafts Brief (**Master Excel**) | File must be attached; Master Excel export and Excel import exist | ✔ |
| Internal Review / Modification; Final Internal Approval; Submission | Initiator and/or CFT | ✔ |
| Neo India Lifeline Review → Approved (Complete / Incomplete) / Reject-send for modification | Approve → "Is the information complete?" → complete / incomplete; Send back needs reason → **loops to Internal Review** | ✔ |
| Incomplete → Clarification Request → back to Internal Review → **Updated Project Brief Received** | Question required; after resubmission skips a second India review | ✔ |
| Feasibility Review Completed → Brief Approved → CFT Review (India Director) | In order | ✔ |
| FMEA → Feasibility Report Preparation → Submission (CFT) | Report file required | ✔ |
| Approved / **Hold-Reject** (India Director) | Approve, or **Hold / Reject** (reason; Hold can be restarted) | ✔ |
| Cost Finalization → Financial Review (India Director **and** Initiator) → Risk Adjustment | Financial Review: both must sign | ✔ |
| Final Commercial Approval (both Directors) | **Both must approve**; shows who signed; Hold/Reject **loops to Financial Review** | ✔ |
| Agreement Preparation → Functional Review (both Directors) → Legal/Quality/PV Review → Approved / Hold-Reject | Draft agreement file required; review needs **all three teams** | ✔ |
| Development → CDMO/CRO identify & confirm; In-Licence → Regulatory Review | Chosen by project type; CDMO name captured | ✔ |
| Handover → Dossier assignment → Approved / Hold-Reject (Regulatory Head) | Hold/Reject **loops to dossier preparation** | ✔ |
| Concept Development → Artwork → Concept/Artwork Approval (OTC Director) | Hold/Reject **loops to Concept Development** | ✔ |
| Manufacturer Technical Review … Regulatory Submission … Commercial Readiness | CMO / Regulatory Head / India Director | ✔ |
| Print Proof → Technical Review → Manufacturer Approval → Final Printing → Shade Card | Artwork + Commercial / Reg. Head / CMO | ✔ |
| Commercial Manufacturing → Pre-shipment Sample → Sample Review (Quality coordinates) → Dispatch → **Project Completion** | Completion by OTC Director closes the project | ✔ |

Changed from v1 to follow the chart more closely: boxes with a **Hold/Reject loop arrow** now offer exactly *Approve* or *Send back to <that step>* (no extra Hold/Reject buttons); boxes without an arrow offer *Hold* and *Reject*.

## 7. Assumptions to confirm with the client

| # | Document is silent / unclear | System does |
|---|---|---|
| A1 | Typos "Reediness", "Quaity" | Shown as "Readiness", "Quality" |
| A2 | "Cross-Functional Review" owner text is cut off | Director – Neo India Lifeline |
| A3 | "Neo Health (OTC) Pty Ltd" is a company, not a role, for Concept Development | Initiator **or** Commercial Team |
| A4 | "Commercial team" vs "Project Commercial Team" | One role |
| A5 | Where the Regulatory Hold/Reject arrow lands | Dossier preparation |
| A6 | "Approval Decision" (Initiator) and "Approved/Reject" (Director) | Two steps |
| A7 | Co-ordinator "Quality Team" | Quality may complete Sample Review |
| A8 | Which steps need a file | Master Excel brief, Feasibility Report, Draft agreement only |
| A9 | "X and Y" responsibility | All must sign only for separate-party approvals/reviews (both Directors, Financial Review, Legal/Quality/PV review) |
| A10 | Deadlines per step | Not in the chart; defaults in section 4 – please confirm with the client |
| A11 | Reporting lines | Proposed in section 4 – please confirm |
| A12 | Office Admin, Director hold/restart/cancel, "correct the step" | Added for practical use; all logged in history |
| A13 | Currency | Est. yearly sales shown as A$ (label only) |

## 8. Test log

| Suite | Result |
|---|---|
| `backend/tests/test_flow.py` (20): whole flow in document order for both project types, each loop, dual-Director approval, all-three-teams review, hold/restart/cancel, admin correction, mandatory notes/files/CDMO, Excel in/out | **pass** |
| `backend/tests/test_access.py` (18): visibility for every list/file/download/export, project appears when it reaches a team and stays, private notifications, directory limited to Directors/Admin, reporting-line loop refused, overdue → reminder → escalation (no spam, reset on move), nudge limit, decision options per chart box, e-mail send + failure handling (simulated SMTP), password change, login throttle, deactivated account, blocked/empty files, **old-format database is backed up and replaced** | **pass** |
| **Total backend** | **38 passed** |
| `e2e/ui_journey.py` – 47 browser checks on a fresh database, driving the real screens as each responsible person: sign-in/out; role-based home/menu/direct links; escalation visible; **Development project completed by clicking through all steps** incl. India send-back, clarification loop, feasibility hold → Director restart, two-Director approval, commercial loop, Legal/Quality/PV sign-offs, CDMO question, regulatory loop, artwork loop; **In-Licence project completed**; reject path; reminders and notifications; notes, files (upload/download/remove), details edit, project Excel, cancel; board search, Master Excel, Excel import; team add/edit/switch off; password change; process map; **phone** (390 px) approve flow | **47 passed, no JavaScript errors** |
| Responsive sweep (Home, Projects, project page, Process map, Team) at 1440 / 820 / 390 / 320 px | No sideways scrolling, no page errors |
| Visual review of screenshots in `e2e/screenshots/` | Done; found and fixed: card/marker style clash, mobile label clipping, login logo background, team card wrapping |

## 9. Bugs found while testing (all fixed)

| # | Bug | Fix |
|---|---|---|
| F1 | Blank page on navigation in Edge/Chrome (effect returned `window.scrollTo()` Promise) | Fixed |
| F2 | CSS class `now` clashed between the big card, journey and flow dots (twice) | Card renamed `nowcard` |
| F3 | Events not saved (SQLAlchemy 2 cascade) | Fixed |
| F4 | Login throttle state leaked between tests | Reset in test fixture |
| F5 | Old v1 databases would crash the new version | Auto backup + fresh start |
| F6 | Mobile: current phase label clipped; step title wrapped badly | Fixed |

## 10. Known limits

* E-mail: needs SMTP settings; verified with a simulated server only (section 5).
* Sign-in is email + password (12 h session, 8 wrong tries → 10 min lock). No single sign-on and no "forgot password" mail; the Office Admin resets passwords.
* Demo sign-in list on the login page: turn off with `NEO_DEMO_LOGIN=0`; start empty with `NEO_AUTOSEED=0`.
* Files are kept on the server disk (20 MB each; executables refused; no virus scan).
* SQLite suits a small team; not load-tested beyond a handful of simultaneous users.
* Browser tests ran in Microsoft Edge; Safari/Firefox not tested.
