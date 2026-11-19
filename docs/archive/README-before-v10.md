# Selected official demo voices - evaluation only

Saved: **Male 007, Female 006, Child Male 002, Child Female 005**. The one-prompt workflow now assigns them automatically. Listen in Settings > Default Cartoon Voices > Preview Character Voices > Selected demo conditioning comparisons.

All four generated demo WAVs were tested with actual Chatterbox conditioning. Ten character audio comparisons and an evaluation MP4 were saved. **Commercial permissions and human listening quality remain unverified.** Production mode requires licensed replacements. See [selection and test details](docs/SELECTED_DEMO_VOICES.md).

Earlier implementation notes follow.

# Bangla Toon Studio v9 preview

**Configure four voices once, then paste stories and generate cartoons.** Settings now has exactly four base-recording selectors (Male, Female, Child Male, Child Female), recording playback and Bengali auditions. Per-character reference setup has been removed from normal generation. Characters automatically share their category reference and use stable experimental DSP presets.

Open **Bangla Toon Studio.exe**. See [v9 setup, architecture, licensing and limits](docs/V9.md). Approved recordings must be selected or uploaded once; no cleared four-voice library is supplied automatically. Naturalness/reference-conditioned listening acceptance remains pending those selections.

Earlier version notes follow for context.

# Bangla Toon Studio v7 preview

The current upgrade adds scene continuity, a 16-category EmotionAnalyzer, reliable prose speaker/gaze attribution and clean audio-timed Bengali subtitles. Large in-video dialogue panels are removed. The minimal chat interface and existing assets/providers remain. Open **Bangla Toon Studio.exe**.

See [v7 implementation and limits](docs/V7.md) and [executed verification](VERIFICATION.md). Real evaluation videos: output/v7-landscape-evaluation.mp4 and output/v7-vertical-evaluation.mp4. These use one unconditioned Chatterbox voice; approved per-character recordings and listening review are still required for distinct production voices.

Earlier version notes follow for historical context.

# Bangla Toon Studio v6 preview

The current chat interface, screenplay interpreter and local Chatterbox integration are documented in [docs/V6.md](docs/V6.md). Open **Bangla Toon Studio.exe** to start the app with visible logs. Settings contains optional authorized voice references and seven local demo auditions; production references require permission. AI interpretation remains optional and off by default.

The sections below preserve the earlier v4 implementation and verification history; their old UI/provider descriptions do not override the v6 behavior.

# Bangla Toon Studio v4 preview

A native Windows 10 Bengali cutout cartoon app. **Paste your story → Generate Cartoon → Download MP4** at **http://127.0.0.1:8000**. Characters, backgrounds, actions, camera, saved voices, lip-sync and sound are planned automatically. Detailed controls remain inside the collapsed **Optional studio** panel. The existing Godot cutout renderer and explicit legacy Pillow renderer are preserved.

## One-click production

Open `Bangla Toon Studio.exe`, paste the story and click **Generate Cartoon**. Duration is optional: Shorts uses 720 × 1280; Mini Cartoon uses 1280 × 720, both at 30 FPS. The app validates assets, prepares or reuses speech, builds mouth cues, plans scene direction and sound, renders in bounded scenes, and assembles the MP4. Local speech requires no per-line approval. Only uncertain instructions/missing assets need a choice. Paid cloud speech requires one exact batch approval showing all submitted dialogue; errors never silently switch providers or trigger paid retries.

Ordinary quoted Bengali dialogue is supported, including `নাবিল বলল, “কে ওখানে?”` and `রায়ান উত্তর দিল, “আমি এখানে।”`. Prose paragraphs are split outside quotes. Explicit `Name: dialogue` remains supported. Actions and scenery are visual; unrecognized prose never silently becomes narration. Arbitrary literary prose cannot always be interpreted by deterministic rules; the app shows a correction only when it cannot make a reliable choice. It does not invent missing characters or backgrounds.

Automatic takes remain saved in the existing production session format. Changing music, volume or animation reuses matching, hash-validated approved audio. A request ID prevents duplicate submission; interrupted cloud work is not automatically retried. Status and sessions survive restart. One heavy worker handles speech, voice auditions and rendering. The visible console continues to own the server/process tree.

## Optional Voice Studio

Four primary tabs are **Male**, **Female**, **Child Male**, and **Child Female**, with Narrator as a separate optional assignment. Provider catalogs contain actual accessible IDs, names and available metadata. Search, preview available provider samples, generate a Bengali audition, compare takes and save permanent character assignments. Each category can retain multiple voice presets. Child suitability is never certified from an age label; saving a child-category alternative requires explicitly accepting it after listening.

The installed offline engine has **one VITS voice**, shared by unassigned characters. It is not four natural voices and is not pitch-shifted to imitate children. Configured ElevenLabs/Azure assignments take precedence. No distinct child voice was verified here because cloud credentials are absent. Provider failures remain visible; selecting an offline alternative is explicit. Four category tabs do not imply four verified voice engines.

Configuration: `workspace/voice_studio.json` (validated category presets), `workspace/voice_assignments.json` (permanent provider identities), `workspace/production/` (original/working audio, cues and takes), and `workspace/automatic/` (automatic job state). Existing saved assignments are preserved. Credentials remain environment variables, never browser settings.

The ElevenLabs adapter uses the official REST Text to Dialogue endpoint with `eleven_v4`, Bengali language selection, supported emotional tags and prior-request context. No ElevenLabs SDK is installed or required. Default account-compatible output remains `mp3_44100_128`; optionally set `TOON_ELEVENLABS_OUTPUT_FORMAT=mp3_44100_192` or `pcm_44100` **only if your account supports that tier**. Original provider bytes are kept as `.provider-original` alongside lossless working WAVs. Unsupported account output fails visibly. Official request/output-tier references: [Text to Dialogue](https://elevenlabs.io/docs/api-reference/text-to-dialogue/convert), [models](https://elevenlabs.io/docs/overview/models), [Azure voice support](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/language-support).

## Motion and sound direction

Godot's walk cycle now follows eased world travel and stride length, with contact/down/passing/up phases, grounded stance targets, outward knee poles, arm counter-swing and acceleration/stopping. Nabil, Rayan, Fahim, Anika and Maliha have restrained motion parameters in `app/motion.py`; these tune movement without changing artwork. Expressions, gaze, speaking gestures and listener reactions remain independent of mouth cues. Automatic framing chooses relevant speakers/listeners, while explicit camera instructions take priority.

`SoundDirector` schedules six logical tracks: dialogue, explicit narration, music, ambience, SFX and contact Foley. The registered library includes eight distinct original mood themes, wind, birds, night, water, distant platform rumble, rustling and footsteps. These are original synthetic assets with CC0 metadata/hash validation, not professional field recordings. Supported mood metadata: `সংগীত: mystery` (or happy/comedy/suspense/adventure/emotional/calm/dramatic). `নীরবতা: on` explicitly suppresses that scene's music/ambience. `leaves_rustling` and `rustling_leaves` both map to the real registered rustle.

Footsteps use the same eased-distance phase as Godot's planted feet. Music fades at scene boundaries, ducks over a 150ms attack to 28% during speech and restores over 500ms. Ambience ducks more subtly. Independent levels in the optional Sound Studio affect the six tracks without regenerating speech. The half-second closing hold lets expressions settle and beds fade without stretching any dialogue. Mixing streams PCM, preserves the frame/sample clock and limits peaks before AAC export.

Acceptance artifacts: [benchmark](output/v4-benchmark.mp4), [old/new walking comparison](output/v4-walk-comparison.mp4), [music-off remix](output/v4-remix.mp4), and [mini cartoon](output/v4-mini-cartoon.mp4). See [verification and limitations](VERIFICATION.md). Reproduce with the app running:

```powershell
.\.venv\Scripts\python.exe tests/v4_browser_smoke.py
.\.venv\Scripts\python.exe scripts/render_v4_samples.py
.\.venv\Scripts\python.exe scripts/audit_v4_media.py
.\.venv\Scripts\python.exe scripts/render_v4_comparison.py
```

**Quality limits:** existing front rigs remain cutout prototypes. Genuine side/back art, alternate hands, fully authored seated views and four adult rigs still need artwork. No generic replacements are used. Broad pose controls and numerical foot locks do not establish TV production quality. Real cloud voice quality, youthful suitability, licensing and pronunciation still require account access and listening. The v3 workflow below remains available in the optional studio; its historical verification results are retained.

## Screenplay understanding: speech is explicit

Unlabelled prose **never defaults to narration**. The old parser treated every non-dialogue paragraph as narrator speech; that behavior has been removed. Label actual speech with a registered character name, or explicitly use `বর্ণনাকারী:` / `Narrator:`. Scene, time, cast, action, camera, emotion and SFX instructions do not become speech.

```text
দৃশ্য: আমবাগান
সময়: বিকেল
চরিত্র: নাবিল, রায়ান
[নাবিল গাছের নিচে দাঁড়িয়ে আছে।]
নাবিল (ভয়ে): কে ওখানে?
[রায়ান ধীরে সামনে এগিয়ে যায়।]
রায়ান: আমি কিছু দেখতে পাচ্ছি না!
[SFX: rustling_leaves]
ক্যামেরা ধীরে গাছের দিকে এগোয়।
```

This produces exactly two spoken lines: “কে ওখানে?” and “আমি কিছু দেখতে পাচ্ছি না!”. Parenthetical or square-bracket delivery tags are separated from spoken text. English/Bengali aliases share the existing permanent character identity. Local VITS has no expressive voice controls; the fear tag controls facial animation. Supported cloud controls retain their existing paid approval workflow.

**Screenplay review** shows every typed event with original source text/line numbers. Expand an event to correct its classification, text, actor, action, emotion, background, camera or sound. Ambiguous instructions block production until corrected or explicitly ignored. Project corrections persist in the browser; edits to the source clear stale corrections. **Spoken Audio Preview** lists only the exact dialogue/narration selected for production. The subsequent voice panel shows pronunciation edits and the exact synthesis text before any take is requested.

Actions receive their own animation time; actual measured WAV durations determine speech timing. Speech, visual and sound-effects tracks share a frame clock. Listeners keep their mouths closed; continuous actions can carry through dialogue. A screenplay containing only recognized visual instructions can generate a silent cartoon directly, with zero TTS calls and optional ambience/effects. Select Godot for broader actions; unsupported legacy actions require changing renderer or selecting a supported action.

Old narration-first production sessions cannot request new speech or approve a new render. Analyze the screenplay and prepare a fresh session. Scene boundary indices now refer to **all screenplay events**, including instructions. The parser is conservative rule matching, not universal Bengali language understanding; unrecognized instructions need review. No LLM or cloud video service is used.

Real acceptance outputs: [two-line dialogue cartoon](output/screenplay-dialogue.mp4), [silent action/SFX cartoon](output/screenplay-silent.mp4), [Nabil WAV](output/screenplay-nabil.wav), [Rayan WAV](output/screenplay-rayan.wav). Reproduce with `.venv\Scripts\python.exe tests/screenplay_browser_smoke.py` while the app is running. These short parser acceptance clips intentionally retain their natural duration.

**Shorts:** 30–40s target, 720 × 1280 (9:16). **Mini Cartoon:** 2–3 minute target, 1280 × 720 (16:9), or optional vertical. Godot renders at **30 FPS**; the explicitly selected legacy Pillow fallback retains 24 FPS. Output is H.264/yuv420p and AAC. Actual speech determines duration; the app warns instead of padding, stretching or cutting speech. Animation stays local. VITS works offline once installed; optional ElevenLabs/Azure speech requires credentials, internet and explicit paid-take approval. No LLM, cloud video generation, login, database, Docker or WSL is used.

**Quality status:** this is a working articulated front-art prototype, not a claim of television quality. Watch `output/godot-comparison.mp4` and `output/godot-benchmark.mp4`. Four adult designs still require layered artwork; true profile/back turnarounds and alternate hand silhouettes are missing from the existing front rigs. See [the layer specification](assets/characters/RIG_LAYER_SPEC.md) and [tested evidence and limits](VERIFICATION.md).

## v3 production workflow

1. Select Shorts or Mini Cartoon. Under **Animation renderer & sound**, Godot is the default; optional original quiet Foley/ambience and instrumental music can be changed here.
2. Analyze and resolve the cast/backgrounds. Character identity, source versions and hashes remain locked. The UI labels the Godot art as a front cutout prototype and provides a style-review warning.
3. Prepare voices & storyboard. Every speech segment keeps its original caption separately from its editable synthesized text. English character-name pronunciation presets and a Bengali correction dictionary are supported without romanizing Bengali.
4. Preview a voice on one line before permanently saving an identity. A narrator can have a separate voice. Save a character voice only after listening; changing a saved voice requires confirmation. VITS genuinely has one voice; it is not pitched into fake character voices.
5. Generate local speech previews, or explicitly approve the displayed character usage for each cloud take. Play the audio, compare takes and approve the best one. A changed pronunciation/voice/emotion invalidates that line's approval; unrelated approved lines remain intact.
6. In each line's storyboard controls, edit the acting character, body action, emotion and camera shot. Narration can direct a visible actor without making that actor speak. Use **Preview animation** for an approved line. Advanced waveform/cue controls allow Rhubarb A–H/X corrections; saving cues requires reapproval.
7. Generate the final video. Exact approved WAVs and mouth cues are frozen into the job; paid audio is never generated during rendering or resume. One heavy worker handles previews/rendering. Scene checkpoints, original-art snapshots and console ownership remain supported.

The rule-based director cannot infer arbitrary prose reliably. It exposes its choices, uses neutral behavior when uncertain and directs only a relevant actor, while listeners gaze toward the speaker with closed mouths. The Nabil/Rayan benchmark validates articulated walking/contact, stop, front head tilt/gaze, gesture, blink, surprise, speaking and listener behavior. Run, seated poses, folded arms and other broader pose controls remain prototypes needing per-character visual review. True over-the-shoulder shots are rejected until back/profile artwork exists rather than mislabeled as completed shots.

## Godot 4 on Windows

The tested installation is **Godot 4.7.2 stable**, downloaded from its official release with SHA-512 verification. It runs locally using OpenGL Compatibility on the RTX 3050. No separate Godot editor window needs to be operated during export.

```powershell
.\.venv\Scripts\python.exe scripts/install_godot.py
```

Alternatively set `GODOT_BINARY` to an installed Godot 4 console executable. The adapter creates a bounded runtime project per job, sends JSON direction/assets and invokes Movie Maker with deterministic `--fixed-fps 30`. Animation samples absolute timestamps, including independently restarted chunks. Godot writes **intermediate MJPEG AVI**, then FFmpeg uses NVENC or libx264 for H.264. Each intermediate is deleted after successful scene encoding; cached H.264 and PCM remain for resume. Godot does not directly produce the final H.264 MP4, and NVENC does not accelerate skeletal calculations.

Reproduce the actual directed comparison and motion checks:

```powershell
.\.venv\Scripts\python.exe scripts/render_godot_benchmark.py
.\.venv\Scripts\python.exe scripts/verify_godot_motion.py
.\.venv\Scripts\python.exe tests/v3_browser_smoke.py
```

The benchmark script uses real existing speech artifacts from this installed workspace. On a fresh checkout, generate the supplied speech in the app first; benchmark source WAVs are not distributed with source code. Normal app generation does not depend on those historical job IDs.

## Optional cloud speech setup

Use Windows user environment variables, then restart the Studio console so its process inherits them. Keys are only read by Python, never sent to frontend JavaScript or stored in a project JSON file.

| Provider | Required environment variables | Actual voice selection |
| --- | --- | --- |
| ElevenLabs | `ELEVENLABS_API_KEY` | Backend retrieves this account's accessible `/v2/voices` catalog; select an actual returned ID. Preferred `eleven_v4`, with `eleven_v3` also supported. |
| Azure | `AZURE_SPEECH_KEY`, `AZURE_SPEECH_REGION` | Backend retrieves the region's voice catalog and offers the available `bn-BD-PradeepNeural` / `bn-BD-NabanitaNeural` voices. |
| Local VITS | Existing model/runtime installation | Explicit `default_bn`; one supported local voice. |

ElevenLabs uses the documented Text to Dialogue endpoint, with conservative documented audio tags and prior request IDs for continuity when returned by the provider. Azure bn-BD voices are not given unsupported expressive-style SSML. Distinct voice quality, regional accent, youthful suitability and commercial rights require listening/account review; the app does not invent native Bangladeshi voices or clone voices.

The usage dialog shows submitted character count, including inserted ElevenLabs control tags. Optional `TOON_ELEVENLABS_USD_PER_MILLION` or `TOON_AZURE_USD_PER_MILLION` supplies **your account's** estimate rate. Without one, the app shows character usage and states that account pricing applies. It never invents a dollar price. Approval is bound to spoken text, voice identity and emotion. Provider errors remain errors; changing to VITS is an explicit user choice. Interrupted paid takes become failed, never automatic paid retries.

Persistent settings: `workspace/voice_assignments.json`, `workspace/pronunciation.json`, and `workspace/production/<session-id>/session.json`. Completed takes retain provider identity and original text; approved render jobs retain their own copies. The local comparison sample is `output/voice-benchmark/vits.wav` with its identical script and a status file. No ElevenLabs/Azure sample is claimed because credentials were unavailable during implementation.

Official references checked for this implementation: [Godot Movie Maker](https://docs.godotengine.org/en/stable/tutorials/animation/creating_movies.html), [Godot AnimationTree](https://docs.godotengine.org/en/stable/classes/class_animationtree.html), [Godot TimeSeek](https://docs.godotengine.org/en/stable/classes/class_animationnodetimeseek.html), [ElevenLabs dialogue API](https://elevenlabs.io/docs/api-reference/text-to-dialogue/convert), [ElevenLabs voice catalog](https://elevenlabs.io/docs/api-reference/voices/search), [ElevenLabs audio tags](https://elevenlabs.io/blog/elevenlabs-audio-tags-list), [Azure REST speech](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/rest-text-to-speech), [Azure language/voice support](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/language-support).

## Double-click startup

Open **`Bangla Toon Studio.exe`** in the main project folder. A **visible console/CMD-style window** opens, starts the local server, displays hardware readiness, and opens http://127.0.0.1:8000 in your browser. **Keep this console open while using the app. Closing its X button stops the server and its encoder/lip-sync subprocesses.** No activation command is needed.

The console displays parsing, character/background selection, speech clip progress and durations, Rhubarb cues, rendering percentages, encoding, validation, output paths, elapsed generation time, memory use and errors. Logs are also saved to `workspace/launcher.log` and `workspace/desktop-server.log`.

**Ctrl+C** requests a clean shutdown, allowing a current blocking operation to return. **Closing X** gives shutdown a short window and then Windows process-tree cleanup ensures no server, FFmpeg or Rhubarb child remains running. An interrupted generation is cancelled or becomes retryable after restart; it is never presented as a completed video.

Opening the executable again while it is already running reuses the server in the **original console**. Closing a duplicate launcher window does not close the original owner's server.

Keep the executable beside `app/`, `scripts/`, `assets/` and the configured `.venv/`. This is a small launcher for this installed project; the Python environment, model and tools remain in their existing folders. Copying just the EXE to another computer is not a complete installation.

Closing only the browser leaves the studio running until its console closes. **`Stop Studio.cmd`** remains an alternative graceful stop command and also closes the owning console when the server exits. `start.bat` now uses this same console-owned launcher.

To rebuild the EXE:

```powershell
.\.venv\Scripts\python.exe -m venv .build-venv
.\.build-venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\.venv\Scripts\python.exe scripts/build_executable.py
```

PyInstaller runs in an isolated build environment and builds a console executable. It packages the supervisor rather than embedding the entire CUDA/TTS environment. `--no-browser` starts the same foreground console server without opening a tab; `--status` checks readiness and exits; `--stop` requests shutdown. In PowerShell, prefix a quoted executable path with `&`. Run `python tests/launcher_smoke.py` with port 8000 free to test actual console closing, live logs, and encoder cleanup.

## Windows 10 installation

Use **64-bit Python 3.11**. Run these commands in the existing project directory:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

On an NVIDIA computer with a compatible driver, install the tested matching **PyTorch 2.8.0 + torchaudio 2.8.0 CUDA 12.6** packages:

```powershell
.\.venv\Scripts\python.exe -m pip install --upgrade torch==2.8.0 torchaudio==2.8.0 --index-url https://download.pytorch.org/whl/cu126
.\.venv\Scripts\python.exe -m pip install -r requirements-tts.txt
```

For CPU-only installations, use the same versions from the CPU index instead:

```powershell
.\.venv\Scripts\python.exe -m pip install torch==2.8.0 torchaudio==2.8.0 --index-url https://download.pytorch.org/whl/cpu
.\.venv\Scripts\python.exe -m pip install -r requirements-tts.txt
```

Do not mix torch and torchaudio versions. These tested versions avoid the TorchCodec requirement of newer PyTorch audio loaders. If deliberately changing an already-installed CUDA build to CPU, add `--force-reinstall` to the matching torch/torchaudio command. Stop the studio before replacing its native packages. Virtual-environment activation is unnecessary.

Allow several GB of free installation space for the CUDA runtime; the tested Windows CUDA wheel alone is approximately 2.9 GB. The VITS checkpoint is a separate approximately 1 GB download.

Install FFmpeg with ffprobe and NVIDIA encoder support. For example, the Windows Gyan build can be installed using:

```powershell
winget install --id Gyan.FFmpeg -e
```

Open a new terminal after installation. Check:

```powershell
ffmpeg -version
ffprobe -version
ffmpeg -hide_banner -encoders | findstr h264_nvenc
nvidia-smi
.\.venv\Scripts\python.exe -c "import torch; print(torch.__version__); print(torch.cuda.is_available())"
```

The studio performs a real eight-frame NVENC encoding probe, so an encoder name alone never enables NVENC. It also tests libx264. Set `FFMPEG_BINARY` or `FFPROBE_BINARY` only when a binary is outside PATH. These are optional installation overrides, not per-video settings.

Install the official Windows Rhubarb release locally:

```powershell
.\.venv\Scripts\python.exe scripts/install_rhubarb.py
```

The installer preserves the release's resource files and license under `tools/rhubarb/`. Detection checks `RHUBARB_BINARY`, `tools/rhubarb/rhubarb.exe`, the earlier `.tools/rhubarb/` location, and PATH. Rhubarb is optional: missing/failed output triggers a clearly recorded amplitude-based approximation. This approximation is not phoneme-accurate lip-sync.

Run the server with **one worker**:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Or double-click `start.bat` after setup. The port can also be changed with `.\.venv\Scripts\python.exe run.py --port 8001`. Keep the default localhost binding; there is no public-server authentication.

The VITS checkpoint downloads on the first generation, approximately 1 GB. To prepare it explicitly:

```powershell
.\.venv\Scripts\hf.exe download EMTIAZZ/bangladeshi-bangla-tts-vits config.json pytorch_model.pth --revision 6f4b22c88c2fcc74805aa54c5f2c5f612d463d08 --local-dir models/bangla-vits
```

Cached model files are used without network requests. `HF_HUB_OFFLINE=1` makes a missing checkpoint an explicit error. A public model download does not need an account. If a saved expired Hugging Face token affects the optional CLI command, set `$env:HF_HUB_DISABLE_IMPLICIT_TOKEN='1'` for that terminal. The application adapter downloads this public model anonymously.

## Supported stories and deterministic rules

Ready characters are **Rahat, Nabil (নাবিল), Rayan (রায়ান/রায়ান), Fahim (ফাহিম), Anika (অনিকা), and Maliha (মালিহা)**. Bengali, English and stable-ID labels are accepted with Unicode and whitespace normalization. All five children have complete permanent, validated rigs under `assets/characters/<id>/`; their supplied sheets and original metadata are preserved. Arif, Sami, Mehna and Tithi remain reference-only and cannot substitute for another character.

```text
এক গভীর রাতে রাহাত গ্রামের পুরোনো রেলস্টেশনে দাঁড়িয়ে ছিল। হঠাৎ সে শুনতে পেল কেউ তাকে ডাকছে।

রাহাত: কে ওখানে?

অচেনা কণ্ঠ: শেষ ট্রেনটা মিস করো না।
```

- Only explicitly labelled narration is spoken. Long explicit speech splits at sentence boundaries for VITS; a single spoken sentence over 1,500 characters produces an input error.
- Known Bengali/English aliases, `Speaker:`, full-width colons, bracketed labels, common Markdown labels, em-dash labels, blank lines and Bengali punctuation are supported.
- `রাহাত`, `Rahat` and `rahat` resolve to the permanent `rahat` ID. `অচেনা কণ্ঠ` resolves to **off-screen** `unknown_voice`; no mysterious visitor is drawn. Narration is also off-screen. Mouth motion is assigned only to the matching visible speaker during their speech.
- Names are normalized for Unicode and whitespace; exact aliases and common Bengali name suffixes are recognized. Unknown or ambiguous speakers open a review item with actual local candidates. Pick a ready character, an off-screen voice, or narration. Generation stays disabled until resolved.
- Locations and time clues select validated local backgrounds. Unknown or ambiguous settings require a visual choice; dialogue-only stories also require an explicit background. The app never invents a missing location or substitutes a character.
- Known walking/looking words select a few predefined motions. Other prose uses the saved idle/talk/reaction sequence; the parser does not invent arbitrary actions or cinematography.
- Legacy/local VITS roles use its **single Bengali voice**, `default_bn`. The v3 production panel can explicitly assign accessible cloud voices per character and narrator. Narration and dialogue remain separate in the timeline.

## Cast, scenes and remembered aliases

The app discovers folders under `assets/characters/` and `assets/backgrounds/`; **Refresh assets** rescans without a server restart. Character/background libraries display real cached thumbnails, Bengali/English search, age/time filters and readiness. Six character rigs are ready (Rahat and all five children); Arif, Sami, Mehna and Tithi have reference sheets only and cannot be selected for rendering. All ten supplied backgrounds are usable. Missing or invalid rig layers appear as `incomplete` rather than passing validation.

After analysis, use **Choose character** or **Choose background** for unresolved items, or **Change** to override an automatic choice. **Edit scene boundaries** splits or merges the complete event timeline. Every scene must have a background; each selected image is used in its actual timeline interval. The duration shown before synthesis is an estimate.

Choices apply to the current browser project by default. **Remember for future stories** explicitly writes normalized aliases atomically to `workspace/user_mappings.json`. Existing alias replacements and generic references require confirmation. **New project** clears project choices and backs up the previous draft locally, while remembered aliases survive app restarts. Invalid saved JSON produces a useful error and is never silently replaced.

Generation revalidates the approved story, mappings, scene ranges and asset identities. Changed queued assets fail before speech. Each job snapshots its approved layers under `workspace/<job-id>/asset_snapshot/`, so later library edits cannot change a running video. Source artwork is never regenerated during a job.

To add a character, provide a new stable folder ID, `character.json`, a complete hash-locked sprite rig and valid `animations/*.json` matching the shipped schema. Include `name_bn`, `name_en`, `aliases`, `age_group`, canvas and anchors. A flattened sheet alone remains reference-only. Background folders need `metadata.json` and actual artwork; the supplied legacy flat metadata is validated and adapted in memory. New backgrounds should follow the locked station metadata schema. See the shipped assets for exact examples.

Recognition is deterministic and local: it uses metadata aliases, Bengali suffix rules, location keywords and time clues. It does not understand every arbitrary name hidden in narration. Label unknown dialogue as `Name: text`, then resolve it visually. Selecting an asset does not create matching castle artwork or a new rig.

## Timing and rendering

Real WAV lengths determine the timeline before animation begins. Intro atmosphere, short pauses/reactions and closing movement add a carefully limited number of seconds. **The selected duration is a target, not a reason to invent speech, accelerate audio, freeze a short story, or truncate dialogue.** Short/long stories display a duration warning. `samples/mini_cartoon_bn.txt` is a complete three-location Bengali story for the Mini Cartoon mode. A ten-minute processing limit prevents accidental huge jobs.

The mixer converts clips to mono 48 kHz 16-bit PCM with modest headroom: **1,600 samples/frame at 30 FPS**, or 2,000 at legacy 24 FPS. Speech starts on frame boundaries, clips do not overlap, and speech is never cut to fit a slot. The timeline is partitioned at location boundaries and into render scenes no longer than 12 seconds. Cuts preserve the original clip offset and mouth cues. Godot records one bounded intermediate AVI per scene; FFmpeg encodes it, then the AVI is removed. The legacy renderer streams raw frames directly to FFmpeg. Neither keeps a full frame sequence in RAM.

FFmpeg concatenates the completed scene videos without re-encoding video and muxes the continuous audio track, encoding AAC **once**. Scene boundaries therefore cannot accumulate separate AAC encoder delays. Subtitles paginate within actual speech intervals rather than visual holds. Landscape composition uses the same saved rigs and source backgrounds, framed to 16:9; it does not invent wider artwork.

The generation panel lists each render scene, its status, progress, duration, measured processing time and cache reuse. One heavy worker processes the queue. A failure or cancellation keeps completed work. Use **Resume unfinished scenes**, or **Retry this scene** beside a failed scene. Resume keeps the same job ID, approved snapshot, voices, format and timeline, validates cached WAV/cue/video hashes, and skips completed valid scenes. It never changes mappings based on an edited editor draft. Use Generate Video for a changed story.

After an app restart, interrupted jobs appear failed and remain resumable. Old jobs created before scene checkpoints still offer a fresh retry. `/resume` continues checkpoints; legacy `/retry` deliberately creates a new job. A damaged scene cache is re-rendered. Approved production speech or cues that fail their hash checks require reapproval; cloud speech is never regenerated automatically. Legacy unapproved local speech can be re-synthesized. Damaged frozen artwork fails rather than switching identity.

The legacy Pillow fallback retains its original simple breathing/blinking, rigid limbs and camera motion. It is available explicitly when Godot cannot be used and is not advertised as equivalent articulated quality. Godot's foreground layers, contact shadows, ground targets, separate brows/pupils, gaze, mouth blends, camera bounds and location dissolves form the new path. Original procedural Foley follows foot-contact timing; quiet ambience/music are ducked under speech and mixed through FFmpeg with a compensated limiter. No downloaded music or environmental recordings are bundled.

CUDA is selected only when `torch.cuda.is_available()` is true. One lazy shared `VITSTTSEngine` instance uses `torch.inference_mode()`. CUDA initialization/inference failures, including OOM, move the shared model to CPU and retry there once; if CPU also fails, the job fails. Silent or fake narration is never substituted.

NVENC is selected only after a real probe succeeds. A later NVENC encoding failure retries the render through tested libx264 (`veryfast`, CRF 23). Encoding uses H.264/yuv420p and AAC at 192 kbps. Before a job becomes completed, ffprobe checks the streams, resolution, FPS and duration, then FFmpeg decodes the complete MP4 for integrity. Invalid files are never exposed as completed outputs.

## Permanent character identity

`assets/characters/rahat/` contains `character.json`, body/head/hair layers, open/closed eyes, all A–H/X mouth sprites, separate arms/legs, and definitions for idle, blink, talk, walk, look_left, look_right, turn_head, surprised and afraid.

The original reference sheets are preserved. The new rig is an original, simplified vector-style interpretation using the reference palette; it is not a pixel-exact extraction of the flattened illustration. All generated videos reuse these same saved rig layers. No artwork is regenerated during video generation.

Validation checks IDs, semantic versions, canvas sizes, PNG transparency/visibility, anchor positions, animation keyframes, required labels and SHA-256 hashes. Reports record the character version, full sprite hashes and aggregate identity fingerprint. Missing/tampered/mixed layers fail validation. Background layers are locked the same way. Any redesign must be explicitly versioned; restore damaged files from source control rather than silently rebuilding them.

`scripts/build_assets.py` is the reproducible source for the shipped original rig/background. Running it normally skips existing ready assets. An intentional redesign requires both `--replace` and a new semantic version, for example `--version 1.1.0`. It is a development tool, not part of generation.

`scripts/build_child_rigs.py` is the corresponding source for the five child rigs. It validates all layers before publishing aliases, skips already locked rigs, and requires a new version for an explicit `--replace`. Children have distinct hair, clothing/patterns, skin palettes and accessories based on the supplied flattened sheets. `hair_back.png` preserves Anika's bob and Maliha's braids behind the face; Rayan's blue glasses remain visible when blinking. All rigs include A–H/X mouths and the full animation set. The stage fits three or five visible children without cropping them off-screen.

Run `python scripts/verify_children.py` with the app running to generate the supplied Nabil/Rayan/Anika dialogue using real VITS and Rhubarb. It saves a validated MP4, per-speaker previews, a five-rig contact sheet and `workspace/children-acceptance.json`. The supplied replacement station painting is preserved and hash-locked as a flat background; unrelated legacy foreground layers are excluded.

## Local API and job storage

Interactive documentation: http://127.0.0.1:8000/docs

| Method | Endpoint | Responsibility |
| --- | --- | --- |
| GET | `/` | Story editor, asset pickers, scene review and generation |
| GET | `/api/characters`, `/api/backgrounds` | Discovered assets and readiness; search/filter parameters |
| POST | `/api/assets/refresh` | Rescan folders and validate assets |
| GET | `/api/assets/{kind}/{id}/preview` | Safe cached thumbnail |
| POST | `/api/analyze`, `/api/resolve`, `/api/preflight` | Structured characters, scenes, issues and review token |
| POST | `/api/mappings` | Project validation or explicit remembered alias, conflict confirmation |
| POST | `/api/generate` | Story, character_mappings, scenes, review_token, duration_mode (`shorts`/`mini`) and video_format (`auto`/`landscape`/`vertical`) |
| GET | `/api/jobs/{id}` | Actual stage, progress, warnings/errors and result URLs |
| GET | `/api/videos/{id}` | Validated MP4 with byte-range playback |
| GET | `/api/videos/{id}?download=true` | Download attachment |
| GET | `/api/health` | CUDA, NVIDIA, tested encoder/tool readiness and model cache |
| POST | `/api/jobs/{id}/cancel` | Safe cancellation request |
| POST | `/api/jobs/{id}/retry` | New attempt for a failed/cancelled job |
| POST | `/api/jobs/{id}/resume` | Resume a failed/cancelled job, reusing validated audio, cues and scenes |
| POST | `/api/jobs/{id}/scenes/{render_scene_id}/retry` | Invalidate one scene checkpoint and resume the job |
| GET | `/api/jobs/{id}/report` | Timings, hardware use, memory, asset hashes |
| GET | `/api/jobs/{id}/timeline` | Frame-aligned speech, holds and animation events |
| GET | `/api/jobs/{id}/subtitles` | UTF-8 SRT |

Production APIs: `GET /api/voices/providers`, `GET /api/voices/{provider}/catalog`, `PUT /api/voices/assignments/{character_id}`, `GET/PUT /api/pronunciation`, `POST /api/production`, and `GET /api/production/{session_id}`. A production segment supports spoken-text/direction edits, voice selection, usage estimates, speech takes, explicit take approval and a short animation preview. Take routes serve WAV, waveform peaks and validated A–H/X cue edits. `POST /api/production/{session_id}/render` requires all approved takes. See `/docs` for request schemas. The reviewed `/api/generate` route also accepts `renderer`, `production_id`, `sound_effects` and `music`; a Godot job requires approved speech.

The older audio/render routes remain for compatibility and testing and retain their original station planning. The reviewed `/api/generate` workflow supports the discovered library and multiple scenes. No silent preview engine is used. The public page exposes asset choices but keeps speech and render configuration automatic.

A single background thread handles heavy jobs. The queue allows up to four active/queued requests and the API stays responsive. Statuses are `queued`, `parsing`, `generating_audio`, `lip_sync`, `rendering`, `encoding`, `validating`, `completed`, `failed` or `cancelled`. A UUID is required before any job file is accessed. The app does not serve arbitrary paths.

Final files are `output/<job-id>.mp4`. `workspace/<job-id>/` keeps state, parsed story, speech clips/cue cache checksums, frozen assets, subtitles, poster, timeline, `scenes.json`, performance report and encoder logs. `render/scenes/` stores completed video/PCM checkpoints; `render/timeline.wav` is intentionally retained for resume. Only temporary per-clip normalization files are removed. Caches consume disk space rather than holding long videos in RAM. Keep the job folder to retain resume ability. The browser restores its latest job and separately preserves newer story edits.

Cancel requests are checked between TTS/Rhubarb operations and every half-second of frames. An in-flight model download, synthesis, Rhubarb call or final validation must return before cancellation completes. Server shutdown requests cancellation and waits for cleanup. Stop the server before removing project folders. There is no multi-process locking: do not run multiple Uvicorn workers or simultaneous studio servers over the same workspace.

## Testing and performance

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
```

Unit tests isolate failures using mocks. The encoder integration produces and validates real MP4s from test PCM; this is not presented as proof of speech synthesis. The separate real browser acceptance uses actual VITS and generates two stories to verify permanent character identity, browser playback, download, reload, mobile layout and useful errors:

```powershell
.\.venv\Scripts\python.exe -m pip install playwright
.\.venv\Scripts\python.exe -m playwright install chromium
# Keep the studio running in another terminal:
.\.venv\Scripts\python.exe tests/review_browser_smoke.py
# Complete real Mini Cartoon, including cancel/resume and landscape playback:
.\.venv\Scripts\python.exe tests/mini_browser_smoke.py
```

To render the sample directly through the running HTTP API: `python scripts/render_sample.py`.

CPU/GPU benchmarks run one device per process to limit RAM usage:

```powershell
.\.venv\Scripts\python.exe scripts/benchmark_tts.py --device cpu
.\.venv\Scripts\python.exe scripts/benchmark_tts.py --device cuda
```

Per-job reports measure parsing/assets, speech, lip-sync, audio preparation, CPU frame composition, pipe waits, stream wall time, validation and total generation time. Encoding overlaps compositing, so its GPU-only duration is not fabricated as an independent number. RSS samples cover the server and its encoder children every 250 ms; PyTorch reports its worker's peak CUDA allocation. Cold model/driver initialization is slower than warm speech. See **[VERIFICATION.md](VERIFICATION.md)** for measured results and remaining limitations.

## Source layout and licenses

Existing modules are retained under `app/engines/`; `app/assets.py`, `app/timeline.py` and `app/hardware.py` provide the registry, persistent asset validation, timing and capability probes. The UI is plain HTML/CSS/JavaScript under `app/templates/` and `app/static/`.

The model is the actual Coqui-format VITS checkpoint, not a Transformers `VitsModel`. It is pinned to revision `6f4b22c88c2fcc74805aa54c5f2c5f612d463d08`. Its [model card](https://huggingface.co/EMTIAZZ/bangladeshi-bangla-tts-vits) lists Apache-2.0 and credits Emtiaz Uddin Ahmed. Only load trusted PyTorch checkpoints. [Coqui TTS](https://github.com/idiap/coqui-ai-TTS), [Rhubarb](https://github.com/DanielSWolf/rhubarb-lip-sync), [FFmpeg](https://ffmpeg.org/) and the bundled Noto Bengali font retain their own licenses; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). No internet artwork, music or voice recordings are mixed into generated videos.

Model weights, tools, generated videos, caches and `.venv` are excluded from Git. No diffusion model is installed. Arbitrary gestures, generating new artwork, distinct natural voices and word-level Bengali forced alignment remain outside this implementation.
