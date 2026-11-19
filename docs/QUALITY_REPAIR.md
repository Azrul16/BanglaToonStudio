# Audio and animation repair — 18 November 2026

## Result and listening decision

The reported source is `output/35334dd3d8a541c1a9de2ceb54854c4f.mp4` (87.5 seconds). It was preserved. Five matched comparisons were exported, each with `original_tts.wav`, `processed_voice.wav` and `final_mix_excerpt.wav`. Fresh Chatterbox recordings were generated without DSP, using the configured references and original settings. An exact-submitted-input control was generated separately.

The user initially rejected fresh speech and requested that rendering remain blocked. Six real local VITS comparisons were then generated explicitly; this did **not** change any production assignment. The user subsequently selected the samples labelled **Fresh Chatterbox, no transformations** and explicitly approved them for the **15–20-second animation test**. Rendering proceeded only after that approval, bound to the selected WAV hashes. This is limited acceptance of those clips, not certification of all future Bengali speech.

Final benchmark: **`output/quality-repair-evaluation.mp4` — 18.733 seconds, 720×1280, 30 FPS, H.264/AAC**, using Nabil, Rayan and Anika in the existing mango orchard. The final renderer is Godot articulated cutouts. A diagnostic draft accidentally selected the legacy CPU compositor; that script error was corrected before final motion acceptance. The draft is not the delivered benchmark.

Open `evaluation/quality-repair/review.html` for the listening comparisons and original/repaired videos. `output/quality-audio-comparisons.zip` contains the WAV comparisons. Evidence is in `evaluation/quality-repair/*.json` and `workspace/quality-*.log`.

## Audio findings

- All five source originals were mono PCM16 at **24 kHz**; final MP4 excerpts decode at **48 kHz**. These are intentional stages, not a playback-rate mismatch. Original and pitch-processed durations were identical. No clipped samples or long silent gaps were found in those five comparisons.
- Fresh inference with the **exact submitted text/reference/seed/settings** reproduced all five original TTS WAVs **byte for byte**. There was no evidence of an unexpected provider switch or an incompatible original recording being substituted.
- The speech normalizer changed canonically equivalent Bengali Unicode spellings before TTS. For three of five lines, the original spelling and NFC-rewritten spelling produced **different tokenizer sequences**, with no unknown tokens in either. The user-approved fresh variant used the **original spelling**. Chatterbox input now preserves that spelling; character/alias lookup still normalizes independently. This isolates a real input-pipeline difference. It does not prove a particular phoneme's error was caused by normalization.
- Character pitch processing was active in the reported video without intelligibility approval. It is now **disabled**, with byte-identical neutral copies and a new DSP cache version/policy. Saved offsets/references remain intact, but effective pitch is zero. No EQ, denoising, reverb or pitch processing is used to disguise incorrect pronunciation.
- Pitch shifting was **not proven to be the sole cause**. The listening decisions and exact-input controls do not justify declaring the base model flawless or identifying specific mispronounced words without further word-level feedback. No such listening results were fabricated.
- `waveform-comparison.json` records timeline-aligned correlation, normalized sample RMSE, least-squares gain and gain-adjusted residual RMS for all five original/processed/mixed pairs at a common 24 kHz diagnostic rate. Pitch shifting intentionally changes waveforms; mixed-track residuals include AAC, resampling, gain and the intentional sound bed. These values are not pronunciation scores.
- VITS remains an explicitly labelled alternative with **one shared voice**. Its exported output uses peak normalization: isolated single full-scale samples were distinguished from sustained clipping plateaus. Signal validity is not listening approval. Chatterbox remains the selected production provider; no silent fallback occurred.

Matched duration examples (old model input versus approved original-spelling inference):

| Source segment | Speaker | Old original/DSP | Approved fresh |
|---|---|---:|---:|
| 001 | Nabil | 5.60 s | 5.00 s |
| 002 | Rayan | 4.56 s | 5.48 s |
| 003 | Anika | 3.12 s | 3.12 s |
| 010 | Rayan | 4.76 s | 4.44 s |
| 017 | Anika | 3.24 s | 3.24 s |

These duration differences are measurements, not intelligibility scores.

## Model, cache and pronunciation controls

The actual five local model/tokenizer/conditioning files were checked against the pinned Hugging Face revision `025a56f71bef7fddc9ee878c9e9557d2ca559499`. The tokenizer vocabulary is **2,530**. The [official model card](https://huggingface.co/BosonLab/chatterbox-bangla) documents the extended Bengali tokenizer and `audio_prompt_path`. The installed CLI lacked model-inspection commands, so public Hub metadata was used for file verification. SHA256 expectations are recorded in `app/voices/chatterbox-checkpoint.json`; the worker verifies the files before loading.

Runtime records include model ID/revision, tokenizer SHA256, verified checkpoint hashes, actual reference SHA256, exact input SHA256, generation settings and inference device. A fresh run of the updated worker verified all five files, applied the selected reference and reproduced an approved sample. Reference IDs remain Male 007 / Female 006 / Child Male 002 / Child Female 005. These files are the selected **generated demo outputs**, not secretly substituted original reference recordings. Their commercial permissions remain unverified.

Original speech and final processing caches remain separate. Reference hashes, exact submitted text, generation settings and processing schema/policy affect cache identity. New neutral speech cannot reuse a previous pitch-processed take as if it were neutral. Existing clips and cache files are retained.

`workspace/pronunciation.json` is the persistent whole-word correction dictionary, with the existing `/api/pronunciation` GET/PUT endpoints. It was initialized with the existing six English-to-Bengali name mappings only because no file existed. No unreviewed Bengali phonetic substitutions were invented. Keep Bengali conjuncts and complete words intact; corrections should be entered only after identifying and reviewing the actual problematic word. Existing long-text splitting uses sentence boundaries where available and preserves whole words; this repair did not claim an untested sentence-splitting strategy improves every voice.

No suitable installed Bengali ASR model was found. No ASR transcript or loudness metric was presented as proof of pronunciation.

## Quality and listening gates

`app/audio/quality.py` checks valid mono PCM16 rates, nonempty/complete frame data, bounded duration, sustained clipping, silence runs, suspiciously short output, abrupt-end risk and processing duration drift. It records warnings rather than claiming to recognize missing words. Isolated normalized full-scale peaks are warnings; sustained plateaus or significant full-scale fractions are errors. Checks run on newly generated takes, approved/cached takes and the main render path.

New automatic Chatterbox jobs pause at **Listen before rendering** inside the existing conversation. Each clip is playable; the user must explicitly accept pronunciation/naturalness. Approval is bound to current clip hashes and rechecked against current voice/reference settings. A stale approval, changed WAV or changed reference blocks rendering. Waiting review state survives restart and does not occupy the heavy worker. No repeated configuration popup or new Voice Studio was added. Existing explicit legacy/manual APIs remain compatibility interfaces.

## Motion, composition, subtitles and mix

- Corrected weight transfer toward the stance leg and reversed arm swing to oppose leg travel. Actual root travel still drives the stride phase, foot plants and Foley. FPS was not increased to mask motion defects.
- Wider stage slots and bounded travel prevent the test walk from pushing Nabil's head into Rayan. Positions carry into later shots instead of resetting. Source rigs remain unchanged.
- A camera cue no longer latches across all subsequent dialogue. The benchmark uses an establishing shot, a speaker-focused shot and two-character conversations with explicit partner framing. A two-shot uses the pair's positions instead of a generic zoom. No object-focused shot was invented for the unregistered box/props.
- Existing gaze, head tilt, facial expressions and talking gestures remain independent of mouth cues. They are deterministic/contextual rather than random camera motion.
- Portrait subtitle target size increased from 40 to 48, with a readable lower bound; measured first-three sizes are **43 / 43 / 48**, versus **40 / 40 / 40** in the source. Bengali shaping, two-line maximum, outline, safe margins and actual-WAV timing remain. No dialogue boxes were restored.
- Music now ducks to **16%** rather than 28%, with a smoother **180 ms** attack and 500 ms release. Ambience is reduced further during speech. Speech-only and mixed WAVs are available for comparison. No extra reverb or aggressive voice compression was added; the limiter remains a safety ceiling.

The rigs contain separate articulated limb/body/head layers, so this is not whole-PNG walking. They are still **front-view cutouts**: convincing profile walking, turns through multiple views, anatomical hands/fingers, complex object interaction and full-body rotation require additional authored artwork. Better grounding does not establish television-quality natural motion.

## Executed validation

- Full regression suite: **176 passed**, 2 warnings (`workspace/quality-repair-full-tests.log`).
- Follow-up voice/spelling checks: **21 passed** (`workspace/quality-spelling-final-tests.log`).
- Final quality/director/subtitle/mix regressions: **28 passed** (`workspace/quality-final-regressions.log`).
- Final six quality/approval/checkpoint tests passed, including rejection of stale/unconfirmed approval and exactly one queued render after a valid approval (`workspace/quality-approval-final-tests.log`). Synthetic test signals in unit checks are not presented as listening evidence.
- Chromium played the approved WAV and final local MP4; the review-card UI rejected an unconfirmed render, with no JavaScript errors or mobile horizontal overflow (`browser-verification.json`). The live planning endpoint also preserved the approved original-spelling model input.
- Godot headless editor parse/import check passed. The actual benchmark was also rendered by Godot, not merely compiled.
- Final MP4 was fully decoded; no black intervals, no clipped master PCM, zero audio/video duration difference. All three children have active speech mouth traces; nonspeakers stay closed. Rhubarb uses final approved WAVs and its language-independent phonetic recognizer; this remains approximate Bengali lip-sync, not certified phoneme alignment.
- Foot-grounding audits retained subpixel stance stability; frame/trace results are recorded in `video-verification.json`. Actual output frames were inspected for subtitle placement, stable designs and the repaired spacing. Human judgment of final motion/acting remains distinct from those measurements.
- All **448 baseline asset files** and **10 existing MP4s** retain their hashes. Four voice selections and source artwork were preserved. The previous source checkpoint is `workspace/quality-before-source.zip`.

The complete 87.5-second story was **not regenerated** under an unreviewed voice. The delivered acceptance artifact is the approved short benchmark, with limitations recorded above.
