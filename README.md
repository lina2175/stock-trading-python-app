# Stock ticker data pipeline

Downloads active stock ticker reference data from Massive, saves it to `tickers.csv`, and uploads the snapshot to Snowflake.

## Setup

1. Install Python and the dependencies: `python -m pip install -r requirements.txt`.
2. Copy `.env.example` to `.env` and fill in your API and Snowflake settings.
3. Give your Snowflake role permission to use the configured warehouse, database, and schema, and create and update the destination table.

Keep `.env` private. Credentials and log files are excluded from Git.

## Run

To review the exported data, open `tickers.csv`. To query the table in Snowflake, open `linadata.sql`, select the database and schema containing `STOCK_TICKERS`, and run the query. The SQL file contains the query; the CSV contains the exported data.

- `python script.py`: download all ticker pages, add a snapshot date, write the CSV, and replace the Snowflake table's rows.
- `python scheduler.py`: run the job immediately and then daily at 09:00 in the machine's local timezone. Keep the process running for scheduled jobs to execute.
- `python REST_API_dataextractor_ETLstyle.py`: run the standalone CSV export without uploading to Snowflake. This version writes to the current working directory.

The main job overwrites `tickers.csv` and replaces the destination table's rows. If inserting rows fails, the database transaction rolls back. Requests pause for 13 seconds between pages.
