"""Validated self-assessment instruments and scoring.

PHQ-9 (mood) and GAD-7 (anxiety) are widely used screening questionnaires
(Spitzer, Kroenke, Williams et al.) that are free to use. They screen for
symptoms. They do not diagnose. Do not reword the questions or the options.
"""

from enum import Enum


class InstrumentId(str, Enum):
    phq9 = "phq9"
    gad7 = "gad7"


RESPONSE_OPTIONS = [
    {"value": 0, "label": "Not at all"},
    {"value": 1, "label": "Several days"},
    {"value": 2, "label": "More than half the days"},
    {"value": 3, "label": "Nearly every day"},
]

INSTRUMENTS = {
    "phq9": {
        "name": "PHQ-9",
        "title": "Mood check-in",
        "intro": (
            "Over the last 2 weeks, how often have you been bothered by "
            "any of the following problems?"
        ),
        "questions": [
            "Little interest or pleasure in doing things",
            "Feeling down, depressed, or hopeless",
            "Trouble falling or staying asleep, or sleeping too much",
            "Feeling tired or having little energy",
            "Poor appetite or overeating",
            "Feeling bad about yourself, or that you are a failure or have "
            "let yourself or your family down",
            "Trouble concentrating on things, such as reading the newspaper "
            "or watching television",
            "Moving or speaking so slowly that other people could have noticed? "
            "Or the opposite, being so fidgety or restless that you have been "
            "moving around a lot more than usual",
            "Thoughts that you would be better off dead, or of hurting "
            "yourself in some way",
        ],
        # (highest score in band, band label)
        "bands": [(4, "minimal"), (9, "mild"), (14, "moderate"),
                  (19, "moderately severe"), (27, "severe")],
        "cutoff": 10,
        "self_harm_item": 8,  # zero-based index of question 9
    },
    "gad7": {
        "name": "GAD-7",
        "title": "Anxiety check-in",
        "intro": (
            "Over the last 2 weeks, how often have you been bothered by "
            "the following problems?"
        ),
        "questions": [
            "Feeling nervous, anxious, or on edge",
            "Not being able to stop or control worrying",
            "Worrying too much about different things",
            "Trouble relaxing",
            "Being so restless that it is hard to sit still",
            "Becoming easily annoyed or irritable",
            "Feeling afraid, as if something awful might happen",
        ],
        "bands": [(4, "minimal"), (9, "mild"), (14, "moderate"), (21, "severe")],
        "cutoff": 10,
        "self_harm_item": None,
    },
}

WHAT_IT_MEANS = (
    "This score reflects how often you reported these symptoms over the last "
    "2 weeks. A score that rises over time is a useful reason to talk to someone."
)

WHAT_IT_DOES_NOT_MEAN = (
    "This is a screening result, not a diagnosis. Only a licensed healthcare "
    "professional can diagnose or decide on treatment. A low score does not mean "
    "you are fine if you feel unwell, and a high score does not mean something "
    "is wrong with you."
)

NEXT_STEP = {
    "minimal": "Few or no symptoms right now. Keep up what helps you and check in again in a few weeks.",
    "mild": "Some symptoms are present. Routine, rest and talking with people you trust can help. Check in again in about 2 weeks.",
    "moderate": "Symptoms may be affecting your days. Consider speaking with a primary care doctor or a counsellor.",
    "moderately severe": "Symptoms are significant. We recommend speaking with a licensed professional soon.",
    "severe": "Symptoms are severe. Please speak with a licensed professional as soon as you can.",
}

CRISIS_NEXT_STEP = (
    "You reported thoughts of harming yourself. Please contact a trained person "
    "now using the contacts below. A human, not this app, should be your next step."
)


def public_definitions() -> dict:
    """Question text and metadata for the frontend (no scoring rules)."""
    return {
        "options": RESPONSE_OPTIONS,
        "instruments": {
            key: {
                "name": inst["name"],
                "title": inst["title"],
                "intro": inst["intro"],
                "questions": inst["questions"],
                "max_score": len(inst["questions"]) * 3,
                "cutoff": inst["cutoff"],
            }
            for key, inst in INSTRUMENTS.items()
        },
    }


def score(instrument: InstrumentId, answers: list[int]) -> dict:
    """Score one questionnaire. Raises ValueError on invalid input."""
    inst = INSTRUMENTS[instrument.value]
    if len(answers) != len(inst["questions"]):
        raise ValueError(f"{inst['name']} needs {len(inst['questions'])} answers.")
    if any(a not in (0, 1, 2, 3) for a in answers):
        raise ValueError("Each answer must be between 0 and 3.")

    total = sum(answers)
    band = next(label for limit, label in inst["bands"] if total <= limit)

    item = inst["self_harm_item"]
    crisis_flag = item is not None and answers[item] > 0
    urgent = crisis_flag or band == "severe"

    return {
        "instrument": instrument.value,
        "instrument_name": inst["name"],
        "total": total,
        "max_score": len(inst["questions"]) * 3,
        "band": band,
        "what_it_means": WHAT_IT_MEANS,
        "what_it_does_not_mean": WHAT_IT_DOES_NOT_MEAN,
        "next_step": CRISIS_NEXT_STEP if crisis_flag else NEXT_STEP[band],
        "crisis_flag": crisis_flag,
        "urgent": urgent,
    }