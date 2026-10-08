# Paper trading bot + dashboard. The bot runs in a background thread of the
# web process, so this must stay at ONE gunicorn worker.
FROM python:3.11-slim
WORKDIR /app
COPY requirements-dashboard.txt .
RUN pip install --no-cache-dir -r requirements-dashboard.txt
COPY . .
ENV STATE_DIR=/state \
    AUTOSTART=1 \
    ALLOW_CONTROL=0 \
    CHECK_INTERVAL=300
VOLUME ["/state"]
EXPOSE 8000
CMD ["gunicorn", "-w", "1", "--threads", "4", "--timeout", "60", "-b", "0.0.0.0:8000", "--chdir", "frontend", "app:app"]
