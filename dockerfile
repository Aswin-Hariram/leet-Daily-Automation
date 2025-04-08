FROM python:3.10-slim

# Install Chrome dependencies and tools
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    xvfb \
    xclip \
    unzip \
    curl \
    git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Chrome
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the script
COPY leetcode_bot.py .
COPY .env .

# Create directory for screenshots
RUN mkdir -p screenshots

# Set display for Xvfb
ENV DISPLAY=:99

# Create entrypoint script
RUN echo '#!/bin/bash\nXvfb :99 -screen 0 1920x1080x24 -ac &\npython leetcode_bot.py' > /app/entrypoint.sh \
    && chmod +x /app/entrypoint.sh

# Run the bot
ENTRYPOINT ["/app/entrypoint.sh"]