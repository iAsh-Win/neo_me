# Workflow research – how Neo runs a project today

Sources: the client's flow chart **AD001-F01-00 "Project Management Flow Chart" (Annexure-I, 7 pages)**, read page by page
(text and arrows), plus public information on the two companies and on industry practice for OTC product development.
Where public sources said nothing, this file says so instead of guessing.

## 1. Who the company is

| | |
|---|---|
| **Neo Health (OTC) Pty Ltd** | Australian sponsor of over-the-counter medicines (Pennant Hills, NSW). Supplies TGA-registered products to pharmacy chains and retailers. Appears as a sponsor on the TGA register. [craft.co](https://craft.co/neo-health-otc), [TGA sponsor list](https://tga.gov.au/resources/sponsor/neo-health-otc-pty-ltd?page=16) |
| **Neo India Lifeline Pvt Ltd** | The India-side partner named in the flow chart (logo in the document header). No public page confirming its corporate link was found; the flow chart itself is the only source, and it shows it as the technical/commercial review and approval body. |
| **CMO / CDMO / CRO** | External manufacturer or research organisation. The chart lists them as a role that gives *Manufacturer Technical Review* and *Manufacturer Approval*. |

**Their current way of working** (from the brief): Excel files ("Master Excel" is named in the chart itself), e-mail and other
messages. The chart therefore is the *only* formal process. The system keeps Excel in and out (Master Excel export,
project summary export, bulk-add from Excel) so people do not have to give it up.

## 2. The process, in plain words

Two organisations take turns. **Neo Health (OTC)** finds and screens the idea, **Neo India Lifeline** reviews, costs and
approves it, then Regulatory, Artwork and the manufacturer carry it to dispatch.

| # | Phase | What happens | Decision points |
|---|---|---|---|
| 1 | Idea & Screening | Opportunity → screening → commercial validation → approval decision | OTC Director: Approve / Reject |
| 2 | Project Brief | Project code generated → draft brief (Master Excel) → internal review → final internal approval → submit to Neo India | – |
| 3 | India Review | Neo India reviews the brief | Approve (complete) / Approve (incomplete → clarification) / Reject & send back |
| 4 | Feasibility | Feasibility review, brief approved, cross-functional review, **FMEA risk analysis**, feasibility report | India Director: Approve / Hold / Reject |
| 5 | Cost & Approval | Cost finalization, financial review, risk adjustment, **final commercial approval by both Directors** | Both Directors: Approve / Hold-Reject (loops back to Financial Review) |
| 6 | Agreement | Agreement prepared → Directors' functional review → Legal / Quality / PV review | India Director: Approve / Hold / Reject |
| 7 | Regulatory | **Development**: identify & confirm CDMO/CRO. **In-Licence**: regulatory review. Then handover and dossier preparation | Regulatory Head: Approve / Hold-Reject (loops back to dossier) |
| 8 | Concept & Artwork | Concept development → artwork design | OTC Director: Approve / Hold-Reject (loops back to concept) |
| 9 | Manufacturer & Print | Manufacturer technical approval, RA reviewer, regulatory submission, commercial readiness, print proof, technical review, manufacturer approval, final printing approval, shade card | – |
| 10 | Manufacture & Dispatch | Commercial manufacturing → pre-shipment sample → sample review (Quality coordinates) → commercial dispatch → **Project Completion** | – |

### Three kinds of arrows in the chart (and how the system treats them)

1. **Straight arrow** – next step, done by the named team.
2. **Approved / Reject / Hold boxes** – a decision step. *Reject* on the first decision closes the idea; *Hold/Reject* with a
   curved arrow means "send back and redo" (5 such loops: India review → Internal Review, clarification → Internal Review,
   Final Commercial Approval → Financial Review, Regulatory → dossier preparation, Concept/Artwork → Concept Development).
3. **Branch** – after the agreement is approved the chart splits into *Development* and *In-Licence* paths that merge again at
   "Handover to the Regulatory".

## 3. How this matches common industry practice

| Neo's step | Industry practice | Source |
|---|---|---|
| Gated approvals from concept to launch (Directors approve at each gate) | Stage-Gate / New Product Introduction: each phase ends with a sign-off gate before the next phase is funded | [PCI NPI deck](https://pci.com/wp-content/uploads/2024/04/New-Product-Introduction.pdf), [Drug Development & Delivery](https://drug-dev.com/new-product-introduction-addressing-the-pitfalls-of-progressing-from-pilot-to-product-through-effective-new-product-introduction/) |
| Regulatory registration is its own gate (dossier → regulatory submission) | A published stage-gate case study for an OTC-type product added an explicit registration gate | [ITB study](https://digilib.itb.ac.id/gdl/view/19746) |
| CDMO identify & confirm; manufacturer technical approval | Sponsors pick the CDMO and define how the sponsor's quality group works with the CDMO's quality system | [Life Science Leader](https://www.qgdigitalpublishing.com/article/CMC+And+Quality+Considerations+When+Engaging+Your+CDMO/4207192/737164/article.html) |
| Agreement prepared by Legal + Quality + PV, each reviewing | Responsibilities (e.g. stability studies) must be written in an agreement or the OTC sponsor and CMO can both be cited | [Contract Pharma](https://www.contractpharma.com/considerations-when-outsourcing-stability-testing-307082) |
| Artwork → print proof → technical review → manufacturer approval → final printing approval → shade card | Artwork approval is a structured review and sign-off of carton, label and leaflet *with a record*; printer proofs are reviewed before print; colour is checked at proof stage; a quality agreement with printers is expected | [Filestage](https://filestage.io/blog/artwork-approval-process-in-pharma/), [Dalim](https://www.dalim.com/dalimfusion_main_blog/artwork-proofing-compliance-color-errors-before-press), [GMP Good Practice 03](https://www.gmpsop.com/gmp_documents/good-practice-03/) |
| Pre-shipment sample reviewed by Quality | Quality unit release / confirmation before commercial supply | industry norm (no specific source found) |

**Gaps – not found in public sources:** FMEA practice in OTC development, in-licensing decision criteria, pharmacovigilance
agreement content, TGA-specific labelling and shade-card sign-off detail. The system does not invent rules for these – it
only records that the named team signed off, with their note and files.

## 4. What this means for the system design

| Finding | Design decision |
|---|---|
| The chart is the only written process and is followed by people in e-mail threads | One **workflow definition** (`backend/app/workflow.py`) is the single source of truth; engine, UI and the "How it works" page all read it |
| Every box names exactly who is responsible | Role-based permissions; only the named role can act; the Project Initiator step is limited to *that project's* initiator |
| Approvals need a record | Every action is stored with person, role, time, note (history on each project) |
| Loops are common (5 in the chart) | Loops are first-class: "send back" jumps to the exact step the chart's arrow points at, keeps history, and re-notifies the owner |
| Joint responsibility ("Director India **and** Director OTC", "Legal / Quality / PV") | "All must sign" steps; project only moves when every named team has signed |
| Users live in Excel / e-mail | Master Excel export, project summary export, bulk-add from Excel, files attached on the project (instead of e-mail), notes on the project, in-app notifications |
| Users are not system-skilled | One screen answers "what needs me?", the project page shows one big "Next step" card, and big buttons say what will happen |
| Monday.com-style working feel (requested) | Grouped board with colour-coded phases, status pills, avatars, inline progress – own design, not a copy |

## 5. UX research for the version-2 redesign

Searches on approval-workflow and enterprise UX (sources below) – findings and what was built from them:

| Finding | Source | Built as |
|---|---|---|
| Approval flows branch; the UI should show the branching without overwhelming the user | [ONES](https://ones.com/blog/?p=1123684), [Hivo](https://hivo.co/blog/improving-uiux-of-workflow-approvals-software) | Decision steps show only *Approve* / *Send back*; the full branching lives on the Process map |
| Show the current task and next action; keep advanced features behind predictable patterns | [ONES](https://ones.com/blog/?p=1097739), [Oracle task UI guide](https://docs.oracle.com/cd/F14158_13/books/BusProcFramework/guidelines-and-techniques-for-developing-a-task-ui.html) | Home = "Needs you now"; project page = one "Your turn" card |
| Progressive disclosure: keep the current task in focus, move the rest to secondary screens | [Parallel](https://www.parallelhq.com/blog/enterprise-saas-ux), [Phenomenon](https://phenomenonstudio.com/article/ui-ux-design-for-enterprise-software-key-principles-and-pitfalls/) | Details in a pop-up; Flow/Files/Notes in tabs; finished phases collapse |
| Role-based views are a UX feature that reduces cognitive load | [Parallel](https://www.parallelhq.com/blog/enterprise-saas-ux) | Visibility rules (AUDIT section 3) |
| Current step must stand out from completed/upcoming; give status an accessible label; overdue in red | [Dubai design system](https://designsystem.dubai.ae/components/steppers/timeline), [PatternFly](https://www.patternfly.org/components/progress-stepper/accessibility), [shadcn stepper](https://www.shadcn.io/blocks/stepper-due-dates) | Journey line and Flow diagram (icon + label + colour), "1 day late" chip |
| Many approvals happen on phones | [ONES](https://ones.com/blog/?p=1123684) | 56 px buttons, bottom tab bar, tested at 390 px |

**Not found in public sources:** guidance specific to low-digital-literacy users, and escalation tiers/notification cadence. These parts (plain-language labels, one-question dialogs, reminder at deadline then manager escalation after one more period) are design decisions documented in AUDIT.md sections 4–5, to be confirmed with the client.
