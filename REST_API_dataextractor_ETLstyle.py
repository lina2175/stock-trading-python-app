# Imports for CSV export, HTTP requests, request pacing, and environment settings.
import csv
import time
import requests
import dotenv
import os

from dotenv import load_dotenv
# Load .env settings using dotenv's default file discovery.
load_dotenv()

# Read the API credential and set the maximum records requested per page.
API_KEY = os.getenv("API_KEY")
limit = 1000
url = f"https://api.massive.com/v3/reference/tickers?market=stocks&active=true&order=asc&limit={limit}&sort=ticker&apiKey={API_KEY}"
# Extract: download the first page of active stock tickers sorted by symbol.
response = requests.get(url)
tickers = []
data = response.json()

# Collect each record from the first page in the ticker list.
for ticker in data['results'] :
    tickers.append(ticker)

# Follow pagination links until all pages have been collected.
while 'next_url' in data:
    print('requesting next page', data['next_url'])

    # Pause between requests to reduce the request rate.
    time.sleep(13)

    response = requests.get(data['next_url'] + f"&apiKey={API_KEY}")

    data = response.json()

    for ticker in data['results']:
        tickers.append(ticker)

# This example defines CSV column names and order; it is not written as a row.
example_ticker = {'ticker': 'ZWS',
    'name': 'Zurn Elkay Water Solutions Corporation',
    'market': 'stocks',
    'locale': 'us', 
    'primary_exchange': 'XNYS',
    'type': 'CS', 
    'active': True, 
    'currency_name': 'usd', 'cik': '0001439288', 
    'composite_figi': 'BBG000H8R0N8', 
    'share_class_figi': 'BBG001T36GB5', 
    'last_updated_utc': '2026-10-04T06:10:29.257907156Z'}

# Load: overwrite the CSV in the current working directory with headers and records.
# Ignore API fields outside the chosen columns; missing fields are written as blanks.
with open("tickers.csv", "w", newline="", encoding="utf-8") as csv_file:
    writer = csv.DictWriter(
        csv_file, fieldnames=list(example_ticker), extrasaction="ignore"
    )
    writer.writeheader()
    writer.writerows(tickers)

# Report how many records were exported.
print(f"Wrote {len(tickers)} tickers to tickers.csv")
