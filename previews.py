"""Thumbnail previews and cached enum items for the picker dropdowns.

Blender does not keep references to the item lists returned by enum-items
callbacks; if Python garbage-collects them, the UI shows corrupted strings or
crashes. Every list handed to Blender is therefore kept in `_enum_cache`.
"""

import bpy.utils.previews

from . import prefs, scanner

_pcoll = None
_enum_cache = {}

FALLBACK_ICON = 'POSE_HLT'  # for presets that ship without a thumbnail

# Library subfolder under People/<Generation>/ for each preset type
CATEGORIES = {'POSES': "Poses", 'EXPRESSIONS': "Expressions"}


def category(props):
    return CATEGORIES.get(props.preset_type, "Poses")


def _previews():
    global _pcoll
    if _pcoll is None:
        _pcoll = bpy.utils.previews.new()
    return _pcoll


def reset():
    """Drop all cached enum items and loaded thumbnails (folder change or
    library refresh)."""
    _enum_cache.clear()
    if _pcoll is not None:
        _pcoll.clear()


def cleanup():
    """Full teardown on addon unregister."""
    global _pcoll
    _enum_cache.clear()
    if _pcoll is not None:
        bpy.utils.previews.remove(_pcoll)
        _pcoll = None


def _cached(key, build):
    items = _enum_cache.get(key)
    if items is None:
        items = build()
        if not items:
            items = [('NONE', "None found", "", 'INFO', 0)]
        _enum_cache[key] = items
    return items


def generation_items(self, context):
    roots = prefs.get_content_dirs()
    cat = category(self)
    return _cached(
        ("generations", roots, cat),
        lambda: [(g.key, g.label, "") for g in
                 scanner.get_generations(roots, cat).values()],
    )


def folder_items(self, context):
    roots = prefs.get_content_dirs()
    cat = category(self)
    gen_key = self.generation
    search = self.folder_search.strip().lower()
    return _cached(
        ("folders", roots, cat, gen_key, search),
        lambda: [(f.key, f.label, f.label) for f in
                 scanner.get_pose_folders(roots, cat, gen_key).values()
                 if search in f.label.lower()],
    )


def pose_items(self, context):
    roots = prefs.get_content_dirs()
    cat = category(self)
    gen_key, folder_key = self.generation, self.folder

    def build():
        pcoll = _previews()
        items = []
        for i, pose in enumerate(
                scanner.get_poses(roots, cat, gen_key, folder_key)):
            if pose.thumb_path:
                preview = pcoll.get(pose.duf_path)
                if preview is None:
                    preview = pcoll.load(pose.duf_path, pose.thumb_path, 'IMAGE')
                icon = preview.icon_id
            else:
                icon = FALLBACK_ICON
            items.append((pose.key, pose.name, pose.name, icon, i))
        return items

    return _cached(("poses", roots, cat, gen_key, folder_key), build)
