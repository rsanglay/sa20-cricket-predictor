#!/bin/bash

# Script to completely remove and rebuild Docker containers

echo "🛑 Stopping all containers..."
docker-compose down

echo "🗑️  Removing all containers, networks, and volumes..."
docker-compose down -v --remove-orphans

echo "🧹 Removing any orphaned containers..."
docker container prune -f

echo "🔨 Rebuilding containers from scratch..."
docker-compose build --no-cache

echo "🚀 Starting all services..."
docker-compose up -d

echo "✅ Done! Containers rebuilt and started."
echo ""
echo "View logs with: docker-compose logs -f"
echo "View status with: docker-compose ps"

