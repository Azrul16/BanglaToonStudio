# Bangla Toon Studio — Background Pack (10)

This pack contains **7 original scene illustrations plus 3 day/time/weather variants** (10 selectable backgrounds total). They are **empty stages** with no characters, intended for overlaying character sprites.

## Install
Copy `assets/backgrounds/` to your application’s `assets/backgrounds/` directory. Use `background_registry.json` and each folder’s `metadata.json` to map Bengali story keywords to scenes.

Each folder includes:
- `background.png`: high-resolution original composition (landscape or portrait)
- `background_720x1280.png`: cropped cover image for 9:16 Shorts
- `metadata.json`: scene ID, Bengali name, keyword tags, timing and variant association

Scenes: riverside ghat sunset, village courtyard day, village home evening, village market day, school courtyard day, mango orchard day, railway station night, village courtyard dusk, village market dusk, misty mango orchard.

**Limitations:** These are flattened static background paintings, not editable parallax layers or 3D sets. Portrait cover versions can crop off scenery, especially when the source illustration is landscape. Character placement, movement, camera effects and any parallax separation must be handled by your renderer. Three variants were created by changing mood/light on existing artwork, not separate newly illustrated locations.
