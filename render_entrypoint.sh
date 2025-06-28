#!/bin/bash
set -e

# Create data directory if it doesn't exist
mkdir -p /app/data

# Set up cron job
echo "# Run crawler job every day at 7:58 PM IST (14:28 UTC)" > /etc/cron.d/crawler-cron
echo "28 14 * * * cd /app && python /app/crawai_pds_selenium.py --shop-list-json /app/shop_list.json --output-json /app/data/shop_status_results.json >> /app/data/crawler.log 2>&1" >> /etc/cron.d/crawler-cron

# Give execution rights to the cron job
chmod 0644 /etc/cron.d/crawler-cron

# Apply cron job
crontab /etc/cron.d/crawler-cron

# Start cron daemon in background
cron

# Run the crawler once at startup if needed
if [ ! -f /app/data/shop_status_results.json ]; then
  echo "Running crawler at startup..."
  python /app/crawai_pds_selenium.py --shop-list-json /app/shop_list.json --output-json /app/data/shop_status_results.json &
fi

# Start the web server
echo "Starting web server..."
exec gunicorn app:app --bind 0.0.0.0:$PORT --log-file -
