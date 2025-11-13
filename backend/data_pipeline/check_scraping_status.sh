#!/bin/bash
# Quick script to check scraping status

echo "=== Player Scraping Status ==="
docker-compose exec backend python data_pipeline/check_scraping_progress.py

echo ""
echo "=== Recent Scraping Activity ==="
tail -20 /tmp/player_scraping.log 2>/dev/null | grep -E "(\[.*\] Scraping|Found|Updated|Summary)" | tail -5 || echo "Log file not available"

echo ""
echo "=== Scraper Process ==="
ps aux | grep "scrape_player_profiles" | grep -v grep | head -2 || echo "Scraper not running"

