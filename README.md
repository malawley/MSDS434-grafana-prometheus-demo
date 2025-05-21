# Prometheus + Grafana Monitoring Pipeline Demo

## Project Title

Chicago Food Inspections Monitoring Demo: Extract, Clean, and Observe

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
