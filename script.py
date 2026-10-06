# Imports for CSV export, HTTP requests, request pacing, environment settings,
# SQL name validation, filesystem paths, and snapshot dates.
import csv
import time
import requests
import dotenv
import os
import re
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Resolve paths relative to this script and load credentials from its .env file.
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# Read the API credential; limit sets the number of tickers requested per page.
API_KEY = os.getenv("API_KEY")
limit = 1000
def upload_csv_to_snowflake(csv_path):
    """Replace the destination snapshot; roll back all row changes on failure."""
    import snowflake.connector

    # Gather required Snowflake settings and reject missing values.
    settings = {
        name: os.getenv("SNOWFLAKE_" + name.upper())
        for name in ("account", "user", "password", "warehouse", "database", "schema")
    }
    missing = ["SNOWFLAKE_" + name.upper() for name, value in settings.items() if not value]
    if missing:
        raise ValueError("Set these values in .env: " + ", ".join(missing))
    # Use an optional role instead of the user's default role.
    if os.getenv("SNOWFLAKE_ROLE"):
        settings["role"] = os.environ["SNOWFLAKE_ROLE"]

    # Validate and quote the destination table name before including it in SQL.
    table = os.getenv("SNOWFLAKE_TABLE", "STOCK_TICKERS")
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", table):
        raise ValueError("SNOWFLAKE_TABLE must be a simple table name (no dots or spaces)")
    table = '"' + table.upper() + '"'
    # Validate CSV headers and convert empty cells to SQL NULL values.
    with open(csv_path, newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        columns = reader.fieldnames
        if not columns or any(not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", col) for col in columns):
            raise ValueError("CSV headers must be valid column names")
        rows = [tuple(row[col] or None for col in columns) for row in reader]
    # Preserve existing database data if the CSV contains no records.
    if not rows:
        raise ValueError("CSV is empty; keeping existing Snowflake data")

    # Prepare SQL column names, definitions, and placeholders for row values.
    column_sql = ", ".join('"' + col.upper() + '"' for col in columns)
    # VARCHAR preserves identifiers, leading zeros, and the source timestamp text.
    definitions = ", ".join('"' + col.upper() + '" VARCHAR' for col in columns)
    placeholders = ", ".join(["%s"] * len(columns))
    print(f"Uploading {len(rows)} tickers to Snowflake {table}...", flush=True)
    # Open the database connection; finally ensures it closes even on failure.
    connection = snowflake.connector.connect(**settings)
    try:
        with connection.cursor() as cursor:
            # Select explicitly: connection setup can leave no active warehouse.
            cursor.execute("USE WAREHOUSE IDENTIFIER(%s)", (settings["warehouse"],))
            cursor.execute("SELECT CURRENT_WAREHOUSE()")
            active_warehouse = cursor.fetchone()[0]
            if not active_warehouse:
                raise RuntimeError("No active Snowflake warehouse; check SNOWFLAKE_WAREHOUSE and role permissions")
            print(f"Using Snowflake warehouse: {active_warehouse}", flush=True)
            cursor.execute(f"CREATE TABLE IF NOT EXISTS {table} ({definitions})")
            # Replace all rows in one transaction, committing only after all batches succeed.
            cursor.execute("BEGIN")
            try:
                cursor.execute(f"DELETE FROM {table}")
                # Insert up to 1,000 records per batch.
                for start in range(0, len(rows), 1000):
                    cursor.executemany(
                        f"INSERT INTO {table} ({column_sql}) VALUES ({placeholders})",
                        rows[start:start + 1000],
                    )
                connection.commit()
            except Exception:
                # Undo row changes on failure and pass the error to the caller.
                connection.rollback()
                raise
    finally:
        connection.close()
    print(f"Loaded {len(rows)} tickers into Snowflake {table}", flush=True)

# Main ETL job: download tickers, add the snapshot date, export CSV, and upload.
def run_stock_job():
    print("Starting stock ticker download...", flush=True)
    # Use the date on this machine to label this snapshot.
    DS = datetime.now().strftime('%Y-%m-%d')
    url = f"https://api.massive.com/v3/reference/tickers?market=stocks&active=true&order=asc&limit={limit}&sort=ticker&apiKey={API_KEY}"
    # Download the first page and stop if the API returns an HTTP error.
    response = requests.get(url)
    response.raise_for_status()
    tickers = []
    data = response.json()

    # Collect the first page's records in a list.
    for ticker in data['results'] :
        tickers.append(ticker)

    # Follow pagination links until there are no more pages.
    while 'next_url' in data:
        print('requesting next page', data['next_url'])

        # Pause between requests to reduce the request rate.
        time.sleep(13)

        response = requests.get(data['next_url'] + f"&apiKey={API_KEY}")
        response.raise_for_status()

        data = response.json()

        for ticker in data['results']:
            tickers.append(ticker)

    # Add the same snapshot-date column to every downloaded record.
    for ticker in tickers:
        ticker["ds"] = DS

    # This example defines CSV column names and order; it is not an output row.
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
        'last_updated_utc': '2026-10-04T06:10:29.257907156Z',
        'ds': DS}

    # Overwrite the CSV with headers and records, ignoring fields outside the schema.
    csv_path = BASE_DIR / "tickers.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(
            csv_file, fieldnames=list(example_ticker), extrasaction="ignore"
        )
        writer.writeheader()
        writer.writerows(tickers)

    print(f"Wrote {len(tickers)} tickers to tickers.csv")
    # Replace the Snowflake snapshot with the completed CSV.
    upload_csv_to_snowflake(csv_path)


# Run directly when launched; importing this module only defines the job.
if __name__ == "__main__":
    run_stock_job()
