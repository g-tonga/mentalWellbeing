import asyncio
import logging
import os
from contextlib import asynccontextmanager
from enum import Enum
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from google import genai
from google.genai import errors, types
from pydantic import BaseModel, Field

import screening
from resources import CRISIS_RESOURCES

logger = logging.getLogger("wellbeing-agent")
logging.basicConfig(level=logging.INFO)

MODELS = [
    m.strip()
    for m in os.environ.get("GEMINI_MODELS", "gemini-3.8-flash,gemini-3.5-flash-lite").split(",")
]

FALLBACK_TIP = (
    "Take a few slow breaths, step outside for a short walk, "
    "or message someone you trust."
)

SYSTEM_PROMPT = (
    "You are an empathetic, non-clinical mental wellbeing first-aid assistant. "
    "You are not a doctor and must never diagnose. You receive only the signals "
    "the user chose to share; never ask for or mention missing ones. Suggest ONE "
    "gentle, low-friction micro-intervention (a short walk, journaling, messaging "
    "a friend, calming music). Warm tone, max 3 sentences. "
    "If the user may be in danger, encourage contacting a trusted person or "
    "local emergency services."
)


class Region(str, Enum):
    AE = "AE"
    KE = "KE"


class Activity(str, Enum):
    resting = "resting"
    walking = "walking"
    exercising = "exercising"
    sleeping = "sleeping"


class WearableTelemetry(BaseModel):
    # Random per-session token. No name, phone number or device ID is ever sent.
    session_id: str = Field(min_length=8, max_length=64)
    region: Region = Region.AE
    # Every signal is optional: a signal the user switched off is simply absent.
    heart_rate_bpm: int | None = Field(default=None, ge=20, le=250)
    activity_state: Activity | None = None
    indoor_steps_last_4_hours: int | None = Field(default=None, ge=0, le=50_000)


class ScoreRequest(BaseModel):
    instrument: screening.InstrumentId
    answers: list[Annotated[int, Field(ge=0, le=3)]]
    region: Region = Region.AE


@asynccontextmanager
async def lifespan(app: FastAPI):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set")
    app.state.client = genai.Client(api_key=api_key)
    yield


app = FastAPI(title="Wearable Mental Wellbeing AI Agent", lifespan=lifespan)


def emergency_numbers(region: Region) -> str:
    items = CRISIS_RESOURCES[region.value]["emergency"]
    return " or ".join(f'{i["number"]} ({i["label"].lower()})' for i in items)


def has_signal(d: WearableTelemetry) -> bool:
    return any(
        v is not None
        for v in (d.heart_rate_bpm, d.activity_state, d.indoor_steps_last_4_hours)
    )


def is_crisis(d: WearableTelemetry) -> bool:
    # Only flag a very high heart rate when the body should be calm
    return (
        d.heart_rate_bpm is not None
        and d.heart_rate_bpm > 140
        and d.activity_state in (Activity.resting, Activity.sleeping)
    )


def needs_checkin(d: WearableTelemetry) -> bool:
    # Placeholder thresholds: tune these with real data
    stressed = (
        d.heart_rate_bpm is not None
        and d.heart_rate_bpm > 100
        and d.activity_state == Activity.resting
    )
    low_movement = (
        d.indoor_steps_last_4_hours is not None
        and d.indoor_steps_last_4_hours < 500
        and d.activity_state in (None, Activity.resting)
    )
    return stressed or low_movement


def build_prompt(d: WearableTelemetry) -> str:
    # Data minimisation: only shared signals go to the model, nothing identifying.
    lines = []
    if d.heart_rate_bpm is not None:
        lines.append(f"Heart rate: {d.heart_rate_bpm} BPM")
    if d.activity_state is not None:
        lines.append(f"Activity: {d.activity_state.value}")
    if d.indoor_steps_last_4_hours is not None:
        lines.append(f"Steps in last 4 hours: {d.indoor_steps_last_4_hours}")
    return "\n".join(lines)


async def generate_with_retry(client: genai.Client, prompt: str) -> str | None:
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        max_output_tokens=200,
        temperature=0.7,
    )
    for model in MODELS:
        for attempt in range(3):
            try:
                response = await client.aio.models.generate_content(
                    model=model, contents=prompt, config=config
                )
                if response.text:
                    return response.text
                break  # empty reply: try next model
            except errors.ServerError as e:  # 5xx: overloaded or unavailable
                logger.warning("%s attempt %d failed: %s", model, attempt + 1, e)
                await asyncio.sleep(2**attempt)
            except errors.ClientError as e:  # 4xx: bad key, bad model name, etc.
                logger.error("%s client error: %s", model, e)
                break
            except Exception:
                logger.exception("%s unexpected error", model)
                await asyncio.sleep(2**attempt)
    return None


@app.post("/api/analyze-telemetry")
async def analyze_telemetry(data: WearableTelemetry):
    # Privacy: telemetry is never stored or logged. It lives only for this request.
    if not has_signal(data):
        return {
            "status": "no_data",
            "suggest_checkin": False,
            "message": "No signals shared. Turn on at least one sensor to get insights.",
        }

    if is_crisis(data):
        return {
            "status": "alert",
            "suggest_checkin": False,
            "message": (
                "Your heart rate is very high while you're at rest. Please pause "
                "and take slow, deep breaths. If you feel unwell or unsafe, "
                f"contact emergency services ({emergency_numbers(data.region)}) "
                "or someone near you right away."
            ),
        }

    if not needs_checkin(data):
        return {
            "status": "ok",
            "suggest_checkin": False,
            "message": "Your signals look steady. Keep it up!",
        }

    text = await generate_with_retry(app.state.client, build_prompt(data))
    if text is None:
        return {"status": "fallback", "suggest_checkin": True, "message": FALLBACK_TIP}
    return {"status": "success", "suggest_checkin": True, "message": text}


@app.get("/api/screening/instruments")
def get_instruments():
    return screening.public_definitions()


@app.post("/api/screening/score")
def score_screening(req: ScoreRequest):
    # Privacy: answers are scored in memory and never stored or logged.
    try:
        result = screening.score(req.instrument, req.answers)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if result["urgent"]:
        result["crisis_resources"] = CRISIS_RESOURCES[req.region.value]
    return result


@app.get("/health")
def health():
    return {"message": "Backend is running!"}


@app.get("/")
def home():
    return FileResponse(Path(__file__).parent / "index.html")