
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "farmer_market.settings")
django.setup()

from products.market_api import fetch_karnataka_prices

records = fetch_karnataka_prices(limit=100)

print("Total records returned:", len(records))
print("\nAvailable Karnataka commodities:\n")

commodities = sorted({
    record.get("commodity", "")
    for record in records
    if record.get("commodity")
})

for commodity in commodities:
    print(commodity)
