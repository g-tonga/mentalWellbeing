"""Crisis numbers and the stepped-care support directory.

VERIFY EVERYTHING before any demo or release.
Entries with verified=False are placeholders. A clinician or the service owner
must confirm each real service, its eligibility and its contact details.
"""

from enum import Enum


class Region(str, Enum):
    AE = "AE"
    KE = "KE"


DIRECTORY_NOTE = (
    "Demo directory. Entries marked as placeholders are not verified services. "
    "A clinician must review this list before any real use."
)

CRISIS_RESOURCES = {
    "AE": {
        "country": "United Arab Emirates",
        "emergency": [
            {"label": "Police and emergency", "number": "999"},  # VERIFY
            {"label": "Ambulance", "number": "998"},  # VERIFY
        ],
        "support": [
            {"label": "National mental health support line (800 HOPE)", "number": "8004673"},  # VERIFY
        ],
    },
    "KE": {
        "country": "Kenya",
        "emergency": [
            {"label": "Emergency services", "number": "999"},  # VERIFY
            {"label": "Emergency (mobile)", "number": "112"},  # VERIFY
        ],
        "support": [
            {"label": "Kenya Red Cross support line", "number": "1199"},  # VERIFY
        ],
    },
}


def _practice(name: str, description: str, how: str) -> dict:
    return {"kind": "practice", "name": name, "description": description, "how_to_reach": how}


def _service(name: str, description: str, how: str, verified: bool = False) -> dict:
    return {
        "kind": "service",
        "name": name,
        "description": description,
        "how_to_reach": how,
        "verified": verified,
    }


SELF_HELP = [
    _practice("Slow breathing", "Breathe in for 4 counts and out for 6. Repeat for about 5 minutes.", "Do it anywhere, right now."),
    _practice("Gentle movement", "A 10 to 20 minute walk outside, ideally in daylight.", "No equipment or booking needed."),
    _practice("A steady routine", "Keep similar sleep and wake times and limit screens before bed.", "Start tonight."),
    _practice("Reach out", "Tell one person you trust how you have been feeling.", "A call, message or visit all count."),
]

TIERS = {
    "self_help": {
        "label": "Self-help",
        "level": 1,
        "eligibility": "Anyone. No referral or booking needed.",
        "what_happens": "You use these on your own, at your own pace. Check in again in about 2 weeks to see if anything changed.",
        "items": {"AE": SELF_HELP, "KE": SELF_HELP},
    },
    "community": {
        "label": "Community support",
        "level": 2,
        "eligibility": "Anyone. Some groups ask you to register or have age or location limits.",
        "what_happens": "You meet others in a group setting. There is no clinical assessment, and you can leave any time.",
        "items": {
            "AE": [_service(
                "Peer support or community wellbeing group",
                "Group sessions run by community or faith organisations or a workplace wellbeing programme.",
                "Ask your community centre or workplace wellbeing team.",
            )],
            "KE": [
                _service(
                    "Community or faith-based support group",
                    "Group support run by community or faith organisations.",
                    "Ask your local community centre or place of worship.",
                ),
                _service(
                    "Befrienders Kenya (listening support)",
                    "Emotional support from trained volunteers.",
                    "Look up their current contact details before using.",
                ),
            ],
        },
    },
    "primary_care": {
        "label": "Primary care",
        "level": 3,
        "eligibility": "Open to anyone. Cost and booking depend on your insurance or the facility.",
        "what_happens": "A doctor or nurse talks with you, checks for physical causes and can refer you onward if needed.",
        "items": {
            "AE": [_service(
                "Licensed primary care clinic",
                "Any clinic licensed by your emirate's health authority.",
                "Ask your insurer for in-network clinics or search the regulator's facility list.",
            )],
            "KE": [_service(
                "Public or private health centre",
                "Ask for the mental health or counselling clinician.",
                "Visit your nearest health centre or call ahead to book.",
            )],
        },
    },
    "tele_mental_health": {
        "label": "Tele-mental health",
        "level": 3,
        "eligibility": "Needs a phone or internet connection. Some providers need insurance details or a referral.",
        "what_happens": "You have a video or phone session with a licensed counsellor or psychologist.",
        "items": {
            "AE": [_service(
                "Tele-mental health from a licensed provider",
                "Online counselling or psychology sessions.",
                "Ask your insurer or check the licensed provider list.",
            )],
            "KE": [_service(
                "Tele-counselling with a licensed counsellor or psychologist",
                "Online or phone sessions.",
                "Ask your health provider or look for a registered practitioner.",
            )],
        },
    },
    "specialist": {
        "label": "Specialist care",
        "level": 4,
        "eligibility": "Often needs a referral from a primary care doctor. Waiting times vary.",
        "what_happens": "A psychiatrist or clinical psychologist assesses you and agrees a care plan with you.",
        "items": {
            "AE": [_service(
                "Psychiatry or psychology specialist",
                "Usually reached through a primary care referral.",
                "Ask your primary care doctor for a referral.",
            )],
            "KE": [_service(
                "Specialist mental health service",
                "For example Mathari National Teaching and Referral Hospital in Nairobi, or a private psychiatrist.",
                "Ask your doctor for a referral and confirm current contact details first.",
            )],
        },
    },
}
