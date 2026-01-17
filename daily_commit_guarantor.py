#!/usr/bin/env python3
"""
Daily Commit Guarantor
Ensures at least one commit per day for GitHub green squares.

Strategy:
1. Check if any commits were made today
2. If not, generate a meaningful commit:
   - Update daily stats file
   - Add learning summary
   - Commit and push

Run this at 23:00 via cron/systemd to guarantee green squares.
"""

import os
import sys
import json
import subprocess
from pathlib import Path
from datetime import datetime, date
from typing import Dict, List, Any, Optional
import requests

# Configuration
HOME = Path.home()
TRACKED_PROJECTS = [
    HOME / 'ai-learning-agent',
    HOME / 'youtube-ai-monitor',
    HOME / 'agi-news-agent',
    HOME / 'claude-mailbox',
    HOME / 'mcp-hub',
    HOME / 'auto-deployer',
    HOME / 'arm-hunter'
]

# Fallback project for daily stats (must exist and be git-tracked)
STATS_PROJECT = HOME / 'auto-deployer'
STATS_FILE = STATS_PROJECT / 'daily_stats.json'

# Telegram notification
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '')


def get_todays_date() -> str:
    """Get today's date in ISO format."""
    return date.today().isoformat()


def check_commit_today(project_path: Path) -> bool:
    """Check if project has commits today."""
    if not (project_path / '.git').exists():
        return False

    today = get_todays_date()

    try:
        result = subprocess.run(
            ['git', '-C', str(project_path), 'log', '--oneline', '--since', today],
            capture_output=True, text=True, timeout=10
        )
        # If there's any output, there were commits today
        return bool(result.stdout.strip())
    except Exception as e:
        print(f'Error checking {project_path.name}: {e}')
        return False


def check_any_commit_today() -> Dict[str, bool]:
    """Check all projects for commits today."""
    results = {}
    for project in TRACKED_PROJECTS:
        if project.exists():
            results[project.name] = check_commit_today(project)
        else:
            results[project.name] = False
    return results


def collect_daily_stats() -> Dict[str, Any]:
    """Collect statistics for the day."""
    stats = {
        'date': get_todays_date(),
        'timestamp': datetime.now().isoformat(),
        'services': {},
        'commits': {},
        'system': {}
    }

    # Check service statuses
    services = [
        'claude-mailbox',
        'youtube-ai-monitor',
        'agi-news-agent',
        'github-auto-sync.timer'
    ]

    for service in services:
        try:
            result = subprocess.run(
                ['systemctl', 'is-active', service],
                capture_output=True, text=True, timeout=5
            )
            stats['services'][service] = result.stdout.strip()
        except:
            stats['services'][service] = 'unknown'

    # Check commits
    stats['commits'] = check_any_commit_today()
    stats['commits_total'] = sum(1 for v in stats['commits'].values() if v)

    # System info
    try:
        result = subprocess.run(['uptime', '-p'], capture_output=True, text=True, timeout=5)
        stats['system']['uptime'] = result.stdout.strip()
    except:
        stats['system']['uptime'] = 'unknown'

    return stats


def create_stats_commit() -> bool:
    """Create a daily stats commit."""
    if not STATS_PROJECT.exists():
        print(f'Stats project not found: {STATS_PROJECT}')
        return False

    # Collect stats
    stats = collect_daily_stats()

    # Load existing stats history
    history = []
    if STATS_FILE.exists():
        try:
            existing = json.loads(STATS_FILE.read_text())
            if isinstance(existing, list):
                history = existing
            elif isinstance(existing, dict) and 'history' in existing:
                history = existing['history']
        except:
            pass

    # Add today's stats
    history.append(stats)

    # Keep last 30 days
    history = history[-30:]

    # Save stats file
    stats_data = {
        'last_updated': datetime.now().isoformat(),
        'history': history
    }

    STATS_FILE.write_text(json.dumps(stats_data, indent=2))
    print(f'Stats file updated: {STATS_FILE}')

    # Git commit
    try:
        # Add file
        subprocess.run(
            ['git', '-C', str(STATS_PROJECT), 'add', STATS_FILE.name],
            check=True, capture_output=True, timeout=30
        )

        # Commit
        commit_msg = f"Daily stats: {stats['date']} - {stats['commits_total']} projects active"
        result = subprocess.run(
            ['git', '-C', str(STATS_PROJECT), 'commit', '-m', commit_msg],
            capture_output=True, text=True, timeout=30
        )

        if 'nothing to commit' in result.stdout or 'nothing to commit' in result.stderr:
            print('No changes to commit')
            return False

        # Push
        subprocess.run(
            ['git', '-C', str(STATS_PROJECT), 'push'],
            check=True, capture_output=True, timeout=60
        )

        print(f'Committed and pushed: {commit_msg}')
        return True

    except subprocess.CalledProcessError as e:
        print(f'Git error: {e.stderr if hasattr(e, "stderr") else e}')
        return False
    except Exception as e:
        print(f'Error: {e}')
        return False


def send_telegram_notification(message: str):
    """Send notification to Telegram."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return

    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = {
            'chat_id': TELEGRAM_CHAT_ID,
            'text': message,
            'parse_mode': 'Markdown'
        }
        requests.post(url, data=data, timeout=10)
    except:
        pass


def main():
    print('=' * 50)
    print('Daily Commit Guarantor')
    print('=' * 50)
    print(f'Date: {get_todays_date()}')
    print()

    # Check existing commits
    commits = check_any_commit_today()

    print('Commits today:')
    has_any_commit = False
    for project, has_commit in commits.items():
        status = '✅' if has_commit else '❌'
        print(f'  {status} {project}')
        if has_commit:
            has_any_commit = True

    print()

    if has_any_commit:
        print('✅ Already have commits today - green square secured!')
        msg = f"🟢 *Green Square Secured*\n\nDate: {get_todays_date()}\nProjects with commits today: {sum(1 for v in commits.values() if v)}"
    else:
        print('⚠️ No commits today - creating daily stats commit...')
        success = create_stats_commit()

        if success:
            print('✅ Daily stats committed - green square secured!')
            msg = f"🟢 *Green Square Created*\n\nDate: {get_todays_date()}\nFallback commit created with daily stats."
        else:
            print('❌ Failed to create commit')
            msg = f"🔴 *Green Square Failed*\n\nDate: {get_todays_date()}\nCould not create fallback commit!"

    # Send notification
    send_telegram_notification(msg)

    print()
    print('Done!')


if __name__ == '__main__':
    main()
