"""Headless smoke test: run inside Blender.

    flatpak run org.blender.Blender --background --python tests/blender_smoke.py

Verifies the addon registers, finds the Daz libraries, and builds the
generation/folder/pose enums with thumbnails — everything except clicking
Apply on a real character.
"""

import os
import sys

import bpy

ADDON = "bl_ext.user_default.daz_preset_browser"
DIFFEO = "bl_ext.user_default.import_daz"


def main():
    # A fresh Blender profile has Diffeomorphic installed but not enabled;
    # enable it explicitly so this test does not depend on saved preferences
    if DIFFEO not in bpy.context.preferences.addons:
        bpy.ops.preferences.addon_enable(module=DIFFEO)
    assert DIFFEO in bpy.context.preferences.addons, "Diffeomorphic did not enable"
    # bl_info is stripped when an extension is loaded from saved preferences
    info = getattr(sys.modules[DIFFEO], "bl_info", {})
    print("Diffeomorphic version:", info.get("version", "(loaded from prefs)"))

    bpy.ops.preferences.addon_enable(module=ADDON)
    assert ADDON in bpy.context.preferences.addons, "addon did not enable"

    mod = sys.modules[ADDON]
    props = bpy.context.scene.dazpresets

    roots = mod.prefs.get_content_dirs()
    print("Content dirs:", list(roots))
    assert roots, "no Daz content dirs found"
    # Must be the user's configured libraries, not Diffeomorphic's built-in
    # defaults (which is what its api reports before it is enabled)
    diffeo_api = mod.prefs._find_diffeo_api()
    assert diffeo_api is not None, "Diffeomorphic api not found"
    assert set(roots) >= {os.path.normpath(d) for d in
                          diffeo_api.get_global_setting("contentDirs")
                          if os.path.isdir(d)}, "content dirs != Diffeo settings"

    gens = mod.previews.generation_items(props, bpy.context)
    print("Generations:", [g[1] for g in gens])
    assert any(g[0] == "genesis 9" for g in gens), "Genesis 9 not found"

    props.generation = "genesis 9"
    folders = mod.previews.folder_items(props, bpy.context)
    print("Folders for Genesis 9: %d (first: %s)" % (len(folders), folders[0][1]))
    assert any("aeon soul" in f[0] for f in folders), "Aeon Soul folders missing"

    props.folder = "aeon soul/everyday walking poses"
    poses = mod.previews.pose_items(props, bpy.context)
    print("Poses in folder: %d (first: %s, icon_id: %s)"
          % (len(poses), poses[0][1], poses[0][3]))
    assert len(poses) > 0 and isinstance(poses[0][3], int), \
        "pose enum items malformed"
    if bpy.app.background:
        # icon_id is always 0 without a UI; verify the image itself loads
        pose = mod.scanner.get_pose(roots, "Poses", props.generation,
                                    props.folder, poses[0][0])
        preview = mod.previews._previews()[pose.duf_path]
        assert tuple(preview.image_size) > (0, 0), "thumbnail failed to load"
        print("Thumbnail loads, size:", tuple(preview.image_size))
    else:
        assert poses[0][3] > 0, "pose thumbnails did not load"

    # Folder search filters the dropdown and auto-picks a matching folder
    props.folder_search = "walking"
    filtered = mod.previews.folder_items(props, bpy.context)
    print("Folders matching 'walking': %d" % len(filtered))
    assert filtered and all("walking" in f[1].lower() for f in filtered)
    assert "walking" in props.folder
    props.folder_search = ""

    # Expressions category works the same way
    props.preset_type = 'EXPRESSIONS'
    gens = mod.previews.generation_items(props, bpy.context)
    print("Expression generations:", [g[1] for g in gens])
    assert any(g[0] == "genesis 9" for g in gens)
    assert props.generation == "genesis 9", "generation not kept on type switch"
    folders = mod.previews.folder_items(props, bpy.context)
    exprs = mod.previews.pose_items(props, bpy.context)
    print("Expression folders: %d, first folder '%s' has %d presets"
          % (len(folders), folders[0][1], len(exprs)))
    assert folders and folders[0][0] != 'NONE'
    assert exprs and exprs[0][0] != 'NONE'
    assert hasattr(bpy.ops.daz, "import_expression")
    props.preset_type = 'POSES'

    assert hasattr(bpy.ops.dazpresets, "apply_pose")
    assert hasattr(bpy.ops.dazpresets, "refresh")
    assert hasattr(bpy.ops.daz, "import_pose"), "Diffeomorphic not available"
    # Apply must refuse politely without an armature
    assert not bpy.ops.dazpresets.apply_pose.poll()

    # Favorites/recents: use a temp store so the user's real one is untouched
    import tempfile
    store_dir = tempfile.mkdtemp()
    mod.store.setup(os.path.join(store_dir, "presets.json"))
    assert mod.previews.favorite_items(props, bpy.context) == []
    browsed = mod.ops.browsed_pose(props)
    bpy.ops.dazpresets.toggle_favorite()
    favs = mod.previews.favorite_items(props, bpy.context)
    print("Favorite after toggle:", favs[0][1] if favs else None)
    assert len(favs) == 1 and favs[0][1] == browsed.name
    assert favs[0][0] == browsed.duf_path
    props.favorite = favs[0][0]
    bpy.ops.dazpresets.remove_favorite()
    assert mod.previews.favorite_items(props, bpy.context) == []
    assert mod.previews.recent_items(props, bpy.context) == []

    # Target resolution: an armature alone in the active collection is found
    # even when a mesh is the active object
    arm_data = bpy.data.armatures.new("TestRig")
    arm_ob = bpy.data.objects.new("TestRig", arm_data)
    bpy.context.collection.objects.link(arm_ob)
    found = mod.ops.find_target_armature(bpy.context)
    assert found is arm_ob, "collection armature not found (got %s)" % found
    assert bpy.ops.dazpresets.apply_pose.poll()

    # Clear Pose keeps the world position (Move Object is off by default)
    arm_ob.location = (1.0, 2.0, 3.0)
    bpy.context.view_layer.update()
    assert bpy.ops.dazpresets.clear_pose.poll()
    result = bpy.ops.dazpresets.clear_pose()
    assert result == {'FINISHED'}, "clear_pose failed: %s" % result
    assert tuple(arm_ob.location) == (1.0, 2.0, 3.0), \
        "clear_pose moved the object to %s" % tuple(arm_ob.location)
    result = bpy.ops.dazpresets.clear_expression()
    assert result == {'FINISHED'}, "clear_expression failed: %s" % result

    print("SMOKE TEST PASSED")


try:
    main()
except Exception:
    import traceback
    traceback.print_exc()
    sys.exit(1)
