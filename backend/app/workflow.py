"""The Neo project-management flow chart (AD001-F01-00, Annexure-I) as data.

Every rule in the client's Word file lives here: who is responsible for each
step, which steps are decisions, where a "Reject / Hold" arrow loops back to,
and which steps only apply to Development or In-Licence projects.
The engine (engine.py) and the UI both read from this one definition.
"""

# ---- Roles ---------------------------------------------------------------
ROLES = {
    "initiator": {"label": "Project Initiator", "short": "Initiator", "org": "Neo Health (OTC)"},
    "otc_director": {"label": "Director – Neo Health OTC", "short": "OTC Director", "org": "Neo Health (OTC)"},
    "india_director": {"label": "Director – Neo India Lifeline", "short": "India Director", "org": "Neo India Lifeline"},
    "cft": {"label": "Cross-Functional Team", "short": "CFT", "org": "Neo Health (OTC)"},
    "legal": {"label": "Legal Team", "short": "Legal", "org": "Neo India Lifeline"},
    "quality": {"label": "Quality Team", "short": "Quality", "org": "Neo India Lifeline"},
    "pv": {"label": "PV Team", "short": "PV", "org": "Neo India Lifeline"},
    "reg_head": {"label": "Regulatory Head", "short": "Reg. Head", "org": "Neo India Lifeline"},
    "reg_team": {"label": "Regulatory Team", "short": "Reg. Team", "org": "Neo India Lifeline"},
    "artwork": {"label": "Artwork Team", "short": "Artwork", "org": "Neo Health (OTC)"},
    "commercial": {"label": "Commercial Team", "short": "Commercial", "org": "Neo Health (OTC)"},
    "cmo": {"label": "CMO (Manufacturer)", "short": "CMO", "org": "Manufacturer"},
    "admin": {"label": "Office Admin", "short": "Admin", "org": "Office"},
}

# ---- Phases (groups shown on the board) -----------------------------------
PHASES = [
    {"key": "idea", "name": "Idea & Screening", "color": "#7C5CFC"},
    {"key": "brief", "name": "Project Brief", "color": "#3B82F6"},
    {"key": "india", "name": "India Review", "color": "#0EA5C6"},
    {"key": "feasibility", "name": "Feasibility", "color": "#14B8A6"},
    {"key": "commercial", "name": "Cost & Approval", "color": "#22A06B"},
    {"key": "agreement", "name": "Agreement", "color": "#E8A317"},
    {"key": "regulatory", "name": "Regulatory", "color": "#F08A24"},
    {"key": "concept", "name": "Concept & Artwork", "color": "#E5537A"},
    {"key": "print", "name": "Manufacturer & Print", "color": "#B455D8"},
    {"key": "launch", "name": "Manufacture & Dispatch", "color": "#4F6BED"},
]


# Decision option kinds:
#  approve : moves forward           back   : "Hold/Reject" arrow that loops back
#  hold    : pause the project       reject : close the project as rejected
def _opt(label, kind, to=None, **extra):
    return {"label": label, "kind": kind, "to": to, **extra}


def _action(key, name, phase, roles, **kw):
    return {"key": key, "name": name, "phase": phase, "roles": roles, "mode": "action", **kw}


def _decision(key, name, phase, roles, options, **kw):
    return {"key": key, "name": name, "phase": phase, "roles": roles, "mode": "decision",
            "options": options, **kw}


STEPS = [
    # --- 1. Idea & Screening (Neo Health OTC) --------------------------------
    _action("opportunity", "Opportunity Identification", "idea", ["initiator"],
            hint="Created when the project is added."),
    _action("screening", "Neo Health (OTC) Screening", "idea", ["initiator"],
            hint="Check the idea fits the OTC range and market."),
    _action("validation", "Commercial Validation", "idea", ["initiator"],
            hint="Project team of Neo Health (OTC) confirms the commercial case."),
    _action("approval_decision", "Approval Decision – submit to Director", "idea", ["initiator"],
            consult="otc_director", button="Send to Director for decision",
            hint="Initiator consults the Director (Neo Health OTC) and asks for a decision."),
    _decision("otc_decision", "Director Decision", "idea", ["otc_director"], {
        "approve": _opt("Approve", "approve"),
        "reject": _opt("Reject", "reject", note=True),
    }, hint="Approve to generate the project code, or reject to close the idea."),

    # --- 2. Project Brief ----------------------------------------------------
    _action("code", "Project Code Generated", "brief", ["initiator"],
            button="Generate project code", hint="A unique project code is created for this project."),
    _action("draft_brief", "Draft Brief (Master Excel)", "brief", ["initiator"],
            needs_file="Master Excel brief", hint="Attach the Master Excel brief in Files."),
    _action("internal_review", "Internal Review / Modification", "brief", ["initiator", "cft"],
            hint="Review the draft, or modify it if it was returned or clarification was asked."),
    _action("final_internal", "Final Internal Approval & Draft Preparation", "brief", ["initiator", "cft"]),
    _action("submission", "Submission to Neo India Lifeline", "brief", ["initiator"],
            button="Submit to Neo India"),

    # --- 3. Neo India Review -------------------------------------------------
    _decision("india_review", "Neo India Lifeline Review", "india", ["india_director"], {
        "complete": _opt("Approve – information complete", "approve", to="updated_brief", short="Information is complete"),
        "incomplete": _opt("Approve – information incomplete (ask clarification)", "approve", to="clarification", short="Information is incomplete"),
        "reject": _opt("Reject – send back for modification", "back", to="internal_review", note=True),
    }, hint="Review the brief submitted by Neo Health (OTC)."),
    _action("clarification", "Clarification Request Raised", "india", ["india_director"],
            needs_note="What clarification is needed?", button="Send clarification request",
            to="internal_review", sets={"clarification_pending": True},
            hint="Goes back to Internal Review; the updated brief returns to Neo India."),
    _action("updated_brief", "Updated Project Brief Received", "india", ["india_director"],
            button="Confirm brief received"),

    # --- 4. Feasibility ------------------------------------------------------
    _action("feas_review_done", "Final Feasibility Review Completed", "feasibility", ["india_director"]),
    _action("brief_approved", "Project Brief Approved", "feasibility", ["india_director"]),
    _action("cft_review", "Cross-Functional Review", "feasibility", ["india_director"]),
    _action("fmea", "Risk Analysis (FMEA)", "feasibility", ["cft"],
            hint="Failure Mode and Effects Analysis by the cross-functional team."),
    _action("feas_prep", "Final Feasibility Report Preparation", "feasibility", ["cft"]),
    _action("feas_submit", "Final Feasibility Report Submission", "feasibility", ["cft"],
            needs_file="Final Feasibility Report", button="Submit report"),
    _decision("feas_decision", "Feasibility Decision", "feasibility", ["india_director"], {
        "approve": _opt("Approve", "approve"),
        "hold": _opt("Hold", "hold", note=True),
        "reject": _opt("Reject", "reject", note=True),
    }),

    # --- 5. Cost & Approval --------------------------------------------------
    _action("cost", "Cost Finalization", "commercial", ["india_director"]),
    _action("fin_review", "Financial Review", "commercial", ["india_director", "initiator"], all=True,
            hint="Both the Director (India) and the Project Initiator confirm."),
    _action("risk_adj", "Risk Adjustment", "commercial", ["india_director"]),
    _decision("commercial_approval", "Final Commercial Approval", "commercial",
              ["india_director", "otc_director"], {
        "approve": _opt("Approve", "approve"),
        "back": _opt("Hold / Reject – back to Financial Review", "back", to="fin_review", note=True),
    }, all=True, hint="Both Directors must approve."),

    # --- 6. Agreement --------------------------------------------------------
    _action("agreement_prep", "Agreement Preparation", "agreement", ["legal", "quality", "pv"],
            needs_file="Draft supplier agreement", hint="Legal, Quality and PV prepare the agreement."),
    _action("functional_review", "Functional Review (Supplier Agreement)", "agreement",
            ["india_director", "otc_director"], all=True, hint="Both Directors review."),
    _action("lqp_review", "Legal / Quality / Pharmacovigilance Review", "agreement",
            ["legal", "quality", "pv"], all=True, hint="Each of the three teams signs off."),
    _decision("agreement_decision", "Agreement Decision", "agreement", ["india_director"], {
        "approve": _opt("Approve", "approve"),
        "hold": _opt("Hold", "hold", note=True),
        "reject": _opt("Reject", "reject", note=True),
    }),

    # --- 7. Regulatory (Development vs In-Licence) ---------------------------
    _action("cdmo", "CDMO / CRO Identify and Confirm", "regulatory", ["india_director"],
            only="development", to="handover",
            needs_text=("manufacturer", "Which CDMO / CRO is confirmed?"),
            hint="Development projects only."),
    _action("reg_review", "Regulatory Review and Approval", "regulatory", ["reg_head"],
            only="in_licence", to="handover", hint="In-Licence projects only."),
    _action("handover", "Handover to the Regulatory", "regulatory", ["reg_head"]),
    _action("dossier_assign", "Assign Task to Regulatory Team for Dossier Preparation", "regulatory",
            ["reg_head", "reg_team"]),
    _decision("reg_decision", "Regulatory Decision", "regulatory", ["reg_head"], {
        "approve": _opt("Approve", "approve"),
        "back": _opt("Hold / Reject – back to dossier preparation", "back", to="dossier_assign", note=True),
    }),

    # --- 8. Concept & Artwork ------------------------------------------------
    _action("concept", "Concept Development / Re-Development", "concept", ["initiator", "commercial"],
            hint="Neo Health (OTC) develops the concept."),
    _action("artwork", "Artwork Design Development / Re-Development", "concept", ["artwork"]),
    _decision("artwork_approval", "Concept / Artwork Approval", "concept", ["otc_director"], {
        "approve": _opt("Approve", "approve"),
        "back": _opt("Hold / Reject – back to concept", "back", to="concept", note=True),
    }),

    # --- 9. Manufacturer & Print ---------------------------------------------
    _action("mfr_tech", "Manufacturer Technical Review and Approval", "print", ["cmo"]),
    _action("ra_reviewer", "Assigned RA Reviewer", "print", ["reg_head"]),
    _action("reg_submission", "Regulatory Submission", "print", ["reg_head"]),
    _action("comm_ready", "Commercial Readiness", "print", ["india_director"]),
    _action("print_proof", "Manufacturer Print Proof", "print", ["artwork", "commercial"]),
    _action("tech_review", "Technical Review", "print", ["artwork", "reg_head"]),
    _action("mfr_approval", "Manufacturer Approval", "print", ["cmo"]),
    _action("final_print", "Final Printing Approval", "print", ["artwork", "commercial"]),
    _action("shade_card", "Shade Card Approval", "print", ["artwork", "commercial"]),

    # --- 10. Manufacture & Dispatch ------------------------------------------
    _action("manufacturing", "Commercial Manufacturing", "launch", ["commercial"]),
    _action("presample", "Pre-Shipment Sample Dispatch", "launch", ["artwork", "commercial"]),
    _action("sample_review", "Sample Review and Approval", "launch", ["artwork", "commercial"],
            coordinator="quality", hint="Quality Team coordinates the review."),
    _action("dispatch", "Commercial Dispatch", "launch", ["commercial"]),
    _action("completion", "Project Completion", "launch", ["otc_director"], button="Complete project"),
]

# Days a step may wait before the owner is reminded (and, later, their manager is told)
SLA_OVERRIDES = {
    "cdmo": 10, "agreement_prep": 10, "dossier_assign": 14, "reg_submission": 7, "mfr_tech": 7,
    "artwork": 7, "concept": 7, "print_proof": 7, "manufacturing": 21, "presample": 7, "dispatch": 7,
    "fmea": 7, "feas_prep": 7, "draft_brief": 5, "cost": 5,
}


def sla_days(step_key: str) -> int:
    step = STEP_BY_KEY[step_key]
    return SLA_OVERRIDES.get(step_key, 2 if step["mode"] == "decision" else 3)


STEP_BY_KEY = {s["key"]: s for s in STEPS}
PHASE_BY_KEY = {p["key"]: p for p in PHASES}
PROJECT_TYPES = {"development": "Development", "in_licence": "In-Licence"}


def steps_for(ptype: str):
    """Steps that apply to a project type (CDMO step vs Regulatory Review step)."""
    return [s for s in STEPS if s.get("only") in (None, ptype)]


def next_step_key(step_key: str, ptype: str, *, clarification_pending: bool = False):
    """Where a completed action step goes next. None = end of the flow."""
    step = STEP_BY_KEY[step_key]
    if step_key == "submission" and clarification_pending:
        return "updated_brief"  # answer to a clarification skips a second India review
    if step.get("to"):
        return step["to"]
    keys = [s["key"] for s in steps_for(ptype)]
    i = keys.index(step_key)
    return keys[i + 1] if i + 1 < len(keys) else None


def decision_target(step_key: str, option: str, ptype: str):
    """Where an 'approve' option goes."""
    opt = STEP_BY_KEY[step_key]["options"][option]
    if opt.get("to"):
        return opt["to"]
    if step_key == "agreement_decision":
        return "cdmo" if ptype == "development" else "reg_review"
    return next_step_key(step_key, ptype)


def actor_roles(step: dict) -> list:
    return list(step["roles"]) + ([step["coordinator"]] if step.get("coordinator") else [])


def public_definition():
    return {
        "roles": [{"key": k, **v} for k, v in ROLES.items()],
        "phases": PHASES,
        "types": [{"key": k, "label": v} for k, v in PROJECT_TYPES.items()],
        "steps": [{
            "key": s["key"], "name": s["name"], "phase": s["phase"], "roles": s["roles"],
            "mode": s["mode"], "all": bool(s.get("all")), "only": s.get("only"),
            "hint": s.get("hint"), "consult": s.get("consult"), "coordinator": s.get("coordinator"),
            "sla": sla_days(s["key"]),
            "options": [{"key": k, "label": v["label"], "short": v.get("short"), "kind": v["kind"], "to": v.get("to"), "note": bool(v.get("note"))}
                        for k, v in s.get("options", {}).items()],
        } for s in STEPS],
    }
