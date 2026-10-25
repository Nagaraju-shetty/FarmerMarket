
import os
import requests
from datetime import datetime
from decimal import Decimal
from dotenv import load_dotenv
from django.utils import timezone

load_dotenv()

API_URL = "https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070"


def fetch_karnataka_prices(commodity=None, district=None, limit=100):
    """Fetch current mandi prices for Karnataka."""
    api_key = os.getenv("DATA_GOV_API_KEY")

    if not api_key:
        raise ValueError("DATA_GOV_API_KEY is missing from .env.")

    params = {
    "api-key": api_key,
    "format": "json",
    "limit": limit,
    "filters[state]": "Karnataka",
}

    if commodity:
        params["filters[commodity]"] = commodity

    if district:
        params["filters[district]"] = district

    response = requests.get(API_URL, params=params, timeout=(15, 60))
    response.raise_for_status()
    return response.json().get("records", [])





def save_karnataka_prices(limit=100):
    """Fetch and save actual Karnataka mandi prices matching website products."""
    from products.models import Product, MarketPrice

    commodity_aliases = {
        # Vegetables
        "Tomato": ["Tomato"],
        "Potato": ["Potato"],
        "Onion": ["Onion"],
        "Carrot": ["Carrot"],
        "Cabbage": ["Cabbage"],
        "Spinach": ["Spinach"],
        "Brinjal": ["Brinjal"],
        "Green Beans": ["Beans"],
        "Cauliflower": ["Cauliflower"],

        # Fruits
        "Apple": ["Apple"],
        "Banana": ["Banana"],
        "Orange": ["Orange"],
        "Mango": ["Mango"],
        "Grapes": ["Grapes"],
        "Papaya": ["Papaya"],
        "Watermelon": ["Water Melon", "Watermelon"],
        "Pomegranates": ["Pomegranate", "Pomegranates"],
        "Guava": ["Guava"],
        "Pineapple": ["Pineapple"],
        "Strawberry": ["Strawberry"],

        # Grains
        "Rice": ["Rice"],
        "Wheat": ["Wheat"],
        "Ragi": ["Ragi(Finger Millet)", "Ragi"],
        "Maize": ["Maize"],
    }

    product_names = (
        Product.objects.filter(available=True)
        .values_list("name", flat=True)
        .distinct()
    )

    saved_count = 0

    for product_name in product_names:
        official_names = commodity_aliases.get(
            product_name, [product_name]
        )

        for official_name in official_names:
            try:
                records = fetch_karnataka_prices(
                    commodity=official_name,
                    limit=limit,
                )
            except Exception as error:
                print(f"Could not fetch {official_name}: {error}")
                continue

            for record in records:
                if (
                    record.get("commodity", "").strip().casefold()
                    != official_name.strip().casefold()
                ):
                    continue

                try:
                    recorded_date = datetime.strptime(
                        record["arrival_date"], "%d/%m/%Y"
                    ).date()

                    MarketPrice.objects.update_or_create(
                        product_name=product_name,
                        market_name=record["market"],
                        location=record["district"],
                        recorded_date=recorded_date,
                        defaults={
                            "min_price": Decimal(str(record["min_price"])),
                            "max_price": Decimal(str(record["max_price"])),
                            "modal_price": Decimal(str(record["modal_price"])),
                        },
                    )

                    saved_count += 1

                except (KeyError, ValueError, TypeError) as error:
                    print("Skipping invalid market-price record:", error)

        print(f"Checked mandi prices for: {product_name}")

    return saved_count
