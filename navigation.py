"""Stepped-care router. A plain rules table, not AI, so every suggestion can be explained."""

from resources import DIRECTORY_NOTE, TIERS

# Lightest safe option first. Higher bands start with more intensive care.
BAND_TO_TIERS = {
    "minimal": ["self_help"],
    "mild": ["self_help", "community"],
    "moderate": ["primary_care", "tele_mental_health", "community"],
    "moderately severe": ["specialist", "tele_mental_health", "primary_care"],
    "severe": ["specialist", "tele_mental_health"],
}


def build_support_plan(band: str, region: str, crisis_flag: bool, urgent: bool) -> dict:
    if crisis_flag:
        return {
            "rationale": (
                "You told us about thoughts of harming yourself. Talking to a trained "
                "person now comes before anything else. The options below are for after."
            ),
            "tiers": [],
            "directory_note": DIRECTORY_NOTE,
            "offer_human": True,
        }

    tiers = []
    for tier_id in BAND_TO_TIERS[band]:
        t = TIERS[tier_id]
        tiers.append({
            "id": tier_id,
            "label": t["label"],
            "level": t["level"],
            "eligibility": t["eligibility"],
            "what_happens": t["what_happens"],
            "items": t["items"][region],
        })

    first = tiers[0]["label"].lower()
    return {
        "rationale": (
            f"Your score is in the {band} range. We suggest starting with {first}, "
            "the lightest option that is still a safe fit for that range. "
            "You choose what suits you, and a licensed professional makes any treatment decision."
        ),
        "tiers": tiers,
        "directory_note": DIRECTORY_NOTE,
        "offer_human": urgent,
    }