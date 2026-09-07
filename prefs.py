"""Addon preferences and resolution of Daz content directories.

Content roots come from the Diffeomorphic importer's settings (its `api`
module when available, else its settings JSON), plus any extra directories
the user adds in this addon's preferences.
"""

import importlib
import json
import os

import bpy

DIFFEO_SETTINGS_JSON = os.path.expanduser("~/DAZ Importer/import_daz_settings.json")

_dirs_cache = None


def _find_diffeo_api():
    """Locate Diffeomorphic's public api module wherever it is installed.

    Only an *enabled* Diffeomorphic counts: its package is importable as soon
    as it is merely installed, but then its global settings were never loaded
    and the api would hand back factory defaults instead of the user's
    content directories."""
    candidates = ["import_daz"]
    try:
        for repo in bpy.context.preferences.extensions.repos:
            candidates.append("bl_ext.%s.import_daz" % repo.module)
    except AttributeError:
        pass
    enabled = bpy.context.preferences.addons
    for name in candidates:
        if name not in enabled:
            continue
        try:
            return importlib.import_module(name + ".api")
        except ImportError:
            continue
    return None


def _diffeo_content_dirs():
    api = _find_diffeo_api()
    if api is not None:
        try:
            return list(api.get_global_setting("contentDirs"))
        except Exception:
            pass
    try:
        # Diffeomorphic writes this file with a UTF-8 BOM
        with open(DIFFEO_SETTINGS_JSON, encoding="utf-8-sig") as fp:
            settings = json.load(fp).get("daz-settings", {})
        return list(settings.get("contentDirs", []))
    except (OSError, ValueError):
        return []


def get_content_dirs():
    """All existing Daz library roots, deduplicated, as a tuple (hashable for
    the scanner cache)."""
    global _dirs_cache
    if _dirs_cache is not None:
        return _dirs_cache

    dirs = _diffeo_content_dirs()
    prefs = get_prefs()
    if prefs is not None:
        dirs += [item.path for item in prefs.extra_dirs if item.path]

    seen = set()
    result = []
    for d in dirs:
        d = os.path.normpath(os.path.expanduser(d))
        key = os.path.normcase(d)
        if key not in seen and os.path.isdir(d):
            seen.add(key)
            result.append(d)
    _dirs_cache = tuple(result)
    return _dirs_cache


def invalidate_dirs_cache():
    global _dirs_cache
    _dirs_cache = None


def get_prefs():
    addon = bpy.context.preferences.addons.get(__package__)
    return addon.preferences if addon else None


class DazExtraDir(bpy.types.PropertyGroup):
    path: bpy.props.StringProperty(
        name="Library Folder",
        description="Extra Daz content directory (containing a People folder)",
        subtype='DIR_PATH',
        update=lambda self, context: invalidate_dirs_cache(),
    )


class DAZPRESETS_OT_add_extra_dir(bpy.types.Operator):
    bl_idname = "dazpresets.add_extra_dir"
    bl_label = "Add Library Folder"
    bl_description = "Add an extra Daz content directory"

    def execute(self, context):
        get_prefs().extra_dirs.add()
        invalidate_dirs_cache()
        return {'FINISHED'}


class DAZPRESETS_OT_remove_extra_dir(bpy.types.Operator):
    bl_idname = "dazpresets.remove_extra_dir"
    bl_label = "Remove Library Folder"
    bl_description = "Remove this extra Daz content directory"

    index: bpy.props.IntProperty()

    def execute(self, context):
        get_prefs().extra_dirs.remove(self.index)
        invalidate_dirs_cache()
        return {'FINISHED'}


class DazPresetBrowserPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    extra_dirs: bpy.props.CollectionProperty(type=DazExtraDir)

    def draw(self, context):
        layout = self.layout
        layout.label(text="Daz library folders from Diffeomorphic settings:")
        box = layout.box()
        diffeo = _diffeo_content_dirs()
        if diffeo:
            for d in diffeo:
                box.label(text=d, icon='FILE_FOLDER')
        else:
            box.label(text="None found (is the Diffeomorphic importer installed?)",
                      icon='ERROR')

        layout.label(text="Extra library folders:")
        for i, item in enumerate(self.extra_dirs):
            row = layout.row(align=True)
            row.prop(item, "path", text="")
            op = row.operator(DAZPRESETS_OT_remove_extra_dir.bl_idname,
                              text="", icon='X')
            op.index = i
        layout.operator(DAZPRESETS_OT_add_extra_dir.bl_idname, icon='ADD')


classes = (
    DazExtraDir,
    DAZPRESETS_OT_add_extra_dir,
    DAZPRESETS_OT_remove_extra_dir,
    DazPresetBrowserPreferences,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
