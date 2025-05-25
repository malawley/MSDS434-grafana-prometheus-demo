# Prometheus + Grafana Monitoring Pipeline Demo

## Project Title

Chicago Food Inspections Monitoring Demo: Extract, Clean, and Observe


Note: setup instructions for running this system are included in the appendix at the bottom of this file.

## System Architecture Overview

This project implements a containerized two-stage data pipeline, monitored via Prometheus + Grafana, and controlled via a Streamlit dashboard.

### Components

* Streamlit Control Dashboard: Launches extraction and cleaning jobs with user-specified parameters, acting as the control interface for the pipeline.
* Extractor Service: Fetches rows from the Chicago food inspections API and stores raw data in GCS.
* Cleaner Service: Processes raw data files by removing rows with missing values and redundancies.
* Message Broker (RabbitMQ): Decouples extractor from cleaner, carrying file-level messages.
* Prometheus: Scrapes metrics from extractor and cleaner services.
* Grafana: Displays job metrics in a real-time monitoring dashboard.

## Pipeline Flow

1. User Input via Streamlit:

   * Number of rows to extract (n)
   * Date (used as GCS prefix/folder name)

2. Extractor:

   * Reads last\_offset.txt from raw data bucket
   * Fetches n rows from API (in 1000-row chunks)
   * Writes files to gs\://prometheus-grafana-demo-raw/{date}/
   * Updates last\_offset.txt
   * For each written file, sends a RabbitMQ message containing the file path

3. Cleaner:

   * Listens for new file messages on RabbitMQ
   * Waits for GCS object availability if needed (with retries)
   * Cleans the file (drop missing/redundant values)
   * Writes cleaned file to gs\://prometheus-grafana-demo-clean/{date}/

## Dashboards

### 1. Control Dashboard (Streamlit)

* Role: Launch pipeline jobs
* Inputs:

  * Number of rows
  * Date string
* Actions:

  * Triggers extractor
  * Displays job response

### 2. Monitoring Dashboard (Grafana)

* Role: Visualize pipeline behavior
* Data Source: Prometheus
* Panels:

  * Extractor: rows fetched, duration, files written, offset
  * Cleaner: files processed, rows cleaned, errors
  * RabbitMQ: queue depth, job throughput
  * Job timeline: run start/end, duration trends

## GCS Buckets

| Purpose      | Bucket Name                   |
| ------------ | ----------------------------- |
| Raw Data     | prometheus-grafana-demo-raw   |
| Cleaned Data | prometheus-grafana-demo-clean |

Each extraction job writes to a date-named prefix (e.g., 2024-05-21/).

## Message Example

Sent to RabbitMQ by extractor:

{
"date": "2024-05-21",
"filename": "food\_inspections\_raw\_offset\_12000.json"
}

## Prometheus Metrics

| Metric                          | Source            | Description                    |
| ------------------------------- | ----------------- | ------------------------------ |
| extractor\_requests\_total      | Extractor         | Total API calls made           |
| extractor\_rows\_fetched\_total | Extractor         | Total rows fetched             |
| extractor\_last\_run\_duration  | Extractor         | Duration of most recent run    |
| cleaner\_files\_cleaned\_total  | Cleaner           | Total files cleaned            |
| cleaner\_rows\_cleaned\_total   | Cleaner           | Total rows cleaned             |
| rabbitmq\_queue\_depth          | RabbitMQ Exporter | Messages waiting to be cleaned |

## Summary

This architecture separates pipeline control from pipeline monitoring, using:

* Streamlit for launch and control
* RabbitMQ for decoupled orchestration
* Prometheus and Grafana for visibility into pipeline behavior

It is designed to demonstrate robust data pipeline operation, monitoring, and control in a modular and realistic setting.


Appendix
## Setup Instructions

These steps will clone the repository, configure Google Cloud resources, and launch the full Prometheus + Grafana monitoring demo.

### 1. Clone the Repository

```bash
git clone https://github.com/malawley/MSDS434-grafana-prometheus-demo.git
cd MSDS434-grafana-prometheus-demo
```

---

### 2. Set Up Google Cloud

#### a. Create a GCP Project

In the GCP Console:

1. Go to https://console.cloud.google.com/
2. Create a new project (e.g., `grafana-demo-project`)

#### b. Enable APIs

Enable these APIs for your project:
- Cloud Storage API
- IAM API
- Service Usage API

#### c. Create Two GCS Buckets

Create two **regionally located** GCS buckets (replace with your names):

- `your-raw-bucket`
- `your-clean-bucket`

These must be globally unique.

#### d. Create a Service Account

1. Go to **IAM & Admin → Service Accounts**
2. Click **"Create Service Account"**
3. Name it (e.g., `grafana-demo-sa`)
4. Assign these roles:
   - `Storage Object Admin`
5. After creation, click the account → **Keys → Add Key → Create new key (JSON)**

Download the key file and save it as:

```bash
hygiene-grafana-key.json
```

Place it in the project root. This file is **ignored by Git** for safety.

---

### 3. Configure the Makefile

Open the `Makefile` and update these environment variable values in the following targets:

- `run-extractor`
- `run-cleaner`

Set:

- `PROJECT_ID` to your GCP project ID
- `RAW_BUCKET` to your raw GCS bucket
- `CLEAN_BUCKET` to your clean GCS bucket

Example:

```make
-e PROJECT_ID=grafana-demo-project
-e RAW_BUCKET=your-raw-bucket
-e CLEAN_BUCKET=your-clean-bucket
```

---

### 4. Build and Run Monitoring Stack

```bash
make run-prometheus
make run-grafana
```

This will start:
- Prometheus on http://localhost:9090
- Grafana on http://localhost:3000

Login to Grafana with:
```
Username: admin
Password: admin
```

---

### 5. Build and Run the Pipeline Services

```bash
make run-extractor
make run-cleaner
```

These containers will connect to RabbitMQ and GCS and expose metrics to Prometheus.

---

### 6. Trigger the Pipeline

Use the Streamlit UI to trigger data extraction and cleaning:

```bash
make run-streamlit
```

Then open http://localhost:8501 and run the pipeline interactively.

---

### 7. View Monitoring Dashboards

In Grafana (http://localhost:3000):

1. Dashboards are pre-provisioned
2. Look for:
   - "Extractor Dashboard"
   - "Cleaner Dashboard"

If not visible, import them manually from:
```text
grafana/dashboards/
```

---

### 8. Verify System

Use Prometheus to verify:

- `up` — confirms services are online
- `extractor_requests_total` — confirms extractor activity
- `cleaner_messages_total` — confirms cleaner activity

Use Grafana to monitor metrics over time.

---

### 9. You're Done

You now have a fully functioning containerized monitoring pipeline using Prometheus and Grafana, instrumented for real-time inspection.

