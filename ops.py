"""Operators: apply the selected pose via Diffeomorphic, refresh the library."""

import os

import bpy

from . import prefs, previews, scanner

def daz_rig_type(ob):
    """Diffeomorphic's rig type string ("genesis9", ...) or "" if not a
    Daz-imported object. Reads both modern and legacy property locations."""
    pg = getattr(ob, "daz_importer", None)
    rig = getattr(pg, "DazRig", "") if pg is not None else ""
    return rig or getattr(ob, "DazRig", "")


def find_target_armature(context):
    """The armature a pose should be applied to: the active armature, the
    armature deforming the active mesh, the only selected armature, or the
    only (Daz) armature in the active collection."""
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
    arms = [o for o in context.selected_objects if is_arm(o)]
    if len(arms) == 1:
        return arms[0]
    coll = context.collection
    if coll is not None:
        arms = [o for o in coll.all_objects if is_arm(o)]
        daz_arms = [o for o in arms if daz_rig_type(o)]
        arms = daz_arms or arms
        if len(arms) == 1:
            return arms[0]
    return None


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
        if not hasattr(bpy.ops, "daz") or not hasattr(bpy.ops.daz, "import_pose"):
            self.report({'ERROR'},
                        "Diffeomorphic DAZ importer is not installed/enabled")
            return {'CANCELLED'}

        is_expression = props.preset_type == 'EXPRESSIONS'
        kind = "expression" if is_expression else "pose"
        pose = scanner.get_pose(prefs.get_content_dirs(),
                                previews.category(props), props.generation,
                                props.folder, props.pose)
        if pose is None:
            self.report({'ERROR'}, "No %s selected" % kind)
            return {'CANCELLED'}

        arm = find_target_armature(context)
        try:
            for sel in list(context.selected_objects):
                sel.select_set(False)
            arm.select_set(True)
            context.view_layer.objects.active = arm
        except RuntimeError as err:
            self.report({'ERROR'},
                        "Cannot select armature '%s': %s" % (arm.name, err))
            return {'CANCELLED'}

        kwargs = dict(
            files=[{"name": os.path.basename(pose.duf_path)}],
            directory=os.path.dirname(pose.duf_path),
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
                    src = scanner.source_for_generation(props.generation)
                    if src is None:
                        self.report({'ERROR'},
                                    "Cannot derive a source character from "
                                    "'%s'; pick one manually" % props.generation)
                        return {'CANCELLED'}
                kwargs.update(useConvert=True, srcCharacter=src)

        try:
            result = operator('EXEC_DEFAULT', **kwargs)
        except Exception as err:
            self.report({'ERROR'},
                        "Diffeomorphic failed to apply %s: %s" % (kind, err))
            return {'CANCELLED'}

        if 'FINISHED' not in result:
            self.report({'WARNING'}, "Import did not finish (%s)" % result)
            return {'CANCELLED'}
        self.report({'INFO'}, "Applied %s: %s" % (kind, pose.name))
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
    DAZPRESETS_OT_refresh,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
