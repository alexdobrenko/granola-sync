#!/usr/bin/env python3
"""
Granola Transcript Auto-Sync
- Extracts completed meeting transcripts from Granola's local cache
- Routes them to project/client folders based on keyword matching
- Re-checks previously synced items for title updates and routing changes
- Run manually or via launchd every 5 minutes

Setup:
    1. Edit the paths and CLIENT_ROUTES below
    2. Run: python3 granola_sync.py
    3. (Optional) Set up launchd for auto-sync - see README
"""

import json
import os
import re
from datetime import datetime

# --- CONFIGURE THESE ---

# Granola stores its cache here (macOS default, shouldn't need to change)
CACHE_PATH = os.path.expanduser("~/Library/Application Support/Granola/cache-v3.json")

# Where unrouted transcripts land
INBOX_DIR = os.path.expanduser("~/granola-transcripts/inbox")

# Tracking file (keeps record of what's been synced)
TRACKING_FILE = os.path.join(INBOX_DIR, ".synced_ids.json")

# Parent folder for client/project directories
CLIENTS_DIR = os.path.expanduser("~/granola-transcripts/clients")

# Keyword -> folder mapping
# If a meeting title contains any keyword in the tuple, it routes to that folder.
# Edit this to match your clients/projects.
CLIENT_ROUTES = {
    ("acme", "acme corp", "jane"): "Acme-Corp",
    ("internal", "standup", "retro"): "Internal",
    # Add your own routes here:
    # ("keyword1", "keyword2"): "Folder-Name",
}

# --- END CONFIG ---


def load_cache():
    """Load and parse Granola's cache file."""
    with open(CACHE_PATH, 'r') as f:
        data = json.load(f)
    # Granola nests a JSON string inside the top-level JSON
    cache = json.loads(data['cache'])
    return cache.get('state', {})


def load_tracking():
    """Load tracking data (synced IDs + metadata)."""
    if os.path.exists(TRACKING_FILE):
        with open(TRACKING_FILE, 'r') as f:
            data = json.load(f)
        if isinstance(data, list):
            return {id_: {"synced_at": "unknown", "routed": False, "file": None} for id_ in data}
        return data
    return {}


def save_tracking(tracking):
    """Save tracking data."""
    with open(TRACKING_FILE, 'w') as f:
        json.dump(tracking, f, indent=2)


def is_meeting_done(doc, entries):
    """Check if a meeting is completed and worth syncing."""
    end_count = doc.get('meeting_end_count')
    title = doc.get('title')
    word_count = sum(len(e.get('text', '').split()) for e in entries) if entries else 0

    if not end_count or end_count < 1:
        return False
    if not title:
        return False
    if word_count < 50:
        return False
    return True


def match_client(title, people=None):
    """Match a meeting to a client folder based on title keywords."""
    search_text = (title or "").lower()

    if people and isinstance(people, dict):
        people_title = people.get('title', '')
        if people_title:
            search_text += " " + people_title.lower()

    for keywords, folder_name in CLIENT_ROUTES.items():
        for kw in keywords:
            if kw in search_text:
                return folder_name
    return None


def get_client_call_notes_dir(client_folder):
    """Get or create the call-notes subfolder for a client."""
    path = os.path.join(CLIENTS_DIR, client_folder, "call-notes")
    os.makedirs(path, exist_ok=True)
    return path


def format_transcript(entries):
    """Format transcript entries into readable markdown."""
    lines = []
    current_source = None

    for entry in entries:
        text = entry.get('text', '').strip()
        source = entry.get('source', 'unknown')

        if not text:
            continue

        if source != current_source:
            if source == 'microphone':
                lines.append('\n**[You]** ')
            elif source == 'system':
                lines.append('\n**[Other]** ')
            else:
                lines.append(f'\n**[{source}]** ')
            current_source = source

        lines.append(text)

    return ' '.join(lines)


def make_filename(date_str, title):
    """Create a safe filename from date and title."""
    safe_title = re.sub(r'[^\w\s-]', '', title)[:60].strip().replace(' ', '-')
    safe_title = re.sub(r'-+', '-', safe_title)
    return f"{date_str}-{safe_title}.md"


def build_content(title, doc, entries):
    """Build the markdown content for a transcript file."""
    start_time = doc.get('start_time') or doc.get('startTime') or doc.get('created_at') or ''
    word_count = sum(len(e.get('text', '').split()) for e in entries) if entries else 0
    doc_id = doc.get('id', 'unknown')

    cal_event = doc.get('google_calendar_event', {}) or {}
    cal_title = cal_event.get('summary', '')

    content = f"# {title}\n\n"
    content += f"**Meeting ID:** {doc_id}\n"
    if cal_title and cal_title != title:
        content += f"**Calendar:** {cal_title}\n"
    content += f"**Date:** {start_time or 'Unknown'}\n"
    content += f"**Words:** ~{word_count}\n"
    content += f"**Segments:** {len(entries)}\n\n"
    content += "---\n\n"
    content += format_transcript(entries)

    return content


def get_date_prefix(doc):
    """Extract date from document."""
    start_time = doc.get('start_time') or doc.get('startTime') or doc.get('created_at') or ''
    if start_time and len(start_time) >= 10:
        try:
            return start_time[:10]
        except Exception:
            pass
    return datetime.now().strftime('%Y-%m-%d')


def sync_transcripts():
    """Main sync: process new transcripts and re-route existing ones."""
    os.makedirs(INBOX_DIR, exist_ok=True)

    state = load_cache()
    transcripts = state.get('transcripts', {})
    documents = state.get('documents', {})
    doc_lookup = documents if isinstance(documents, dict) else {d.get('id'): d for d in documents}

    tracking = load_tracking()
    new_count = 0
    routed_count = 0
    updated_count = 0

    for doc_id, entries in transcripts.items():
        if not entries:
            continue

        doc = doc_lookup.get(doc_id, {})

        if not is_meeting_done(doc, entries):
            continue

        title = doc.get('title', 'Untitled Meeting')
        date_prefix = get_date_prefix(doc)
        people = doc.get('people')
        client_folder = match_client(title, people)

        if client_folder:
            dest_dir = get_client_call_notes_dir(client_folder)
        else:
            dest_dir = INBOX_DIR

        filename = make_filename(date_prefix, title)
        filepath = os.path.join(dest_dir, filename)

        tracked = tracking.get(doc_id)

        if tracked:
            old_file = tracked.get('file')
            was_routed = tracked.get('routed', False)

            if not was_routed and client_folder and old_file:
                old_path = os.path.join(INBOX_DIR, old_file)
                if os.path.exists(old_path):
                    content = build_content(title, doc, entries)
                    with open(filepath, 'w') as f:
                        f.write(content)
                    os.remove(old_path)
                    tracking[doc_id] = {
                        "synced_at": datetime.now().isoformat(),
                        "routed": True,
                        "client": client_folder,
                        "file": filename,
                        "title": title,
                    }
                    routed_count += 1
                    print(f"Routed: {old_file} -> {client_folder}/call-notes/{filename}")

            elif old_file and tracked.get('title') != title:
                old_path = os.path.join(dest_dir if was_routed else INBOX_DIR, old_file)
                if os.path.exists(old_path):
                    content = build_content(title, doc, entries)
                    with open(filepath, 'w') as f:
                        f.write(content)
                    if old_path != filepath:
                        os.remove(old_path)
                    tracking[doc_id] = {
                        "synced_at": datetime.now().isoformat(),
                        "routed": was_routed,
                        "client": client_folder if was_routed else None,
                        "file": filename,
                        "title": title,
                    }
                    updated_count += 1
                    print(f"Updated: {old_file} -> {filename}")

        else:
            content = build_content(title, doc, entries)
            with open(filepath, 'w') as f:
                f.write(content)

            tracking[doc_id] = {
                "synced_at": datetime.now().isoformat(),
                "routed": bool(client_folder),
                "client": client_folder,
                "file": filename,
                "title": title,
            }
            new_count += 1

            if client_folder:
                print(f"Synced -> {client_folder}/call-notes/{filename}")
            else:
                print(f"Synced -> inbox/{filename}")

    save_tracking(tracking)

    total = new_count + routed_count + updated_count
    if total == 0:
        print("No new transcripts to sync.")
    else:
        parts = []
        if new_count:
            parts.append(f"{new_count} new")
        if routed_count:
            parts.append(f"{routed_count} routed")
        if updated_count:
            parts.append(f"{updated_count} updated")
        print(f"\nDone: {', '.join(parts)}.")


if __name__ == "__main__":
    sync_transcripts()
