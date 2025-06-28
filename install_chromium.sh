#!/bin/bash
# Script to install Chromium and ChromeDriver on Linode server

echo "Installing Chromium and ChromeDriver..."

# Update package lists
apt-get update

# Install Chromium browser
apt-get install -y chromium-browser

# Verify Chromium installation
CHROMIUM_VERSION=$(chromium-browser --version || chromium --version)
echo "Chromium version: $CHROMIUM_VERSION"

# Install ChromeDriver
apt-get install -y chromium-chromedriver

# Verify ChromeDriver installation
echo "ChromeDriver installed at: $(which chromedriver)"
echo "ChromeDriver version: $(chromedriver --version)"

# Create symbolic links if needed
if [ ! -f /usr/bin/chromedriver ]; then
    echo "Creating symbolic link for ChromeDriver in /usr/bin/"
    ln -s $(which chromedriver) /usr/bin/chromedriver
fi

echo "Installation complete!"
echo "You can now run the crawler with:"
echo "cd /root/tn-pds-crawler && python crawai_pds_selenium.py --shop-list-json data/shop_list.json --output-json data/shop_status_results.json --headless"
