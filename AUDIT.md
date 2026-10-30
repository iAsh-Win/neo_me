# AUDIT – Neo Project Flow (version 3)

Maintained as required by `RULEBOOK.md`. Last updated: 2026-10-30.

## 1. Feedback on version 2 and what was done

| # | Client feedback | What was done | Where to see it | Verified by |
|---|---|---|---|---|
| 1 | "No proper way to send back from the relevant entity" | **Send back** on every step. The sender picks *which earlier step* (a list, nearest first) and sees **exactly who will receive it** (names + role). A reason is required and documents can be attached. The receiver gets a red "Sent back to you" card showing **who sent it, why, and where it returns**. After the fix it comes **straight back to the sender**. The chart's own Hold/Reject loops are still there, marked "As in the flow chart" | Project page → red **Send back** button | `test_send_back_*` (3), browser checks "send back…" (3) |
| 2 | "No proper docs + doc links, both, everywhere a file is submitted at the final stage" | Every step that needs paperwork has **named document slots** (e.g. *Supplier agreement*, *Quality agreement*, *PV agreement*, *Dossier (CTD)*, *GMP evidence*, *Print proof*, *Shade card*, *Batch record / COA*, *Dispatch documents*). Each slot takes **several files at once and/or links** (SharePoint, Drive…). A step cannot be finished until each required slot has at least one file **or** link. Same buttons in the Send-back dialog and the Files tab | Your-turn card → document slots | `test_files_and_links_*`, `test_each_required_document_type_*`, browser |
| 3 | "Text notes are there everywhere – research, notes are never enough" | Researched (section 2). Steps now ask for **structured details** (cost per unit, MOQ, batch number, submission number, dates…), **ticks** (e.g. "Claims and mandatory statements checked") and **documents**, not free text. Details are saved in the history and some update the project (sales estimate, target date, CDMO). Notes remain, but are optional ("message for the next person") | Your-turn card | `test_details_and_ticks_are_checked`, `test_the_button_says_who_gets_it_next…` |
| 4 | "Remove the download Excel things" | All Excel export/import buttons and endpoints are **removed**. (The chart's "Master Excel" is still a document you attach, file or link.) | – | `test_excel_downloads_are_gone`, browser |
| 5 | "No proper status, and notes aren't shown" | Every project has a **status strip**: health (On track / At risk / Late / On hold / Completed / Stopped), progress %, **who it is with**, next date, open tasks / requests and the **latest note**. Notes appear in the History tab and the latest one is pinned in the strip | Top of every project | browser, `test_project_health_*` |
| 6 | "Phases are too wide – align with the Word file" | The chart has **no named phases**. Seven stages now follow its own structure (section 3), down from ten, in a compact line | Journey line, Process map | `test_flow_definition_matches_document` |
| 7 | "Proper history for each thing" | **History tab**: every action with who, role, time, **where it went** ("Goes to …"), the details entered, ticks, files and links, notes, send-backs, task and time-request events. Each step in the Flow also opens its own history. Filter: All / Steps / Notes / Files / Tasks / Requests | History tab, Flow node → "History" | `test_every_kind_of_event_is_in_the_history`, browser |
| 8 | "No task-like features" | **Tasks**: anyone working on a project (or a Director/initiator) gives a task to a person, with due date, optional link to a step and an optional **"blocks this step until done"**. The assignee sees it on Home and gets a notification, can finish it or ask for more time | Project → Tasks tab, Home | `test_tasks_*` (3), browser |
| 9 | "Identify other things for pharma project management" | Section 2: documents per stage, GMP evidence, dossier/submission numbers, batch records, tasks, checklists, time requests, parallel tracks, health status, history | – | – |
| 10 | "Which phases work in parallel – ensure the same" | Section 4. **Fast track**: a Director can switch on side-by-side running of independent tracks; the project waits until all finish. Off by default (chart order) | Project menu → Fast track | `test_fast_track_*` (4), browser |
| 11 | "Due date change request by the assignee, like the flow" | Every step and task has a due date. The person it is waiting for can **Ask for more time** (new date + reason). The request goes to **whoever gave the date**; the dialog shows who. They Approve or Decline (reason needed). The requester is notified. The date moves only on approval. Pending requests are reminded after 2 days. Directors/the giver can also change a date directly | Your-turn card ⋯ → Ask for more time | `test_time_request_*`, browser |
| 12 | "For all send features show whom it goes to, and the receiver must know who sent it" | Buttons show **"Next: <step> · <people>"**; send-back, time request and task dialogs show **"This goes to <person>"**; every received item shows **"From <person> (role)"** with their message; notifications say "from X (role)"; history records both | everywhere | tests above |
| 13 | "Proper hierarchy and flow, simple yet professional" | Reporting lines, deadlines, reminders and escalation (v2) plus requests to the right approver. Screens kept to one idea each | Team (org chart) | v2 tests + new |

## 2. Research

Detailed notes and links: `docs/WORKFLOW_RESEARCH.md` (sections 1-6).

| Question | Finding | Used for |
|---|---|---|
| What does a pharma stage need beyond notes? | Stage-gate / tech-transfer practice: each gate has **discrete deliverables** that become a **checklist** that drives the schedule ([ISPE](https://www.ispeboston.org/download/educational_presentations/2010/2010-01-26-Scale-Up-and-Tech-Transfer-JSocolow.pdf), [PDA TR65](https://www.pda.org/bookstore/product-detail/6680-tr-65-revised-technology-transfer)) | Required documents, details and ticks per step |
| TGA / OTC evidence | Valid **GMP evidence for each manufacturer**, application dossier in **CTD** format (Modules 1 & 3 for N3), online application via TGA Business Services ([TGA](https://www.tga.gov.au/sites/default/files/otc-new-medicines-registration-process.pdf)) | *GMP evidence*, *Dossier (CTD)*, *Submission number + receipt* |
| Artwork | A known **time-to-market bottleneck**; "right first time" ([Freyr](https://www.freyrsolutions.com/blog/crafting-high-quality-regulatory-artwork-strategies-for-achieving-right-first-time-capabilities), [ManageArtworks](https://manageartworks.com/blog-post/diving-into-the-intricacies-of-pharma-artwork-management)) | Artwork starts alongside the dossier under Fast track |
| Extension requests | Ask early, give a **reason and a new date**, route to a **named approver**, notify the decision, remind approvers who sit on requests ([ZenQMS](https://support.zenqms.com/hc/en-us/articles/360024189934-Requesting-a-Due-Date-Extension-for-an-Issue-Record-Stage-Task), [SSW](https://www.ssw.com.au/rules-beta/do-you-timebox-approval-requests)) | Time-request flow |
| Gaps | No public source found for parallel-activity practice in OTC development, or for escalation tiers. These are design decisions (section 4) to be confirmed with the client | – |

## 3. Stages: aligned with the Word file

The Word chart is one long flow with **no stage names**; it changes owner company at set points and splits only after the agreement. Version 2's ten invented phases were too many. The seven stages below follow the chart's own breaks (who is responsible and the page structure):

| # | Stage | Chart boxes it holds |
|---|---|---|
| 1 | Opportunity | Opportunity Identification → Screening → Commercial Validation → Approval Decision → Director Approved/Reject → Project Code |
| 2 | Brief | Drafts Brief (Master Excel) → Internal Review → Final Internal Approval → Submission to Neo India |
| 3 | India Review | Neo India Review (complete / incomplete / reject) → Clarification → Updated Brief Received |
| 4 | Feasibility & Cost | Final Feasibility Review → Brief Approved → CFT Review → FMEA → Report prep/submission → Approved/Hold-Reject → Cost Finalization → Financial Review → Risk Adjustment → Final Commercial Approval |
| 5 | Agreement | Agreement Preparation → Functional Review → Legal/Quality/PV Review → Approved/Hold-Reject |
| 6 | Regulatory & Artwork | CDMO/CRO (Development) or Regulatory Review (In-Licence) → Handover → Dossier → Approved/Hold-Reject · Concept → Artwork → Concept/Artwork Approval |
| 7 | Print & Launch | Manufacturer Technical Review → RA Reviewer → Regulatory Submission → Commercial Readiness → Print Proof → Technical Review → Manufacturer Approval → Final Printing → Shade Card → Manufacturing → Pre-shipment Sample → Sample Review → Dispatch → Project Completion |

All 48 steps, their owners, decisions, loops and the Development / In-Licence split are unchanged from the chart (`test_full_development_flow_in_document_order` compares the completed order with the document).

## 4. Parallel work

| Candidate | In the chart | Why it can run side by side | Join |
|---|---|---|---|
| **Regulatory dossier ‖ Concept & artwork** (after Regulatory Review / CDMO) | one after the other | Different teams, different outputs; each has its own Hold/Reject loop in the chart. Artwork is a known bottleneck | Both approved before Manufacturer Technical Review |
| **Regulatory submission ‖ Commercial readiness ‖ Print approval** (after Manufacturer Technical Review) | one after the other | Independent teams and outputs | All three before Commercial Manufacturing |
| Considered, **not** parallel | – | Agreement before CDMO/Regulatory (the chart makes the agreement a prerequisite); cost after feasibility approval | – |

Rules: **off by default**, so the chart order is what the client signed off. A Director switches **Fast track** on per project. It applies to blocks that have not started yet. Each track keeps its own loops. A send-back inside a track stays inside that track. The project moves on only when every track is finished. Sequential mode is shown in the Flow as one list with track tags; Fast track shows the tracks as columns.

## 5. Who sees what, hierarchy, notifications (unchanged from v2, extended)

* Staff see only projects waiting on their role or ones they worked on **or where they hold a task or a request**; Directors and the Office Admin see all.
* Hierarchy and escalation: overdue → owner reminded → manager told. Time requests go to the person who gave the date, else the manager, else a Director.
* Notifications: your turn (with **from whom**), sent back, on hold, rejected, completed, notes, reminders, escalations, **time requests and answers**, **new tasks**. E-mail copy via SMTP (verified with a simulated server only).

## 6. Assumptions to confirm with the client

| # | Document silent / unclear | System does |
|---|---|---|
| A1 | Typos "Reediness", "Quaity" | "Readiness", "Quality" |
| A2 | "Cross-Functional Review" owner cut off | Director – Neo India Lifeline |
| A3 | Concept Development owner "Neo Health (OTC)" | Initiator **or** Commercial Team |
| A4 | "Commercial team" vs "Project Commercial Team" | One role |
| A5 | Where the Regulatory Hold/Reject arrow lands | Dossier preparation |
| A6 | Approval Decision (Initiator) vs Approved/Reject (Director) | Two steps |
| A7 | Quality as co-ordinator | Quality may complete Sample Review |
| A8 | **Which documents each step needs** (not in the chart apart from "Master Excel") | Proposed from the research in section 2 – **please review the list** (`Process map` shows it under each step with ★ = required) |
| A9 | Stage names | Section 3 |
| A10 | Deadlines per step; reporting lines | Proposed defaults |
| A11 | Parallel tracks | Section 4; off by default |
| A12 | Generic send-back to any earlier done step | Added (chart only shows five loops); the chart's loops stay the default where they exist |
| A13 | Hold / Reject without a loop arrow | Hold (restartable) and Reject (closes) |
| A14 | Office Admin, Director hold/restart/cancel, Admin "correct the step" | Added for practical use, all logged |
| A15 | E-mail | In-app always; e-mail needs SMTP settings |

## 7. Test log

| Suite | Result |
|---|---|
| `backend/tests/test_flow.py` (18): whole flow in document order for both project types **with documents, details and ticks required**; each chart loop; dual-Director approval; Legal/Quality/PV each with own tick; hold/restart/cancel; Admin correction; permissions; Excel endpoints gone | pass |
| `backend/tests/test_features.py` (22): send back (targets, recipients, receiver card, return-to-sender, documents, beyond the chart loop); Fast track (director only, sequential without it, side by side and join, track-limited send-back, mode fixed at start); time requests (routed to the giver, reason, one at a time, decline/approve, notifications, history, first-step → manager, direct change); tasks (visibility, blocking, extension, cancel, overdue); documents (files + links, several files, each required type, bad link, removal); details and ticks validation; next-step preview; history; health | pass |
| `backend/tests/test_access.py` (18): visibility, hierarchy, reminders/escalation, nudge, dashboard types, decision options, e-mail (simulated SMTP), security, old-database backup | pass |
| **Total backend** | **58 passed** |
| `e2e/ui_journey.py` – **34 browser checks** on a fresh database, driving the real screens as each responsible person. Includes a **Development project completed by clicking through every step** with files, links, details and ticks; India send-back; clarification loop; **send back to a chosen step**; hold/restart; two-Director approval; Legal/Quality/PV; **Fast track with two then three tracks side by side**; a CMO send-back inside a track; an **In-Licence project completed**; reject; **time requests (ask, decline, ask, approve)**; **tasks**; **several files + link**; history; status strip; Process map; admin; password; phone | **34 passed, no JavaScript errors** |
| Responsive (Home, Projects, project page, Process map, Team at 1440 / 820 / 390 / 320 px) | no sideways scrolling |

## 8. Bugs found while testing (fixed)

| Bug | Fix |
|---|---|
| Any failed request while loading signed the user out (transient server errors looked like "logged out") | Only an invalid session (401) signs out; other errors show a retry |
| Database lock risk under simultaneous use | 30 s wait; reminder job not repeated at start-up |
| Earlier: CSS class clashes, blank page on navigation in Edge, mobile label clipping | fixed in v2 |
| Group of people shown as "2P" avatar; reminder button said "Dr."; hand-over banner shown when you handed it to yourself; on phones the summary pushed the task down | fixed |

## 9. Known limits

* E-mail verified with a simulated server only. Sign-in is email + password (no SSO, no reset mail). Files on server disk (20 MB each, executables refused, no virus scan). SQLite suits a small team. Browser tests ran in Edge only.
* Send-back inside a Fast-track track is limited to that track; the Office Admin can correct anything else with "Correct the step".
* An older database (from version 1 or 2) is backed up as `neo.old-<date>.db` and the app starts fresh.

---

## Round 4 (v4) – feedback and what was done

| # | Feedback | Done |
|---|---|---|
| 1 | The receiver of a request cannot see what the sender sent (documents, details, ticks) | Every step card opens with a **"sent to you"** panel: who, message, details, ticked checks, documents (send-backs too). Stored on the step (`handover`), so it is always shown in full. |
| 2 | Documents and links should be one thing, with a file name; existing documents could not be chosen | One **Add document** dialog: name + file(s) and/or link, or **Already in this project** (reuse without re-upload). A document can be a file, a link, or both. |
| 3 | Files should manage all and important documents | Files tab: search, **key documents** at the top (star; required-slot documents count automatically), grouped by step/task, "also used in", remove. |
| 4 | Flow was automatic; allow selection | Sender picks **who** (one person of the team, or anyone) for the next step; the chosen person alone can act and is notified. The sender, the person it is with, a Director or the Admin can change it (**Change who**). |
| 5 | Ask for a date when sending to the next person | Hand-over panel (and send-back dialog) has a **Due** date, default = the step's normal time, cannot be in the past. |
| 6 | Tasks can have documents | Same dialog on tasks (while giving the task and afterwards, by giver and receiver). |
| 7 | Cluttered; people should see only what they need | Focus view for team members (their steps, their documents, tasks and requests; other steps stay on the map without content). **Owner (initiator), Directors and Admin see everything.** |
| 8 | A reviewer must not have to read the whole history | **Summary** tab (needs attention, 7 stages with who/when/how long, key numbers, key documents, latest key moments). History starts on **Key moments**; "Everything" shows all. |
| 9 | Test the reverse flow | Found and fixed a real bug: after a two-level send-back the fixed step lost its way home to the first sender (now tracked per step: `return_to` + `return_user_id`). 23 new tests: chains, skipping steps, return to the same person, parallel track, chart loop vs free send-back, repeat send-back. |
| 10 | Which phases can run in parallel and how | Unchanged analysis, now explained in the Fast-track dialog and the Process map: (1) Regulatory dossier ‖ Concept & artwork, (2) Regulatory submission ‖ Commercial readiness ‖ Print approval. Director switches it on; all tracks must finish before the next step; send-back stays inside its own track. |

Also fixed: removing a document left it in the list until reload (stale collection).

Tests: 81 backend (flow 18, features 22, access 18, round 4: 23), 41 browser checks. Screens: `e2e/screenshots/L1–L3`.

New assumption **A16**: choosing a person is only offered where exactly one team works on the step (joint steps with several teams stay "everyone in those teams").

### Round 4.1
- Joint step **Agreement Preparation** is now signed by Legal, Quality and PV, each adding only its own agreement (slots are owned by a team; other teams get a 403). All three reach the next step.
- Redesigned: "sent to you" panel, hand-over card (person + date), document chips/rows, number/date inputs. Typography is now **Montserrat**.
- Scope rule widened: Directors, Admin, the owner **and managers of anyone working on the project** see everything (escalations reach managers, so they can open the project). Test `test_managers_of_the_people_working_on_a_project_see_all_of_it`.
- Tests: 82 backend, 42 browser checks.
