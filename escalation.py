"""Human escalation (DEMO). Holds consented requests in memory for a simulated
counsellor queue. No real person is notified.

Privacy by design:
- Nothing is created without explicit consent.
- Only the minimum is kept: result category, region, channel, optional contact detail.
- The user can withdraw at any time, which deletes the case.
- Cases live in memory only, expire after 24 hours and vanish on restart.
- The counsellor endpoints need an access code.
"""

import logging
import os
import secrets
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

import screening
from resources import Region

logger = logging.getLogger("wellbeing-agent")
router = APIRouter()

_ENV_CODE = os.environ.get("COUNSELLOR_CODE")
COUNSELLOR_CODE = _ENV_CODE or secrets.token_urlsafe(6)

TTL_SECONDS = 24 * 60 * 60
MAX_CASES = 200
STATUS_ORDER = {"new": 0, "acknowledged": 1, "contacted": 2}

Status = Literal["new", "acknowledged", "contacted"]
Band = Literal["minimal", "mild", "moderate", "moderately severe", "severe"]


def announce_code() -> None:
    if not _ENV_CODE:
        logger.warning("Counsellor demo code (this run only): %s", COUNSELLOR_CODE)


def iso(ts: float | None) -> str | None:
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(timespec="seconds")


@dataclass
class Case:
    id: str
    created_at: float
    session_id: str
    region: str
    instrument: str
    band: str
    crisis_flag: bool
    channel: str
    contact_hint: str | None
    status: str = "new"
    acknowledged_at: float | None = None
    contacted_at: float | None = None


class CaseStore:
    def __init__(self) -> None:
        self._cases: dict[str, Case] = {}
        self._lock = threading.Lock()

    def _purge(self) -> None:
        now = time.time()
        for key in [k for k, c in self._cases.items() if now - c.created_at > TTL_SECONDS]:
            del self._cases[key]

    def create(self, **fields) -> Case:
        with self._lock:
            self._purge()
            for existing in self._cases.values():
                if existing.session_id == fields["session_id"]:
                    return existing  # one open request per session
            if len(self._cases) >= MAX_CASES:
                raise HTTPException(status_code=503, detail="Demo queue is full. Try again later.")
            case = Case(id=uuid.uuid4().hex, created_at=time.time(), **fields)
            self._cases[case.id] = case
            return case

    def get(self, case_id: str) -> Case | None:
        with self._lock:
            self._purge()
            return self._cases.get(case_id)

    def all_cases(self) -> list[Case]:
        with self._lock:
            self._purge()
            return sorted(self._cases.values(), key=lambda c: c.created_at, reverse=True)

    def set_status(self, case_id: str, status: str) -> Case | None:
        with self._lock:
            case = self._cases.get(case_id)
            if case is None:
                return None
            if STATUS_ORDER[status] < STATUS_ORDER[case.status]:
                raise HTTPException(status_code=409, detail="Status cannot go backwards.")
            now = time.time()
            if status in ("acknowledged", "contacted") and case.acknowledged_at is None:
                case.acknowledged_at = now
            if status == "contacted":
                case.contacted_at = now
            case.status = status
            return case

    def withdraw(self, case_id: str) -> bool:
        with self._lock:
            return self._cases.pop(case_id, None) is not None


store = CaseStore()


def require_counsellor(x_counsellor_code: str | None = Header(default=None)) -> None:
    supplied = (x_counsellor_code or "").encode()
    if not secrets.compare_digest(supplied, COUNSELLOR_CODE.encode()):
        raise HTTPException(status_code=401, detail="Invalid counsellor code.")


class EscalationRequest(BaseModel):
    session_id: str = Field(min_length=8, max_length=64)
    region: Region
    instrument: screening.InstrumentId
    band: Band
    crisis_flag: bool = False
    consent: bool
    channel: Literal["call", "message"] = "call"
    contact_hint: str | None = Field(default=None, max_length=64)


class StatusUpdate(BaseModel):
    status: Status


def counsellor_view(c: Case, now: float) -> dict:
    return {
        "id": c.id,
        "created_at": iso(c.created_at),
        "waiting_minutes": int((now - c.created_at) // 60) if c.status == "new" else None,
        "region": c.region,
        "instrument": c.instrument.upper(),
        "band": c.band,
        "crisis_flag": c.crisis_flag,
        "reason": (
            "Reported thoughts of self-harm (self-reported answer)"
            if c.crisis_flag else "Severe score range (self-reported)"
        ),
        "channel": c.channel,
        "contact_hint": c.contact_hint,
        "status": c.status,
        "acknowledged_at": iso(c.acknowledged_at),
        "contacted_at": iso(c.contacted_at),
    }


@router.post("/api/escalate")
def request_human(req: EscalationRequest):
    if not req.consent:
        raise HTTPException(status_code=400, detail="Consent is required to share anything with a counsellor.")
    hint = (req.contact_hint or "").strip() or None
    case = store.create(
        session_id=req.session_id,
        region=req.region.value,
        instrument=req.instrument.value,
        band=req.band,
        crisis_flag=req.crisis_flag,
        channel=req.channel,
        contact_hint=hint,
    )
    logger.info("Escalation case created (ending %s)", case.id[-6:])  # no personal data in logs
    return {"case_id": case.id, "status": case.status, "demo": True}


@router.get("/api/escalate/{case_id}")
def case_status(case_id: str):
    case = store.get(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Request not found.")
    return {"status": case.status}


@router.delete("/api/escalate/{case_id}")
def withdraw_request(case_id: str):
    if not store.withdraw(case_id):
        raise HTTPException(status_code=404, detail="Request not found.")
    return {"withdrawn": True}


@router.get("/api/counsellor/cases", dependencies=[Depends(require_counsellor)])
def list_cases():
    now = time.time()
    return {"cases": [counsellor_view(c, now) for c in store.all_cases()]}


@router.post("/api/counsellor/cases/{case_id}/status", dependencies=[Depends(require_counsellor)])
def update_case(case_id: str, body: StatusUpdate):
    case = store.set_status(case_id, body.status)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found.")
    return counsellor_view(case, time.time())