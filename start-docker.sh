#!/bin/bash
set -e

echo "🚀 Starting Mamlarr + AudioBookRequest Docker Setup"
echo "=================================================="
echo

# Check if .env exists
if [ ! -f .env ]; then
    echo "❌ Error: .env file not found!"
    echo "Please copy .env.example to .env and fill in your credentials:"
    echo "  cp .env.example .env"
    echo "  nano .env"
    exit 1
fi

# Check if required variables are set
source .env

if [ "$MAM_SERVICE_API_KEY" = "your-api-key-here" ] || [ "$MAM_SERVICE_API_KEY" = "changeme" ]; then
    echo "⚠️  Warning: MAM_SERVICE_API_KEY is not set in .env"
    echo "   Please edit .env and set your API key"
fi

if [ "$MAM_SERVICE_MAM_SESSION_ID" = "your-mam-session-cookie-here" ] || [ -z "$MAM_SERVICE_MAM_SESSION_ID" ]; then
    echo "⚠️  Warning: MAM_SERVICE_MAM_SESSION_ID is not set in .env"
    echo "   Please edit .env and add your MAM session cookie"
fi

if [ "$MAM_SERVICE_TRANSMISSION_URL" = "http://your-seedbox:9091/transmission/rpc" ]; then
    echo "⚠️  Warning: MAM_SERVICE_TRANSMISSION_URL is not set in .env"
    echo "   Please edit .env and add your Transmission RPC URL"
fi

echo
echo "📦 Building Docker image..."
docker compose build

echo
echo "🏃 Starting containers..."
docker compose up -d

echo
echo "✅ Containers started!"
echo
echo "📊 Services available at:"
echo "   - AudioBookRequest: http://localhost:8000"
echo "   - Mamlarr Dashboard: http://localhost:8800/mamlarr/"
echo "   - Mamlarr Settings:  http://localhost:8800/mamlarr/settings"
echo
echo "📝 View logs with:"
echo "   docker compose logs -f"
echo
echo "🛑 Stop with:"
echo "   docker compose down"
echo
echo "=================================================="
echo "🎯 Next Steps:"
echo "1. Configure Mamlarr at: http://localhost:8800/mamlarr/settings"
echo "2. Test Transmission connection"
echo "3. Configure AudioBookRequest to use Mamlarr as Prowlarr"
echo "4. Search and download an audiobook!"
echo
echo "📖 Full setup guide: See DOCKER_SETUP.md"
echo "=================================================="
