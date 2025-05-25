import json
import os
from io import StringIO
from datetime import datetime
import pandas as pd
import pika
from google.cloud import storage
from flask import Flask
from threading import Thread
from prometheus_client import start_http_server, Counter

# === Config ===
project_id = os.getenv("PROJECT_ID", "hygiene-prediction-434")
raw_bucket = os.getenv("RAW_BUCKET", "prometheus-grafana-demo-raw")
clean_bucket = os.getenv("CLEAN_BUCKET", "prometheus-grafana-demo-clean")
credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
rabbit_url = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")

# === Prometheus Metric ===
messages_processed = Counter("cleaner_messages_total", "Total messages processed by the cleaner")

# === Connect to GCS ===
storage_client = storage.Client.from_service_account_json(credentials_path)
raw = storage_client.bucket(raw_bucket)
clean = storage_client.bucket(clean_bucket)

def log(message):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}", flush=True)

# === Flask app for /health ===
app = Flask(__name__)

@app.route("/health")
def health():
    return {"status": "ok"}, 200

def start_health_server():
    log("🌐 Starting /health endpoint on port 8000")
    app.run(host="0.0.0.0", port=8000)

# === Consume from RabbitMQ ===
def callback(ch, method, properties, body):
    try:
        msg = json.loads(body)
        filename = msg["filename"]
        date = msg["date"]
        log(f"🔔 Received message for: {filename}")

        raw_blob = raw.blob(filename)
        raw_data = raw_blob.download_as_text()
        df = pd.read_json(StringIO(raw_data))
        log(f"📦 Raw file loaded: {filename} with {len(df)} rows")

        df_clean = pd.json_normalize(df).dropna().drop_duplicates()
        log(f"🧹 Cleaned data: {len(df_clean)} rows remaining")

        clean_path = f"{date}/cleaned_{os.path.basename(filename)}"
        clean_blob = clean.blob(clean_path)
        clean_blob.upload_from_string(df_clean.to_json(orient="records"), content_type="application/json")

        log(f"✅ Cleaned file written to GCS: {clean_path}")
        messages_processed.inc()  # Prometheus metric increment
        ch.basic_ack(delivery_tag=method.delivery_tag)

    except Exception as e:
        log(f"❌ Error processing message: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

def start_consumer():
    try:
        connection = pika.BlockingConnection(pika.URLParameters(rabbit_url))
        channel = connection.channel()
        channel.queue_declare(queue="cleaning-jobs", durable=True)
        channel.basic_consume(queue="cleaning-jobs", on_message_callback=callback)

        log("🧼 Cleaner is waiting for messages...")
        channel.start_consuming()

    except Exception as e:
        log(f"❌ Failed to start cleaner: {e}")

if __name__ == "__main__":
    # Start Prometheus /metrics server in the background with logging
    def start_prometheus():
        log("📊 Starting Prometheus metrics server on port 9100")
        start_http_server(9100)

    Thread(target=start_prometheus, daemon=True).start()

    # Start health check server in background
    Thread(target=start_health_server, daemon=True).start()

    # Start RabbitMQ consumer (this blocks)
    start_consumer()


