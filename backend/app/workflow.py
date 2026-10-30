"""The Neo project-management flow chart (AD001-F01-00, Annexure-I) as data.

Everything the client's Word file decides lives here: who is responsible for each step, which steps are
decisions, where a "Hold/Reject" arrow loops back to, what is Development-only or In-Licence-only, and which
documents / details / checks each step must have before it can be completed.
The engine (engine.py) and the screens both read this one definition.
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

# ---- Stages ----------------------------------------------------------------
# The chart has no stage names. These seven follow the chart's own structure: the Neo Health (OTC) side
# (idea, brief), the Neo India Lifeline side (review, feasibility & cost approval, agreement), then
# regulatory + artwork, and finally print approval and launch.
PHASES = [
    {"key": "opportunity", "name": "Opportunity", "color": "#7C5CFC"},
    {"key": "brief", "name": "Brief", "color": "#3B82F6"},
    {"key": "india", "name": "India Review", "color": "#0EA5C6"},
    {"key": "feasibility", "name": "Feasibility & Cost", "color": "#22A06B"},
    {"key": "agreement", "name": "Agreement", "color": "#E8A317"},
    {"key": "regulatory", "name": "Regulatory & Artwork", "color": "#E5537A"},
    {"key": "launch", "name": "Print & Launch", "color": "#4F6BED"},
]


# ---- builders -----------------------------------------------------------------
def doc(key, label, required=True, multi=True, role=None):
    """`role`: on a joint step, only that team adds this document (and signs for it)."""
    return {"key": key, "label": label, "required": required, "multi": multi, "role": role}


def fld(key, label, type="text", required=True, maps=None, options=None, unit=None):
    return {"key": key, "label": label, "type": type, "required": required, "maps": maps,
            "options": options, "unit": unit}


def chk(key, label, role=None):
    return {"key": key, "label": label, "role": role}


# Decision option kinds:
#  approve : moves forward     back : the chart's "Hold/Reject" loop arrow     hold : pause     reject : close
def _opt(label, kind, to=None, **extra):
    return {"label": label, "kind": kind, "to": to, **extra}


def _action(key, name, phase, roles, **kw):
    return {"key": key, "name": name, "phase": phase, "roles": roles, "mode": "action", **kw}


def _decision(key, name, phase, roles, options, **kw):
    return {"key": key, "name": name, "phase": phase, "roles": roles, "mode": "decision", "options": options, **kw}


STEPS = [
    # --- Opportunity (Neo Health OTC) ----------------------------------------
    _action("opportunity", "Opportunity Identification", "opportunity", ["initiator"]),
    _action("screening", "Neo Health (OTC) Screening", "opportunity", ["initiator"],
            checks=[chk("fit", "Fits the OTC range"), chk("market", "Market and competitors checked"),
                    chk("ip", "No patent / IP concern")]),
    _action("validation", "Commercial Validation", "opportunity", ["initiator"],
            fields=[fld("est_value", "Estimated yearly sales", "number", maps="est_value", unit="A$"),
                    fld("margin", "Expected margin", "number", required=False, unit="%")],
            docs=[doc("business_case", "Business case")]),
    _action("approval_decision", "Approval Decision", "opportunity", ["initiator"],
            consult="otc_director", button="Send to Director"),
    _decision("otc_decision", "Director Decision", "opportunity", ["otc_director"], {
        "approve": _opt("Approve", "approve"),
        "reject": _opt("Reject", "reject", note=True),
    }),
    _action("code", "Project Code Generated", "opportunity", ["initiator"], button="Generate code"),

    # --- Brief (Neo Health OTC) -------------------------------------------------
    _action("draft_brief", "Draft Brief (Master Excel)", "brief", ["initiator"],
            docs=[doc("master_excel", "Master Excel brief")],
            fields=[fld("target_date", "Target launch date", "date", maps="target_date")]),
    _action("internal_review", "Internal Review / Modification", "brief", ["initiator", "cft"]),
    _action("final_internal", "Final Internal Approval & Draft Preparation", "brief", ["initiator", "cft"]),
    _action("submission", "Submission to Neo India Lifeline", "brief", ["initiator"], button="Submit to Neo India"),

    # --- India review (Neo India Lifeline) -----------------------------------------
    _decision("india_review", "Neo India Lifeline Review", "india", ["india_director"], {
        "complete": _opt("Approve – information complete", "approve", to="updated_brief",
                         short="Information is complete"),
        "incomplete": _opt("Approve – information incomplete", "approve", to="clarification",
                           short="Information is incomplete"),
        "reject": _opt("Reject – send back for modification", "back", to="internal_review", note=True),
    }),
    _action("clarification", "Clarification Request Raised", "india", ["india_director"],
            fields=[fld("question", "What clarification is needed?", "textarea")],
            button="Send request", to="internal_review", sets={"clarification_pending": True}),
    _action("updated_brief", "Updated Project Brief Received", "india", ["india_director"], button="Confirm received"),

    # --- Feasibility & Cost ------------------------------------------------------------
    _action("feas_review_done", "Final Feasibility Review Completed", "feasibility", ["india_director"]),
    _action("brief_approved", "Project Brief Approved", "feasibility", ["india_director"]),
    _action("cft_review", "Cross-Functional Review", "feasibility", ["india_director"]),
    _action("fmea", "Risk Analysis (FMEA)", "feasibility", ["cft"],
            docs=[doc("fmea", "FMEA worksheet")],
            fields=[fld("risk_level", "Highest risk found", "select", options=["Low", "Medium", "High"])]),
    _action("feas_prep", "Final Feasibility Report Preparation", "feasibility", ["cft"]),
    _action("feas_submit", "Final Feasibility Report Submission", "feasibility", ["cft"], button="Submit report",
            docs=[doc("feas_report", "Final feasibility report")],
            fields=[fld("recommendation", "Recommendation", "select", options=["Go", "Hold", "No-go"])]),
    _decision("feas_decision", "Feasibility Decision", "feasibility", ["india_director"], {
        "approve": _opt("Approve", "approve"),
        "hold": _opt("Hold", "hold", note=True),
        "reject": _opt("Reject", "reject", note=True),
    }),
    _action("cost", "Cost Finalization", "feasibility", ["india_director"],
            fields=[fld("unit_cost", "Cost per unit", "number", unit="A$"),
                    fld("moq", "Minimum order quantity", "number"),
                    fld("lead_days", "Lead time", "number", required=False, unit="days")],
            docs=[doc("quotation", "Supplier quotation", required=False)]),
    _action("fin_review", "Financial Review", "feasibility", ["india_director", "initiator"], all=True),
    _action("risk_adj", "Risk Adjustment", "feasibility", ["india_director"]),
    _decision("commercial_approval", "Final Commercial Approval", "feasibility", ["india_director", "otc_director"], {
        "approve": _opt("Approve", "approve"),
        "back": _opt("Hold / Reject", "back", to="fin_review", note=True),
    }, all=True),

    # --- Agreement ---------------------------------------------------------------------------
    _action("agreement_prep", "Agreement Preparation", "agreement", ["legal", "quality", "pv"], all=True,
            docs=[doc("supplier_agreement", "Supplier agreement", role="legal"),
                  doc("quality_agreement", "Quality agreement", role="quality"),
                  doc("pv_agreement", "Pharmacovigilance agreement", role="pv")]),
    _action("functional_review", "Functional Review (Supplier Agreement)", "agreement",
            ["india_director", "otc_director"], all=True),
    _action("lqp_review", "Legal / Quality / Pharmacovigilance Review", "agreement", ["legal", "quality", "pv"],
            all=True,
            checks=[chk("legal", "Legal terms reviewed", "legal"), chk("quality", "Quality clauses reviewed", "quality"),
                    chk("pv", "PV reporting timelines agreed", "pv")]),
    _decision("agreement_decision", "Agreement Decision", "agreement", ["india_director"], {
        "approve": _opt("Approve", "approve"),
        "hold": _opt("Hold", "hold", note=True),
        "reject": _opt("Reject", "reject", note=True),
    }),

    # --- Regulatory & Artwork ------------------------------------------------------------------
    _action("cdmo", "CDMO / CRO Identify and Confirm", "regulatory", ["india_director"], only="development",
            fields=[fld("manufacturer", "CDMO / CRO name", maps="manufacturer"),
                    fld("country", "Country", required=False)],
            docs=[doc("cdmo_audit", "CDMO qualification / audit report")]),
    _action("reg_review", "Regulatory Review and Approval", "regulatory", ["reg_head"], only="in_licence",
            docs=[doc("licence_docs", "Licence / partner documents")]),
    _action("handover", "Handover to the Regulatory", "regulatory", ["reg_head"]),
    _action("dossier_assign", "Dossier Preparation (Regulatory Team)", "regulatory", ["reg_head", "reg_team"],
            fields=[fld("pathway", "Pathway", "select",
                        options=["ARTG listing (AUST L)", "ARTG registration (AUST R)", "Other"]),
                    fld("target_submission", "Target submission date", "date", required=False)],
            docs=[doc("gmp_evidence", "GMP evidence (licence / TGA clearance)"), doc("dossier", "Dossier (CTD)")]),
    _decision("reg_decision", "Regulatory Decision", "regulatory", ["reg_head"], {
        "approve": _opt("Approve", "approve"),
        "back": _opt("Hold / Reject", "back", to="dossier_assign", note=True),
    }, checks=[chk("complete", "Dossier is complete"), chk("labelling", "Labelling requirements met")]),
    _action("concept", "Concept Development / Re-Development", "regulatory", ["initiator", "commercial"]),
    _action("artwork", "Artwork Design Development / Re-Development", "regulatory", ["artwork"],
            docs=[doc("artwork_files", "Artwork files")],
            fields=[fld("version", "Artwork version")]),
    _decision("artwork_approval", "Concept / Artwork Approval", "regulatory", ["otc_director"], {
        "approve": _opt("Approve", "approve"),
        "back": _opt("Hold / Reject", "back", to="concept", note=True),
    }, checks=[chk("claims", "Claims and mandatory statements checked"), chk("codes", "Barcode / pack codes checked")]),

    # --- Print & Launch ------------------------------------------------------------------------------
    _action("mfr_tech", "Manufacturer Technical Review and Approval", "launch", ["cmo"],
            docs=[doc("tech_review_doc", "Technical review summary")]),
    _action("ra_reviewer", "Assigned RA Reviewer", "launch", ["reg_head"]),
    _action("reg_submission", "Regulatory Submission", "launch", ["reg_head"],
            fields=[fld("reference", "Submission / application number"), fld("submitted_on", "Submission date", "date")],
            docs=[doc("receipt", "Submission receipt")]),
    _action("comm_ready", "Commercial Readiness", "launch", ["india_director"],
            checks=[chk("stock", "Launch stock plan agreed"), chk("distribution", "Distribution partners informed"),
                    chk("price", "Price list approved")]),
    _action("print_proof", "Manufacturer Print Proof", "launch", ["artwork", "commercial"],
            docs=[doc("print_proof_doc", "Print proof")]),
    _action("tech_review", "Technical Review", "launch", ["artwork", "reg_head"]),
    _action("mfr_approval", "Manufacturer Approval", "launch", ["cmo"],
            docs=[doc("signed_proof", "Signed print proof")]),
    _action("final_print", "Final Printing Approval", "launch", ["artwork", "commercial"],
            docs=[doc("final_artwork", "Final approved artwork")]),
    _action("shade_card", "Shade Card Approval", "launch", ["artwork", "commercial"],
            docs=[doc("shade_card_doc", "Approved shade card")]),
    _action("manufacturing", "Commercial Manufacturing", "launch", ["commercial"],
            fields=[fld("batch_no", "Batch number"), fld("batch_size", "Batch size", "number"),
                    fld("mfg_date", "Manufacturing date", "date")],
            docs=[doc("batch_record", "Batch record / COA")]),
    _action("presample", "Pre-Shipment Sample Dispatch", "launch", ["artwork", "commercial"],
            fields=[fld("tracking", "Courier / tracking number", required=False)]),
    _action("sample_review", "Sample Review and Approval", "launch", ["artwork", "commercial"], coordinator="quality",
            checks=[chk("matches", "Sample matches approved artwork"), chk("quality", "Quality report reviewed")]),
    _action("dispatch", "Commercial Dispatch", "launch", ["commercial"],
            fields=[fld("invoice", "Invoice number"), fld("qty", "Quantity dispatched", "number"),
                    fld("dispatched_on", "Dispatch date", "date")],
            docs=[doc("dispatch_docs", "Dispatch documents (invoice, packing list, COA)")]),
    _action("completion", "Project Completion", "launch", ["otc_director"], button="Complete project",
            checks=[chk("filed", "All documents are filed")]),
]

STEP_BY_KEY = {s["key"]: s for s in STEPS}
PHASE_BY_KEY = {p["key"]: p for p in PHASES}
PROJECT_TYPES = {"development": "Development", "in_licence": "In-Licence"}

# ---- parallel work ---------------------------------------------------------------------------------
# In the chart these tracks follow each other. They do not depend on each other's output, so a Director may
# switch on "Fast track" for a project and they run side by side (all tracks must finish before the next step).
GROUPS = {
    "g1": {"name": "Regulatory dossier and Concept & artwork",
           "why": "Dossier preparation and artwork development do not need each other until the final approvals.",
           "tracks": [
               {"name": "Regulatory", "steps": ["handover", "dossier_assign", "reg_decision"]},
               {"name": "Concept & artwork", "steps": ["concept", "artwork", "artwork_approval"]},
           ]},
    "g2": {"name": "Submission, readiness and print approval",
           "why": "The regulatory submission, commercial readiness and print approval are independent of each other.",
           "tracks": [
               {"name": "Regulatory submission", "steps": ["ra_reviewer", "reg_submission"]},
               {"name": "Commercial readiness", "steps": ["comm_ready"]},
               {"name": "Print approval", "steps": ["print_proof", "tech_review", "mfr_approval", "final_print", "shade_card"]},
           ]},
}

# The chart order. {"group": id} stands for the parallel-capable block; run in order unless Fast track is on.
FLOW = [
    "opportunity", "screening", "validation", "approval_decision", "otc_decision", "code",
    "draft_brief", "internal_review", "final_internal", "submission",
    "india_review", "clarification", "updated_brief",
    "feas_review_done", "brief_approved", "cft_review", "fmea", "feas_prep", "feas_submit", "feas_decision",
    "cost", "fin_review", "risk_adj", "commercial_approval",
    "agreement_prep", "functional_review", "lqp_review", "agreement_decision",
    "cdmo", "reg_review", {"group": "g1"},
    "mfr_tech", {"group": "g2"},
    "manufacturing", "presample", "sample_review", "dispatch", "completion",
]

SLA_OVERRIDES = {
    "cdmo": 10, "agreement_prep": 10, "dossier_assign": 14, "reg_submission": 7, "mfr_tech": 7,
    "artwork": 7, "concept": 7, "print_proof": 7, "manufacturing": 21, "presample": 7, "dispatch": 7,
    "fmea": 7, "feas_prep": 7, "draft_brief": 5, "cost": 5,
}


def sla_days(step_key: str) -> int:
    return SLA_OVERRIDES.get(step_key, 2 if STEP_BY_KEY[step_key]["mode"] == "decision" else 3)


def applies(step_key: str, ptype: str) -> bool:
    return STEP_BY_KEY[step_key].get("only") in (None, ptype)


def flat_order(ptype: str) -> list:
    """All steps that apply to a project type, in chart order."""
    out = []
    for n in FLOW:
        if isinstance(n, str):
            if applies(n, ptype):
                out.append(n)
        else:
            for t in GROUPS[n["group"]]["tracks"]:
                out += t["steps"]
    return out


def steps_for(ptype: str) -> list:
    return [STEP_BY_KEY[k] for k in flat_order(ptype)]


def group_of(step_key: str):
    """(group id, track index, position in track) when the step belongs to a parallel-capable block."""
    for gid, g in GROUPS.items():
        for ti, t in enumerate(g["tracks"]):
            if step_key in t["steps"]:
                return gid, ti, t["steps"].index(step_key)
    return None


def _node_index(step_key: str) -> int:
    for i, n in enumerate(FLOW):
        if n == step_key or (isinstance(n, dict) and group_of(step_key) and group_of(step_key)[0] == n["group"]):
            return i
    raise KeyError(step_key)


def after_node(idx: int, ptype: str, fast: bool):
    """Steps to start after the FLOW node at `idx` is finished. Returns (keys, group_entered, mode)."""
    for n in FLOW[idx + 1:]:
        if isinstance(n, str):
            if applies(n, ptype):
                return [n], None, None
        else:
            g = GROUPS[n["group"]]
            if fast:
                return [t["steps"][0] for t in g["tracks"]], n["group"], "fast"
            return [g["tracks"][0]["steps"][0]], n["group"], "seq"
    return [], None, None


def successors(step_key: str, ptype: str, fast: bool, group_mode: dict, is_done):
    """What starts when `step_key` is completed. Returns (keys, group_entered, mode, finished)."""
    gi = group_of(step_key)
    if gi is None:
        keys, g, mode = after_node(_node_index(step_key), ptype, fast)
        return keys, g, mode, not keys
    gid, ti, pos = gi
    g = GROUPS[gid]
    track = g["tracks"][ti]["steps"]
    if pos + 1 < len(track):
        return [track[pos + 1]], None, None, False
    mode = group_mode.get(gid, "seq")
    if mode == "fast":
        others_done = all(is_done(t["steps"][-1]) for i, t in enumerate(g["tracks"]) if i != ti)
        if not others_done:
            return [], None, None, False
    elif ti + 1 < len(g["tracks"]):
        return [g["tracks"][ti + 1]["steps"][0]], None, None, False
    keys, g2, m2 = after_node(_node_index(step_key), ptype, fast)
    return keys, g2, m2, not keys


def actor_roles(step: dict) -> list:
    return list(step["roles"]) + ([step["coordinator"]] if step.get("coordinator") else [])


def required_checks(step: dict, role: str) -> list:
    return [c for c in step.get("checks", []) if c["role"] in (None, role)]


def public_definition():
    return {
        "roles": [{"key": k, **v} for k, v in ROLES.items()],
        "phases": PHASES,
        "types": [{"key": k, "label": v} for k, v in PROJECT_TYPES.items()],
        "groups": [{"id": k, **v} for k, v in GROUPS.items()],
        "steps": [{
            "key": s["key"], "name": s["name"], "phase": s["phase"], "roles": s["roles"], "mode": s["mode"],
            "all": bool(s.get("all")), "only": s.get("only"), "consult": s.get("consult"),
            "coordinator": s.get("coordinator"), "sla": sla_days(s["key"]), "group": (group_of(s["key"]) or [None])[0],
            "docs": s.get("docs", []), "fields": s.get("fields", []), "checks": s.get("checks", []),
            "options": [{"key": k, "label": v["label"], "short": v.get("short"), "kind": v["kind"], "to": v.get("to"),
                         "note": bool(v.get("note"))} for k, v in s.get("options", {}).items()],
        } for s in STEPS],
    }
