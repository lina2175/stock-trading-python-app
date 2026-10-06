# Imports for scheduling, polling delays, the stock job, and log timestamps.
import schedule 
import time
from script import run_stock_job
from datetime import datetime

# Print a heartbeat to show that the scheduler is running.
def basic_job():
    print("job started at:", datetime.now())

# Register a heartbeat every minute and a daily stock job at 09:00.
# The daily time uses the timezone of the machine running this script.
schedule.every().minute.do(basic_job)
schedule.every().day.at("09:00").do(run_stock_job)

# Download and upload to Snowflake once before entering the scheduling loop.
run_stock_job()  # Download once immediately at startup.

# Check for due jobs once per second while keeping this process alive.
# Jobs run synchronously, so a long stock job delays other scheduled jobs.
while True:
    schedule.run_pending()
    time.sleep(1)
