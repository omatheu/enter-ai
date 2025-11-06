#!/bin/bash

# Performance test script for extraction endpoint

API_URL="http://localhost:8001/extract"
DATASET_FILE="docs/data/dataset.json"
FILES_DIR="docs/files"

echo "Performance Testing for Enter AI Extraction API"
echo "=================================================="
echo ""

# Test first PDF from dataset
echo "=== Single Extraction Test ==="
echo ""

# Extract first item from dataset
LABEL=$(jq -r '.[0].label' "$DATASET_FILE")
SCHEMA=$(jq -c '.[0].extraction_schema' "$DATASET_FILE")
PDF_FILE=$(jq -r '.[0].pdf_path' "$DATASET_FILE")
PDF_PATH="$FILES_DIR/$PDF_FILE"

if [ ! -f "$PDF_PATH" ]; then
    echo "Error: PDF file not found: $PDF_PATH"
    exit 1
fi

echo "Testing with: $PDF_FILE"
echo "Label: $LABEL"
echo ""

# First call (cold - no cache)
echo "First call (cold):"
START=$(date +%s.%N)
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$API_URL" \
    -F "label=$LABEL" \
    -F "extraction_schema=$SCHEMA" \
    -F "pdf_file=@$PDF_PATH")
END=$(date +%s.%N)
HTTP_CODE=$(echo "$RESPONSE" | tail -n 1)
DURATION=$(echo "$END - $START" | bc)

echo "  Duration: ${DURATION}s"
echo "  HTTP Status: $HTTP_CODE"

if [ "$HTTP_CODE" = "200" ]; then
    SOURCE=$(echo "$RESPONSE" | head -n -1 | jq -r '.metadata.source // "unknown"')
    echo "  Source: $SOURCE"
fi

echo ""

# Second call (should hit cache)
echo "Second call (cached):"
START=$(date +%s.%N)
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$API_URL" \
    -F "label=$LABEL" \
    -F "extraction_schema=$SCHEMA" \
    -F "pdf_file=@$PDF_PATH")
END=$(date +%s.%N)
HTTP_CODE=$(echo "$RESPONSE" | tail -n 1)
DURATION2=$(echo "$END - $START" | bc)

echo "  Duration: ${DURATION2}s"
echo "  HTTP Status: $HTTP_CODE"

if [ "$HTTP_CODE" = "200" ]; then
    SOURCE=$(echo "$RESPONSE" | head -n -1 | jq -r '.metadata.source // "unknown"')
    echo "  Source: $SOURCE"

    # Calculate speedup
    SPEEDUP=$(echo "scale=2; $DURATION / $DURATION2" | bc)
    echo "  Speedup: ${SPEEDUP}x"
fi

echo ""
echo "=================================================="
echo "PERFORMANCE SUMMARY"
echo "=================================================="
echo "Cold call: ${DURATION}s"
echo "Cached call: ${DURATION2}s"

# Check if meets 10 second goal
if (( $(echo "$DURATION < 10" | bc -l) )); then
    echo "✓ Goal achieved! Response under 10s: ${DURATION}s"
else
    echo "✗ Response time: ${DURATION}s (target: <10s)"
fi

echo ""
echo "Note: For batch processing, the frontend should send"
echo "      requests in parallel to achieve optimal performance."
