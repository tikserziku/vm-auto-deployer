#\!/bin/bash
# Auto-commit changes - SMART VERSION
# Only notify when actual commits happen

cd /home/ubuntu/auto-deployer
LAST_NOTIFY_FILE="/tmp/auto_commit_last_notify"
LOG_FILE="/tmp/auto_commit.log"

# Scan for changes
python3 change_tracker.py scan >> $LOG_FILE 2>&1

# Get pending count
PENDING=$(python3 -c "
from change_tracker import get_pending_changes
print(len(get_pending_changes()))
" 2>/dev/null)

if [ "$PENDING" -gt "0" ]; then
    echo "$(date): Found $PENDING pending changes" >> $LOG_FILE
    
    # Try to commit and capture result
    COMMIT_OUTPUT=$(python3 change_tracker.py commit 2>&1)
    echo "$COMMIT_OUTPUT" >> $LOG_FILE
    
    # Check if any actual commits happened
    if echo "$COMMIT_OUTPUT" | grep -q "status.*committed"; then
        # Check if we already notified in last hour
        if [ -f "$LAST_NOTIFY_FILE" ]; then
            LAST_TIME=$(cat "$LAST_NOTIFY_FILE")
            NOW=$(date +%s)
            DIFF=$((NOW - LAST_TIME))
            if [ "$DIFF" -lt 3600 ]; then
                echo "$(date): Skipping notification (sent ${DIFF}s ago)" >> $LOG_FILE
                exit 0
            fi
        fi
        
        # Count successful commits
        COMMITTED=$(echo "$COMMIT_OUTPUT" | grep -c "committed")
        
        if [ "$COMMITTED" -gt "0" ]; then
            # Send notification
            curl -s "https://api.telegram.org/bot7579834718:AAHOxEjB6GvqKFA0ztql2qKvOg0u3LqDU2M/sendMessage"               -H "Content-Type: application/json"               -d "{\"chat_id\": \"171656163\", \"text\": \"📦 Auto-commit: $COMMITTED проектов обновлено в GitHub\"}" > /dev/null
            
            # Save notification time
            date +%s > "$LAST_NOTIFY_FILE"
            echo "$(date): Notification sent" >> $LOG_FILE
        fi
    else
        echo "$(date): No actual commits made" >> $LOG_FILE
    fi
else
    echo "$(date): No pending changes" >> $LOG_FILE
fi
