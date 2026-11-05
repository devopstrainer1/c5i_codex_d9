"""Small offline teaching core. Synthetic data, single process, no live AI calls."""
import copy
import hashlib
import json
import re
import time
import uuid
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit

POLICY = {"number": "POL-20481971", "holder": "Asha Rao", "start": "2026-01-01", "end": "2026-12-31"}
STAGES = {"Review", "Underwriting", "Approved"}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


class Store:
    def __init__(self):
        self.claims = {"CLM-000101": {"stage": "Review", "version": 0}}
        self.accepted = {}
        self.quarantine = []
        self.audit = []

    def event(self, kind, **fields):
        self.audit.append({"event": kind, **fields})

    def move(self, claim_id, stage, expected_version):
        if claim_id not in self.claims or stage not in STAGES:
            raise ValueError("Unknown claim or stage")
        row = self.claims[claim_id]
        if row["version"] != expected_version:
            raise ValueError("STALE")
        row.update(stage=stage, version=row["version"] + 1)
        self.event("write", operation="move_stage", version=row["version"])


class VoiceController:
    """Replay controller. confirm is a teaching event, not caller authentication."""
    def __init__(self, store, clock=time.monotonic):
        self.store, self.clock = store, clock
        self.pending = None

    def handle(self, text):
        text = text.strip()
        if self.pending and self.clock() >= self.pending["expires"]:
            self.pending = None
            self.store.event("expired")
            return "EXPIRED"
        if text.lower() == "status":
            return self.store.claims["CLM-000101"]["stage"]
        if text.startswith("move "):
            if self.pending:
                return "PENDING_EXISTS"
            stage = text[5:]
            if stage not in STAGES:
                return "INVALID_STAGE"
            self.pending = {"action_id": str(uuid.uuid4()), "claim_id": "CLM-000101",
                            "stage": stage, "version": self.store.claims["CLM-000101"]["version"],
                            "expires": self.clock() + 10}
            self.store.event("proposed", action_id=self.pending["action_id"], stage=stage)
            return "AWAITING_CONFIRM"
        if text.lower() == "confirm":
            if not self.pending:
                return "NO_PENDING"
            proposal, self.pending = self.pending, None
            try:
                self.store.move(proposal["claim_id"], proposal["stage"], proposal["version"])
            except ValueError:
                return "STALE"
            self.store.event("confirmed", action_id=proposal["action_id"])
            return "EXECUTED"
        if self.pending:
            self.pending = None
            self.store.event("cancelled")
            return "CANCELLED"
        return "UNRECOGNIZED"


def validate_claim(candidate, source, as_of=date(2026, 11, 5)):
    """Returns independent named checks. source is trusted fixture text in replay."""
    checks = {}
    def check(name, ok, reason):
        checks[name] = {"status": "PASS" if ok else "FAIL", "reason": "ok" if ok else reason}
    check("schema", isinstance(candidate, dict) and all(k in candidate for k in (
        "claim_id", "policy_number", "claimant_name", "date_of_loss", "line_items", "total_amount", "evidence")),
        "required field missing")
    if checks["schema"]["status"] != "PASS":
        return checks
    check("claim_id", bool(re.fullmatch(r"CLM-\d{6}", str(candidate["claim_id"]))), "invalid claim ID")
    number = str(candidate["policy_number"])
    match = re.fullmatch(r"POL-(\d{7})(\d)", number)
    check("policy_checksum", bool(match and sum(map(int, match[1])) % 10 == int(match[2])), "checksum mismatch")
    check("policy_lookup", number == POLICY["number"] and candidate["claimant_name"] == POLICY["holder"],
          "unknown policy or claimant mismatch")
    try:
        loss = datetime.strptime(candidate["date_of_loss"], "%Y-%m-%d").date()
        date_ok = date.fromisoformat(POLICY["start"]) <= loss <= min(as_of, date.fromisoformat(POLICY["end"]))
    except (ValueError, TypeError):
        date_ok = False
    check("date_rules", date_ok, "date must be ISO and within policy period and as_of date")
    try:
        items = [Decimal(str(x)) for x in candidate["line_items"]]
        total = Decimal(str(candidate["total_amount"]))
        amount_ok = bool(items) and total.is_finite() and total >= 0 and all(x.is_finite() and x >= 0 for x in items)
        arithmetic_ok = amount_ok and sum(items, Decimal("0")) == total
    except (InvalidOperation, TypeError, ValueError):
        arithmetic_ok = False
    check("arithmetic", arithmetic_ok, "missing items, invalid amounts or sum differs from total")
    evidence = candidate["evidence"]
    check("evidence_present", isinstance(evidence, dict) and all(
        k in evidence and evidence[k] and evidence[k] in source for k in ("policy_number", "total_amount")),
        "critical source evidence missing")
    if checks["evidence_present"]["status"] == "PASS":
        try:
            evidence_ok = evidence["policy_number"] == number and Decimal(evidence["total_amount"].replace(",", "")) == Decimal(str(candidate["total_amount"]))
        except (InvalidOperation, ValueError, TypeError):
            evidence_ok = False
        check("evidence_values", evidence_ok, "evidence does not support candidate value")
    else:
        checks["evidence_values"] = {"status": "UNRESOLVED", "reason": "evidence unavailable"}
    return checks


class ExtractionPipeline:
    """Machine validation plus explicit synthetic human review token."""
    def __init__(self, store):
        self.store = store
        self.reviews = {}

    def review(self, candidate, source, reviewer):
        # The caller is a synthetic reviewer in this offline exercise. Auth is a learner extension.
        token = str(uuid.uuid4())
        self.reviews[token] = (digest(candidate), digest(source), reviewer)
        return token

    def process(self, candidate, source, token=None):
        checks = validate_claim(candidate, source)
        if any(c["status"] != "PASS" for c in checks.values()):
            self.store.quarantine.append({"candidate_hash": digest(candidate), "checks": checks})
            return {"status": "QUARANTINED", "checks": checks}
        review = self.reviews.get(token)
        if not review or review[:2] != (digest(candidate), digest(source)):
            return {"status": "AWAITING_REVIEW", "checks": checks}
        claim_id = candidate["claim_id"]
        if claim_id in self.store.accepted:
            return {"status": "DUPLICATE", "checks": checks}
        self.reviews.pop(token)
        self.store.accepted[claim_id] = copy.deepcopy(candidate)
        self.store.event("write", operation="accept_document", candidate_hash=digest(candidate))
        return {"status": "SAVED", "checks": checks}


class ScreenPolicy:
    """Pure policy simulator; does not execute or confine a browser."""
    def __init__(self, origin="http://127.0.0.1:5050", max_steps=15):
        self.origin, self.max_steps = origin, max_steps

    def allowed_url(self, url):
        try:
            p, expected = urlsplit(url), urlsplit(self.origin)
            return (p.scheme, p.hostname, p.port) == (expected.scheme, expected.hostname, expected.port) and not p.username and not p.password
        except ValueError:
            return False

    def run(self, plan, approvals=(), dry_run=False):
        if len(plan) > self.max_steps:
            return {"status": "STEP_LIMIT", "events": []}
        events, choices = [], iter(approvals)
        for step in plan:
            action = step.get("action")
            if action not in {"open", "read", "fill", "submit"}:
                return {"status": "UNKNOWN_ACTION", "events": events}
            if "url" in step and not self.allowed_url(step["url"]):
                return {"status": "BLOCKED", "events": events + [{"event": "blocked"}]}
            if not dry_run and action in {"fill", "submit"} and next(choices, False) is not True:
                return {"status": "DENIED", "events": events + [{"event": "denied", "action": action}]}
            events.append({"event": "planned" if dry_run else "simulated", "action": action})
        return {"status": "DRY_RUN" if dry_run else "SIMULATED", "events": events}
