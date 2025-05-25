import streamlit as st
import requests
from google.cloud import storage
from datetime import datetime

# === Configuration ===
EXTRACTOR_URL = "http://grafana-extractor:8000"
CLEANER_URL = "http://grafana-cleaner:8000"
CHICAGO_API = "https://data.cityofchicago.org/resource/4ijn-s7e5.json?$limit=1"
RABBITMQ_API = "http://rabbit:15672/api/overview"
RABBITMQ_AUTH = ("guest", "guest")


RAW_BUCKET = "prometheus-grafana-demo-raw"
CLEAN_BUCKET = "prometheus-grafana-demo-clean"

# === Streamlit UI Setup ===
st.set_page_config(page_title="Pipeline Control Dashboard", layout="centered")
st.title("Prometheus-Grafana Demo: Control Dashboard")

# === Health Checks ===
st.header("Service Health Checks")

def is_healthy(url, auth=None):
    try:
        r = requests.get(url, timeout=3, auth=auth)
        return r.status_code in (200, 405)
    except:
        return False

statuses = {
    "Extractor": is_healthy(f"{EXTRACTOR_URL}/health"),
    "Cleaner": is_healthy(f"{CLEANER_URL}/health"),
    "Chicago API": is_healthy(CHICAGO_API),
    "RabbitMQ": is_healthy(RABBITMQ_API, auth=RABBITMQ_AUTH),
}

for name, healthy in statuses.items():
    st.write(f"**{name}** → {'🟢 Alive' if healthy else '🔴 Down'}")

# === GCS Bucket File Counts with Refresh Buttons ===

# === GCS Bucket Connection Check ===
st.header("🗃 GCS Bucket Connectivity")

# Reuse one GCS client across all checks
@st.cache_resource
def get_gcs_client():
    return storage.Client()

gcs_client = get_gcs_client()

def check_bucket_access(bucket_name):
    try:
        gcs_client.get_bucket(bucket_name)
        return True
    except Exception as e:
        st.error(f"{bucket_name}: 🔴 Not reachable or no access — {str(e)}")
        return False


for label, bucket in {
    "Raw Data": RAW_BUCKET,
    "Cleaned Data": CLEAN_BUCKET
}.items():
    col1, col2 = st.columns([4, 1])
    with col1:
        if check_bucket_access(bucket):
            st.write(f"**{label}** → 🟢 Accessible")
        else:
            st.error(f"{label}: 🔴 Not reachable or no access")
    with col2:
        if st.button("🔄", key=f"refresh_{bucket}"):
            st.rerun()




# st.header("🗃 GCS Bucket Contents")

# def count_files(bucket_name):
#     client = storage.Client()
#     blobs = list(client.list_blobs(bucket_name))
#     count = len(blobs)
#     latest = max([b.updated for b in blobs], default=None)
#     return count, latest

# for label, bucket in {
#     "Raw Data": RAW_BUCKET,
#     "Cleaned Data": CLEAN_BUCKET
# }.items():
#     col1, col2 = st.columns([4, 1])
#     with col1:
#         try:
#             count, latest = count_files(bucket)
#             latest_fmt = latest.strftime("%Y-%m-%d %H:%M:%S") if latest else "N/A"
#             st.write(f"**{label}** → {count:,} files (Last updated: {latest_fmt})")
#         except Exception as e:
#             st.error(f"{label}: {e}")
#     with col2:
#         if st.button("🔄", key=f"refresh_{bucket}"):
#             st.rerun()

# === Trigger Extractor ===
st.header("Trigger Extraction Job")

with st.form("extract_form"):
    date = st.text_input("Run date (YYYY-MM-DD)", value=str(datetime.today().date()))
    num_rows = st.number_input("Number of rows to extract", value=1000, step=100)
    submitted = st.form_submit_button("▶️ Extract Now")

if submitted:
    try:
        r = requests.get(f"{EXTRACTOR_URL}/extract", params={"n": num_rows, "date": date})
        if r.status_code == 200:
            st.success(f"✅ Extraction started: {r.json()}")
        else:
            st.error(f"❌ Failed with status {r.status_code}: {r.text}")
    except Exception as e:
        st.error(f"❌ Request error: {e}")

# === Clear Buckets ===
st.header("Reset Pipeline (GCS Buckets)")

def clear_bucket(bucket_name):
    try:
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blobs = list(bucket.list_blobs())
        if blobs:
            bucket.delete_blobs(blobs)
            return True, len(blobs)
        return False, 0
    except Exception as e:
        return False, str(e)

if st.button("Clear Raw + Clean Buckets"):
    for label, bucket in {
        "Raw Data": RAW_BUCKET,
        "Cleaned Data": CLEAN_BUCKET
    }.items():
        ok, msg = clear_bucket(bucket)
        if ok:
            st.success(f"✅ Cleared {label} bucket ({msg} files)")
        else:
            st.warning(f"⚠️ {label} not cleared: {msg}")
