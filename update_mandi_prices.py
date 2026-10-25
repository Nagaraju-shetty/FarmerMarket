
import os
import sys
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent
os.chdir(BASE_DIR)
sys.path.insert(0, str(BASE_DIR))

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "farmer_market.settings",
)

import django
django.setup()

from products.market_api import save_karnataka_prices

log_file = BASE_DIR / "mandi_update.log"

try:
    count = save_karnataka_prices(limit=100)

    with log_file.open("a", encoding="utf-8") as log:
        log.write(
            f"{datetime.now():%Y-%m-%d %H:%M:%S} "
            f"- Update completed. Records saved or updated: {count}\n"
        )

except Exception as error:
    with log_file.open("a", encoding="utf-8") as log:
        log.write(
            f"{datetime.now():%Y-%m-%d %H:%M:%S} "
            f"- Update failed: {error}\n"
        )
    raise
