# Bangla Toon Studio v10 preview

**Audio-quality repair:** Chatterbox now preserves original Bengali spelling and uses no character pitch processing. New Chatterbox stories pause for listening approval before rendering. The four saved category selections remain. See [repair findings and limitations](docs/QUALITY_REPAIR.md), [audio comparisons](evaluation/quality-repair/review.html), and the [approved 18.7-second test](output/quality-repair-evaluation.mp4). Earlier v10 results below are historical, not a claim that every voice was listening-approved.

Open **Bangla Toon Studio.exe** in this folder. Its visible console shows progress and owns the local server: closing that console stops the application and its children. The browser opens at http://127.0.0.1:8000. The EXE runs the source and environments in this folder; it is not a self-contained installer and must not be moved alone.

**Paste Story → Generate Cartoon → Watch → Download.** Ctrl+Enter submits; Enter adds a line. Registered characters, scenery, speech, supported actions, emotions, subtitles and sound are planned locally. Unknown assets or ambiguous instructions can require a choice. Normal generation never requests individual character recordings.

Every new cartoon is **portrait 9:16, native 1080×1920 at 30 FPS**. Landscape export is unsupported. Settings offers duration (Shorts or Mini Cartoon), music and four persistent base voices; duration never changes orientation. An explicit `video_profile: "low_memory"` API option renders native 720×1280. Duration follows actual speech and actions; Mini does not stretch a short script to three minutes. Longer stories render in cached scene chunks. Resume retries stopped work; **Regenerate Video** creates a new history entry, preserves the original video and reuses matching speech. Failed stories have **Edit story**. Existing completed videos remain unchanged.

See [portrait implementation and real verification](docs/PORTRAIT_VIDEO.md). Matched 21.3-second tests: [2D](output/flat-portrait-1080p-evaluation.mp4) and [hybrid prototype](output/hybrid-portrait-1080p-evaluation.mp4). Both reuse the approved fresh Bengali speech without transformations. The orchard hybrid remains an explicit evaluation prototype while its visual style is reviewed; automatic production uses the existing 2D renderer.

## Saved voices

Adult Male **007**, Adult Female **006**, Child Male **002**, Child Female **005** remain selected. These are official **generated demo outputs**, tested as Chatterbox conditioning inputs, not substituted original reference recordings. Their commercial permissions and perceptual suitability remain unverified. They remain **evaluation only**.

Settings → Four saved voices supports listening, Bengali previews and licensed replacement PCM16 WAVs (3–30 seconds). Enter source/permission details, upload, select and Save Four Voices. Production mode requires authorized replacements and retains character mappings and variation presets. Rahat/Arif/Sami use Male; Mehna/Tithi use Female; Nabil/Rayan/Fahim use Child Male; Anika/Maliha use Child Female. Saved variation presets are retained, but pitch processing is currently disabled. Characters sharing a category use its unshifted voice. Lip-sync uses the final approved audio.

## Windows 10 setup

The existing installation is ready to launch. For a fresh source installation, use 64-bit Python 3.11 and a compatible NVIDIA driver. In PowerShell from the project folder:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install torch==2.8.0 torchaudio==2.8.0 --index-url https://download.pytorch.org/whl/cu126
.\.venv\Scripts\python.exe scripts/setup_chatterbox.py
.\.venv\Scripts\python.exe scripts/download_chatterbox_weights.py
winget install --id Gyan.FFmpeg -e
.\.venv\Scripts\python.exe scripts/install_rhubarb.py
.\.venv\Scripts\python.exe scripts/install_godot.py
```

The setup script creates an isolated Chatterbox environment, reuses matching Torch binaries through Windows junctions and patches its pinned toolkit loader for the checkpoint vocabulary. Do not install its requirements into the main environment. CPU installations use the same Torch/torchaudio versions from `https://download.pytorch.org/whl/cpu` instead. Allow several GB for runtimes, models and scenes. These are existing installer commands; v10 cleanup did not repeat a fresh installation.

Open a new terminal after installing FFmpeg. Verify and start:

```powershell
ffmpeg -version
ffprobe -version
.\.venv\Scripts\python.exe -c "import torch; print(torch.__version__); print(torch.cuda.is_available())"
.\.venv\Scripts\python.exe run.py
```

Use `start.bat` or the EXE for console ownership and browser launch. Run only one server / Uvicorn worker against this workspace. CUDA is preferred; a detected CUDA failure retries once on CPU. Set `$env:CHATTERBOX_DEVICE='cpu'` before launch for explicit CPU inference. NVENC is enabled after a real encoding probe; libx264 is the fallback. Frame streaming and sequential scene rendering bound memory. Optional binary overrides are `FFMPEG_BINARY`, `FFPROBE_BINARY`, `RHUBARB_BINARY` and `GODOT_BINARY`. `.env.example` is documentation, not automatically loaded. Missing Rhubarb is explicitly reported as approximate amplitude lip-sync, not phoneme accuracy.

## Story example

```text
দৃশ্য: আমবাগান
চরিত্র: নাবিল, রায়ান, অনিকা
[নাবিল ধীরে হাঁটে।]
নাবিল: এই! তোরা কিছু শুনলি?
রায়ান: হ্যাঁ! মনে হচ্ছে কেউ আছে!
অনিকা: দাঁড়া! ওই পাতাগুলো নড়ছে কেন?
[SFX: rustling_leaves]
```

Quoted prose dialogue also works. Only dialogue and explicit narration become speech; headings, camera notes, stage directions and screen text remain visual. Local interpretation is deterministic and can misunderstand literary prose. Existing optional AI interpretation stays off unless a provider is configured and story-sharing/cost consent is selected. No new cloud service or LLM was added.

## Data and recovery

- `assets/characters`, `assets/backgrounds`: permanent artwork, anchors and validated rigs.
- `assets/voice_references`: category selections, managed recordings, provenance and presets.
- `workspace`: conversations, preferences, production sessions, audio, cues and compatible scene caches.
- `output`: validated MP4s and evaluation comparisons.
- `workspace/desktop-server.log`, `workspace/chatterbox-runtime.log`: local diagnostics.

Settings → Temporary storage removes only recognized leftover render AVI intermediates in stopped jobs. References, models, audio/scene caches, history and finished videos are retained. Nothing is bulk-deleted automatically. Interrupted work is marked stopped/failed on restart; resume explicitly. Cancelling speech terminates the active default worker; model downloads, Rhubarb and some validation operations can still delay stopping. Regeneration never silently approves paid speech.

The obsolete `/studio` screen redirects home; its source is archived under `docs/archive/legacy-studio`, with compatible backend APIs retained. The previous README is archived at `docs/archive/README-pre-v10.md`. The source checkpoint is `workspace/v10-baseline-source.zip`.

## Troubleshooting and tests

If port 8000 is occupied, close the original console before starting again. Restore missing assets instead of bypassing validation. For CUDA memory failures close other GPU applications or select CPU before launch. For reference validation errors choose a valid category recording; failures never silently change providers. Missing/altered optional sounds are skipped with diagnostics; speech failures stop the job.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest tests -q
```

Browser scripts additionally require Playwright and Chromium. Automated audio/cue checks establish execution and timing, not human pronunciation or acting quality. See `docs/V10_AUDIT.md`, `VERIFICATION.md` and `docs/SELECTED_DEMO_VOICES.md` for evidence and historical limitations.

Current cleanup results and real-media evidence are recorded in [v10 verification](docs/V10_VERIFICATION.md). Reproduce current browser acceptance with `tests/v10_browser_acceptance.py`; `scripts/render_v10_mini.py` runs the longer sample after that acceptance finishes. Both require the local app running.

Validated examples: [2-minute 13-second mini cartoon](output/v10-mini-cartoon-evaluation.mp4) and [vertical benchmark](output/v10-shorts-evaluation.mp4). These are evaluation videos with unverified commercial voice permissions.

## Limits

Six supported rigs are complete: Rahat, Nabil, Rayan, Fahim, Anika and Maliha. Arif, Sami, Mehna and Tithi remain reference-only. Art is a front-view articulated cutout prototype, not television-quality full-angle animation. Complex props, interactions and literary understanding remain limited. Human review is needed for Bangladeshi pronunciation, clarity and voice similarity; demo voices are not commercially cleared.

Keep third-party notices and provenance. Model licensing does not establish source-voice cloning rights. FFmpeg/Rubber Band redistribution obligations and font, Godot, Rhubarb and model/tool licenses remain separate. Existing optional VITS/cloud adapters are retained for explicit compatibility use.
