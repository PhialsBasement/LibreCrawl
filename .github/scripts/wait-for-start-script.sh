#!/bin/bash
# Runs a start script in the background and passes once LibreCrawl answers.
# Usage: wait-for-start-script.sh <start script>
# Needs LIBRECRAWL_URL and STARTUP_TIMEOUT_SECONDS; the script's output goes to start.log.

"$1" > start.log 2>&1 &
script_pid=$!

deadline=$((SECONDS + STARTUP_TIMEOUT_SECONDS))
while [ "$SECONDS" -lt "$deadline" ]; do
    status=$(curl -s -o /dev/null -w '%{http_code}' "$LIBRECRAWL_URL" || true)
    if [ "$status" = "200" ] || [ "$status" = "302" ]; then
        echo "LibreCrawl answered with HTTP $status"
        kill "$script_pid" 2>/dev/null || true
        exit 0
    fi
    if ! kill -0 "$script_pid" 2>/dev/null; then
        echo "$1 exited before the server came up"
        exit 1
    fi
    sleep 5
done

echo "LibreCrawl did not answer within ${STARTUP_TIMEOUT_SECONDS}s"
kill "$script_pid" 2>/dev/null || true
exit 1
