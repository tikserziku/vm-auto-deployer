#!/usr/bin/env python3
"""
Change Tracker & Auto-Deployer
Отслеживает изменения в проектах, коммитит в GitHub, уведомляет агентов
"""
import os
import json
import sqlite3
import hashlib
import subprocess
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "changes.db"
TRACKED_PROJECTS = {
    "claude-mailbox": "/home/ubuntu/claude-mailbox",
    "agi-news-agent": "/home/ubuntu/agi-news-agent",
    "mcp-hub": "/home/ubuntu/mcp-hub-data",
    "auto-deployer": "/home/ubuntu/auto-deployer"
}

# Files to track (patterns)
TRACK_PATTERNS = ["*.py", "*.js", "*.md", "*.json", "*.sh"]
IGNORE_PATTERNS = ["__pycache__", "*.pyc", "node_modules", "*.db", "*.log", "*.enc"]

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS file_hashes (
        id INTEGER PRIMARY KEY,
        project TEXT,
        filepath TEXT,
        hash TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(project, filepath)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS changes (
        id INTEGER PRIMARY KEY,
        project TEXT,
        filepath TEXT,
        change_type TEXT,
        description TEXT,
        committed INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    conn.commit()
    conn.close()

def get_file_hash(filepath):
    """Calculate MD5 hash of file"""
    try:
        with open(filepath, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()
    except:
        return None

def should_track(filepath):
    """Check if file should be tracked"""
    name = os.path.basename(filepath)
    path_str = str(filepath)
    
    # Check ignore patterns
    for pattern in IGNORE_PATTERNS:
        if pattern.startswith("*"):
            if name.endswith(pattern[1:]):
                return False
        elif pattern in path_str:
            return False
    
    # Check track patterns
    for pattern in TRACK_PATTERNS:
        if pattern.startswith("*"):
            if name.endswith(pattern[1:]):
                return True
    
    return False

def scan_project(project_name, project_path):
    """Scan project for changes"""
    changes = []
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    project_dir = Path(project_path)
    if not project_dir.exists():
        return changes
    
    # Get all tracked files
    current_files = set()
    for pattern in TRACK_PATTERNS:
        for filepath in project_dir.rglob(pattern):
            if should_track(filepath):
                current_files.add(str(filepath))
    
    # Check for new/modified files
    for filepath in current_files:
        file_hash = get_file_hash(filepath)
        if not file_hash:
            continue
        
        rel_path = str(Path(filepath).relative_to(project_dir))
        
        c.execute("SELECT hash FROM file_hashes WHERE project=? AND filepath=?",
                  (project_name, rel_path))
        row = c.fetchone()
        
        if row is None:
            # New file
            changes.append({
                "project": project_name,
                "filepath": rel_path,
                "type": "added",
                "description": f"New file: {rel_path}"
            })
            c.execute("INSERT INTO file_hashes (project, filepath, hash) VALUES (?, ?, ?)",
                      (project_name, rel_path, file_hash))
        elif row[0] != file_hash:
            # Modified file
            changes.append({
                "project": project_name,
                "filepath": rel_path,
                "type": "modified",
                "description": f"Modified: {rel_path}"
            })
            c.execute("UPDATE file_hashes SET hash=?, updated_at=CURRENT_TIMESTAMP WHERE project=? AND filepath=?",
                      (file_hash, project_name, rel_path))
    
    # Record changes
    for change in changes:
        c.execute("INSERT INTO changes (project, filepath, change_type, description) VALUES (?, ?, ?, ?)",
                  (change["project"], change["filepath"], change["type"], change["description"]))
    
    conn.commit()
    conn.close()
    return changes

def scan_all():
    """Scan all tracked projects"""
    all_changes = []
    for project, path in TRACKED_PROJECTS.items():
        changes = scan_project(project, path)
        all_changes.extend(changes)
    return all_changes

def get_pending_changes():
    """Get changes not yet committed to GitHub"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""SELECT id, project, filepath, change_type, description, created_at 
                 FROM changes WHERE committed=0 ORDER BY created_at""")
    changes = [{"id": r[0], "project": r[1], "filepath": r[2], 
                "type": r[3], "description": r[4], "created_at": r[5]} 
               for r in c.fetchall()]
    conn.close()
    return changes

def get_github_token():
    """Get decrypted GitHub token"""
    result = subprocess.run(
        ["openssl", "enc", "-aes-256-cbc", "-d", "-pbkdf2",
         "-in", "/home/ubuntu/.secrets/gh_token.enc",
         "-pass", "pass:v360admin"],
        capture_output=True, text=True
    )
    return result.stdout.strip()

def commit_to_github(project_name, message):
    """Commit project changes to GitHub"""
    project_path = TRACKED_PROJECTS.get(project_name)
    if not project_path:
        return {"error": f"Unknown project: {project_name}"}
    
    os.chdir(project_path)
    
    # Check if git repo
    if not os.path.exists(".git"):
        return {"error": "Not a git repository"}
    
    try:
        # Stage all changes
        subprocess.run(["git", "add", "-A"], check=True, capture_output=True)
        
        # Commit
        result = subprocess.run(
            ["git", "commit", "-m", message],
            capture_output=True, text=True
        )
        
        if "nothing to commit" in result.stdout or "nothing to commit" in result.stderr:
            return {"status": "no_changes"}
        
        # Push
        token = get_github_token()
        # Set token in URL temporarily
        subprocess.run(["git", "push"], capture_output=True, text=True)
        
        return {"status": "committed", "message": message}
    except Exception as e:
        return {"error": str(e)}

def mark_committed(change_ids):
    """Mark changes as committed"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    for cid in change_ids:
        c.execute("UPDATE changes SET committed=1 WHERE id=?", (cid,))
    conn.commit()
    conn.close()

def generate_commit_message(changes):
    """Generate commit message from changes"""
    if not changes:
        return None
    
    projects = set(c["project"] for c in changes)
    
    if len(projects) == 1:
        project = list(projects)[0]
        files = [c["filepath"] for c in changes]
        if len(files) == 1:
            return f"[{project}] Update {files[0]}"
        else:
            return f"[{project}] Update {len(files)} files"
    else:
        return f"Update {len(changes)} files across {len(projects)} projects"

def get_recent_changes(limit=20):
    """Get recent changes for agents to see"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""SELECT project, filepath, change_type, description, committed, created_at 
                 FROM changes ORDER BY created_at DESC LIMIT ?""", (limit,))
    changes = [{"project": r[0], "filepath": r[1], "type": r[2], 
                "description": r[3], "committed": bool(r[4]), "created_at": r[5]} 
               for r in c.fetchall()]
    conn.close()
    return changes

if __name__ == "__main__":
    import sys
    init_db()
    
    cmd = sys.argv[1] if len(sys.argv) > 1 else "scan"
    
    if cmd == "scan":
        changes = scan_all()
        if changes:
            print(f"🔍 Found {len(changes)} changes:")
            for c in changes:
                print(f"  [{c['type']}] {c['project']}/{c['filepath']}")
        else:
            print("✅ No new changes")
    
    elif cmd == "pending":
        pending = get_pending_changes()
        if pending:
            print(f"📋 {len(pending)} pending changes:")
            for p in pending:
                status = "⏳" 
                print(f"  {status} [{p['project']}] {p['filepath']} ({p['type']})")
        else:
            print("✅ No pending changes")
    
    elif cmd == "recent":
        recent = get_recent_changes()
        print(json.dumps(recent, indent=2, ensure_ascii=False))
    
    elif cmd == "commit":
        pending = get_pending_changes()
        if not pending:
            print("No changes to commit")
            sys.exit(0)
        
        # Group by project
        by_project = {}
        for p in pending:
            if p["project"] not in by_project:
                by_project[p["project"]] = []
            by_project[p["project"]].append(p)
        
        for project, changes in by_project.items():
            msg = generate_commit_message(changes)
            print(f"Committing {project}: {msg}")
            result = commit_to_github(project, msg)
            print(f"  Result: {result}")
            
            if result.get("status") == "committed":
                mark_committed([c["id"] for c in changes])
    
    elif cmd == "init":
        print("Database initialized")
        # Initial scan to establish baseline
        scan_all()
        print("Initial scan complete")
