"""Persistent favorites and recently applied presets.

Pure Python (no bpy): the caller provides the JSON file path via setup().
Entries carry everything needed to re-apply a preset without re-browsing:
preset type, generation/folder keys, display name, duf and thumbnail paths.
"""

import json
import os

MAX_RECENTS = 12

_path = None
_data = None

# Bumped on every mutation; cached UI enum items key on this to invalidate.
version = 0


def setup(path):
    global _path, _data
    if path != _path:
        _path = path
        _data = None


def _load():
    global _data
    if _data is None:
        try:
            with open(_path, encoding="utf-8") as fp:
                _data = json.load(fp)
        except (OSError, ValueError):
            _data = {}
        for key in ("favorites", "recents"):
            _data.setdefault(key, [])
    return _data


def _save():
    global version
    version += 1
    try:
        os.makedirs(os.path.dirname(_path), exist_ok=True)
        with open(_path, "w", encoding="utf-8") as fp:
            json.dump(_data, fp, indent=1)
    except OSError:
        pass


def favorites():
    return _load()["favorites"]


def recents():
    return _load()["recents"]


def make_entry(preset_type, generation, folder, pose):
    return {
        "type": preset_type,
        "generation": generation,
        "folder": folder,
        "name": pose.name,
        "duf": pose.duf_path,
        "thumb": pose.thumb_path,
    }


def find(entries, duf):
    for entry in entries:
        if entry["duf"] == duf:
            return entry
    return None


def is_favorite(duf):
    return find(favorites(), duf) is not None


def toggle_favorite(entry):
    """Add or remove a favorite. Returns True if it was added."""
    favs = favorites()
    existing = find(favs, entry["duf"])
    if existing is not None:
        favs.remove(existing)
    else:
        favs.append(entry)
    _save()
    return existing is None


def remove_favorite(duf):
    favs = favorites()
    existing = find(favs, duf)
    if existing is not None:
        favs.remove(existing)
        _save()


def add_recent(entry):
    """Record an applied preset, most recent first, deduplicated, capped."""
    recs = recents()
    existing = find(recs, entry["duf"])
    if existing is not None:
        recs.remove(existing)
    recs.insert(0, entry)
    del recs[MAX_RECENTS:]
    _save()
