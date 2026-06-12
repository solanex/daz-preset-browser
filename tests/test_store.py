"""Unit tests for store.py (favorites/recents persistence)."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import store
from scanner import Pose


@pytest.fixture(autouse=True)
def fresh_store(tmp_path):
    store.setup(str(tmp_path / "presets.json"))
    yield
    store.setup(None)


def entry(name, duf=None):
    pose = Pose(name.lower() + ".duf", name, duf or "/lib/%s.duf" % name,
                "/lib/%s.png" % name)
    return store.make_entry('POSES', "genesis 9", "vendor/product", pose)


def test_toggle_favorite_roundtrip():
    e = entry("Pose A")
    assert store.toggle_favorite(e) is True
    assert store.is_favorite(e["duf"])
    assert store.toggle_favorite(e) is False
    assert not store.is_favorite(e["duf"])


def test_remove_favorite():
    e = entry("Pose A")
    store.toggle_favorite(e)
    store.remove_favorite(e["duf"])
    assert store.favorites() == []
    store.remove_favorite("/not/there.duf")  # harmless


def test_recents_dedupe_order_and_cap():
    for i in range(store.MAX_RECENTS + 3):
        store.add_recent(entry("Pose %02d" % i))
    recs = store.recents()
    assert len(recs) == store.MAX_RECENTS
    assert recs[0]["name"] == "Pose %02d" % (store.MAX_RECENTS + 2)
    # Re-applying an existing entry moves it to the front without duplicating
    store.add_recent(entry("Pose 05"))
    recs = store.recents()
    assert recs[0]["name"] == "Pose 05"
    assert sum(1 for e in recs if e["name"] == "Pose 05") == 1
    assert len(recs) == store.MAX_RECENTS


def test_persists_across_reload(tmp_path):
    path = str(tmp_path / "persist.json")
    store.setup(path)
    store.toggle_favorite(entry("Keeper"))
    store.add_recent(entry("Recent"))
    # Force a reload from disk
    store.setup(None)
    store.setup(path)
    assert [e["name"] for e in store.favorites()] == ["Keeper"]
    assert [e["name"] for e in store.recents()] == ["Recent"]


def test_version_bumps_on_mutation():
    before = store.version
    store.add_recent(entry("Pose A"))
    assert store.version > before


def test_corrupt_file_is_harmless(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text("{not json")
    store.setup(str(path))
    assert store.favorites() == []
    store.add_recent(entry("Pose A"))
    assert len(store.recents()) == 1
