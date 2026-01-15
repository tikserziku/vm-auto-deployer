#!/bin/bash
# Auto-commit changes every hour
cd /home/ubuntu/auto-deployer

# Scan for changes
python3 change_tracker.py scan

# Get pending count
PENDING=$(python3 -c "
from change_tracker import get_pending_changes
print(len(get_pending_changes()))
")

if [ "$PENDING" -gt "0" ]; then
    echo "$(date): Found $PENDING pending changes, committing..."
    python3 change_tracker.py commit
    
    # Notify via Telegram
    curl -s "https://api.telegram.org/bot7579834718:AAHOxEjB6GvqKFA0ztql2qKvOg0u3LqDU2M/sendMessage" \
      -H "Content-Type: application/json" \
      -d "{\"chat_id\": \"171656163\", \"text\": \"📦 Auto-commit: $PENDING изменений закоммичено в GitHub\"}" > /dev/null
fi
