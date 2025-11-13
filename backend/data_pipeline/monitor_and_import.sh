#!/bin/bash
# Monitor scraper progress and import when complete

echo "Monitoring scraper progress..."
echo "Press Ctrl+C to stop monitoring"

while true; do
    COUNT=$(docker-compose exec -T backend python3 -c "import json; f=open('/players.json'); print(len(json.load(f))); f.close()" 2>/dev/null || echo "0")
    echo "$(date +%H:%M:%S) - Players scraped: $COUNT/113"
    
    if [ "$COUNT" -ge 113 ]; then
        echo ""
        echo "✓ Scraping complete! Importing data..."
        docker-compose exec backend python /app/data_pipeline/import_player_profiles.py --file /players.json
        echo ""
        echo "✓ Import complete!"
        break
    fi
    
    sleep 60  # Check every minute
done

