"""Scene properties and the 3D viewport sidebar panel."""

import bpy

from . import ops, prefs, previews, scanner


def _first_item(items):
    return items[0][0] if items else 'NONE'


def _on_generation_update(self, context):
    # Dynamic enums store an index, which goes stale when the items list
    # changes (e.g. on preset type switch). Remember the identifier while the
    # index is still valid, for _on_preset_type_update.
    self["last_generation"] = self.generation
    self.folder = _first_item(previews.folder_items(self, context))


def _on_preset_type_update(self, context):
    # Keep the generation when it exists for the new type, else pick the first
    items = previews.generation_items(self, context)
    wanted = self.get("last_generation", "")
    if not any(item[0] == wanted for item in items):
        wanted = _first_item(items)
    self.generation = wanted  # always reassign so the folder list resets


def _on_folder_update(self, context):
    # Thumbnails of the previous folder are dropped to bound memory use
    previews.reset()
    self.pose = _first_item(previews.pose_items(self, context))


SOURCE_CHARACTER_ITEMS = [
    ('AUTO', "Auto (Browsed Generation)",
     "Derive the source character from the generation selected above"),
] + [
    (ident, ident.replace("_", " ").title(), "")
    for ident in scanner.SOURCE_CHARACTERS
]


class DazPresetBrowserProperties(bpy.types.PropertyGroup):
    preset_type: bpy.props.EnumProperty(
        name="Type",
        description="Kind of Daz preset to browse",
        items=[
            ('POSES', "Poses", "Pose presets (People/<Generation>/Poses)"),
            ('EXPRESSIONS', "Expressions",
             "Expression presets (People/<Generation>/Expressions)"),
        ],
        default='POSES',
        update=_on_preset_type_update,
    )
    generation: bpy.props.EnumProperty(
        name="Generation",
        description="Genesis generation (folder under People/)",
        items=previews.generation_items,
        update=_on_generation_update,
    )
    folder_search: bpy.props.StringProperty(
        name="Filter",
        description="Filter pose folders by name",
        options={'TEXTEDIT_UPDATE'},
        update=_on_generation_update,  # re-pick the first matching folder
    )
    folder: bpy.props.EnumProperty(
        name="Folder",
        description="Pose folder (subfolders under Poses/ are flattened)",
        items=previews.folder_items,
        update=_on_folder_update,
    )
    pose: bpy.props.EnumProperty(
        name="Pose",
        description="Pose to apply",
        items=previews.pose_items,
    )
    clear_pose_first: bpy.props.BoolProperty(
        name="Clear Pose First",
        description="Reset the pose before applying, so the result matches "
                    "the thumbnail exactly",
        default=True,
    )
    affect_morphs: bpy.props.BoolProperty(
        name="Affect Morphs",
        description="Also apply morphs included in the pose preset",
        default=True,
    )
    affect_object: bpy.props.BoolProperty(
        name="Move Object",
        description="Apply the preset's object-level transform, moving the "
                    "character in world space (off keeps it where it is)",
        default=False,
    )
    morph_strength: bpy.props.FloatProperty(
        name="Strength",
        description="Multiplier for the expression's morph values",
        default=1.0, min=0.1, max=10.0,
    )
    convert_pose: bpy.props.BoolProperty(
        name="Convert Pose",
        description="Convert the pose to the target rig's generation, e.g. "
                    "apply a Genesis 8 pose to a Genesis 9 character. "
                    "Diffeomorphic also auto-detects this from the pose file "
                    "when possible; enable this when that fails",
        default=False,
    )
    source_character: bpy.props.EnumProperty(
        name="Source",
        description="Character generation the pose file was made for",
        items=SOURCE_CHARACTER_ITEMS,
        default='AUTO',
    )


class DAZPRESETS_PT_browser(bpy.types.Panel):
    bl_label = "Daz Preset Browser"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Daz Presets"

    def draw(self, context):
        layout = self.layout
        props = context.scene.dazpresets

        if not prefs.get_content_dirs():
            layout.label(text="No Daz library folders found", icon='ERROR')
            layout.label(text="Configure them in Diffeomorphic or in the "
                              "addon preferences")
            layout.operator(ops.DAZPRESETS_OT_refresh.bl_idname, icon='FILE_REFRESH')
            return

        layout.prop(props, "preset_type")
        layout.prop(props, "generation")
        col = layout.column(align=True)
        col.prop(props, "folder_search", text="", icon='VIEWZOOM')
        col.prop(props, "folder", text="")

        col = layout.column(align=True)
        col.template_icon_view(props, "pose", show_labels=True, scale=7.0)
        items = previews.pose_items(props, context)
        label = next((i[1] for i in items if i[0] == props.pose), "")
        col.label(text=label)

        is_expression = props.preset_type == 'EXPRESSIONS'
        if is_expression:
            layout.prop(props, "clear_pose_first", text="Clear Morphs First")
            layout.prop(props, "morph_strength")
        else:
            layout.prop(props, "clear_pose_first")
            layout.prop(props, "affect_morphs")
            layout.prop(props, "affect_object")
            layout.prop(props, "convert_pose")
            if props.convert_pose:
                layout.prop(props, "source_character")

        arm = ops.find_target_armature(context)
        if arm is None:
            layout.label(text="Select a Daz armature or its collection",
                         icon='INFO')
        else:
            layout.label(text="Target: %s" % arm.name, icon='ARMATURE_DATA')
        layout.operator(ops.DAZPRESETS_OT_apply_pose.bl_idname,
                        text="Apply Expression" if is_expression
                        else "Apply Pose",
                        icon='ARMATURE_DATA')
        layout.operator(ops.DAZPRESETS_OT_refresh.bl_idname, icon='FILE_REFRESH')


classes = (
    DazPresetBrowserProperties,
    DAZPRESETS_PT_browser,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.dazpresets = bpy.props.PointerProperty(type=DazPresetBrowserProperties)


def unregister():
    del bpy.types.Scene.dazpresets
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
