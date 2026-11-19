# Selected official demos — evaluation configuration

These exact selections are saved in `assets/voice_references/four_voices.json` and survive restarts:

| Category | Generated official demo output | Characters |
|---|---|---|
| Adult Male | 007 | Rahat, Arif, Sami |
| Adult Female | 006 | Mehna, Tithi |
| Child Male | 002 | Nabil, Rayan, Fahim |
| Child Female | 005 | Anika, Maliha |

The mode is **evaluation**. Each record has `approved: false`, `evaluation_only: true`, and `commercial_permission_verified: false`. The managed WAV's content hash and pinned source URL are recorded. Category labels reflect the requested roles, not verified original speaker age or identity. Previous settings were backed up before these selections; existing recordings and variation presets were retained.

## What was actually tested

The inputs were the repository's **generated output WAVs**, not the files linked under **Original**. Original-reference URLs are recorded for provenance, but those recordings were neither downloaded nor substituted in this test. The two kinds of recording are not assumed interchangeable.

The installed Bengali-compatible Chatterbox loader accepted all four generated WAVs through `audio_prompt_path`. All four actual inference runs used CUDA, the pinned BosonLab revision and the verified 2,530-token vocabulary. The same new Bengali text was synthesized for each category:

> এই! তোরা কিছু শুনলি? চল, আমরা একসঙ্গে ভালো করে দেখি।

| Category/demo | New speech duration | Conditioning applied | Technical execution |
|---|---:|---|---|
| Male / 007 | 4.12 s | Yes | Passed |
| Female / 006 | 3.88 s | Yes | Passed |
| Child Male / 002 | 4.36 s | Yes | Passed |
| Child Female / 005 | 3.88 s | Yes | Passed |

Peak allocated GPU memory was approximately 3,315 MiB (3.24 GiB). Category speech was reused for the other characters in that category; ten character comparisons were saved. Stable conservative presets and the supported Rubber Band formant-preserving mode were applied. Final processed WAVs retained the exact original sample count. Rhubarb cues were generated from those processed WAVs.

Some model float samples exceeded nominal full scale. The untouched model waveform is preserved separately as FLOAT WAV. A constant headroom gain is applied to the PCM conversion before character variation; no pitch or speed change is used for this level adjustment. The resulting PCM comparisons have no clipped samples. This is not denoising or a claim of perceptually perfect speech.

Files are in `evaluation/selected-demo-conditioning/`: each character has a processed WAV, a before-variation PCM WAV, an unmodified model FLOAT WAV, cue data and a detailed provenance/runtime report. `output/selected-demo-audio-comparisons.zip` packages the comparisons. `workspace/selected-demo-verification.json` records the audit.

## Listen in the application

Settings → Default Cartoon Voices shows the selected IDs and **Evaluation only** mode. Its optional Preview Character Voices section contains **Selected demo conditioning comparisons** with before/after players for all ten characters and a comparison download link. No individual reference upload is required.

The normal one-prompt browser workflow generated a real MP4 from Nabil, Rayan, Fahim and Anika using these selected conditioned voices. It reused the tested speech, generated final-waveform lip-sync and rendered through Godot/NVENC/FFmpeg. The result is `output/selected-demo-evaluation.mp4`. Downloads are labeled evaluation and the MP4 contains an evaluation-only permissions comment. The browser played the result and verified the download bytes.

A Windows progress-file replacement lock interrupted the first render. The atomic writer now uses unique temporary files and bounded retries; the unfinished render resumed with one completed scene reused and one rendered. Audio was not regenerated.

## What is not established

Successful conditioning execution, waveform checks and a valid MP4 do **not** establish natural Bangladeshi pronunciation, original-speaker similarity, perceptual clarity or commercial voice-use permission. Human listening review remains pending. No Original reference recording or demo voice has been marked commercially cleared, and a model-card software license is not treated as a speaker-consent grant.

Production mode rejects these evaluation-only records. To replace them, upload or select a licensed reference for each category, choose Production and Save Four Voices. Mappings and character variations remain; affected speech caches invalidate by reference hash. Historical official sample IDs remain recorded under `official_evaluation_selections`.
