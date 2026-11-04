import asyncio
import logging
import os
from contextlib import asynccontextmanager
from enum import Enum

from fastapi import FastAPI
from google import genai
from google.genai import errors, types
from pydantic import BaseModel, Field

logger = logging.getLogger("wellbeing-agent")
logging.basicConfig(level=logging.INFO)

MODELS = ["gemini-3.8-flash", "gemini-3.5-flash-lite"]  # primary, then fallback

FALLBACK_TIP = (
    "Take a few slow breaths, step outside for a short walk, "
    "or message someone you trust."
)

SYSTEM_PROMPT = (
    "You are an empathetic, non-clinical mental wellbeing first-aid assistant. "
    "You are not a doctor and must never diagnose. Given wearable signals, "
    "suggest ONE gentle, low-friction micro-intervention (a short walk, "
    "journaling, messaging a friend). Warm tone, max 3 sentences. "
    "If the user may be in danger, encourage contacting a trusted person or "
    "local emergency services."
)


class Activity(str, Enum):
    resting = "resting"
    walking = "walking"
    exercising = "exercising"
    sleeping = "sleeping"


class CommFrequency(str, Enum):
    high = "high"
    normal = "normal"
    low = "low"
    none = "none"


class WearableTelemetry(BaseModel):
    user_id: str = Field(min_length=1, max_length=64)
    heart_rate_bpm: int = Field(ge=20, le=250)
    activity_state: Activity
    indoor_steps_last_4_hours: int = Field(ge=0, le=50_000)
    communication_frequency: CommFrequency


@asynccontextmanager
async def lifespan(app: FastAPI):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set")
    app.state.client = genai.Client(api_key=api_key)
    yield


app = FastAPI(title="Wearable Mental Wellbeing AI Agent", lifespan=lifespan)


def is_crisis(d: WearableTelemetry) -> bool:
    # Only flag a high heart rate when the body should be calm
    return d.heart_rate_bpm > 140 and d.activity_state in (
        Activity.resting,
        Activity.sleeping,
    )


def needs_ai_check(d: WearableTelemetry) -> bool:
    # Placeholder thresholds: tune these with real data
    stressed = d.heart_rate_bpm > 100 and d.activity_state == Activity.resting
    isolated = d.indoor_steps_last_4_hours < 500 and d.communication_frequency in (
        CommFrequency.low,
        CommFrequency.none,
    )
    return stressed or isolated


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
                await asyncio.sleep(2**attempt)  # wait 1s, 2s, 4s
            except errors.ClientError as e:  # 4xx: bad key, bad model name, etc.
                logger.error("%s client error: %s", model, e)
                break  # retrying won't help, move to next model
    return None


@app.post("/api/analyze-telemetry")
async def analyze_telemetry(data: WearableTelemetry):
    if is_crisis(data):
        return {
            "status": "alert",
            "intervention_type": "crisis_support",
            "message": (
                "Your heart rate is very high while you're at rest. Please pause "
                "and take slow, deep breaths. If you feel unwell or unsafe, "
                "contact emergency services (112 or 999 in Kenya) or someone "
                "near you right away."
            ),
        }

    if not needs_ai_check(data):
        return {"status": "ok", "message": "Your signals look steady. Keep it up!"}

    prompt = (
        f"Heart rate: {data.heart_rate_bpm} BPM\n"
        f"Activity: {data.activity_state.value}\n"
        f"Steps in last 4 hours: {data.indoor_steps_last_4_hours}\n"
        f"Communication frequency: {data.communication_frequency.value}"
    )

    text = await generate_with_retry(app.state.client, prompt)
    if text is None:
        return {
            "status": "fallback",
            "ai_first_aid_recommendation": FALLBACK_TIP,
        }

    return {
        "status": "success",
        "ai_first_aid_recommendation": text,
    }


@app.get("/")
def home():
    return {"message": "Backend is running!"}