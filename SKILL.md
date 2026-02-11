---
name: granola
description: "Manage Granola meeting transcripts - sync, search, list, export, and auto-route to client folders by keyword."
license: MIT
---

# Granola - Meeting Transcript Manager

Extracts and organizes [Granola](https://granola.ai) meeting transcripts from the local cache into markdown files. Routes meetings to client/project folders based on keywords you define.

Two Python scripts, no dependencies beyond Python 3.

## Setup

Before using this skill, clone and configure the scripts:

```bash
git clone https://github.com/alexdobrenko/granola-sync.git ~/granola-sync
```

Edit `~/granola-sync/granola_sync.py` and update `CLIENT_ROUTES` with your clients:

```python
CLIENT_ROUTES = {
    ("acme", "jane", "acme corp"): "Acme-Corp",
    ("standup", "retro"): "Internal",
}
```

For auto-sync every 5 minutes, edit the plist path and load it:

```bash
# Edit com.granola-sync.plist first - update the script path
cp ~/granola-sync/com.granola-sync.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.granola-sync.plist
```

## Commands

### `/granola` or `/granola status`
Show sync health. Run these and present the results:

```bash
# Launchd status
launchctl list | grep granola

# Inbox count
ls ~/granola-transcripts/inbox/*.md 2>/dev/null | wc -l

# Last sync info from tracking
python3 -c "
import json, os
path = os.path.expanduser('~/granola-transcripts/inbox/.synced_ids.json')
if not os.path.exists(path):
    print('No sync data yet. Run: python3 ~/granola-sync/granola_sync.py')
else:
    t = json.load(open(path))
    times = [v.get('synced_at','') for v in t.values() if isinstance(v, dict)]
    times.sort(reverse=True)
    print(f'Last sync: {times[0] if times else \"never\"}')
    print(f'Total synced: {len(t)}')
    routed = sum(1 for v in t.values() if isinstance(v, dict) and v.get('routed'))
    print(f'Routed to clients: {routed}')
    print(f'In inbox: {len(t) - routed}')
"
```

### `/granola sync`
Run a manual sync:

```bash
python3 ~/granola-sync/granola_sync.py
```

### `/granola search <term>`
Search all transcripts:

```bash
python3 ~/granola-sync/granola_transcripts.py --search "<term>"
```

### `/granola list`
List recent transcripts:

```bash
python3 ~/granola-sync/granola_transcripts.py
```

### `/granola export`
Export all transcripts to markdown:

```bash
python3 ~/granola-sync/granola_transcripts.py --export
```

### `/granola show <title or id>`
View a specific transcript:

```bash
python3 ~/granola-sync/granola_transcripts.py --id "<title or id>"
```

### `/granola routes`
Show routing rules. Read `CLIENT_ROUTES` from the sync script and present as a table.

### `/granola add-route <keywords> <folder>`
Add a new routing rule by editing the `CLIENT_ROUTES` dict in `granola_sync.py`.

## How Granola stores data

Cache location: `~/Library/Application Support/Granola/cache-v3.json`

The cache has a nested structure. The top-level `cache` key is a JSON string that needs a second parse:

```python
data = json.load(open(cache_path))
state = json.loads(data['cache'])['state']
# state['transcripts'] = { doc_id: [entries...] }
# state['documents'] = { doc_id: { title, start_time, ... } }
```

Each transcript entry has `text`, `source` ("microphone" = you, "system" = others), and `start_timestamp`.

A meeting is considered "done" when: `meeting_end_count >= 1`, has a title, and has 50+ words.
