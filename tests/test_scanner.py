"""Unit tests for scanner.py — runs with plain pytest, no Blender needed."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scanner


def touch(*parts):
    path = os.path.join(*parts)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w"):
        pass


@pytest.fixture
def roots(tmp_path):
    """Two content roots with overlapping content that differs in case."""
    a = tmp_path / "lib_a"
    b = tmp_path / "lib_b"

    # Root A: normal spelling
    touch(a, "People", "Genesis 9", "Poses", "Aeon Soul",
          "Everyday Walking Poses", "Wlk Cautious 01 G9.duf")
    touch(a, "People", "Genesis 9", "Poses", "Aeon Soul",
          "Everyday Walking Poses", "Wlk Cautious 01 G9.png")
    touch(a, "People", "Genesis 9", "Poses", "Aeon Soul",
          "Everyday Walking Poses", "Wlk Cautious 01 G9.tip.png")
    # A pose with no thumbnail at all
    touch(a, "People", "Genesis 9", "Poses", "Aeon Soul",
          "Everyday Walking Poses", "No Thumb Pose.duf")
    # A duf directly in a vendor folder (single level)
    touch(a, "People", "Genesis 9", "Poses", "FG Sitting Poses", "Sit 01.duf")
    touch(a, "People", "Genesis 9", "Poses", "FG Sitting Poses", "Sit 01.png")
    # A generation folder without Poses must be ignored
    touch(a, "People", "Genesis 8 Female", "Characters", "Vicky.duf")
    # Non-pose junk directly in People/
    touch(a, "People", "Z Store.png")

    # Root B: same folders but different case, plus unique content,
    # and a thumbnail whose case doesn't match its duf
    touch(b, "people", "GENESIS 9", "poses", "aeon soul",
          "everyday walking poses", "Wlk Extra 02 G9.duf")
    touch(b, "people", "GENESIS 9", "poses", "aeon soul",
          "everyday walking poses", "WLK EXTRA 02 G9.PNG")
    touch(b, "people", "GENESIS 9", "poses", "Daz Originals",
          "Magic Lessons Poses", "MGCLSNS 01 Standing.duf")
    # The other thumbnail convention: <name>.duf.png
    touch(b, "people", "GENESIS 9", "poses", "Daz Originals",
          "Magic Lessons Poses", "MGCLSNS 01 Standing.duf.png")
    touch(b, "people", "Genesis 8.1 Female", "Poses", "Base", "T-Pose.duf")

    # Expressions category, only in root A and only for Genesis 9
    touch(a, "People", "Genesis 9", "Expressions", "3D Sugar", "Happy.duf")
    touch(a, "People", "Genesis 9", "Expressions", "3D Sugar", "Happy.png")

    return [str(a), str(b)]


def test_generations_merge_case_insensitively(roots):
    gens = scanner.list_generations(roots, "Poses")
    assert set(gens) == {"genesis 9", "genesis 8.1 female"}
    g9 = gens["genesis 9"]
    assert g9.label == "Genesis 9"  # first spelling wins
    assert len(g9.paths) == 2       # found in both roots


def test_folders_flatten_and_merge(roots):
    gens = scanner.list_generations(roots, "Poses")
    folders = scanner.list_pose_folders(gens["genesis 9"], "Poses")
    labels = {f.label for f in folders.values()}
    assert "Aeon Soul - Everyday Walking Poses" in labels
    assert "FG Sitting Poses" in labels
    assert "Daz Originals - Magic Lessons Poses" in labels
    # The Aeon Soul folder exists in both roots under different case: one entry
    merged = folders["aeon soul/everyday walking poses"]
    assert len(merged.paths) == 2


def test_poses_merge_thumbnails_and_skip_tips(roots):
    gens = scanner.list_generations(roots, "Poses")
    folders = scanner.list_pose_folders(gens["genesis 9"], "Poses")
    poses = scanner.list_poses(folders["aeon soul/everyday walking poses"])
    by_name = {p.name: p for p in poses}
    assert set(by_name) == {"Wlk Cautious 01 G9", "No Thumb Pose", "Wlk Extra 02 G9"}
    # Thumbnail paired, and it is the .png, not the .tip.png
    assert by_name["Wlk Cautious 01 G9"].thumb_path.endswith("Wlk Cautious 01 G9.png")
    # Thumbnail matched despite case mismatch
    assert by_name["Wlk Extra 02 G9"].thumb_path.endswith("WLK EXTRA 02 G9.PNG")
    assert by_name["No Thumb Pose"].thumb_path is None
    # The <name>.duf.png convention is also recognized
    magic = scanner.list_poses(folders["daz originals/magic lessons poses"])
    assert magic[0].thumb_path.endswith("MGCLSNS 01 Standing.duf.png")


def test_cache_and_lookup(roots):
    scanner.clear_cache()
    gens = scanner.get_generations(roots, "Poses")
    assert scanner.get_generations(roots, "Poses") is gens  # cached
    pose = scanner.get_pose(roots, "Poses", "genesis 9", "fg sitting poses",
                            "sit 01.duf")
    assert pose is not None and pose.name == "Sit 01"
    scanner.clear_cache()


def test_expressions_category(roots):
    # Only generations with an Expressions folder show up for that category
    gens = scanner.list_generations(roots, "Expressions")
    assert set(gens) == {"genesis 9"}
    folders = scanner.list_pose_folders(gens["genesis 9"], "Expressions")
    assert [f.label for f in folders.values()] == ["3D Sugar"]
    exprs = scanner.list_poses(folders["3d sugar"])
    assert len(exprs) == 1 and exprs[0].name == "Happy"
    assert exprs[0].thumb_path.endswith("Happy.png")
    # Pose and expression caches don't bleed into each other
    scanner.clear_cache()
    assert "3d sugar" not in scanner.get_pose_folders(roots, "Poses", "genesis 9")
    scanner.clear_cache()


def test_missing_roots_are_harmless(tmp_path):
    gens = scanner.list_generations([str(tmp_path / "nope"), str(tmp_path)],
                                    "Poses")
    assert gens == {}


def test_source_for_generation():
    assert scanner.source_for_generation("genesis 9") == "genesis_9"
    assert scanner.source_for_generation("genesis 9 toon") == "genesis_9"
    assert scanner.source_for_generation("genesis 8.1 female") == "genesis_8_female"
    assert scanner.source_for_generation("genesis 8 female") == "genesis_8_female"
    # Unisex generation folders fall back to the female rest pose
    assert scanner.source_for_generation("genesis 3") == "genesis_3_female"
    assert scanner.source_for_generation("genesis") == "genesis"
    assert scanner.source_for_generation("victoria 8") == "victoria_8"
    assert scanner.source_for_generation("freak 4") is None
