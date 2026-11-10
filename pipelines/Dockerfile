FROM python:3.11
LABEL authors="Nathan"

# Cron Install
RUN apt-get update && apt-get install -y cron && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# Copy & Install crontab
COPY crontab /etc/cron.d/nhl-pipeline
RUN chmod 0644 /etc/cron.d/nhl-pipeline && \
    crontab /etc/cron.d/nhl-pipeline && \
    mkdir -p /var/log

# Start cron in foreground
CMD ["cron", "-f"]
