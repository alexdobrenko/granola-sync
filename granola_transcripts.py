#!/usr/bin/env python3
"""
Granola Transcript CLI
List, search, view, and export your Granola meeting transcripts.

Usage:
    python3 granola_transcripts.py                    # List all transcripts
    python3 granola_transcripts.py --export           # Export all to markdown
    python3 granola_transcripts.py --id <doc_id>      # Show specific transcript
    python3 granola_transcripts.py --search <term>    # Search transcripts
"""

import json
import os
import sys
import re
from datetime import datetime

# Granola's local cache (macOS default)
CACHE_PATH = os.path.expanduser("~/Library/Application Support/Granola/cache-v3.json")

# Where exported transcripts go
EXPORT_DIR = os.path.expanduser("~/granola-transcripts/exports")


def load_cache():
    """Load and parse Granola's cache file."""
    with open(CACHE_PATH, 'r') as f:
        data = json.load(f)
    # Granola nests a JSON string inside the top-level JSON
    cache = json.loads(data['cache'])
    return cache.get('state', {})


def get_transcripts_with_docs(state):
    """Get transcripts paired with their document metadata."""
    transcripts = state.get('transcripts', {})
    documents = state.get('documents', {})

    doc_lookup = documents if isinstance(documents, dict) else {d.get('id'): d for d in documents}

    results = []
    for doc_id, entries in transcripts.items():
        if not entries:
            continue
        doc = doc_lookup.get(doc_id, {})
        results.append({
            'id': doc_id,
            'title': doc.get('title', 'Untitled Meeting'),
            'start_time': doc.get('start_time') or doc.get('startTime'),
            'entries': entries,
            'word_count': sum(len(e.get('text', '').split()) for e in entries)
        })

    return sorted(results, key=lambda x: x.get('start_time') or '', reverse=True)


def format_transcript(entries):
    """Format transcript entries into readable text."""
    lines = []
    current_source = None

    for entry in entries:
        text = entry.get('text', '').strip()
        source = entry.get('source', 'unknown')

        if not text:
            continue

        if source != current_source:
            if source == 'microphone':
                lines.append('\n**[You]**')
            elif source == 'system':
                lines.append('\n**[Other]**')
            current_source = source

        lines.append(text)

    return ' '.join(lines)


def list_transcripts():
    """List all available transcripts."""
    state = load_cache()
    transcripts = get_transcripts_with_docs(state)

    print("=" * 60)
    print("GRANOLA TRANSCRIPTS")
    print("=" * 60)

    for t in transcripts:
        print(f"\n{t['title']}")
        print(f"   ID: {t['id']}")
        print(f"   Words: ~{t['word_count']}")

        preview_entries = t['entries'][:5]
        preview = ' | '.join(e.get('text', '')[:30] for e in preview_entries)
        print(f"   Preview: {preview[:80]}...")


def show_transcript(doc_id):
    """Show full transcript for a specific document."""
    state = load_cache()
    transcripts = get_transcripts_with_docs(state)

    for t in transcripts:
        if t['id'] == doc_id or doc_id.lower() in t['title'].lower():
            print(f"# {t['title']}")
            print(f"Words: ~{t['word_count']}")
            print("=" * 60)
            print(format_transcript(t['entries']))
            return

    print(f"Transcript not found: {doc_id}")


def export_all():
    """Export all transcripts to markdown files."""
    os.makedirs(EXPORT_DIR, exist_ok=True)
    state = load_cache()
    transcripts = get_transcripts_with_docs(state)

    for t in transcripts:
        title = t['title'] or 'Untitled'
        safe_title = re.sub(r'[^\w\s-]', '', title)[:50]
        filename = f"{safe_title.strip().replace(' ', '-')}.md"
        filepath = os.path.join(EXPORT_DIR, filename)

        content = f"# {t['title']}\n\n"
        content += f"**ID:** {t['id']}\n"
        content += f"**Words:** ~{t['word_count']}\n\n"
        content += "---\n\n"
        content += format_transcript(t['entries'])

        with open(filepath, 'w') as f:
            f.write(content)

        print(f"Exported: {filename}")

    print(f"\nAll transcripts exported to: {EXPORT_DIR}")


def search_transcripts(term):
    """Search all transcripts for a term."""
    state = load_cache()
    transcripts = get_transcripts_with_docs(state)

    print(f"Searching for: '{term}'")
    print("=" * 60)

    found = 0
    for t in transcripts:
        full_text = ' '.join(e.get('text', '') for e in t['entries'])
        if term.lower() in full_text.lower():
            idx = full_text.lower().find(term.lower())
            start = max(0, idx - 50)
            end = min(len(full_text), idx + len(term) + 50)
            context = full_text[start:end]

            print(f"\n{t['title']}")
            print(f"   ...{context}...")
            found += 1

    if not found:
        print(f"No matches for '{term}'")


if __name__ == "__main__":
    if len(sys.argv) == 1:
        list_transcripts()
    elif sys.argv[1] == '--export':
        export_all()
    elif sys.argv[1] == '--id' and len(sys.argv) > 2:
        show_transcript(sys.argv[2])
    elif sys.argv[1] == '--search' and len(sys.argv) > 2:
        search_transcripts(' '.join(sys.argv[2:]))
    else:
        print(__doc__)
