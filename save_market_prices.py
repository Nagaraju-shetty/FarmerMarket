
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "farmer_market.settings")
django.setup()

from products.market_api import save_karnataka_prices

count = save_karnataka_prices(limit=100)

print(f"\nSuccessfully saved or updated {count} mandi price records.")
