#!/usr/bin/env python3
"""
Documentation Generator
Automatically generates documentation for all tracked projects.
Part of the Self-Learning System.
"""

import os
import sys
import json
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any

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
PROJECTS_DIR = Path.home()
DOCS_DIR = Path.home() / 'docs'
KNOWLEDGE_FILE = DOCS_DIR / 'knowledge-base.json'

TRACKED_PROJECTS = [
    'ai-learning-agent',
    'youtube-ai-monitor',
    'agi-news-agent',
    'claude-mailbox',
    'mcp-hub',
    'auto-deployer',
    'arm-hunter'
]

class ProjectAnalyzer:
    """Analyzes project structure and code."""

    def __init__(self, project_path: Path):
        self.path = project_path
        self.name = project_path.name

    def analyze(self) -> Dict[str, Any]:
        """Analyze project and return structured data."""
        return {
            'name': self.name,
            'path': str(self.path),
            'files': self._get_files(),
            'main_file': self._find_main_file(),
            'dependencies': self._get_dependencies(),
            'env_vars': self._get_env_vars(),
            'service': self._get_service_info(),
            'git_info': self._get_git_info(),
            'analyzed_at': datetime.now().isoformat()
        }

    def _get_files(self) -> List[str]:
        """Get list of important files."""
        files = []
        for ext in ['*.py', '*.js', '*.sh', '*.json', '*.md']:
            files.extend([str(f.relative_to(self.path))
                         for f in self.path.glob(ext) if f.is_file()])
        return sorted(files)[:20]

    def _find_main_file(self) -> str:
        """Find the main entry point."""
        candidates = ['main.py', 'app.py', 'server.py', 'bot.py',
                     'index.js', 'server.js']
        # Add project-specific name
        candidates.append(f'{self.name}.py')
        candidates.append(f'{self.name.replace("-", "_")}.py')

        for c in candidates:
            if (self.path / c).exists():
                return c
        py_files = list(self.path.glob('*.py'))
        if py_files:
            return py_files[0].name
        js_files = list(self.path.glob('*.js'))
        if js_files:
            return js_files[0].name
        return ''

    def _get_dependencies(self) -> List[str]:
        """Get project dependencies."""
        deps = []
        req_file = self.path / 'requirements.txt'
        if req_file.exists():
            content = req_file.read_text()
            for line in content.split('\n'):
                line = line.strip()
                if line and not line.startswith('#'):
                    # Extract package name without version
                    pkg = line.split('==')[0].split('>=')[0].split('<=')[0].split('[')[0]
                    if pkg:
                        deps.append(pkg)

        pkg_file = self.path / 'package.json'
        if pkg_file.exists():
            try:
                pkg = json.loads(pkg_file.read_text())
                deps.extend(pkg.get('dependencies', {}).keys())
            except:
                pass
        return deps[:20]

    def _get_env_vars(self) -> List[str]:
        """Get required environment variables (names only)."""
        import re
        env_vars = set()

        for py_file in self.path.glob('*.py'):
            try:
                content = py_file.read_text()
                # Find os.environ.get() and os.getenv()
                pattern1 = r'os\.(?:environ\.get|getenv)\s*\(\s*[\'"]([^\'"]+)[\'"]'
                matches = re.findall(pattern1, content)
                env_vars.update(matches)
                # Find os.environ[]
                pattern2 = r'os\.environ\s*\[\s*[\'"]([^\'"]+)[\'"]\s*\]'
                matches = re.findall(pattern2, content)
                env_vars.update(matches)
            except:
                pass
        return sorted(list(env_vars))

    def _get_service_info(self) -> Dict[str, Any]:
        """Get systemd service information."""
        service_name = self.name.replace('_', '-')
        try:
            result = subprocess.run(
                ['systemctl', 'is-active', service_name],
                capture_output=True, text=True, timeout=5
            )
            status = result.stdout.strip()
        except:
            status = 'unknown'

        return {
            'name': service_name,
            'status': status
        }

    def _get_git_info(self) -> Dict[str, Any]:
        """Get git repository information."""
        git_dir = self.path / '.git'
        if not git_dir.exists():
            return {'tracked': False}

        try:
            result = subprocess.run(
                ['git', '-C', str(self.path), 'remote', 'get-url', 'origin'],
                capture_output=True, text=True, timeout=5
            )
            remote = result.stdout.strip()
            if 'github.com' in remote:
                # Extract repo name from URL (remove token if present)
                parts = remote.split('/')
                repo = '/'.join(parts[-2:]).replace('.git', '')
                # Clean up token from URL
                if '@github.com' in repo:
                    repo = repo.split('@github.com/')[-1]
                return {'tracked': True, 'repo': repo}
        except:
            pass
        return {'tracked': True, 'repo': 'unknown'}


class DocsGenerator:
    """Main documentation generator."""

    def __init__(self):
        self.docs_dir = DOCS_DIR
        self.docs_dir.mkdir(exist_ok=True)
        (self.docs_dir / 'projects').mkdir(exist_ok=True)

        # Initialize Gemini if available
        self.model = None
        api_key = get_key()
        if api_key and genai:
            try:
                genai.configure(api_key=api_key)
                self.model = genai.GenerativeModel('gemini-2.0-flash')
            except Exception as e:
                print(f'Warning: Could not initialize Gemini: {e}')

    def generate_all(self) -> Dict[str, Any]:
        """Generate documentation for all projects."""
        knowledge_base = {
            'generated_at': datetime.now().isoformat(),
            'projects': {}
        }

        for project_name in TRACKED_PROJECTS:
            project_path = PROJECTS_DIR / project_name
            if project_path.exists():
                print(f'Analyzing {project_name}...')
                analyzer = ProjectAnalyzer(project_path)
                data = analyzer.analyze()
                knowledge_base['projects'][project_name] = data
                self._generate_project_doc(project_name, data)
            else:
                print(f'  Skipping {project_name} (not found)')

        # Save knowledge base
        with open(KNOWLEDGE_FILE, 'w') as f:
            json.dump(knowledge_base, f, indent=2)

        # Generate main README
        self._generate_main_readme(knowledge_base)
        return knowledge_base

    def _generate_project_doc(self, name: str, data: Dict[str, Any]):
        """Generate markdown documentation for a project."""
        # Format file list
        if data['files']:
            files_str = '\n'.join(f'- `{f}`' for f in data['files'])
        else:
            files_str = '- No files found'

        # Format dependencies
        if data['dependencies']:
            deps_str = '\n'.join(f'- {d}' for d in data['dependencies'])
        else:
            deps_str = '- None'

        # Format env vars
        if data['env_vars']:
            env_str = '\n'.join(f'- `{e}`' for e in data['env_vars'])
        else:
            env_str = '- None'

        # Git info
        tracked = 'Yes' if data['git_info']['tracked'] else 'No'
        repo = data['git_info'].get('repo', 'N/A')

        doc = f"""# {name}

## Overview
- **Path:** `{data['path']}`
- **Main File:** `{data['main_file']}`
- **Last Analyzed:** {data['analyzed_at']}

## Service Status
- **Service Name:** {data['service']['name']}
- **Status:** {data['service']['status']}

## Files
{files_str}

## Dependencies
{deps_str}

## Environment Variables
{env_str}

## Git Repository
- **Tracked:** {tracked}
- **Repository:** {repo}

---
*Auto-generated by docs_generator.py*
"""

        doc_path = self.docs_dir / 'projects' / f'{name}.md'
        doc_path.write_text(doc)
        print(f'  Generated: {doc_path}')

    def _generate_main_readme(self, kb: Dict[str, Any]):
        """Generate main README."""
        projects = kb['projects']
        total = len(projects)
        running = sum(1 for p in projects.values()
                     if p['service']['status'] == 'active')

        # Build table rows
        table_rows = []
        for name, data in projects.items():
            status = data['service']['status']
            emoji = '🟢' if status == 'active' else '🔴' if status in ['inactive', 'failed'] else '⚪'
            deps = len(data['dependencies'])
            main_file = data['main_file'] or 'N/A'
            table_rows.append(f'| {name} | {emoji} {status} | {main_file} | {deps} |')

        # Build project links
        project_links = []
        for name in projects.keys():
            project_links.append(f'- [{name}](projects/{name}.md)')

        summary = f"""# Oracle VM Knowledge Base

## System Overview
- **Total Projects:** {total}
- **Running Services:** {running}/{total}
- **Last Updated:** {kb['generated_at']}

## Projects

| Project | Status | Main File | Dependencies |
|---------|--------|-----------|--------------|
{chr(10).join(table_rows)}

## Project Documentation
{chr(10).join(project_links)}

---
*Auto-generated by docs_generator.py*
"""

        readme_path = self.docs_dir / 'README.md'
        readme_path.write_text(summary)
        print(f'Generated: {readme_path}')


def main():
    print('=' * 50)
    print('Documentation Generator')
    print('=' * 50)
    print()

    generator = DocsGenerator()
    kb = generator.generate_all()

    print()
    print(f'Knowledge base saved to: {KNOWLEDGE_FILE}')
    print(f'Total projects documented: {len(kb["projects"])}')
    print('Done!')


if __name__ == '__main__':
    main()
