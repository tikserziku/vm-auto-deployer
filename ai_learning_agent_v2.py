#!/usr/bin/env python3
"""
AI Learning Agent v2 - Self-Learning System
Now learns from OUR systems, not just external sources.

Features:
- Scans internal project code
- Extracts patterns and concepts
- Builds knowledge base from our own systems
- Still supports YouTube learning as supplementary
- Sends reports to Telegram
"""

import os
import sys
import json
import re
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
import requests

# Add key manager
sys.path.insert(0, str(Path.home() / '.keys'))
try:
    from key_manager import get_key, rotate_on_error
except ImportError:
    def get_key(): return os.environ.get('GEMINI_API_KEY', '')
    def rotate_on_error(e): return None

try:
    import google.generativeai as genai
except ImportError:
    genai = None

# Configuration
HOME = Path.home()
KNOWLEDGE_DIR = HOME / 'agent-memory'
KNOWLEDGE_FILE = KNOWLEDGE_DIR / 'internal-knowledge.json'
DOCS_DIR = HOME / 'docs'

# Telegram configuration
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '')

# Projects to learn from
INTERNAL_PROJECTS = [
    'agi-news-agent',
    'claude-mailbox',
    'auto-deployer',
    'tiktok-transcriber',
    'veo-video-api',
    'todo-app',
    'mcp-hub',
    'visaginas360-bot',
    'voice-tts-bot',
    'telegram-bot'
]


class InternalLearner:
    """Learns from internal project code."""

    def __init__(self):
        self.knowledge_dir = KNOWLEDGE_DIR
        self.knowledge_dir.mkdir(exist_ok=True)
        self.knowledge = self._load_knowledge()

        # Initialize Gemini
        self.model = None
        api_key = get_key()
        if api_key and genai:
            try:
                genai.configure(api_key=api_key)
                self.model = genai.GenerativeModel('gemini-2.0-flash')
            except Exception as e:
                print(f'Warning: Could not initialize Gemini: {e}')

    def _load_knowledge(self) -> Dict[str, Any]:
        """Load existing knowledge base."""
        if KNOWLEDGE_FILE.exists():
            try:
                return json.loads(KNOWLEDGE_FILE.read_text())
            except:
                pass
        return {
            'created_at': datetime.now().isoformat(),
            'last_updated': None,
            'projects': {},
            'concepts': [],
            'patterns': [],
            'apis': [],
            'services': []
        }

    def _save_knowledge(self):
        """Save knowledge base."""
        self.knowledge['last_updated'] = datetime.now().isoformat()
        with open(KNOWLEDGE_FILE, 'w') as f:
            json.dump(self.knowledge, f, indent=2, ensure_ascii=False)

    def learn_from_project(self, project_name: str) -> Dict[str, Any]:
        """Learn from a single project."""
        project_path = HOME / project_name
        if not project_path.exists():
            return {'status': 'not_found', 'project': project_name}

        print(f'\n  Learning from {project_name}...')

        # Collect project info
        project_info = {
            'name': project_name,
            'path': str(project_path),
            'learned_at': datetime.now().isoformat(),
            'files': [],
            'functions': [],
            'classes': [],
            'imports': [],
            'api_endpoints': [],
            'env_vars': [],
            'concepts': []
        }

        # Analyze Python files
        py_files = list(project_path.glob('*.py'))
        for py_file in py_files[:10]:  # Limit to 10 files
            file_info = self._analyze_python_file(py_file)
            project_info['files'].append(file_info['name'])
            project_info['functions'].extend(file_info['functions'])
            project_info['classes'].extend(file_info['classes'])
            project_info['imports'].extend(file_info['imports'])
            project_info['api_endpoints'].extend(file_info['api_endpoints'])
            project_info['env_vars'].extend(file_info['env_vars'])

        # Remove duplicates
        project_info['imports'] = list(set(project_info['imports']))
        project_info['env_vars'] = list(set(project_info['env_vars']))

        # Use AI to extract concepts
        if self.model and py_files:
            concepts = self._extract_concepts_with_ai(project_path, py_files[:3])
            project_info['concepts'] = concepts

        # Update knowledge base
        self.knowledge['projects'][project_name] = project_info

        return {'status': 'learned', 'project': project_name, 'info': project_info}

    def _analyze_python_file(self, file_path: Path) -> Dict[str, Any]:
        """Analyze a Python file for patterns."""
        info = {
            'name': file_path.name,
            'functions': [],
            'classes': [],
            'imports': [],
            'api_endpoints': [],
            'env_vars': []
        }

        try:
            content = file_path.read_text(errors='ignore')

            # Find function definitions
            func_pattern = r'def\s+(\w+)\s*\('
            info['functions'] = re.findall(func_pattern, content)[:20]

            # Find class definitions
            class_pattern = r'class\s+(\w+)\s*[\(:]'
            info['classes'] = re.findall(class_pattern, content)[:10]

            # Find imports
            import_pattern = r'^(?:from\s+(\S+)|import\s+(\S+))'
            for match in re.finditer(import_pattern, content, re.MULTILINE):
                imp = match.group(1) or match.group(2)
                if imp:
                    info['imports'].append(imp.split('.')[0])

            # Find API endpoints (Flask/FastAPI style)
            route_pattern = r'@(?:app|router)\.(?:get|post|put|delete|route)\s*\([\'"]([^\'"]+)[\'"]'
            info['api_endpoints'] = re.findall(route_pattern, content)

            # Find environment variables
            env_pattern = r'os\.(?:environ\.get|getenv)\s*\(\s*[\'"]([^\'"]+)[\'"]'
            info['env_vars'] = re.findall(env_pattern, content)

            env_pattern2 = r'os\.environ\s*\[\s*[\'"]([^\'"]+)[\'"]\s*\]'
            info['env_vars'].extend(re.findall(env_pattern2, content))

        except Exception as e:
            print(f'    Error analyzing {file_path.name}: {e}')

        return info

    def _extract_concepts_with_ai(self, project_path: Path, files: List[Path]) -> List[str]:
        """Use Gemini to extract high-level concepts from code."""
        if not self.model:
            return []

        # Collect code samples
        code_samples = []
        for f in files:
            try:
                content = f.read_text(errors='ignore')[:2000]  # First 2000 chars
                code_samples.append(f'# File: {f.name}\n{content}')
            except:
                pass

        if not code_samples:
            return []

        prompt = f"""Analyze this code from project "{project_path.name}" and extract 3-5 key concepts or patterns.

Code samples:
{chr(10).join(code_samples[:2])}

Return a JSON array of concept strings. Example:
["Uses Telegram bot API", "Implements async handlers", "Environment-based configuration"]

Only return the JSON array, nothing else."""

        try:
            response = self.model.generate_content(prompt)
            text = response.text.strip()

            # Clean up response
            if text.startswith('```'):
                text = text.split('```')[1]
                if text.startswith('json'):
                    text = text[4:]
            text = text.strip()

            concepts = json.loads(text)
            if isinstance(concepts, list):
                return concepts[:5]
        except Exception as e:
            new_key = rotate_on_error(str(e))
            if new_key:
                print(f'    Rotated to new API key')
            else:
                print(f'    AI concept extraction failed: {e}')

        return []

    def learn_all_projects(self) -> Dict[str, Any]:
        """Learn from all internal projects."""
        results = {
            'started_at': datetime.now().isoformat(),
            'projects_learned': 0,
            'projects_failed': 0,
            'details': []
        }

        print('Starting internal learning cycle...')

        for project in INTERNAL_PROJECTS:
            result = self.learn_from_project(project)
            results['details'].append(result)

            if result['status'] == 'learned':
                results['projects_learned'] += 1
                print(f'    -> Learned {len(result["info"]["functions"])} functions, '
                      f'{len(result["info"]["classes"])} classes')
            else:
                results['projects_failed'] += 1
                print(f'    -> Not found')

        # Extract global patterns
        self._extract_global_patterns()

        # Save knowledge
        self._save_knowledge()

        results['completed_at'] = datetime.now().isoformat()
        return results

    def _extract_global_patterns(self):
        """Extract patterns across all projects."""
        all_imports = []
        all_env_vars = []
        all_endpoints = []

        for project in self.knowledge['projects'].values():
            all_imports.extend(project.get('imports', []))
            all_env_vars.extend(project.get('env_vars', []))
            all_endpoints.extend(project.get('api_endpoints', []))

        # Count common imports
        import_counts = {}
        for imp in all_imports:
            import_counts[imp] = import_counts.get(imp, 0) + 1

        # Find common patterns
        common_imports = [k for k, v in sorted(import_counts.items(),
                                               key=lambda x: -x[1])[:10]]

        self.knowledge['patterns'] = {
            'common_imports': common_imports,
            'all_env_vars': list(set(all_env_vars)),
            'api_endpoints': list(set(all_endpoints))
        }


class TelegramNotifier:
    """Send learning reports to Telegram."""

    def __init__(self):
        self.token = TELEGRAM_BOT_TOKEN
        self.chat_id = TELEGRAM_CHAT_ID

    def send_report(self, results: Dict[str, Any]):
        """Send learning report to Telegram."""
        if not self.token or not self.chat_id:
            print('Telegram not configured, skipping notification')
            return

        # Build message
        msg = "🧠 *AI Learning Agent v2 Report*\n\n"
        msg += f"📊 *Internal Learning Cycle*\n"
        msg += f"• Projects learned: {results['projects_learned']}\n"
        msg += f"• Projects not found: {results['projects_failed']}\n"
        msg += f"• Time: {results.get('started_at', 'N/A')[:19]}\n\n"

        # List successful projects
        learned = [d['project'] for d in results['details'] if d['status'] == 'learned']
        if learned:
            msg += f"✅ *Learned from:*\n"
            for p in learned[:5]:
                msg += f"  • {p}\n"

        msg += f"\n💾 Knowledge saved to internal database"

        # Send via Telegram API
        try:
            url = f"https://api.telegram.org/bot{self.token}/sendMessage"
            data = {
                'chat_id': self.chat_id,
                'text': msg,
                'parse_mode': 'Markdown'
            }
            requests.post(url, data=data, timeout=10)
            print('Telegram notification sent')
        except Exception as e:
            print(f'Failed to send Telegram notification: {e}')


def generate_summary_report(knowledge: Dict[str, Any]) -> str:
    """Generate a summary report of current knowledge."""
    projects = knowledge.get('projects', {})
    patterns = knowledge.get('patterns', {})

    total_functions = sum(len(p.get('functions', [])) for p in projects.values())
    total_classes = sum(len(p.get('classes', [])) for p in projects.values())

    report = f"""# AI Learning Agent v2 - Knowledge Summary

## Overview
- **Projects analyzed:** {len(projects)}
- **Total functions discovered:** {total_functions}
- **Total classes discovered:** {total_classes}
- **Last updated:** {knowledge.get('last_updated', 'Never')}

## Common Imports
{chr(10).join(f'- {imp}' for imp in patterns.get('common_imports', [])[:10])}

## Environment Variables Used
{chr(10).join(f'- `{env}`' for env in patterns.get('all_env_vars', [])[:15])}

## API Endpoints
{chr(10).join(f'- `{ep}`' for ep in patterns.get('api_endpoints', [])[:10])}

## Projects
"""
    for name, info in projects.items():
        concepts = info.get('concepts', [])
        report += f"\n### {name}\n"
        report += f"- Functions: {len(info.get('functions', []))}\n"
        report += f"- Classes: {len(info.get('classes', []))}\n"
        if concepts:
            report += f"- Concepts: {', '.join(concepts[:3])}\n"

    return report


def main():
    print('=' * 60)
    print('AI Learning Agent v2 - Internal Knowledge System')
    print('=' * 60)

    # Initialize learner
    learner = InternalLearner()

    # Run learning cycle
    results = learner.learn_all_projects()

    print()
    print(f'Learning complete!')
    print(f'  Projects learned: {results["projects_learned"]}')
    print(f'  Projects not found: {results["projects_failed"]}')

    # Generate summary report
    report = generate_summary_report(learner.knowledge)
    report_file = DOCS_DIR / 'AI_LEARNING_SUMMARY.md'
    report_file.parent.mkdir(exist_ok=True)
    report_file.write_text(report)
    print(f'  Report saved to: {report_file}')

    # Send Telegram notification
    notifier = TelegramNotifier()
    notifier.send_report(results)

    print()
    print('Done!')


if __name__ == '__main__':
    main()
