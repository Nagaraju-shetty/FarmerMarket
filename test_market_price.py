
import requests

url = "https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070"

params = {
    "api-key": "579b464db66ec23bdd000001cdd3946e44ce4aad7209ff7b23ac571b",
    "format": "json",
    "limit": 1,
}

headers = {
    "User-Agent": "Mozilla/5.0 FarmerMarket/1.0",
    "Accept": "application/json",
}

try:
    response = requests.get(
        url,
        params=params,
        headers=headers,
        timeout=(10, 20),
    )

    print("HTTP status:", response.status_code)
    print("Response:", response.text[:2000])

except requests.RequestException as error:
    print("API connection failed:", error)
