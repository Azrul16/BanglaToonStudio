# v10 verification — 18 November 2026

## Changes

The existing FastAPI/vanilla-JS monolith remains. The obsolete studio screen and its exclusive scripts/styles are archived, and `/studio` redirects to the chat. Required benchmark routes were moved into the category-voice router; unused per-character recording implementation and guessed subtitle-page helper were retired. Existing production APIs and optional providers remain. Historical browser scripts are archived; `tests/v10_browser_acceptance.py` covers the current screen.

Settings now has compact format/music controls, four collapsed category selections and one shared audio player. Licensed replacements, optional configured AI consent and narrowly scoped user-initiated temporary cleanup remain collapsed. No new framework, cloud service or model was added. Failed/uncertain stories can be restored to the editor. Completed cartoons can be regenerated into independent, idempotent history entries without copying paid approval. Scene processing times come from real job records. Queued cancellation is immediate; active default speech cancellation terminates its worker. Shutdown releases the default worker. Missing/altered optional sound assets are skipped with diagnostics.

Live acceptance discovered and fixed an unresolved-speaker `KeyError` in Chatterbox assignment: asset clarification now occurs before a real category voice is assigned. The regression test covers the real conversation endpoint as well as the assignment function.

## Executed checks

- Full suite: **170 passed**, 2 warnings, 427.56 seconds (`workspace/v10-full-tests.txt`).
- Final maintenance/cancellation/sound checks: **6 passed** (`workspace/v10-final-focused-tests.txt`).
- Final safety checks: **10 passed** (`workspace/v10-final-safety-tests.txt`); unresolved-speaker endpoint regression additionally passed after that run.
- Final selected-voice/category/cancellation regressions: **21 passed** (`workspace/v10-final-voice-tests.txt`), including the unresolved-speaker endpoint fix.
- Python compilation and both JavaScript syntax checks passed.
- Real Chromium acceptance: desktop and 390px mobile, four exact saved demo IDs, one shared audition player, Ctrl+Enter submission, duplicate guard, real MP4 playback/download checksum, regeneration with separate IDs, clarification and Edit story restoration. No JavaScript errors or mobile horizontal overflow. `workspace/v10-browser-acceptance.json` contains the evidence.
- All four selected recordings actually played through the shared player (`workspace/v10-voice-auditions.json`); this does not constitute perceptual listening approval.
- Both real short benchmark formats: **26.1 seconds / 783 frames**, 720×1280 and 1280×720, H.264/AAC. Full FFmpeg decode passed, no detected black intervals, zero audio/video duration difference, no clipped master PCM samples. Nabil/Rayan/Anika had active mouth traces; nonspeakers remained closed. Foot-contact and stance-lock audits passed. Music and Foley were present.
- `scripts/verify_v10_preservation.py` checked **448 original asset files and 10 existing MP4s** against pre-change hashes; none changed. **35 speech/cue records** passed: visible dialogue used Rhubarb from byte-identical final processed audio; off-screen narration correctly had no animated mouth cues. Source backup: `workspace/v10-baseline-source.zip`.

The two-format browser rerun reused matching real Chatterbox WAVs generated in the preceding run; that preceding run executed new selected-demo-conditioned Bengali synthesis on CUDA. It was not tone/mock synthesis. Regeneration reused speech but rendered a separate video. GUI playback is an execution check, not human listening acceptance.

## Media

- `output/v10-shorts-evaluation.mp4`: three-child mango-orchard benchmark, vertical.
- `output/v10-mini-evaluation.mp4`: the same short benchmark in landscape; **26.1 seconds, not a 2–3-minute cartoon**.
- **`output/v10-mini-cartoon-evaluation.mp4`: 132.933 seconds (2:13), 1280×720, 3,988 frames, 12 rendered chunks.** Full decode passed: no black intervals, no clipped master PCM and 0.000325-second audio/video duration difference. All three children had speaking mouth traces; walking/Foley and source speech hashes passed. Playback and download checksum passed through chat history (`workspace/v10-delivery-smoke.json`). Courtyard, orchard and school frames were inspected, including two-line subtitles.
- Existing ten-character/four-category before/after WAV comparisons remain at `output/selected-demo-audio-comparisons.zip`; their conditioning evidence remains in `evaluation/selected-demo-conditioning/results.json`.

## Comparison and limits

The original mini sample produced a **116.3-second** timeline. Its render was cancelled after two completed chunks, preserving the audio and scene caches. `samples/v10_mini_cartoon_bn.txt` adds supported walking/waving/camera/title actions to the unchanged dialogue. All **25 speech hashes remained identical** in the completed revised benchmark. Initial speech preparation took **667.51 seconds**; final rendering reused that speech and took **188.80 seconds** (194.14 seconds including orchestration and polling). This is not fresh end-to-end synthesis in three minutes. Observed peak server/TTS/render process-tree RAM was **2,357 MB**, excluding Windows/browser; encoding used **h264_nvenc**. See `workspace/v10-mini-verification.json`, `workspace/v10-mini-memory.json` and both mini run logs.

An idle owned-server stop/restart completed successfully, with the category IDs retained. The existing visible-console EXE loads the updated source; its process-tree ownership was retained.

The previous same-text v7 benchmark used one unconditioned voice and lasted 24.933 seconds. The new benchmark uses the selected category references and lasts 26.1 seconds. Different speech durations prevent a direct render-speed or perceptual-quality comparison. Original rig/background hashes and the shared motion engine remain stable; there is no claimed new artwork or measured listening-quality improvement.

Real export frames were visually inspected for identity, framing and Bengali subtitle placement. Automated timing/pose/waveform checks do not establish every phoneme's accuracy, natural Bangladeshi pronunciation, distinct child identity or expressive acting. Human listening review remains pending. Rhubarb's Bengali acoustic approximation is not certified phoneme alignment.

All four official selected generated demos remain evaluation-only with commercial permissions unverified. Original reference recordings were not substituted or declared cleared. Production mode requires licensed replacements. Six rigs are ready; Arif, Sami, Mehna and Tithi remain reference-only. Front-view cutout motion, limited props/interactions and deterministic prose understanding remain prototype limitations. Long generation time depends on model load, speech length and hardware; no real-time guarantee is made. Installation instructions reference existing scripts; no fresh Windows reinstall was performed during cleanup.
