#!/bin/bash
# Start monitoring script in background and redirect output to log

MONITOR_LOG="/tmp/scraping_monitor.log"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Starting scraping monitor..."
echo "Monitor log: $MONITOR_LOG"
echo "To view progress: tail -f $MONITOR_LOG"
echo "To stop monitor: pkill -f monitor_scraping_completion"

# Run monitor in background
cd "$SCRIPT_DIR/../../.."
docker-compose exec -T backend python data_pipeline/monitor_scraping_completion.py \
    --interval 30 \
    --expected 113 \
    > "$MONITOR_LOG" 2>&1 &

MONITOR_PID=$!
echo "Monitor started with PID: $MONITOR_PID"
echo "PID saved to: /tmp/scraping_monitor.pid"
echo $MONITOR_PID > /tmp/scraping_monitor.pid

echo ""
echo "Monitor is running. You will receive a notification when scraping is complete."
echo "Check progress with: tail -f $MONITOR_LOG"

