FROM python:3.9-slim

# Install Chrome dependencies and cron
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    gnupg \
    unzip \
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
    cron \
    && rm -rf /var/lib/apt/lists/*

# Install Chrome and ChromeDriver
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable chromium-driver \
    && ln -s /usr/lib/chromium/chromedriver /usr/local/bin/chromedriver \
    && rm -rf /var/lib/apt/lists/*

# Set up working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create data directory
RUN mkdir -p data

# Set environment variables for headless Chrome
ENV PYTHONUNBUFFERED=1
ENV DISPLAY=:99

# Set up cron job to run at 7:58 PM IST (14:28 UTC)
RUN echo "28 14 * * * cd /app && python /app/crawai_pds_selenium.py --shop-list-json /app/shop_list.json --output-json /app/data/shop_status_results.json >> /app/data/crawler.log 2>&1" > /etc/cron.d/crawler-cron \
    && chmod 0644 /etc/cron.d/crawler-cron \
    && crontab /etc/cron.d/crawler-cron

# Create a simple web server to keep the app running
RUN pip install --no-cache-dir flask gunicorn

# Copy the web server file
COPY app.py /app/app.py

# Default command (will be overridden by processes in fly.toml)
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:8080", "--workers", "1"]
