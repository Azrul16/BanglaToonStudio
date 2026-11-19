# Bangla Toon Studio — 5-character reference pack

## Animation-ready children

**নাবিল / Nabil (`nabil`), রায়ান / Rayan (`rayan`), ফাহিম / Fahim (`fahim`), অনিকা / Anika (`anika`), and মালিহা / Maliha (`maliha`) now have permanent layered PNG rigs.** Rahat also remains ready. The adult reference-only entries below are preserved separately.

Each child rig has 28 locked sprite/animation files: body, head, front/back hair, eyes with blink states, articulated arms/legs, all Rhubarb A–H/X mouth sprites, and idle/blink/talk/walk/look/turn/surprised/afraid definitions. All use a shared 384×640 coordinate system with explicit anchors and per-child height scaling. Nabil's checked teal shirt/orange shoes, Rayan's yellow hoodie/blue glasses, Fahim's maroon panjabi/red gamcha, Anika's turquoise tunic/purple clip, and Maliha's coral floral dress/braids/butterfly clip are retained in simplified original artwork.

These are reproducible layered recreations based on the supplied flattened sheets, rather than automatic crops of baked-in expressions. `character_sheet.png` is unchanged; `design_reference.json` preserves original metadata. The new rig metadata uses the requested IDs without the old `child_` prefix, locks every layer with SHA-256, and retains legacy aliases. Registration and name lookup validate the complete rig; missing or changed files are rejected.

Source: `scripts/build_child_rigs.py`. Normal runs skip and validate existing rigs. Explicit replacements require a different semantic version. No runtime generation changes a child's identity. Real speech/video acceptance is available through `scripts/verify_children.py`; see `workspace/children-acceptance.json` after running it.

## v0.3 runtime integration

The original images below are preserved. **Rahat now additionally has a complete permanent PNG rig**, stable anchors, A–H/X mouth shapes, animation definitions, version metadata and SHA-256 identity checks. It uses the saved blue-shirt palette in a simplified original vector style; it is not a pixel-exact crop of the flattened reference. Rendering reuses the same saved layers and never regenerates them. The other four characters remain reference-only and cannot be silently substituted with Rahat. See the project README for validation and redesign rules.

Contains **3 male** and **2 female** recurring Bengali cartoon character designs:

| ID | Bangla name | English name | Gender | Role |
|---|---|---|---|---|
| rahat | রাহাত | Rahat | Male | Protagonist |
| arif | আরিফ | Arif | Male | Friend |
| sami | সামি | Sami | Male | Elder / Guide |
| mehna | মেহনা | Mehna | Female | Friend |
| tithi | তিথি | Tithi | Female | Cousin / Friend |

## Contents

- `all_5_character_sheets.png`: all five designs together.
- `assets/characters/<id>/character_sheet.png`: separate character sheet for each person, with turnaround views, expressions and action references.
- `assets/characters/<id>/portrait_reference.png`: reference crop for each character.
- `assets/characters/<id>/character.json`: stable IDs, Bengali names, visual identity palette and artwork version.
- `manifest.json`: registry for your application.

## Integration into your app

Copy `assets/characters/` to your Bangla Toon Studio project and load names/IDs via the manifest. The same reference sheet should be used when creating animation assets for that character, maintaining visual continuity.

**Important:** These are **flattened raster character-sheet references**, not cutout rig sprites. They cannot directly drive head, eyes, body and Rhubarb mouth animation. For actual animation, create separate transparent PNG layers and Rhubarb mouth shapes from these references, with validated anchors. The small mouth-shape illustrations in the sheet are visual references, not production-ready cropped mouth sprites.

The image generator can occasionally produce imperfect small labels and turnarounds; use the metadata as the authoritative name/ID registry.


# Bangla Toon Studio — 5 Original Child Character Sheets

Five **new** Bangladeshi-inspired child characters (not child versions of the previous cast):

| ID | Name | Age | Gender | Role |
|---|---|---:|---|---|
| child_nabil | নাবিল (Nabil) | 10 | Male | Explorer |
| child_rayan | রায়ান (Rayan) | 11 | Male | Inventor |
| child_fahim | ফাহিম (Fahim) | 9 | Male | Village friend |
| child_anika | অনিকা (Anika) | 10 | Female | Science enthusiast |
| child_maliha | মালিহা (Maliha) | 8 | Female | Nature lover |

Each character folder contains `character_sheet.png` and `character.json`. Nabil also has a detailed high-resolution variant. `all_characters_reference.png` shows the whole cast side by side.

Character sheets have turnaround poses, facial expressions, illustrated mouth shape references, action-pose references, and palette cues. The drawings are **concept sheets**, not animation-ready transparent layered rigs; use them to create separate and aligned head/body/eye/mouth layers. Exact lip-sync shape placement and side-view anatomical consistency should be manually checked.

## Source inspiration (no third-party images included)

- https://tourismboard.gov.bd/ (Bangladesh tourism handbook, traditional attire references)
- https://www.observerbd.com/news/130489 (Bangladeshi children's clothing)
- https://www.behance.net/gallery/92081567/Ekam-Water-Conservation-Character-Background-Design (character sheet layout reference)

All included illustrations are newly AI-generated original character concepts rather than copied reference images.
