# Critical quality repair - 2026-11-18

User-approved original-spelling, neutral Chatterbox speech was used for an 18.733-second Godot benchmark. Source originals, processed speech, mixed excerpts and alternative VITS samples were exported. Unicode input preservation, a neutral DSP policy and explicit speech review now precede normal Chatterbox rendering. The full regression run passed 176 tests, followed by targeted checks. See [quality findings and measured limitations](docs/QUALITY_REPAIR.md).

# v10 cleanup and real-media acceptance ? 2026-11-18

170 full-suite tests passed; 21 final voice/safety regressions passed. The real mini-cartoon is 132.933 seconds, 1280?720, with 12 scene chunks and validated playback/download. All 448 baseline asset files and 10 existing MP4s retain their hashes. Human listening and commercial demo-voice permissions remain unverified. See [v10 details](docs/V10_VERIFICATION.md).

# Selected official demo conditioning - 2026-11-18

- Exact persistent evaluation selections: Male 007 / Female 006 / Child Male 002 / Child Female 005. Approved/commercial flags remain false; original recording URLs are provenance-only, not conditioning inputs.
- Actual CUDA conditioning succeeded for all four generated output WAVs with vocabulary 2,530 and audio_prompt_path applied. New category durations: 4.12 / 3.88 / 4.36 / 3.88 seconds. Ten before/after character pairs were saved with final-waveform Rhubarb cues; six additional character takes reused the four category originals.
- Model FLOAT output is preserved unmodified. PCM headroom prevents the observed raw over-range peaks from clipping; final PCM has zero clipped samples and exact duration preservation. Evidence: evaluation/selected-demo-conditioning/results.json, workspace/selected-demo-verification.json.
- A normal one-prompt browser run generated and played output/selected-demo-evaluation.mp4, verified its evaluation download filename and downloaded-byte hash, and checked that no voice setup questions appeared. The completed render reused all approved speech and one finished scene after a Windows progress-file lock interruption. Unique atomic temporaries and bounded sharing-violation retries fixed the progress save.
- Full regression suite: 165 passed in 384.38s (workspace/selected-demo-full-tests.txt); focused permission/mapping/replacement checks and the atomic-write retry test passed (workspace/selected-demo-final-focused.txt).
- Production rejects the selected demos; licensed replacements retain mappings/presets. Human pronunciation, naturalness, similarity and commercial-permission verification remain pending. No subjective listening success is claimed.

- Final focused regression check: 15 passed in 74.09s (workspace/selected-demo-final-regressions.txt), including clearing obsolete category prompts without automatically starting old stories.

- After the final EXE restart, a live browser test confirmed the same four IDs and evaluation mode, played actual before/after conditioned speech for all four categories, downloaded the comparison ZIP, and found no JavaScript errors (workspace/selected-demo-live-auditions.json). These are playback/decodability checks, not human pronunciation approval.

Earlier verification history follows.

# v9 verification - 2026-11-18

- Final full suite: 160 passed in 262.30s (workspace/v9-final-tests.txt). Final focused category/reference/DSP/safety tests: 14 passed in 22.58s (workspace/v9-final-focused-tests.txt). Synthetic fixtures and labeled speech doubles are not evidence of pronunciation quality.
- The four-reference config and all presets were loaded identically in a fresh Python process. Migration backed up previous settings, retained source WAVs and refused automatic assignment for conflicting Child Male candidates. Missing setup was grouped by category; a configured Nabil/Rayan/Anika story queued without per-character questions.
- Real FFmpeg Rubber Band processing was tested, including exact frame-count preservation. Original TTS cache reuse and separate character-transform cache keys were tested. Changing a variation reused the original TTS take. The production take test verified that Rhubarb read the processed audio hash, not the original.
- Isolated real browser test passed: exactly four voice selectors, no per-character recording controls, upload/recording playback, processed preview playback, original comparison, persisted selections after reload and no JavaScript errors. Preview speech used a labeled synthetic test tone; the user production library was not modified (workspace/v9-browser-smoke.json).
- Actual prior Chatterbox speech was transformed for Nabil, Rayan, Fahim and Anika and rendered through real Rhubarb/Godot/NVENC/FFmpeg (output/v9-dsp-evaluation.mp4). Full decode passed: 19.3s, 1280x720, 30 FPS, 579 frames, zero AV duration difference, zero final PCM clipped samples. All four active mouths were checked; original audio hashes remained unchanged. All four DSP outputs retained exact input sample counts. Evidence: workspace/v9-media-audit.json, evaluation/v9-dsp-benchmark/manifest.json.
- This movie is explicitly an unconditioned DSP-only evaluation, not a configured four-reference voice benchmark. Authorized base selections and human Bengali naturalness/accent/clarity/consistency listening review remain pending. No cleared production reference IDs were fabricated.
- HF CLI confirmed the pinned BosonLab revision (workspace/v9-hf-model-info.json). The installed FFmpeg exposes Rubber Band formant/quality settings and reports GPL v3-or-later (workspace/v9-ffmpeg-license.txt). No proprietary redistribution clearance is asserted.

- Final visible-console EXE restart serves 9.0.0-preview. A read-only live browser check confirmed exactly four selectors and played both actual processed and original Chatterbox-derived DSP experiments through the web interface, with no JavaScript errors and no reference changes (workspace/v9-live-smoke.json).

Earlier verification history follows.

# v7 verification - 2026-11-18

- Initial full suite: 147 passed in 242.55s (workspace/v7-full-tests.txt). Further targeted tests cover continuous-walk boundaries, undeclared but referenced listeners and distinguishing another character's emotion.
- Real end-to-end unconditioned Chatterbox/Rhubarb/Godot/NVENC videos were generated in 1280x720 and 720x1280, 30 FPS, 24.933333s (748 frames). Five real dialogue clips, three active child speakers. Evidence: workspace/v7-chatterbox-evaluation/acceptance.json.
- Both exports fully decoded. Zero AV duration difference, zero black intervals, zero final clipped PCM samples, and source WAV hashes unchanged. Actual foot-lock drift remained under 0.00013px. Five subtitle cues per movie follow exact WAV durations; trace checks verify disappearance after speech. Positions are continuous across event boundaries. Fear, embarrassment and relief transitions were checked against actual direction/pose traces. Both music moods and footsteps are present. Evidence: workspace/v7-media-audit.json.
- Landscape and vertical subtitle frames were visually inspected: shaped Bengali, readable centered white text, dark outline, no large box or name card (workspace/v7-landscape-subtitle.png, workspace/v7-vertical-subtitle.png).
- These are evaluated cutout prototypes, not proof of perfect story understanding, distinct voices, reference-conditioned consistency or exact Bengali pronunciation. All production reference profiles remain unconfigured. Listening review and approved recordings are pending. No demo voice was authorized or reused as a production reference.

- Final full regression run: 150 passed in 273.40s (workspace/v7-final-tests.txt). After the final narration-camera/cache fix, all 14 focused v7 tests passed in 10.17s (workspace/v7-final-focused-tests.txt).
- Separate real two-line narration export: output/v7-two-line-subtitle-evaluation.mp4, 5.8s, 720x1280, uses the actual earlier Chatterbox sample 003 and off-screen narration. Its exact 4.28s WAV determines the two-line cue. The exported conjunct-rich Bengali frame was visually inspected after the wide narration-camera correction (workspace/v7-two-line-subtitles.png).

- Live EXE serves FastAPI 7.0.0-preview. Real browser checks passed: minimal UI, no unnecessary script questions, only the three missing authorized-reference requirements. Both actual v7 MP4s played in Chromium at the expected resolutions; downloaded bytes matched their local hashes; no JavaScript errors (workspace/v7-browser-smoke.json). User preferences were preserved.
- A repeat of the two-line sample reused the completed scene (1 reused, 0 rendered) with identical source audio; cache evidence is in workspace/v7-cache-check.txt.

Earlier verification history follows.

# v6 verification — 2026-11-18

- Full suite: 135 passed in 281.67 seconds (workspace/v6-final-tests.txt). After the essential-action guard was added, all nine v6 semantics/safety tests passed (workspace/v6-safety-final.txt).
- Real browser: seven local benchmark choices, actual sample-003 playback, Local Rules by default, AI disabled without configuration, no JavaScript errors (workspace/v6-browser-smoke.json).
- Real Chatterbox CUDA inference: all three supplied Bengali benchmark sentences generated 24 kHz PCM16 WAVs; peak allocated GPU memory 3,326.56 MiB, zero clipped float samples. Detailed timing/hash-independent audio metrics: evaluation/chatterbox-local/results.json. No pronunciation or distinct-character consistency clearance is claimed from waveform checks.
- Official checkpoint SHA256 verification completed for T3 and S3Gen. Runtime Torch/torchaudio 2.8.0+cu126, vocabulary 2,530. An initial float WAV compatibility failure was corrected by writing explicit PCM16; only the retry results count as valid pipeline audio.
- Live production plan: exactly five speech lines and one scene; only three authorized-reference requirements remain, for Nabil/Rayan/Anika (workspace/v6-live-plan.json). No screenplay metadata/instruction clarifications.
- Production reference conditioning and distinct voice consistency await authorized recordings. Demo Original recording provenance/commercial cloning permission remains unverified.

- Real v6 regression MP4: 26.9s, 1280x720, 30 FPS, H.264 NVENC/AAC. Three render chunks, five actual Chatterbox dialogue clips, all Rhubarb. Fully decoded; 807 frames, zero AV duration difference, zero black intervals, zero clipped PCM samples. Pose traces confirm all three active speakers and closed listeners. Both music moods and 3.8s Bengali screen text checked; the extracted frame was visually inspected. Evidence: workspace/v6-media-audit.json, workspace/v6-screen-text.png, output/v6-chatterbox-evaluation.mp4. This is an unconditioned evaluation, not a distinct-voice production result.
- Final focused checks: 11 passed in 50.38s, including the newer essential-action guard, missing-reference protection and a mocked CUDA-to-CPU control-flow check (workspace/v6-last-focused-tests.txt).

- Real CPU-only Chatterbox sample: 3.44 seconds of valid PCM16 Bengali speech, 92.47 seconds including model load, zero clipped samples (evaluation/chatterbox-local/cpu/results.json). CUDA fallback control flow was tested separately with an injected failure; no real CUDA OOM was observed or claimed.

- The EXE was gracefully stopped through its own stop mechanism after confirming no active jobs, restarted, and the live OpenAPI version verified as 6.0.0-preview. The real browser checks passed again on the restarted app.

Earlier verification history follows.

# Bangla Toon Studio — verification history

## v4: automatic story-to-cartoon workflow — November 17, 2026

The default page is now **paste story → Generate Cartoon → preview/download**. Cast, backgrounds, actions, saved voice identities, lip-sync, camera and sound are planned automatically. Scene editing, individual take approval, four-category Voice Studio and Sound Studio remain available inside a collapsed optional panel. The normal local workflow does not require opening these controls or approving each speech line. Missing/ambiguous information still prompts a specific correction; arbitrary prose comprehension is not claimed. No LLM or video diffusion model was introduced.

Added quoted Bengali dialogue recognition, source-preserving prose splitting, music/silence metadata, target-aware action detection, automatic speaker/listener framing, movement profiles, a travel-driven four-phase gait and a dedicated SoundDirector. Final gait refinement avoids excessive crouching and uses bounded subpixel reach compensation to keep feet grounded during hip motion. Original character art, IDs and appearance hashes remain unchanged; all earlier reference-only characters remain reference-only.

The four primary Voice Studio categories are **Male, Female, Child Male, Child Female**. Real catalogs, metadata, available public previews, Bengali auditions, multiple category presets and permanent character assignments are supported. Narrator remains optional. Configurations are schema-validated and persisted. A youthful label is not treated as a verified child voice; saving such an alternative requires explicit selection. The actual installed offline model still has **one shared VITS voice**. No distinct child/adult cloud voice was generated or listened to in this environment because neither provider's credentials were configured.

ElevenLabs request schema/model/output-tier documentation and Azure's bn-BD voice list were checked against official sources. The existing REST adapter does not require an installed provider SDK. Bengali language control, documented tags/context, configurable account-supported output formats and original provider audio preservation are implemented. Cloud transport/approval tests remain mocked. Original bytes and lossless working WAVs are retained; no paid retry or lower-quality provider fallback is automatic.

Automatic production uses the existing single heavy executor and persistent sessions. Exact batch approval is required before uncached paid speech. Request IDs are idempotent. Approved line-level WAV/cue caches also work for partially completed sessions, and cached cloud audio can be rendered without credentials or a new charge. Changing music, volumes, visual actions or camera does not regenerate matching approved speech. The cloud cache, partial-cache accounting, stale approval and failed-take cases have automated tests; this is not a claim of real paid account billing verification.

### Actual media

| Test | Final output | Duration / frames | Format |
| --- | --- | --- | --- |
| Nabil / Rayan / Anika orchard benchmark | `output/v4-benchmark.mp4` | 30.3333s / 910 | 720 × 1280, 30 FPS |
| Complete three-location mini cartoon | `output/v4-mini-cartoon.mp4` | 153.2333s / 4,597 | 1280 × 720, 30 FPS |
| Original music-off remix | `output/v4-remix.mp4` | 29.8333s before the closing-hold refinement | 720 × 1280, 30 FPS |
| Controlled walking comparison | `output/v4-walk-comparison.mp4` | Same approved speech and frame clock in both versions | Old versus revised movement |

The Short's final job is `b43d67025125446cbdf2167a92d28152`; the mini cartoon is `a38ceae456084d728343a895e267062e`. Real local CUDA VITS synthesized the dialogue. Real Rhubarb produced cues, Godot rendered the frames and FFmpeg/NVENC produced H.264/AAC MP4s. The mini cartoon generated **25 actual speech clips** and used courtyard, orchard and school backgrounds. Its render/assembly phase took **192.5145s**, measured render process-tree peak RSS **839.3 MB**; this excludes the separate automatic speech-preparation phase. The final Short reused three exact approved speech files. No cloud voice call was made.

`scripts/audit_v4_media.py` decoded both full MP4s. Frame counts and master PCM sample counts match exactly. A/V duration difference was **0.0s** for the Short and **0.000651s** for the mini cartoon. There were no detected black intervals and zero clipped PCM samples (peaks **29,795** and **30,077**). Pose traces verified closed listener mouths and active speaking mouths for all three children. The final benchmark's sampled stance drift was **0.000023 pixels horizontally** and **0.000122 pixels vertically**. Its two footsteps matched the same travel/stride contact clock as the rig. These numerical checks do not certify how natural an animation looks.

The sound library contains **17 original registered WAV assets**, including eight mood themes and two additional environment beds. The benchmark uses mystery music, birds/wind, leaf rustling and action contacts. The mini cartoon demonstrates distinct happy/calm scene themes. Music and ambience fade at scene boundaries/end, with 150ms music duck attack and 500ms restoration. Independent six-track levels and envelope continuity have tests. These are simple original synthetic sounds, not a professionally recorded orchestra or field ambience library.

`tests/v4_browser_smoke.py` passed using the actual webpage and real media: default studio collapsed, one-click generation with no manual voice steps, automatic cast/background resolution, voice category tabs, audio/video playback, MP4 download/hash validation, mobile layout, and necessary-only prompts for unknown assets. A music-off remix reused all three original speech hashes. `tests/v4_final_ui_smoke.py` additionally passed desktop/mobile restoration of the final completed automatic job after reload and confirmed a cached, zero-paid-usage plan. No JavaScript errors were observed.

Final full automated suite: **119 passed**, one upstream Starlette/httpx deprecation warning, **197.19s**. Additional real export, post-refinement foot-lock audit and final browser restoration checks passed. `pip check` and JavaScript syntax checks passed. Evidence is saved in `workspace/v4-final-tests.txt`, `workspace/v4-browser-acceptance.json`, `workspace/v4-final-ui-acceptance.json`, `workspace/v4-samples-acceptance.json`, `workspace/v4-media-audit.json`, `workspace/v4-comparison.json`, the jobs' cues/direction/pose traces, and final desktop/mobile screenshots.

**Remaining acceptance limits:** this does not satisfy every professional-quality condition in the v4 brief. Distinct natural adult/child voices, regional accent, youthful suitability and live cloud behavior remain unverified without accessible licensed voices and listening. The six existing front rigs remain cutout prototypes; true side/back artwork, alternate hands, fully authored seated views and four adult rigs are incomplete. Over-shoulder shots requiring those views remain blocked. No generic adult/child replacement, extreme pitch shifting, real-child recording download, or broadcast-quality claim was used. The original thin executable starts the updated external app and keeps its visible console/process-tree behavior.

The sections below preserve earlier milestones.

## Screenplay parser and strict speech filtering — November 17, 2026

Removed the original narration-first fallback. Unlabelled paragraphs previously became narrator segments and entered the speech loop. The new Pydantic event interpreter preserves source text and line numbers, classifies instructions separately, and creates speech only from labelled dialogue or explicit narration. Unknown instructions block production. Backend guards apply before take estimation/queueing, inside the synthesis worker, during approved-audio reuse, and in the normal speech job loop. Old sessions missing explicit speech authorization cannot generate new takes.

The editable browser review includes per-event classification, actors/actions, emotion, background, camera and SFX controls; exact spoken-text preview; project correction persistence; and source-bound correction validation. The new timeline retains separate speech, visual and effects tracks on a shared frame clock. Event scene ranges replace the older speech-only ranges. Existing source art, voice assignments, original WAV approval, Rhubarb, Godot, NVENC/CPU fallback and console lifecycle remain in place.

`tests/screenplay_browser_smoke.py` **executed successfully with real local CUDA VITS, real Rhubarb and real Godot**. It exercised ambiguous-line rejection, an Ignore correction saved through reload, exactly two speech previews, audio playback/approval, video playback/download, responsive layout, and unchanged registered Nabil/Rayan asset hashes. No cloud request was made. Real inputs were exactly `কে ওখানে?` and `আমি কিছু দেখতে পাচ্ছি না!`; WAV durations were **1.6145s** and **2.4969s**. Labels, fear tags, descriptions, actions and camera directions were absent from synthesis inputs.

| Real test | Output | Duration / frames | Speech requests |
| --- | --- | --- | --- |
| Critical Nabil/Rayan screenplay | `output/screenplay-dialogue.mp4` | 9.5333s / 286 | Exactly 2 |
| Instructions + walking + rustling leaves | `output/screenplay-silent.mp4` | 4.3s / 129 | Zero |

Both are **720 × 1280, 30 FPS, H.264/AAC**. `scripts/audit_screenplay_media.py` decoded both entire files, verified exact master PCM sample counts and video frames, found **0.0s A/V duration difference**, no black intervals, and zero clipped PCM samples. Real Godot pose traces confirmed only the active speaker used non-X mouths and the silent scene used only X. Nabil/Rayan speech samples are retained as `output/screenplay-nabil.wav` and `output/screenplay-rayan.wav`. Machine verification establishes exact input text, successful synthesis and cue ownership; it does not certify pronunciation quality through human listening.

Evidence: `workspace/screenplay-browser-acceptance.json`, `workspace/screenplay-media-audit.json`, `workspace/screenplay-dialogue-video.png`, `workspace/screenplay-studio.png`, `workspace/screenplay-mobile.png`, and the jobs' original source/event/timeline/direction/cue/pose artifacts. Reproduction samples are under `samples/screenplay_*_bn.txt`. The longer sample scripts now explicitly label their intended narrator speech and preserve their original 5/25 speech segments.

Final full automated suite: **111 passed**, one upstream Starlette/httpx deprecation warning, **133.21s**. JavaScript syntax checks and `pip check` also passed. Coverage includes explicit narration, mixed aliases, delivery tags, source preservation, metadata, multiple scenes, concurrent action timing, unknown assets/actions/camera views, stale-session speech blocking and recording-provider input checks.

The interpreter remains conservative and LLM-free. Unsupported physical actions and unavailable camera views require correction, and broader Godot poses retain the previously documented artwork/prototype limitations. Live ElevenLabs/Azure integration remains untested without credentials. Older milestone exports and test counts below are historical.

## v3 preview: articulated Godot production — November 17, 2026

The installed application now runs a Godot-based front-cutout production path while preserving the legacy Pillow renderer and all source artwork. This is **not** a claim of television-level acting or natural multi-voice speech. The two cloud providers were not called because no credentials were configured, and several required artwork views remain missing.

### Actual exported evidence

| Artifact | Measured result |
| --- | --- |
| `output/godot-benchmark.mp4` | 30.1s, 1280×720, 30 FPS: Nabil walks, stops, front head tilt/gaze, surprise, speaking/arm gesture; Rayan listens/reacts/speaks. |
| `output/godot-comparison.mp4` | Matched-timeline side-by-side of the previous Pillow implementation and articulated Godot prototype, using the same real Bengali speech. |
| `output/8689cbc236e9424bbdec4f60ed3e38eb.mp4` | Final Short: **33.5667s**, **720×1280**, **30 FPS**, approved real VITS speech, Godot and NVENC. |
| `output/d003c9aa9c064a618c4b7804c4b0e5e3.mp4` | Final episode: **156.4s (2:36.4)**, **1280×720**, **30 FPS**, three locations, approved real VITS/Rhubarb, original ambience/Foley, Godot and NVENC. |
| `output/voice-benchmark/vits.wav` | Real local speech plus an identical comparison script/status file. No fake ElevenLabs/Azure audio files were created. |

Godot **4.7.2 stable** was installed from the official Windows release and verified with its SHA-512 manifest. Its actual Movie Maker output was MJPEG AVI; FFmpeg produced the H.264/yuv420p MP4s. Godot ran through OpenGL Compatibility on the RTX 3050. The original rigs' face, hair, clothing and source sprite hashes remained unchanged. The new pieces are rigid cutouts attached to **16 Bone2D nodes**, including separate upper/lower limbs, hands and feet, with separately controlled brows, pupils and mouth shapes. AnimationPlayer/AnimationTree state machines, TimeSeek, procedural foot-target IK and a deterministic camera share the audio frame clock.

`scripts/verify_godot_motion.py` **passed** on the actual exported pose traces. Knee/elbow angles varied independently; listener mouths stayed `X` during the other speaker's speech. Sampled planted-foot horizontal and vertical drift were about **0.000061px**, and independently starting a chunk at the same mid-dialogue timestamps produced **0.0 sampled pose difference**. These checks establish articulation/contact and deterministic seeking, not human judgments of naturalness. The evidence sheet `workspace/godot-benchmark/review-sheet.png` was visually inspected for contact/swing, stop, expression, gesture and listener frames. True profile head turns were not claimed.

### Real workflow and interruption checks

`tests/v3_browser_smoke.py` **passed** in Chromium with real speech and actual UI operations. It generated/played speech previews, edited one pronunciation while retaining the original caption, regenerated only that line, preserved other takes, approved audio through the UI and exported both a Short and full episode. Playback, seeking into all source locations, byte-identical downloads, responsive mobile layout and zero JavaScript errors passed. Its initial export IDs were `d444b337161342c6bcfcc1a1a34f7088` and `6488e0ed86624b66bce3051b333e3124`; final current-clock exports are listed above.

`tests/v3_resume_smoke.py` **passed** after closing the actual visible console with X during the second Godot scene. Both active Godot processes (PIDs 16236 and 6212) and the server stopped. After a real EXE restart, the episode resumed with the first completed scene byte-identical and all approved source audio unchanged. Final scene cache reuse was recorded; no speech provider was called during resume. It also generated the fresh final Short. The resumed episode attempt took **167.235s**, with a measured server/child-process peak RSS of **696.9 MB**; the subsequent cached-speech Short took **42.783s**, peak **698.6 MB**. These measurements cover rendering with already approved audio, not the earlier speech-preview phase. Actual local preview metrics recorded CUDA VITS and approximately **467.5 MB peak CUDA allocation**. NVENC encoded video; it did not perform the skeletal animation.

`tests/v3_editor_smoke.py` **passed** on the final interface: saved acting-character selection, rendered an actual waveform, saved mouth cues, required reapproval and exported a validated one-line Godot preview (`336048ec249141caa774d07d26008118`). No JavaScript errors or mobile overflow occurred.

`scripts/audit_v3_media.py` **passed** on both final exports. The episode contained **4,692 frames**, the Short **1,007**, exactly matching their 30-FPS timelines. Audio/video duration difference was **0.000651s** for the episode and **0.0s** for the Short. No black intervals of 0.05s or more were detected. Master PCM peaks were **30,039** and **29,724** respectively, with **zero full-scale clipped samples**; master WAV sample counts were exactly frame count × 1,600. FFmpeg decoded both complete MP4s without integrity errors. This does not certify accent or intelligibility through human listening.

### Automated verification and honest limits

Final full suite: **101 passed**, one upstream Starlette/httpx deprecation warning, **129.98s**. Additional focused production/director checks passed, including an actual short-animation preview and ensuring a Godot script failure is not mislabeled/retried as an NVENC failure. A further real Godot integration passed with **music enabled**, confirming the original music event and sample-aligned FFmpeg mix. JavaScript syntax checks and `pip check` passed. Cloud request shape, XML escaping, voice identity persistence, paid approval binding, no-silent-fallback behavior, pronunciation, cue edits, waveforms, approved media freezing and incomplete-rig rejection have automated coverage. Cloud transport tests use mocks; they are not successful live provider requests.

Remaining work is explicit:

- **ElevenLabs/Azure:** adapters and real-account voice discovery are implemented, but live generation, billing behavior, voice suitability, regional accent and expressive delivery require credentials, explicit paid approval and listening tests. The actual tested offline path still has **one VITS voice**. Distinct natural voices were not demonstrated or imitated with pitch changes.
- **Artwork:** Arif, Sami, Mehna and Tithi remain reference-only. No generic adults were substituted. All six existing front rigs have derived cutout prototypes, but true profile/back turnarounds, alternate hand silhouettes and fully authored seated views need artist-supplied layers. [The rigging specification](assets/characters/RIG_LAYER_SPEC.md) identifies the missing work. The Nabil/Rayan benchmark and Nabil/Rayan/Anika episodes do not automatically certify every other character/action combination.
- **Acting:** front walking/contact, stop, head tilt/gaze, talking gesture, brows/blink, mouth blends and listener behavior were demonstrated. Run, seated poses, folding/scratching/chin gestures and other exposed pose controls remain prototypes, not a complete visually accepted animation library. True over-the-shoulder shots are rejected until the necessary art exists. No universal story comprehension or television quality is claimed.
- **Environment:** preserved source backgrounds, available foregrounds, contact shadows, restrained camera framing and location dissolves are supported. The original procedural sounds/four-note bed are simple local assets, not a professionally recorded score or a full library of every requested environmental effect.

Reproduction/evidence: `workspace/v3-browser-acceptance.json`, `workspace/v3-resume-acceptance.json`, `workspace/v3-editor-acceptance.json`, `workspace/v3-media-audit.json`, `workspace/godot-benchmark/motion-acceptance.json`, per-scene Godot logs/pose traces, audio cache hashes and desktop/mobile screenshots. Keys remain in environment variables; no paid call was made during implementation. The existing thin EXE starts the updated external source and still owns the visible console/process tree.

The sections below retain earlier milestone results.

## Shorts and 2–3 minute Mini Cartoons — November 17, 2026

**A complete real Bengali mini-cartoon passed acceptance:** `output/57058130e6d047c2bd08f44b30dfa9ff.mp4`, **156.375 seconds (2:36.375), 1280×720, 24 FPS, H.264/AAC**. Its complete script is `samples/mini_cartoon_bn.txt`. This is actual local VITS speech and sprite animation, not test tones or a simulated result. It uses Nabil, Rayan and Anika across the village courtyard, mango orchard and school courtyard, partitioned into **14 render scenes** of at most 12 seconds.

`tests/mini_browser_smoke.py` passed using the real webpage. It checked the duration/format selectors, automatic recognition, scene progress, playback, seeking into all three source locations, download byte identity, responsive mobile layout and zero JavaScript errors. It deliberately cancelled after the first completed scene and resumed through the UI. The first scene MP4 remained byte-identical; all source WAV bytes **and modification times** stayed unchanged. The final report recorded **1 scene reused, 13 rendered**. All three speakers used actual Rhubarb cue lists with speaking mouth shapes that exist in their permanent rigs, and their source sprite hashes stayed unchanged.

FFprobe reported **3,753 video frames**, matching the exact timeline, and both streams start at **0.000000 seconds**. Video duration was 156.374349s and audio 156.375000s, a difference under one millisecond. The normal completion check decoded the entire MP4 through FFmpeg with error checking. The final download SHA-256 is `cbb2330749be125879b7c1faa28b3c9c26fbf1c25f42919b01bbc808ae3463bf`.

On this Windows machine (RTX 3050 Laptop 4 GB / approximately 8 GB RAM), the cancelled attempt took **34.5919s**, and the resumed attempt **205.1385s**: **239.7304s total recorded processing** including the intentional interruption. The resumed attempt's measured server/child-process peak RSS was **1,858.8 MB**; the VITS worker reported **493 MB peak CUDA allocation**. Encoding used **h264_nvenc**; Pillow compositing remained on CPU. These are measurements from this run, not guaranteed processing times on other hardware.

Evidence: `workspace/mini-cartoon-acceptance.json`, `workspace/57058130e6d047c2bd08f44b30dfa9ff/{job,timeline,scenes,report}.json`, `workspace/mini-<background_id>.png`, and desktop/mobile studio screenshots. The earlier longer draft produced an actual 229-second timeline and was cancelled; complete passages were removed before the successful 2:36 run. No speech was sped up or truncated to force the target.

The final automated suite passed **93 tests in 107.04s**, with one upstream Starlette/httpx deprecation warning. Dependency checks found no broken requirements and JavaScript syntax validation passed. Mini-cartoon integration tests execute real FFmpeg output for both landscape and optional vertical formats, injected scene failure/resume, corrupted-cache regeneration, sample-exact scene audio reassembly and CPU encoding. A separate test injected an NVENC failure in the middle scene and successfully validated concatenation of **NVENC → libx264 → NVENC** scenes. Their speech is deliberately mocked; only the browser acceptance above verifies the installed VITS/Rhubarb pipeline with the full-length story.

Limits: the duration selector sets a target and format, not an automatic story writer. Actual speech lengths can put a different story outside the target, and the UI reports a warning. Existing flattened backgrounds are cropped to the selected aspect ratio. Scene video, PCM and audio checkpoints intentionally consume disk space for resume. This is not a distributed render farm or a guarantee that every arbitrary long script/asset combination has been tested. No LLM or cloud generation service was added.

## Asset recognition and review upgrade — November 17, 2026

The final automated suite passed **88 tests** in **71.32 seconds**, with one upstream Starlette/httpx deprecation warning. `pip check` found no broken requirements and the frontend passed `node --check`. Coverage includes discovery, readiness, real thumbnails, Bengali aliases and suffixes, ambiguous names/locations, unknown-speaker resolution, voice roles, manual scene partitions, project isolation, atomic remembered mappings, conflicts, malformed mappings, preflight/tool errors, added-folder refresh, metadata/queued-asset changes, immutable job snapshots and real MP4 encoding with approved choices. Speech is mocked in automated tests; the separate acceptance runs below use the actual installed model.

Discovery found **10 character folders: 6 ready rigs and 4 reference-only designs**, plus **10 usable backgrounds**. The four reference-only adults remain unavailable for production rendering. Existing IDs and artwork are preserved. No new artwork or model is generated by the review workflow.

`tests/review_browser_smoke.py` passed in real Chromium with actual CUDA VITS, Rhubarb and NVENC. It verified automatic Nabil/Rayan/orchard recognition, actual library thumbnails, unknown boy → explicitly chosen Fahim, unknown castle → manually chosen village courtyard, a second manually added orchard scene, exact approved mappings in the generated timeline, video playback, byte-identical downloads, mobile layout and zero JavaScript errors. Two separate Nabil exports used identical character ID, version and complete sprite hashes. The initial successful exports were `ef7a700ea6874dc2b9f26751cb535db6` (13.375s) and `74fc4d94719d4a7bb9817f35b00cfe00` (14.4167s); the repeatable script writes current results to `workspace/review-browser-acceptance.json` and screenshots to `workspace/review-browser-*.png`.

`tests/mapping_restart_smoke.py` passed: character and background aliases saved through the UI survived a new project, browser reload and actual EXE/server restart (PID 8008 → 11768). The test restored the original user mapping file afterward. Evidence: `workspace/mapping-restart-acceptance.json`.

`scripts/verify_children.py` passed again with the supplied Nabil/Rayan/Anika dialogue and an explicitly selected station stage. Job `637fc5437210407f8e43ac3376b19e9e` produced a validated **14.5s** MP4 in **37.6838s**, using CUDA, actual Rhubarb cues and NVENC. All three speaking mouths mapped to the correct permanent sprites; all five child rigs remained valid. Evidence: `workspace/children-acceptance.json`.

The updated `tests/launcher_smoke.py` also passed again. It generated actual speech/video, checked live console logs and duplicate-launch reuse, closed the real console with its X event, closed another console during active FFmpeg rendering and verified server/encoder cleanup, and checked explicit shutdown. Its latest completed-generation job is `07828fed03c74bcd83f027ff68ef0534`. Evidence: `workspace/launcher-acceptance.json`. The existing console EXE loads the updated source from this project; a rebuild is unnecessary.

Limits: recognition uses local rules and supplied metadata, not general language understanding. Unknown dialogue labels are resolved visually; arbitrary unnamed people in narration are not inferred. Missing day/night variants require a manual choice. Selecting a different setting does not create new artwork. All roles still share the model's single Bengali voice. Preflight checks dependency presence without loading the large model; actual inference errors remain visible job failures. Legacy audio/render compatibility routes retain their original station planner; the reviewed generation workflow supports the complete discovered library and multiple backgrounds. Windows hardware fallback behavior retains its prior implementation; every new asset combination has not been rendered exhaustively.

The earlier sections below record the previous milestones.

## Five-child registration and real animation update

All five supplied children are now validated permanent rigs: **নাবিল/nabil, রায়ান/rayan, ফাহিম/fahim, অনিকা/anika and মালিহা/maliha**, each at rig version **1.1.0**. Every child has 28 locked PNG/animation files, including distinct body/head/hair art, back hair, open/closed eyes, separate limbs, A–H/X mouth shapes and all supported animation definitions. Source sheets and original metadata are preserved. Unicode NFC/NFD, zero-width copy/paste marks, case and whitespace normalization are tested. Aliases are published only after validation and require a complete rig at lookup.

Final automated result after this update: **63 passed**, one upstream deprecation warning, in **26.46 seconds**. Dependency checks report no broken requirements. Tests include exact supplied Bengali dialogue, both language aliases for all five children, unique persistent identities, missing-rig rejection, all mouth labels, blinking/walking, three/five-child framing, and pixel differences showing only the speaking child's mouth changes.

Real acceptance used the exact three-line Nabil/Rayan/Anika dialogue through `/api/generate`, with **actual CUDA VITS, Rhubarb and NVENC**. Job `f9f0a82ff1ca4761895fdd043de62344` completed in **59.7411 seconds**, producing a **14.625-second 720×1280/24 FPS H.264/AAC MP4**. ffprobe checks and full FFmpeg decode passed. All three actual Rhubarb cue lists contained speaking shapes and matched the correct child's locked mouth sprites. Rig identities were unchanged before and after rendering. No amplitude fallback was used in this acceptance run.

The supplied station painting had replaced the earlier runtime metadata. Its pixels were preserved; its source metadata was saved, the painting was hash-locked as a flat stage, and unrelated legacy foreground layers are excluded. Other background-pack locations have not been integrated by this child-registration change.

Artifacts: `output/f9f0a82ff1ca4761895fdd043de62344.mp4`, `workspace/children-acceptance.json`, `workspace/children-rigs-preview.png`, and per-speaker previews at `workspace/children-speaking-<id>.png`. Reproduce with `python scripts/verify_children.py` while the studio is running. `tests/children_browser_smoke.py` also **passed**: actual video playback, seeking to each child's speaking cue, matching the downloaded MP4 SHA-256, mobile layout, and zero JavaScript errors. Its results are in `workspace/children-browser-acceptance.json`.

## Windows executable launcher

The executable has been rebuilt with **PyInstaller 6.22.3 in console mode**. It is **8,933,507 bytes** and uses the existing project runtime. It stays alive as the visible console owner, opens the browser after readiness checks, and prints live hardware/generation diagnostics. The server owns a Windows kill-on-exit process job, covering its FFmpeg and Rhubarb descendants, and monitors its console owner.

The updated `python tests/launcher_smoke.py` **passed** using real visible Windows consoles. It verified:

- Cold startup from a different working directory and a visible console window.
- Duplicate launches reuse the original console's single server.
- Real CUDA VITS/Rhubarb/NVENC generation, job `d705b45609414274af49e62c2d8f2121`, with actual speech and a validated MP4.
- Live logs containing queue/stage progress, clip duration/device, mouth-cue details, rendering, validation, completion and output/encoder details.
- Sending the actual console-window X/WM_CLOSE event stops the server and releases port 8000.
- Closing a second real console while FFmpeg was actively encoding stops both the server and the encoder process; neither remained orphaned.
- `--stop` gracefully shuts down the server and exits its owning console.

Results are in `workspace/launcher-acceptance.json`. The existing **63 automated tests also passed** after the logging/lifecycle changes, in 24.52 seconds, and `pip check` found no broken requirements. Keep the executable beside the project files and `.venv`; it is not a standalone distribution of all model/runtime files. Closing only the browser leaves the server available while its console is open. Ctrl+C is the clean-stop option; an X-interrupted generation can be retried after restart.

Verified on **17 November 2026**, directly on Windows 10 64-bit (build 19045), Python 3.11, NVIDIA RTX 3050 Laptop GPU with 4 GB VRAM, and **7.71 GB usable system RAM**. The NVIDIA driver reported 610.78. PyTorch and torchaudio are matching **2.8.0+cu126** builds; Coqui TTS is 0.28.0.

## Automated checks

The earlier Rahat-only baseline had **47 passing tests**. The final child update has **63 passing tests**, as recorded above. One upstream Starlette/httpx deprecation warning remains; there are no test failures.

Coverage includes Bengali paragraphs and Unicode, common dialogue formats, aliases, off-screen voices, unknown/reference-only speakers, missing/changed assets, versions, transparency, anchors, timelines, duration warnings, actual 48 kHz PCM placement against the frame clock, malformed Rhubarb output, amplitude fallback, CUDA initialization/inference recovery, silence rejection, the bounded single-worker queue, cancellation, interrupted-job recovery, retry, real MP4 generation/validation, download attachments, HTTP ranges, and cross-video sprite identity.

Tests using synthetic PCM or mocked failures are isolated tests. They are not counted as proof of real VITS inference. The NVENC-runtime failure test deliberately injects an encoder failure, then produces a real validated libx264 MP4. A separate probe and the browser runs below exercise real NVENC hardware.

`python -m pip check`: **No broken requirements found.** JavaScript syntax checking passed. No unimplemented rendering boundaries remain.

## Real browser acceptance

`tests/browser_smoke.py` passed with **two distinct jobs** using actual VITS speech, native CUDA inference, the permanent Rahat rig and real Rhubarb cues:

| Measurement | Sample station story | Second Rahat story |
| --- | --- | --- |
| Job ID | `c0138bbe5a784c3ca2bea46a8dd58155` | `1baee368cd0d489d989a65411750ae75` |
| Video duration | 17.1667 s | 10.5000 s |
| Total generation | 23.9317 s | 12.0050 s |
| Parsing/assets | 0.0289 s | 0.0278 s |
| Speech generation | 7.2105 s, including cold model initialization | 0.5268 s, shared model already loaded |
| Rhubarb processing | 0.8402 s | 0.7359 s |
| Audio preparation | 0.2454 s | 0.1023 s |
| CPU sprite composition | 14.6411 s | 9.8712 s |
| Stream wall time | 15.1666 s | 10.2406 s |
| Encoder drain after frames | 0.1324 s | 0.1525 s |
| Integrity validation | 0.3585 s | 0.3386 s |
| Sampled peak process-tree RSS | 2600.4 MB | 2480.2 MB |
| Shared worker peak CUDA allocation | 446.1 MB | 446.1 MB |
| TTS device / encoder | CUDA / h264_nvenc | CUDA / h264_nvenc |

Encoding runs concurrently with CPU composition. Stream time and encoder drain are measured; neither is represented as an isolated GPU-only encoding duration. RSS is sampled every 250 ms, so short transient peaks may be missed. These are observed runs, not guaranteed timings.

Both MP4s passed ffprobe checks for **H.264, AAC, 720×1280, 24 FPS, yuv420p, duration and audio presence**, followed by full FFmpeg decode validation. Both played and sought in Chromium and were downloaded through the actual Download MP4 button. The page restored its result after reload while preserving newer story edits. The 390px mobile layout had no horizontal overflow. Unsupported speakers produced visible errors. The final browser run recorded **zero JavaScript errors**.

Both videos reference the same Rahat ID, version `1.0.0`, full sprite hashes and identity fingerprint:

```text
3db393f27c6c914fb0b544894af406a073094e8e144b26879df4b7274b18ea42
```

`unknown_voice` is off-screen and is absent from visible-character lists. Only Rahat's dialogue drives his mouth. Audio offsets and subtitle intervals use the same frame clock. Actual PCM placement and silence between speech slots are additionally checked by an FFmpeg-backed automated test.

## CPU / CUDA comparison

Each benchmark loaded one engine in its own process and synthesized the same Bengali utterance three times. The warm mean uses the last two runs. **CPU mode was rechecked after the CUDA packages were installed.**

| Measurement | CPU using the CUDA-enabled installation | CUDA |
| --- | --- | --- |
| Cold load wall time | 10.4937 s | 15.9702 s |
| First synthesis | 1.0392 s | 5.6572 s |
| Warm mean synthesis | 0.7913 s | 0.2799 s |
| Resulting speech lengths | approximately 3.4–3.7 s | approximately 3.5–3.8 s |
| Sampled peak process-tree RSS | 1854.3 MB | 2320.8 MB |
| Worker peak CUDA allocation | not used | 391.8 MB |

VITS is stochastic, so generated waveform duration varies slightly. Cold timing includes runtime initialization and depends on OS/file caches. No real GPU OOM was intentionally induced; OOM/driver recovery is verified with controlled unit failures, while actual CPU inference and CUDA inference are verified separately.

## Reproducible artifacts

- `output/c0138bbe5a784c3ca2bea46a8dd58155.mp4`: complete sample cartoon with real speech.
- `output/1baee368cd0d489d989a65411750ae75.mp4`: second story proving asset reuse.
- `workspace/<job-id>/report.json`: full timing, device and asset report.
- `workspace/<job-id>/timeline.json`: shared-clock scene/audio/animation schedule.
- `workspace/<job-id>/cues/segment_002.json`: real Rhubarb cues for Rahat in the sample.
- `workspace/browser-acceptance.json`: browser test summary and distinct job IDs.
- `workspace/shorts-browser-1.png`, `shorts-browser-2.png`, `shorts-mobile.png`: screenshots.
- `workspace/benchmarks/cpu.json`, `cuda.json`: raw benchmark results.

Generated artifacts, binaries, weights and the virtual environment are intentionally excluded from Git. See README.md to reproduce them on another machine.

## Remaining limits

- Rahat and all five children have ready sprite rigs. The older Arif, Sami, Mehna and Tithi entries remain design references. Missing rigs and unsupported locations produce errors.
- Only the saved night railway station is implemented. Scene selection and action recognition are deliberately conservative, rule-based operations.
- The sample is shorter than 30 seconds. Limited atmosphere/reaction holds are used and a clear warning is shown; extend the story naturally for the 30–40-second target.
- One single-speaker VITS voice is reused for all roles. Real nonzero PCM/model inference was verified; subjective Bengali pronunciation and acting quality have not been independently rated by a Bengali listener.
- Rhubarb phonetic recognition does not guarantee accurate Bengali phonemes. Failures fall back to explicitly labeled approximate envelope cues.
- Captions use page-level timing within speech, not word-level forced alignment. There is no music/SFX library, arbitrary scene invention, arbitrary action synthesis or photorealistic rendering.
- GPU acceleration covers speech and tested NVENC encoding. Pillow sprite composition remains on CPU.
- One active generation worker is supported. Cancellation waits for the current blocking synthesis, download, Rhubarb or validation operation to return. Server/process interruption leaves a retryable job rather than resuming a half-rendered file.
- Automatic approval review blocked cleanup of inactive pip backup directories `~orch` and `~orchaudio` under `.venv/Lib/site-packages`, without a detailed reason. These unused backups remain; the active CUDA packages and dependency check are healthy.
