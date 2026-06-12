"""Daz Preset Browser — thumbnail picker for Daz Studio presets (poses,
expressions, ...), applied through the Diffeomorphic DAZ importer."""

bl_info = {
    "name": "Daz Preset Browser",
    "author": "Robbie",
    "version": (0, 1, 0),
    "blender": (4, 2, 0),
    "location": "3D Viewport > Sidebar > Daz Presets",
    "description": "Browse Daz Studio presets with thumbnails and apply them "
                   "via the Diffeomorphic importer",
    "category": "Animation",
}

try:
    import bpy
except ModuleNotFoundError:
    # Imported outside Blender (pytest collecting the package): stay inert.
    bpy = None

if bpy is not None:
    if "scanner" in locals():
        import importlib
        for _mod in (scanner, store, prefs, previews, ops, ui):
            importlib.reload(_mod)

    from . import scanner, store, prefs, previews, ops, ui

    _modules = (prefs, ops, ui)

    def register():
        import os
        store.setup(os.path.join(bpy.utils.user_resource('CONFIG'),
                                 "dazpresets.json"))
        for mod in _modules:
            mod.register()

    def unregister():
        for mod in reversed(_modules):
            mod.unregister()
        previews.cleanup()
