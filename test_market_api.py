
import os
import requests
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("DATA_GOV_API_KEY")

if not api_key:
    print("API key not found. Check your .env file.")
    raise SystemExit

url = "https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070"



params = {
    "api-key": api_key,
    "format": "json",
    "limit": 10,
    "filters[state.keyword]": "Karnataka",
}



try:
    
    response = requests.get(
    url,
    params=params,
    headers={"User-Agent": "Mozilla/5.0 FarmerMarket/1.0"},
    timeout=30,
)

    print("HTTP Status:", response.status_code)

    if response.ok:
        data = response.json()
        records = data.get("records", [])

        if records:
            print("Success! Mandi price data received.")
            for record in records:
                print(record)
        else:
            print("Request succeeded, but no matching records were returned.")
            print(data)
    else:
        print("API request failed. Response:")
        print(response.text[:1000])

except requests.RequestException as error:
    print("Connection error:", error)
