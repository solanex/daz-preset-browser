"""Scan and merge Daz Studio content libraries for pose presets.

Pure Python on purpose: no bpy imports, so this module can be unit-tested
and run standalone outside Blender.

Daz libraries are authored on Windows, so every path component lookup and
every merge across multiple content directories is done case-insensitively,
even on case-sensitive filesystems (Linux).
"""

import os
from dataclasses import dataclass, field

THUMB_EXTS = (".png", ".jpg", ".jpeg")

# Diffeomorphic srcCharacter identifiers (file names under
# import_daz/data/restposes/), used for pose conversion between generations.
SOURCE_CHARACTERS = (
    "genesis",
    "genesis_2_female", "genesis_2_male",
    "genesis_3_female", "genesis_3_male",
    "genesis_8_female", "genesis_8_male",
    "genesis_9",
    "victoria_7", "victoria_8", "michael_8",
)


def source_for_generation(gen_key):
    """Map a generation folder key ("genesis 8.1 female") to a Diffeomorphic
    srcCharacter identifier ("genesis_8_female"). Generations without their
    own rest pose use the skeleton they share (8.1 = 8, 9 Toon = 9); unisex
    folders ("Genesis 3") fall back to the female variant. None if unknown."""
    key = gen_key.strip().lower().replace(".1", "")
    for suffix in (" toon", " female", " male"):
        if key == "genesis 9" + suffix:
            key = "genesis 9"
    for candidate in (key, key + " female"):
        ident = candidate.replace(" ", "_")
        if ident in SOURCE_CHARACTERS:
            return ident
    return None


@dataclass
class Generation:
    key: str            # lowercased folder name, merge key
    label: str          # display name (first spelling encountered)
    paths: list = field(default_factory=list)  # People/<gen> dirs across roots


@dataclass
class PoseFolder:
    key: str            # lowercased relative path under Poses/, '/'-separated
    label: str          # flattened display name, e.g. "Aeon Soul - Everyday Walking Poses"
    paths: list = field(default_factory=list)  # absolute dirs across roots


@dataclass
class Pose:
    key: str            # lowercased duf filename, merge key
    name: str           # duf stem, display name
    duf_path: str
    thumb_path: str = None


def ci_subdir(parent, name):
    """Return the path of a child directory of `parent` whose name matches
    `name` case-insensitively, or None."""
    target = name.lower()
    try:
        with os.scandir(parent) as it:
            for entry in it:
                if entry.name.lower() == target and entry.is_dir():
                    return entry.path
    except OSError:
        pass
    return None


def list_generations(roots):
    """Union of People/* directories across all content roots, merged
    case-insensitively. Only folders that contain a Poses subfolder count."""
    gens = {}
    for root in roots:
        people = ci_subdir(root, "People")
        if not people:
            continue
        try:
            entries = list(os.scandir(people))
        except OSError:
            continue
        for entry in entries:
            if not entry.is_dir():
                continue
            if not ci_subdir(entry.path, "Poses"):
                continue
            key = entry.name.lower()
            gen = gens.get(key)
            if gen is None:
                gens[key] = Generation(key, entry.name, [entry.path])
            else:
                gen.paths.append(entry.path)
    return {k: gens[k] for k in sorted(gens)}


def list_pose_folders(generation):
    """Walk the Poses/ subtree of every root of a generation. Any directory
    holding at least one .duf becomes a PoseFolder; nested paths are flattened
    into a single label ("Vendor - Product - Subset")."""
    folders = {}
    for gen_path in generation.paths:
        poses_root = ci_subdir(gen_path, "Poses")
        if not poses_root:
            continue
        for dirpath, dirnames, filenames in os.walk(poses_root):
            dirnames.sort()
            if not any(f.lower().endswith(".duf") for f in filenames):
                continue
            rel = os.path.relpath(dirpath, poses_root)
            parts = [] if rel == "." else rel.replace(os.sep, "/").split("/")
            key = "/".join(p.lower() for p in parts) or "."
            label = " - ".join(parts) or "(top level)"
            folder = folders.get(key)
            if folder is None:
                folders[key] = PoseFolder(key, label, [dirpath])
            else:
                folder.paths.append(dirpath)
    return {f.key: f for f in sorted(folders.values(), key=lambda f: f.label.lower())}


def list_poses(folder):
    """All poses in a (possibly multi-root) folder. Each .duf is paired with a
    thumbnail named either "<stem>.png" or "<stem>.duf.png" (both conventions
    exist in the wild), matched case-insensitively; *.tip.png files are not
    thumbnails. On a duf name collision across roots, the first root wins."""
    poses = {}
    for dirpath in folder.paths:
        try:
            entries = [e for e in os.scandir(dirpath) if e.is_file()]
        except OSError:
            continue
        thumbs = {}
        for entry in entries:
            low = entry.name.lower()
            if low.endswith(".tip.png"):
                continue
            for ext in THUMB_EXTS:
                if low.endswith(ext):
                    thumbs.setdefault(low[: -len(ext)], entry.path)
                    break
        for entry in entries:
            low = entry.name.lower()
            if not low.endswith(".duf") or low in poses:
                continue
            stem = entry.name[:-4]
            thumb = thumbs.get(stem.lower()) or thumbs.get(low)
            poses[low] = Pose(low, stem, entry.path, thumb)
    return sorted(poses.values(), key=lambda p: p.name.lower())


# ---------------------------------------------------------------------------
# Cached front-end used by the Blender UI. Keyed on the tuple of roots so a
# changed library configuration naturally misses the cache.

_cache = {}


def _root_data(roots):
    sig = tuple(roots)
    data = _cache.get(sig)
    if data is None:
        data = _cache[sig] = {"generations": None, "folders": {}, "poses": {}}
    return data


def clear_cache():
    _cache.clear()


def get_generations(roots):
    data = _root_data(roots)
    if data["generations"] is None:
        data["generations"] = list_generations(roots)
    return data["generations"]


def get_pose_folders(roots, gen_key):
    data = _root_data(roots)
    folders = data["folders"].get(gen_key)
    if folders is None:
        gen = get_generations(roots).get(gen_key)
        folders = list_pose_folders(gen) if gen else {}
        data["folders"][gen_key] = folders
    return folders


def get_poses(roots, gen_key, folder_key):
    data = _root_data(roots)
    poses = data["poses"].get((gen_key, folder_key))
    if poses is None:
        folder = get_pose_folders(roots, gen_key).get(folder_key)
        poses = list_poses(folder) if folder else []
        data["poses"][(gen_key, folder_key)] = poses
    return poses


def get_pose(roots, gen_key, folder_key, pose_key):
    for pose in get_poses(roots, gen_key, folder_key):
        if pose.key == pose_key:
            return pose
    return None


if __name__ == "__main__":
    # Standalone smoke test: scan real libraries given on the command line.
    import sys

    roots = sys.argv[1:]
    gens = get_generations(roots)
    print("Generations:", ", ".join(g.label for g in gens.values()))
    for gen in gens.values():
        folders = get_pose_folders(roots, gen.key)
        n_poses = sum(len(get_poses(roots, gen.key, k)) for k in folders)
        print(f"\n{gen.label}: {len(folders)} folders, {n_poses} poses")
        for folder in list(folders.values())[:10]:
            poses = get_poses(roots, gen.key, folder.key)
            missing = sum(1 for p in poses if not p.thumb_path)
            extra = f", {missing} without thumbnail" if missing else ""
            print(f"  {folder.label} ({len(poses)} poses{extra})")
