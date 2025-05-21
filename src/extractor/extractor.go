package main

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"strconv"
	"strings"
	"time"

	"cloud.google.com/go/storage"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promhttp"
	"github.com/streadway/amqp"
)

var (
	apiURL      = "https://data.cityofchicago.org/resource/4ijn-s7e5.json"
	projectID   = os.Getenv("PROJECT_ID")
	bucketName  = os.Getenv("RAW_BUCKET")
	rabbitMQURL = os.Getenv("RABBITMQ_URL")
	offsetFile  = "last_offset.txt"
	port        = os.Getenv("PORT")
	chunkSize   = 1000

	requestsTotal = prometheus.NewCounter(prometheus.CounterOpts{
		Name: "extractor_requests_total",
		Help: "Total number of API requests made",
	})
	rowsFetched = prometheus.NewCounter(prometheus.CounterOpts{
		Name: "extractor_rows_fetched_total",
		Help: "Total rows fetched from API",
	})
	lastRunDuration = prometheus.NewGauge(prometheus.GaugeOpts{
		Name: "extractor_last_run_duration_seconds",
		Help: "Duration of the most recent extraction job in seconds",
	})
)

func init() {
	prometheus.MustRegister(requestsTotal, rowsFetched, lastRunDuration)
	if port == "" {
		port = "8000"
	}
}

func main() {
	http.HandleFunc("/extract", handleExtract)
	http.Handle("/metrics", promhttp.Handler())
	http.HandleFunc("/health", func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{"status":"ok"}`))
	})

	log.Printf("🚀 Extractor service running on port %s", port)
	log.Fatal(http.ListenAndServe(":"+port, nil))
}

func handleExtract(w http.ResponseWriter, r *http.Request) {
	ctx := context.Background()
	start := time.Now()

	nStr := r.URL.Query().Get("n")
	date := r.URL.Query().Get("date")
	if nStr == "" || date == "" {
		http.Error(w, "Missing 'n' or 'date' query parameters", http.StatusBadRequest)
		return
	}

	n, err := strconv.Atoi(nStr)
	if err != nil || n <= 0 {
		http.Error(w, "'n' must be a positive integer", http.StatusBadRequest)
		return
	}

	storageClient, err := storage.NewClient(ctx)
	if err != nil {
		http.Error(w, "Storage client error: "+err.Error(), 500)
		return
	}
	bucket := storageClient.Bucket(bucketName)

	startOffset, err := readOffset(ctx, bucket)
	if err != nil {
		startOffset = 0
	}

	conn, err := amqp.Dial(rabbitMQURL)
	if err != nil {
		http.Error(w, "RabbitMQ connection failed: "+err.Error(), 500)
		return
	}
	defer conn.Close()
	ch, _ := conn.Channel()
	defer ch.Close()
	q, _ := ch.QueueDeclare("cleaning-jobs", true, false, false, false, nil)

	files := []string{}
	for i := 0; i < n; i += chunkSize {
		offset := startOffset + i
		url := fmt.Sprintf("%s?$limit=%d&$offset=%d", apiURL, chunkSize, offset)
		resp, err := http.Get(url)
		if err != nil {
			log.Println("Fetch error:", err)
			break
		}
		defer resp.Body.Close()

		var data []map[string]interface{}
		if err := json.NewDecoder(resp.Body).Decode(&data); err != nil {
			log.Println("Decode error:", err)
			break
		}

		if len(data) == 0 {
			log.Println("No more data to fetch")
			break
		}

		filename := fmt.Sprintf("%s/food_inspections_raw_offset_%05d.json", date, offset)
		if err := writeFileToGCS(ctx, bucket, filename, data); err != nil {
			log.Println("Write error:", err)
			break
		}
		files = append(files, filename)
		requestsTotal.Inc()
		rowsFetched.Add(float64(len(data)))

		msgBody, _ := json.Marshal(map[string]string{
			"date":     date,
			"filename": filename,
		})
		_ = ch.Publish("", q.Name, false, false, amqp.Publishing{
			ContentType: "application/json",
			Body:        msgBody,
		})

		time.Sleep(1 * time.Second) // pacing to avoid API rate limits
	}

	newOffset := startOffset + len(files)*chunkSize
	_ = writeOffset(ctx, bucket, newOffset)
	lastRunDuration.Set(time.Since(start).Seconds())

	resp := map[string]interface{}{
		"status":          "success",
		"files_written":   len(files),
		"starting_offset": startOffset,
		"ending_offset":   newOffset,
	}
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(resp)
}

func writeFileToGCS(ctx context.Context, bucket *storage.BucketHandle, filename string, data interface{}) error {
	obj := bucket.Object(filename)
	w := obj.NewWriter(ctx)
	defer w.Close()
	enc := json.NewEncoder(w)
	return enc.Encode(data)
}

func readOffset(ctx context.Context, bucket *storage.BucketHandle) (int, error) {
	obj := bucket.Object(offsetFile)
	r, err := obj.NewReader(ctx)
	if err != nil {
		return 0, err
	}
	defer r.Close()
	buf := new(strings.Builder)
	_, _ = io.Copy(buf, r)
	return strconv.Atoi(strings.TrimSpace(buf.String()))
}

func writeOffset(ctx context.Context, bucket *storage.BucketHandle, offset int) error {
	obj := bucket.Object(offsetFile)
	w := obj.NewWriter(ctx)
	defer w.Close()
	_, err := fmt.Fprintf(w, "%d", offset)
	return err
}
