#!/bin/bash
# Quick API test script - tests all mamlarr endpoints

API_KEY="${MAM_SERVICE_API_KEY:-dev-test-key}"
BASE_URL="${MAMLARR_URL:-http://localhost:8000}"

echo "Testing Mamlarr API"
echo "==================="
echo "Base URL: $BASE_URL"
echo "API Key: $API_KEY"
echo ""

# Test 1: Health check
echo "1. Health check..."
response=$(curl -s "$BASE_URL/health")
echo "   Response: $response"
echo ""

# Test 2: Get indexers
echo "2. Get indexers..."
response=$(curl -s -H "X-Api-Key: $API_KEY" "$BASE_URL/api/v1/indexer")
echo "   Response: $response"
echo ""

# Test 3: Search
echo "3. Search for 'test audiobook'..."
response=$(curl -s -H "X-Api-Key: $API_KEY" "$BASE_URL/api/v1/search?query=test+audiobook&limit=5&offset=0")
echo "   Response: $response"

# Extract guid and indexerId from first result (if jq is available)
if command -v jq &> /dev/null; then
    guid=$(echo "$response" | jq -r '.[0].guid // empty')
    indexerId=$(echo "$response" | jq -r '.[0].indexerId // empty')

    if [ -n "$guid" ] && [ -n "$indexerId" ]; then
        echo ""
        echo "4. Download first result..."
        echo "   GUID: $guid"
        echo "   Indexer ID: $indexerId"

        download_response=$(curl -s -X POST \
            -H "X-Api-Key: $API_KEY" \
            -H "Content-Type: application/json" \
            -d "{\"guid\":\"$guid\",\"indexerId\":$indexerId}" \
            "$BASE_URL/api/v1/search")

        echo "   Response: $download_response"

        jobId=$(echo "$download_response" | jq -r '.jobId // empty')

        if [ -n "$jobId" ]; then
            echo ""
            echo "5. Wait 3 seconds for processing..."
            sleep 3

            echo "6. Check job status..."
            job_response=$(curl -s -H "X-Api-Key: $API_KEY" "$BASE_URL/api/v1/jobs/$jobId")
            echo "   Response: $job_response"
        fi
    fi
else
    echo ""
    echo "   (Install 'jq' to test download and job status endpoints)"
fi

echo ""
echo "==================="
echo "API test complete!"
