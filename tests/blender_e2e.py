"""Headless end-to-end test: run inside Blender.

    flatpak run org.blender.Blender --background --python tests/blender_e2e.py

Imports the base Genesis 9 figure through Diffeomorphic (with FACS morphs,
no .dbz needed), then applies a pose and an expression through the addon's
operators and checks bones/morphs actually change and clear again. Slow
(a minute or so) and needs the Daz libraries on disk.
"""

import os
import sys

import bpy

DIFFEO = "bl_ext.user_default.import_daz"
ADDON = "bl_ext.user_default.daz_preset_browser"

def main():
    for m in (DIFFEO, ADDON):
        if m not in bpy.context.preferences.addons:
            bpy.ops.preferences.addon_enable(module=m)
    mod = sys.modules[ADDON]
    import tempfile
    mod.store.setup(os.path.join(tempfile.mkdtemp(), "presets.json"))

    # Import base Genesis 9 with FACS/units so expressions have morphs to drive
    d = next(os.path.join(root, "People", "Genesis 9")
             for root in mod.prefs.get_content_dirs()
             if os.path.isfile(os.path.join(root, "People", "Genesis 9",
                                            "Genesis 9.duf")))
    r = bpy.ops.daz.easy_import_daz('EXEC_DEFAULT', files=[{"name": "Genesis 9.duf"}], directory=d,
                                    useUnits=True, useExpressions=True, useFacs=True, useFacsexpr=True, fitMeshes="MORPHED")
    print("IMPORT:", r)
    rigs = [o for o in bpy.data.objects if o.type == 'ARMATURE']
    print("RIGS:", [(o.name, mod.ops.daz_rig_type(o)) for o in rigs])
    rig = rigs[0]
    bpy.context.view_layer.objects.active = rig
    rig.select_set(True)
    assert mod.ops.find_target_armature(bpy.context) is rig

    props = bpy.context.scene.dazpresets
    props.preset_type = 'POSES'
    props.generation = "genesis 9"
    props.folder = "aeon soul/everyday walking poses"
    poses = mod.previews.pose_items(props, bpy.context)
    props.pose = poses[0][0]
    before = {b.name: b.matrix_basis.copy() for b in rig.pose.bones}
    r = bpy.ops.dazpresets.apply_pose()
    print("APPLY POSE:", r, poses[0][1])
    assert r == {'FINISHED'}
    def differs(a, b):
        return any(abs(x) > 1e-4 for row in (a - b) for x in row)
    moved = [n for n, m in before.items()
             if differs(rig.pose.bones[n].matrix_basis, m)]
    print("BONES CHANGED:", len(moved), moved[:6])
    assert len(moved) > 10, "pose did not move bones"
    assert tuple(round(v, 4) for v in rig.location) == (0, 0, 0), "object moved: %s" % tuple(rig.location)

    # Clear pose resets bones
    r = bpy.ops.dazpresets.clear_pose()
    assert r == {'FINISHED'}
    still = [n for n in moved
             if differs(rig.pose.bones[n].matrix_basis, before[n])]
    print("BONES STILL POSED AFTER CLEAR:", len(still))
    assert not still

    # Expression
    props.preset_type = 'EXPRESSIONS'
    props.generation = "genesis 9"
    folders = mod.previews.folder_items(props, bpy.context)
    fk = next(f[0] for f in folders if "daz originals" in f[0])
    props.folder = fk
    exprs = mod.previews.pose_items(props, bpy.context)
    props.pose = exprs[0][0]
    def morphvals():
        return {k: rig[k] for k in rig.keys() if isinstance(rig[k], float)}
    mb = morphvals()
    r = bpy.ops.dazpresets.apply_pose()
    print("APPLY EXPRESSION:", r, exprs[0][1], fk)
    assert r == {'FINISHED'}
    ma = morphvals()
    changed = [k for k in ma if abs(ma[k] - mb.get(k, 0.0)) > 1e-4]
    print("MORPHS CHANGED:", len(changed), changed[:8])
    assert changed, "expression changed no morphs"
    r = bpy.ops.dazpresets.clear_expression()
    assert r == {'FINISHED'}
    mc = morphvals()
    left = [k for k in changed if abs(mc[k]) > 1e-4]
    print("MORPHS LEFT AFTER CLEAR:", len(left), [(k, round(mc[k],4), round(ma[k],4)) for k in left])
    assert not left
    recents = mod.previews.recent_items(props, bpy.context)
    print("RECENTS:", [r[1] for r in recents])
    assert len(recents) == 2
    print("E2E PASSED")

try:
    main()
except Exception:
    import traceback; traceback.print_exc(); sys.exit(1)
