# Daz Preset Browser

Blender addon: browse Daz Studio presets (poses today; expressions etc. are a
natural extension) with thumbnails and apply them to an imported Daz character
through the [Diffeomorphic DAZ importer](https://diffeomorphic.blogspot.com/).

- Merges multiple Daz content libraries (read automatically from
  Diffeomorphic's settings, plus extra folders in the addon preferences).
- All path matching is case-insensitive, so Windows-authored libraries work
  on Linux.
- Nested folders under `People/<Generation>/Poses/` are flattened into one
  dropdown ("Aeon Soul - Everyday Walking Poses").
- Pose thumbnails (`Name.png` or `Name.duf.png`, `*.tip.png` ignored) shown
  in a `template_icon_view` picker.

## Usage

3D Viewport → Sidebar (N) → **Daz Presets** tab. Pick generation, folder, and
pose, select the Daz armature, click **Apply Pose**. *Clear Pose First* makes
the result match the thumbnail exactly; disable it to layer partial poses.

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

## Requirements

- Blender 4.2+ with the Diffeomorphic DAZ importer installed and configured
  (its content directories are reused).

## Development install (Linux, Flatpak Blender)

```sh
ln -sfn "$PWD" ~/.var/app/org.blender.Blender/config/blender/5.1/extensions/user_default/daz_preset_browser
```

The symlink name must match the extension id (`daz_preset_browser`), not the
repo folder name. Then enable "Daz Preset Browser" in Preferences → Add-ons.

## Tests

```sh
.venv/bin/python -m pytest tests/            # scanner unit tests (no Blender)
python scanner.py <library-dir>...           # standalone scan of real libraries
flatpak run org.blender.Blender --background --python tests/blender_smoke.py
```
