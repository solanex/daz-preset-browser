# Daz Preset Browser

Blender addon: browse Daz Studio presets (poses and expressions) with
thumbnails and apply them to an imported Daz character through the
[Diffeomorphic DAZ importer](https://diffeomorphic.blogspot.com/).

- Merges multiple Daz content libraries (read automatically from
  Diffeomorphic's settings, plus extra folders in the addon preferences).
- All path matching is case-insensitive, so Windows-authored libraries work
  on Linux.
- Nested folders under `People/<Generation>/Poses/` are flattened into one
  dropdown ("Aeon Soul - Everyday Walking Poses").
- Pose thumbnails (`Name.png` or `Name.duf.png`, `*.tip.png` ignored) shown
  in a `template_icon_view` picker.

## Usage

3D Viewport → Sidebar (N) → **Daz Presets** tab. Pick the preset type (Poses
or Expressions), generation, folder, and preset, select the Daz armature,
click **Apply**. *Clear Pose First* makes the result match the thumbnail
exactly; disable it to layer partial poses. Expressions are morph-only (bones
and object transform untouched) and offer *Clear Morphs First* plus a
*Strength* multiplier instead of the pose options.

- The search field above the folder dropdown filters folders by name
  (e.g. type `sit` to see only sitting-pose folders).
- The target armature is resolved from context: the active armature, the
  armature deforming the active mesh, the only selected armature, or the only
  Daz armature in the active collection — so clicking a character's collection
  in the outliner is enough. The panel shows the resolved target.
- *Convert Pose* converts between generations (e.g. a Genesis 8 pose onto a
  Genesis 9 character) using Diffeomorphic's converter. The source character
  is derived from the browsed generation, with a manual override dropdown.
  Diffeomorphic also auto-detects the source from the pose file itself, so
  try without conversion first.
- **Clear Pose** resets all bones to the rest pose (keeping the character's
  world position unless *Move Object* is on); **Clear Expression** zeroes the
  face morph sets (units, expressions, visemes, FACS) without touching body
  or shaping morphs.
- The star next to the selected preset adds it to **Favorites**; every applied
  preset lands in **Recent** (last 12). Both live in collapsible sub-panels
  with their own picker and Apply button, work across generations and preset
  types, and persist in `dazpresets.json` in Blender's config directory.

## Requirements

- Blender 4.2+ with the Diffeomorphic DAZ importer installed, **enabled** and
  configured (its content directories are reused). Verified with Blender 5.2
  LTS and Diffeomorphic 5.2.

## Development install (Linux, Flatpak Blender)

```sh
ln -sfn "$PWD" ~/.var/app/org.blender.Blender/config/blender/5.2/extensions/user_default/daz_preset_browser
```

The symlink name must match the extension id (`daz_preset_browser`), not the
repo folder name, and the `5.2` segment must match the running Blender
version (each Blender X.Y has its own extensions folder, so redo this after
an upgrade). Then enable "Daz Preset Browser" in Preferences → Add-ons.

## Tests

```sh
.venv/bin/python -m pytest tests/            # scanner unit tests (no Blender)
python scanner.py <library-dir>...           # standalone scan of real libraries
flatpak run org.blender.Blender --background --python "$PWD/tests/blender_smoke.py"
flatpak run org.blender.Blender --background --python "$PWD/tests/blender_e2e.py"
```

The Flatpak needs absolute paths. The smoke test checks registration,
library scanning and the enums; the end-to-end test imports the base
Genesis 9 figure and really applies a pose and an expression (slow).
