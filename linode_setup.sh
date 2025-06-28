#!/bin/bash
# Setup script for TN PDS Crawler on Linode Nanode VPS
# This script should be run as root or with sudo privileges

set -e  # Exit on any error

echo "Setting up TN PDS Crawler on Linode Nanode VPS..."

# Update system packages
echo "Updating system packages..."
apt-get update
apt-get upgrade -y

# Install Python and pip
echo "Installing Python and pip..."
apt-get install -y python3 python3-pip python3-venv

# Install Chrome dependencies
echo "Installing Chrome and dependencies..."
apt-get install -y wget gnupg xvfb fonts-liberation libasound2 libatk-bridge2.0-0 \
    libatk1.0-0 libatspi2.0-0 libcups2 libdbus-1-3 libdrm2 libgbm1 \
    libgtk-3-0 libnspr4 libnss3 libxcomposite1 libxdamage1 libxfixes3 \
    libxkbcommon0 libxrandr2 xdg-utils

# Install Chrome
wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add -
echo "deb http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list
apt-get update
apt-get install -y google-chrome-stable

# Create app directory
echo "Creating application directory..."
mkdir -p /opt/tn-pds-crawler
mkdir -p /opt/tn-pds-crawler/data

# Copy application files (assuming you've uploaded them to /tmp/tn-pds-crawler)
echo "Copying application files..."
if [ -d "/tmp/tn-pds-crawler" ]; then
    cp -r /tmp/tn-pds-crawler/* /opt/tn-pds-crawler/
else
    echo "Please upload the application files to /tmp/tn-pds-crawler first"
    exit 1
fi

# Set up Python virtual environment
echo "Setting up Python virtual environment..."
cd /opt/tn-pds-crawler
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Create data directory with proper permissions
echo "Setting up data directory..."
mkdir -p /opt/tn-pds-crawler/data
chmod 755 /opt/tn-pds-crawler/data

# Set up cron job to run crawler at 7:58 PM IST (14:28 UTC)
echo "Setting up cron job..."
(crontab -l 2>/dev/null || echo "") | grep -v "crawai_pds_selenium.py" | { cat; echo "28 14 * * * cd /opt/tn-pds-crawler && /opt/tn-pds-crawler/venv/bin/python /opt/tn-pds-crawler/crawai_pds_selenium.py --shop-list-json /opt/tn-pds-crawler/shop_list.json --output-json /opt/tn-pds-crawler/data/shop_status_results.json --headless >> /opt/tn-pds-crawler/data/cron.log 2>&1"; } | crontab -

# Create systemd service file for the web server
echo "Creating systemd service..."
cat > /etc/systemd/system/tn-pds-crawler.service << EOF
[Unit]
Description=TN PDS Crawler Web Service
After=network.target

[Service]
User=root
WorkingDirectory=/opt/tn-pds-crawler
Environment="PATH=/opt/tn-pds-crawler/venv/bin"
Environment="PYTHONUNBUFFERED=1"
Environment="DISPLAY=:99"
ExecStartPre=/usr/bin/Xvfb :99 -screen 0 1280x1024x24 -ac &
ExecStart=/opt/tn-pds-crawler/venv/bin/gunicorn --bind 0.0.0.0:8080 app:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Enable and start the service
echo "Enabling and starting the service..."
systemctl daemon-reload
systemctl enable tn-pds-crawler.service
systemctl start tn-pds-crawler.service

# Run the crawler once at setup
echo "Running the crawler for the first time..."
cd /opt/tn-pds-crawler
Xvfb :99 -screen 0 1280x1024x24 -ac &
export DISPLAY=:99
sleep 2
/opt/tn-pds-crawler/venv/bin/python /opt/tn-pds-crawler/crawai_pds_selenium.py --shop-list-json /opt/tn-pds-crawler/shop_list.json --output-json /opt/tn-pds-crawler/data/shop_status_results.json --headless

echo "Setup complete! The TN PDS Crawler is now running on your Linode Nanode VPS."
echo "You can access the web interface at http://YOUR_SERVER_IP:8080"
echo "The crawler will run daily at 7:58 PM IST (14:28 UTC)"
