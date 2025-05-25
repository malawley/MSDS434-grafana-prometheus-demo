# === CONFIGURATION ===
KEY_PATH := /mnt/c/Users/malaw/OneDrive/Documents/MSDS/MSDS434/grafana_monitoring_demo/hygiene-grafana-key.json

EXTRACTOR_IMAGE := extractor:latest
CLEANER_IMAGE := cleaner:latest
STREAMLIT_IMAGE := streamlit-ui:latest

PROJECT_ID := hygiene-prediction-434
RAW_BUCKET := prometheus-grafana-demo-raw
CLEAN_BUCKET := prometheus-grafana-demo-clean

DATE := 2024-05-21
N := 1000

# === RESET: stop/remove containers + network ===
reset:
	docker rm -f grafana-extractor grafana-cleaner rabbit streamlit-ui || true
	docker network rm pipeline-net || true

# === STOP individual containers ===
stop-extractor:
	docker rm -f grafana-extractor || true

stop-cleaner:
	docker rm -f grafana-cleaner || true

stop-rabbit:
	docker rm -f rabbit || true

stop-streamlit:
	docker rm -f streamlit-ui || true

# === BUILD: build all Docker images ===
build: build-extractor build-cleaner build-streamlit

build-extractor:
	cd src/extractor && docker build -t $(EXTRACTOR_IMAGE) .

build-cleaner:
	cd src/cleaner && docker build -t $(CLEANER_IMAGE) .

build-streamlit:
	cd streamlit_ui && docker build -t $(STREAMLIT_IMAGE) .

# === NETWORK: create Docker network ===
network:
	docker network create pipeline-net

# === RUN: launch RabbitMQ, extractor, cleaner ===
run: network
	docker run -d --name rabbit --network pipeline-net \
		-p 5672:5672 -p 15672:15672 \
		rabbitmq:3-management

	docker run -d --name grafana-extractor --network pipeline-net \
		-p 8000:8000 \
		-e GOOGLE_APPLICATION_CREDENTIALS=/secrets/hygiene-grafana-key.json \
		-e PROJECT_ID=$(PROJECT_ID) \
		-e RAW_BUCKET=$(RAW_BUCKET) \
		-e RABBITMQ_URL=amqp://guest:guest@rabbit:5672/ \
		-v $(KEY_PATH):/secrets/hygiene-grafana-key.json:ro \
		$(EXTRACTOR_IMAGE)

	docker run -d --name grafana-cleaner --network pipeline-net \
		-e GOOGLE_APPLICATION_CREDENTIALS=/secrets/hygiene-grafana-key.json \
		-e PROJECT_ID=$(PROJECT_ID) \
		-e RAW_BUCKET=$(RAW_BUCKET) \
		-e CLEAN_BUCKET=$(CLEAN_BUCKET) \
		-e RABBITMQ_URL=amqp://guest:guest@rabbit:5672/ \
		-v $(KEY_PATH):/secrets/hygiene-grafana-key.json:ro \
		$(CLEANER_IMAGE)

# === RUN Cleaner ===
run-cleaner:
	docker run -d --name grafana-cleaner --network pipeline-net \
		-e GOOGLE_APPLICATION_CREDENTIALS=/secrets/hygiene-grafana-key.json \
		-e PROJECT_ID=$(PROJECT_ID) \
		-e RAW_BUCKET=$(RAW_BUCKET) \
		-e CLEAN_BUCKET=$(CLEAN_BUCKET) \
		-e RABBITMQ_URL=amqp://guest:guest@rabbit:5672/ \
		-v "$(KEY_PATH):/secrets/hygiene-grafana-key.json:ro" \
		$(CLEANER_IMAGE)

# === RUN STREAMLIT UI ===
run-streamlit:
	docker run -d --name streamlit-ui --network pipeline-net \
		-p 8501:8501 \
		-e GOOGLE_APPLICATION_CREDENTIALS=/secrets/hygiene-grafana-key.json \
		-v "$(KEY_PATH):/secrets/hygiene-grafana-key.json:ro" \
		$(STREAMLIT_IMAGE)

run-prometheus:
	docker rm -f prometheus || true
	docker run -d --name prometheus --network pipeline-net \
		-p 9090:9090 \
		-v $(shell pwd)/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml \
		prom/prometheus

stop-prometheus:
	docker rm -f prometheus || true


# === Start Grafana Dashboard UI ===
run-grafana:
	docker rm -f grafana || true
	docker run -d --name grafana --network pipeline-net \
		-p 3000:3000 \
		grafana/grafana

# === Stop Grafana Dashboard UI ===
stop-grafana:
	docker rm -f grafana || true


# === TRIGGER EXTRACT ===
extract:
	curl "http://localhost:8000/extract?n=$(N)&date=$(DATE)"

# === CLEANER LOGS ===
logs:
	docker logs grafana-cleaner

# === LIST CLEANED FILES ===
ls-clean:
	gsutil ls gs://$(CLEAN_BUCKET)/$(DATE)/
