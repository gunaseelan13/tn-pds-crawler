FROM python:3.9-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV DISPLAY=:99

# Install Chrome, ChromeDriver, and other dependencies
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    cron \
    xvfb \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    xdg-utils \
    && wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create data directory
RUN mkdir -p /app/data

# Set up cron job to run crawler at 11:55 PM IST (18:25 UTC)
RUN echo "25 18 * * * cd /app && python /app/crawai_pds_selenium.py --shop-list-json /app/shop_list.json --output-json /app/data/shop_status_results.json >> /app/data/cron.log 2>&1" > /etc/cron.d/crawler-cron \
    && chmod 0644 /etc/cron.d/crawler-cron \
    && crontab /etc/cron.d/crawler-cron

# Install ChromeDriver
RUN apt-get update && apt-get install -y unzip \
    && CHROME_VERSION=$(google-chrome --version | awk '{print $3}' | cut -d. -f1) \
    && CHROMEDRIVER_VERSION=$(wget -qO- "https://chromedriver.storage.googleapis.com/LATEST_RELEASE_${CHROME_VERSION}") \
    && wget -q "https://chromedriver.storage.googleapis.com/${CHROMEDRIVER_VERSION}/chromedriver_linux64.zip" \
    && unzip chromedriver_linux64.zip -d /usr/local/bin/ \
    && chmod +x /usr/local/bin/chromedriver \
    && rm chromedriver_linux64.zip \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create entrypoint script
RUN echo '#!/bin/bash\n\
# Create data directory if it does not exist\n\
mkdir -p /app/data\n\
\n\
# Start Xvfb for headless browser\n\
Xvfb :99 -screen 0 1280x1024x24 > /dev/null 2>&1 &\n\
sleep 1\n\
\n\
# Start cron service\n\
/etc/init.d/cron start || service cron start || echo "Could not start cron"\n\
\n\
# Run crawler once at startup with explicit headless mode\n\
python /app/crawai_pds_selenium.py --shop-list-json /app/shop_list.json --output-json /app/data/shop_status_results.json --headless &\n\
\n\
# Start Flask web server\n\
exec gunicorn --bind 0.0.0.0:$PORT app:app\n' > /app/entrypoint.sh \
    && chmod +x /app/entrypoint.sh

# Expose the port the app runs on
ENV PORT=8080
EXPOSE 8080

# Run entrypoint script
CMD ["/app/entrypoint.sh"]
