# === Build Stage ===
FROM golang:1.24.2 AS builder

# Set working directory
WORKDIR /app

# Copy Go module files first to cache dependencies
COPY go.mod go.sum ./
RUN go mod download

# Copy the rest of the source code
COPY . .

# Build the Go binary
RUN go build -o extractor

# === Runtime Stage ===
FROM golang:1.24.2

WORKDIR /app

# Copy the compiled binary from the builder
COPY --from=builder /app/extractor .

# Expose the HTTP port
EXPOSE 8000

# Start the app
ENTRYPOINT ["./extractor"]
