"""Operators: apply the selected pose via Diffeomorphic, refresh the library."""

import os

import bpy

from . import prefs, previews, scanner, store


def daz_rig_type(ob):
    """Diffeomorphic's rig type string ("genesis9", ...) or "" if not a
    Daz-imported object. Reads both modern and legacy property locations."""
    pg = getattr(ob, "daz_importer", None)
    rig = getattr(pg, "DazRig", "") if pg is not None else ""
    return rig or getattr(ob, "DazRig", "")


def find_target_armature(context):
    """The armature a pose should be applied to: the active armature, the
    armature deforming the active mesh, the only selected armature, or the
    only (Daz) armature in the active collection. When that armature is
    itself driven by a control rig (Diffeomorphic's MHX/Rigify conversion
    with the Daz rig kept), the control rig is returned instead."""
    arm = _find_context_armature(context)
    return control_rig(arm) if arm is not None else None


def _find_context_armature(context):
    def is_arm(ob):
        return ob is not None and ob.type == 'ARMATURE'

    ob = context.active_object
    if is_arm(ob):
        return ob
    if ob is not None and ob.type == 'MESH':
        for mod in ob.modifiers:
            if mod.type == 'ARMATURE' and mod.object is not None:
                return mod.object
        if is_arm(ob.parent):
            return ob.parent
    arms = _pick_armatures(o for o in context.selected_objects if is_arm(o))
    if len(arms) == 1:
        return arms[0]
    coll = context.collection
    if coll is not None:
        arms = _pick_armatures(o for o in coll.all_objects if is_arm(o))
        if len(arms) == 1:
            return arms[0]
    return None


# Constraint types Diffeomorphic uses to slave the kept Daz rig to its
# MHX/Rigify control rig
_SLAVE_CONSTRAINTS = {'COPY_TRANSFORMS', 'COPY_ROTATION', 'COPY_LOCATION'}


def control_rig(arm):
    """The rig that actually drives `arm`: if most of its bones copy their
    transforms from another Daz armature, poses and expressions have to go
    to that armature (its sliders drive `arm`'s), so return it. Otherwise
    `arm` itself."""
    seen = {arm}
    while arm.pose is not None:  # None until the armature was evaluated once
        targets = {}
        for pb in arm.pose.bones:
            for con in pb.constraints:
                target = getattr(con, "target", None)
                if (con.type in _SLAVE_CONSTRAINTS and target is not None
                        and target.type == 'ARMATURE' and target is not arm):
                    targets[target] = targets.get(target, 0) + 1
        if not targets:
            return arm
        master, count = max(targets.items(), key=lambda kv: kv[1])
        if (master in seen or not daz_rig_type(master)
                or count < len(arm.pose.bones) // 2):
            return arm
        seen.add(master)
        arm = master
    return arm


def _pick_armatures(candidates):
    """Narrow a set of armatures down to the most plausible pose targets:
    Daz rigs over plain ones, and rigs that actually deform meshes over
    orphaned ones (e.g. a leftover MHX copy next to the original rig)."""
    arms = list(candidates)
    daz_arms = [o for o in arms if daz_rig_type(o)]
    arms = daz_arms or arms
    deforming = [o for o in arms
                 if any(c.type == 'MESH' for c in o.children)]
    return deforming or arms


def browsed_pose(props):
    """The Pose currently selected in the main browser, or None."""
    return scanner.get_pose(prefs.get_content_dirs(),
                            previews.category(props), props.generation,
                            props.folder, props.pose)


def _select_only(op, context, ob):
    """Make `ob` the only selected and the active object, as the Diffeomorphic
    operators expect. Reports through `op`; returns False on failure."""
    try:
        for sel in list(context.selected_objects):
            sel.select_set(False)
        ob.select_set(True)
        context.view_layer.objects.active = ob
        return True
    except RuntimeError as err:
        op.report({'ERROR'},
                  "Cannot select armature '%s': %s" % (ob.name, err))
        return False


def _apply_entry(op, context, entry, props):
    """Apply a favorites/recents-style entry dict with the panel's option
    toggles. Reports through `op`; returns True on success."""
    is_expression = entry["type"] == 'EXPRESSIONS'
    kind = "expression" if is_expression else "pose"
    if not hasattr(bpy.ops, "daz") or not hasattr(bpy.ops.daz, "import_pose"):
        op.report({'ERROR'},
                  "Diffeomorphic DAZ importer is not installed/enabled")
        return False
    if not os.path.isfile(entry["duf"]):
        op.report({'ERROR'}, "Preset file no longer exists: %s" % entry["duf"])
        return False

    arm = find_target_armature(context)
    if not _select_only(op, context, arm):
        return False

    kwargs = dict(
        files=[{"name": os.path.basename(entry["duf"])}],
        directory=os.path.dirname(entry["duf"]),
    )
    if is_expression:
        # import_expression shares import_pose's properties; calling with
        # EXEC_DEFAULT skips its invoke(), which is what normally turns
        # bones/object off — so pass these explicitly
        operator = bpy.ops.daz.import_expression
        kwargs.update(
            affectBones=False,
            affectObject=False,
            affectMorphs=True,
            useClearMorphs=props.clear_pose_first,
            multiplier=props.morph_strength,
        )
    else:
        operator = bpy.ops.daz.import_pose
        kwargs.update(
            useClearPose=props.clear_pose_first,
            affectMorphs=props.affect_morphs,
            affectObject=props.affect_object,
        )
        if props.convert_pose:
            src = props.source_character
            if src == 'AUTO':
                src = scanner.source_for_generation(entry["generation"])
                if src is None:
                    op.report({'ERROR'},
                              "Cannot derive a source character from "
                              "'%s'; pick one manually" % entry["generation"])
                    return False
            kwargs.update(useConvert=True, srcCharacter=src)

    try:
        result = operator('EXEC_DEFAULT', **kwargs)
    except Exception as err:
        op.report({'ERROR'},
                  "Diffeomorphic failed to apply %s: %s" % (kind, err))
        return False

    if 'FINISHED' not in result:
        op.report({'WARNING'}, "Import did not finish (%s)" % result)
        return False
    op.report({'INFO'}, "Applied %s: %s" % (kind, entry["name"]))
    return True


class DAZPRESETS_OT_apply_pose(bpy.types.Operator):
    bl_idname = "dazpresets.apply_pose"
    bl_label = "Apply"
    bl_description = "Apply the selected Daz preset to the target armature " \
                     "using the Diffeomorphic importer"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return find_target_armature(context) is not None

    def execute(self, context):
        props = context.scene.dazpresets
        pose = browsed_pose(props)
        if pose is None:
            self.report({'ERROR'}, "No preset selected")
            return {'CANCELLED'}
        entry = store.make_entry(props.preset_type, props.generation,
                                 props.folder, pose)
        if not _apply_entry(self, context, entry, props):
            return {'CANCELLED'}
        store.add_recent(entry)
        return {'FINISHED'}


class DAZPRESETS_OT_apply_entry(bpy.types.Operator):
    bl_idname = "dazpresets.apply_entry"
    bl_label = "Apply"
    bl_description = "Apply this preset to the target armature " \
                     "using the Diffeomorphic importer"
    bl_options = {'REGISTER', 'UNDO'}

    source: bpy.props.EnumProperty(
        items=[('FAVORITES', "Favorites", ""), ('RECENTS', "Recents", "")],
        options={'HIDDEN'},
    )

    @classmethod
    def poll(cls, context):
        return find_target_armature(context) is not None

    def execute(self, context):
        props = context.scene.dazpresets
        if self.source == 'FAVORITES':
            entry = store.find(store.favorites(), props.favorite)
        else:
            entry = store.find(store.recents(), props.recent)
        if entry is None:
            self.report({'ERROR'}, "No preset selected")
            return {'CANCELLED'}
        if not _apply_entry(self, context, entry, props):
            return {'CANCELLED'}
        store.add_recent(entry)
        return {'FINISHED'}


class DAZPRESETS_OT_toggle_favorite(bpy.types.Operator):
    bl_idname = "dazpresets.toggle_favorite"
    bl_label = "Favorite"
    bl_description = "Add or remove the selected preset from the favorites"

    def execute(self, context):
        props = context.scene.dazpresets
        pose = browsed_pose(props)
        if pose is None:
            self.report({'ERROR'}, "No preset selected")
            return {'CANCELLED'}
        entry = store.make_entry(props.preset_type, props.generation,
                                 props.folder, pose)
        added = store.toggle_favorite(entry)
        self.report({'INFO'}, "Added to favorites" if added
                    else "Removed from favorites")
        return {'FINISHED'}


class DAZPRESETS_OT_remove_favorite(bpy.types.Operator):
    bl_idname = "dazpresets.remove_favorite"
    bl_label = "Remove Favorite"
    bl_description = "Remove this preset from the favorites"

    def execute(self, context):
        store.remove_favorite(context.scene.dazpresets.favorite)
        return {'FINISHED'}


# Diffeomorphic morph sets that expression presets drive (MS.Standards minus
# the body/shape ones, which a "clear expression" must not touch)
FACE_MORPH_SETS = ("Units", "Expressions", "Visemes", "Facs",
                   "Facsdetails", "Facsexpr", "Head")

# Expression presets also write to FACS helper properties (facs_bs_*,
# facs_ctrl_*) that Diffeomorphic does not register as morphs, so its
# clear_morphs leaves them behind although they drive shape keys. Anything
# with these prefixes is face-only, so zeroing leftovers is safe.
FACE_PROP_PREFIXES = ("facs_",)


def _zero_leftover_face_props(rig):
    """Zero non-zero float custom properties on the rig that belong to the
    face but escaped Diffeomorphic's clear. Returns how many were reset."""
    count = 0
    for key in list(rig.keys()):
        if not key.startswith(FACE_PROP_PREFIXES):
            continue
        value = rig[key]
        if isinstance(value, float) and value != 0.0:
            rig[key] = 0.0
            count += 1
    if count:
        rig.update_tag()
    return count


class DAZPRESETS_OT_clear_pose(bpy.types.Operator):
    bl_idname = "dazpresets.clear_pose"
    bl_label = "Clear Pose"
    bl_description = "Reset all bones of the target armature to the rest " \
                     "pose. Keeps the object's world position unless " \
                     "Move Object is enabled"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return find_target_armature(context) is not None

    def execute(self, context):
        props = context.scene.dazpresets
        if not hasattr(bpy.ops, "daz") or not hasattr(bpy.ops.daz, "clear_pose"):
            self.report({'ERROR'},
                        "Diffeomorphic DAZ importer is not installed/enabled")
            return {'CANCELLED'}
        arm = find_target_armature(context)
        if not _select_only(self, context, arm):
            return {'CANCELLED'}
        # daz.clear_pose also resets the object's world matrix; honor the
        # panel's Move Object toggle like Apply does
        world = arm.matrix_world.copy()
        try:
            bpy.ops.daz.clear_pose()
        except Exception as err:
            self.report({'ERROR'}, "Diffeomorphic failed to clear pose: %s" % err)
            return {'CANCELLED'}
        if not props.affect_object:
            arm.matrix_world = world
        self.report({'INFO'}, "Cleared pose: %s" % arm.name)
        return {'FINISHED'}


class DAZPRESETS_OT_clear_expression(bpy.types.Operator):
    bl_idname = "dazpresets.clear_expression"
    bl_label = "Clear Expression"
    bl_description = "Zero all face morphs (units, expressions, visemes, " \
                     "FACS) of the target armature. Body and shaping morphs " \
                     "are not touched"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return find_target_armature(context) is not None

    def execute(self, context):
        if not hasattr(bpy.ops, "daz") or not hasattr(bpy.ops.daz, "clear_morphs"):
            self.report({'ERROR'},
                        "Diffeomorphic DAZ importer is not installed/enabled")
            return {'CANCELLED'}
        arm = find_target_armature(context)
        if not _select_only(self, context, arm):
            return {'CANCELLED'}
        errors = []
        for morphset in FACE_MORPH_SETS:
            try:
                bpy.ops.daz.clear_morphs(morphset=morphset)
            except Exception as err:
                errors.append("%s: %s" % (morphset, err))
        if len(errors) == len(FACE_MORPH_SETS):
            self.report({'ERROR'},
                        "Diffeomorphic failed to clear morphs (%s)" % errors[0])
            return {'CANCELLED'}
        _zero_leftover_face_props(arm)
        if errors:
            self.report({'WARNING'},
                        "Some morph sets failed to clear: %s" % "; ".join(errors))
        else:
            self.report({'INFO'}, "Cleared expression: %s" % arm.name)
        return {'FINISHED'}


class DAZPRESETS_OT_refresh(bpy.types.Operator):
    bl_idname = "dazpresets.refresh"
    bl_label = "Refresh Library"
    bl_description = "Rescan the Daz library folders for poses"

    def execute(self, context):
        prefs.invalidate_dirs_cache()
        scanner.clear_cache()
        previews.reset()
        return {'FINISHED'}


classes = (
    DAZPRESETS_OT_apply_pose,
    DAZPRESETS_OT_apply_entry,
    DAZPRESETS_OT_toggle_favorite,
    DAZPRESETS_OT_remove_favorite,
    DAZPRESETS_OT_clear_pose,
    DAZPRESETS_OT_clear_expression,
    DAZPRESETS_OT_refresh,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
