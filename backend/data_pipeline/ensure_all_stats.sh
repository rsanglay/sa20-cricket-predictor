#!/bin/bash
# Script to ensure all players have stats

set -e

echo "=========================================="
echo "Ensuring All Players Have Stats"
echo "=========================================="
echo ""

# Check if Docker is running
if ! docker ps > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker Desktop and try again."
    exit 1
fi

# Check current status
echo "Step 1: Checking current status..."
docker-compose exec backend python data_pipeline/check_stats_progress.py

echo ""
echo "Step 2: Generating stats from deliveries data for players without scraped stats..."
docker-compose exec backend python data_pipeline/generate_stats_from_deliveries.py

echo ""
echo "Step 3: Final status..."
docker-compose exec backend python data_pipeline/check_stats_progress.py

echo ""
echo "✅ Done! Check the output above for final status."

