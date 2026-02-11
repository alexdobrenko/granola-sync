# Granola Sync

Extract and auto-route your [Granola](https://granola.ai) meeting transcripts to markdown files. Meetings get sorted into client/project folders based on keywords you define.

No dependencies. Just Python 3 and a Mac running Granola.

## What it does

Granola records your meetings and stores transcripts locally in a cache file. These scripts read that cache and turn it into organized markdown files:

- **Unmatched meetings** go to an inbox folder
- **Matched meetings** get routed to client folders based on keywords in the title
- **Title updates** are detected and files get renamed automatically
- **Re-routing** happens when a previously unmatched meeting gets a title that matches a client

## Quick start

```bash
git clone https://github.com/alexdobrenko/granola-sync.git
cd granola-sync
```

Edit `granola_sync.py` and update the `CLIENT_ROUTES` dict with your own clients:

```python
CLIENT_ROUTES = {
    ("acme", "jane", "acme corp"): "Acme-Corp",
    ("internal", "standup"): "Internal",
}
```

Run it:

```bash
python3 granola_sync.py      # Sync transcripts
python3 granola_transcripts.py          # List all transcripts
python3 granola_transcripts.py --search "budget"    # Search
python3 granola_transcripts.py --export             # Export all to markdown
python3 granola_transcripts.py --id "meeting title"  # View one transcript
```

## Auto-sync with launchd

To run the sync every 5 minutes automatically:

1. Edit `com.granola-sync.plist` and update the path to `granola_sync.py`
2. Copy it to your LaunchAgents folder:

```bash
cp com.granola-sync.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.granola-sync.plist
```

Check it's running:

```bash
launchctl list | grep granola
```

Stop it:

```bash
launchctl unload ~/Library/LaunchAgents/com.granola-sync.plist
```

Logs go to `/tmp/granola-sync.log`.

## How Granola stores data

Granola keeps a local cache at `~/Library/Application Support/Granola/cache-v3.json`. The structure is a bit unusual: the top-level JSON has a `cache` key whose value is a JSON *string* (not an object). So you need to parse it twice:

```python
import json

with open(cache_path) as f:
    data = json.load(f)

state = json.loads(data['cache'])['state']

# state['transcripts'] = { doc_id: [entries...] }
# state['documents'] = { doc_id: { title, start_time, ... } }
```

Each transcript entry has:
- `text` - the transcribed text
- `source` - either `"microphone"` (you) or `"system"` (everyone else)
- `start_timestamp` - when the segment started

A meeting is "done" when it has `meeting_end_count >= 1`, a title, and 50+ words of content.

## File structure

```
~/granola-transcripts/
  inbox/                    # Unrouted transcripts
    .synced_ids.json        # Tracking file
    2024-01-15-Team-Standup.md
  clients/
    Acme-Corp/
      call-notes/
        2024-01-14-Acme-Kickoff.md
    Internal/
      call-notes/
        2024-01-15-Sprint-Retro.md
  exports/                  # Bulk exports from CLI
```

## License

MIT
