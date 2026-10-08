# ChainProof dashboard: verifies the 30 on-chain commitments live from Sepolia.
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt flask gunicorn
COPY . .
EXPOSE 8000
# One worker with threads: the app is I/O bound (RPC calls), and one process
# keeps memory low on a small server.
CMD ["gunicorn", "-w", "1", "--threads", "4", "--timeout", "120", "-b", "0.0.0.0:8000", "--chdir", "dashboard", "dashboard_app:app"]
