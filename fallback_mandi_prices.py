
from datetime import date

# Secondary-source reference prices.
# These are NOT direct records from the official API.
# Verify the source and date before displaying them as current.

FALLBACK_MANDI_PRICES = {
    "Orange": {
        "price_per_kg": 38.00,
        "market_name": "Secondary-source reference",
        "location": "Karnataka",
        "recorded_date": date(2026, 10, 20),
        "source_type": "Secondary-source reference",
    },
    "Papaya": {
        "price_per_kg": 13.00,
        "market_name": "Secondary-source reference",
        "location": "Karnataka",
        "recorded_date": date(2026, 10, 20),
        "source_type": "Secondary-source reference",
    },
    "Wheat": {
        "price_per_kg": 36.53,
        "market_name": "Secondary-source reference",
        "location": "Karnataka",
        "recorded_date": date(2026, 10, 20),
        "source_type": "Secondary-source reference",
    },
}

# Strawberry remains unavailable until a reliable mandi price is verified.
