"""Crisis resources by region.

VERIFY EVERY NUMBER with an official source before any demo or release.
Milestone 2 will replace this with a full, verified resource directory.
"""

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