#!/usr/bin/env python3
"""
Daily Orchestrator
Coordinates all AI learning and automation systems.

Schedule:
- 06:00 - Morning learning cycle
- 12:00 - Midday documentation update
- 18:00 - Evening profile update
- 23:00 - Daily commit check (green squares)

Run with argument: morning, midday, evening, night
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path
from datetime import datetime
import requests
import json

# Configuration
HOME = Path.home()
AUTO_DEPLOYER = HOME / 'auto-deployer'

TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '')


def send_telegram(message: str):
    """Send notification to Telegram."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print('Telegram not configured')
        return

    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = {
            'chat_id': TELEGRAM_CHAT_ID,
            'text': message,
            'parse_mode': 'Markdown'
        }
        requests.post(url, data=data, timeout=10)
    except Exception as e:
        print(f'Telegram error: {e}')


def run_script(script_name: str) -> bool:
    """Run a Python script and return success status."""
    script_path = AUTO_DEPLOYER / script_name

    if not script_path.exists():
        print(f'Script not found: {script_path}')
        return False

    print(f'\n>>> Running {script_name}...')
    print('-' * 40)

    try:
        result = subprocess.run(
            ['python3', str(script_path)],
            cwd=str(AUTO_DEPLOYER),
            capture_output=False,
            timeout=300  # 5 minute timeout
        )
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print(f'Timeout running {script_name}')
        return False
    except Exception as e:
        print(f'Error running {script_name}: {e}')
        return False


def morning_cycle():
    """Morning cycle: Learn from internal systems."""
    print('=' * 60)
    print('🌅 MORNING CYCLE - Internal Learning')
    print('=' * 60)

    results = []

    # 1. Run AI Learning Agent v2
    success = run_script('ai_learning_agent_v2.py')
    results.append(('AI Learning', success))

    # 2. Generate documentation
    success = run_script('docs_generator.py')
    results.append(('Documentation', success))

    # Summary
    successful = sum(1 for _, s in results if s)
    total = len(results)

    msg = f"🌅 *Morning Cycle Complete*\n\n"
    msg += f"Tasks: {successful}/{total} successful\n\n"
    for task, success in results:
        emoji = '✅' if success else '❌'
        msg += f"{emoji} {task}\n"

    print()
    print(msg.replace('*', '').replace('_', ''))
    send_telegram(msg)


def midday_cycle():
    """Midday cycle: Update documentation and push."""
    print('=' * 60)
    print('☀️ MIDDAY CYCLE - Documentation Sync')
    print('=' * 60)

    results = []

    # 1. Generate fresh docs
    success = run_script('docs_generator.py')
    results.append(('Docs Generation', success))

    # 2. Run auto-sync if available
    auto_commit = AUTO_DEPLOYER / 'auto_commit.sh'
    if auto_commit.exists():
        try:
            subprocess.run(['bash', str(auto_commit)], timeout=120)
            results.append(('Auto-sync', True))
        except:
            results.append(('Auto-sync', False))

    successful = sum(1 for _, s in results if s)
    total = len(results)

    msg = f"☀️ *Midday Cycle Complete*\n\nTasks: {successful}/{total}"
    send_telegram(msg)


def evening_cycle():
    """Evening cycle: Update GitHub profile."""
    print('=' * 60)
    print('🌆 EVENING CYCLE - Profile Update')
    print('=' * 60)

    results = []

    # 1. Update GitHub profile
    success = run_script('github_profile_updater.py')
    results.append(('Profile Update', success))

    successful = sum(1 for _, s in results if s)
    total = len(results)

    msg = f"🌆 *Evening Cycle Complete*\n\nGitHub Profile: {'✅ Updated' if successful else '❌ Failed'}"
    send_telegram(msg)


def night_cycle():
    """Night cycle: Guarantee green squares."""
    print('=' * 60)
    print('🌙 NIGHT CYCLE - Green Square Guarantee')
    print('=' * 60)

    results = []

    # 1. Run daily commit guarantor
    success = run_script('daily_commit_guarantor.py')
    results.append(('Commit Check', success))

    # Note: The guarantor sends its own Telegram message


def full_cycle():
    """Run all cycles (for testing)."""
    print('=' * 60)
    print('🔄 FULL CYCLE - All Systems')
    print('=' * 60)

    cycles = [
        ('morning', morning_cycle),
        ('midday', midday_cycle),
        ('evening', evening_cycle),
        ('night', night_cycle)
    ]

    for name, func in cycles:
        print(f'\n\n{"#" * 60}')
        print(f'Running {name} cycle...')
        print(f'{"#" * 60}\n')
        func()


def status_check():
    """Check status of all systems."""
    print('=' * 60)
    print('📊 SYSTEM STATUS CHECK')
    print('=' * 60)

    # Check scripts exist
    scripts = [
        'docs_generator.py',
        'ai_learning_agent_v2.py',
        'github_profile_updater.py',
        'daily_commit_guarantor.py',
        'change_tracker.py'
    ]

    print('\n📁 Scripts:')
    for script in scripts:
        exists = (AUTO_DEPLOYER / script).exists()
        emoji = '✅' if exists else '❌'
        print(f'  {emoji} {script}')

    # Check knowledge files
    print('\n📚 Knowledge Files:')
    knowledge_files = [
        HOME / 'docs' / 'knowledge-base.json',
        HOME / 'agent-memory' / 'internal-knowledge.json',
        HOME / 'docs' / 'AI_LEARNING_SUMMARY.md'
    ]

    for kf in knowledge_files:
        exists = kf.exists()
        emoji = '✅' if exists else '❌'
        print(f'  {emoji} {kf.name}')

    # Check services
    print('\n⚙️ Services:')
    services = [
        'github-auto-sync.timer',
        'claude-mailbox'
    ]

    for service in services:
        try:
            result = subprocess.run(
                ['systemctl', 'is-active', service],
                capture_output=True, text=True, timeout=5
            )
            status = result.stdout.strip()
            emoji = '🟢' if status == 'active' else '🔴'
            print(f'  {emoji} {service}: {status}')
        except:
            print(f'  ⚪ {service}: unknown')


def main():
    parser = argparse.ArgumentParser(description='Daily Orchestrator')
    parser.add_argument('cycle', nargs='?', default='status',
                       choices=['morning', 'midday', 'evening', 'night', 'full', 'status'],
                       help='Which cycle to run')

    args = parser.parse_args()

    print(f'\n🤖 Daily Orchestrator - {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n')

    cycles = {
        'morning': morning_cycle,
        'midday': midday_cycle,
        'evening': evening_cycle,
        'night': night_cycle,
        'full': full_cycle,
        'status': status_check
    }

    if args.cycle in cycles:
        cycles[args.cycle]()
    else:
        print(f'Unknown cycle: {args.cycle}')
        sys.exit(1)

    print('\n✅ Orchestrator complete\n')


if __name__ == '__main__':
    main()
