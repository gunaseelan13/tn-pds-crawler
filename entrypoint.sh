#!/bin/bash
set -e

# Create cron job file
echo "# Run crawler job every day at 7:53 PM IST (14:23 UTC)"
echo "23 14 * * * cd /app && python /app/crawai_pds_selenium.py --shop-list-json /app/shop_list.json --output-json /app/data/shop_status_results.json >> /app/data/crawler.log 2>&1" > /etc/cron.d/crawler-cron

# Give execution rights to the cron job
chmod 0644 /etc/cron.d/crawler-cron

# Apply cron job
crontab /etc/cron.d/crawler-cron

# Create the log file to be able to run tail
touch /app/data/crawler.log

# Run the crawler once at startup
echo "Running crawler at startup..."
python /app/crawai_pds_selenium.py --shop-list-json /app/shop_list.json --output-json /app/data/shop_status_results.json

# Start cron daemon
echo "Starting cron daemon..."
cron -f
