# Permanent portrait video contract

Every new video defaults to native 1080×1920, 30 FPS, 9:16. Landscape and square requests fail validation. The optional explicit API `video_profile: "low_memory"` produces native 720×1280 at the same frame rate. This is a resource-saving export, not stretched 1080p. Shorts and Mini select duration targets only. Existing completed videos are preserved byte for byte.

`app/video_config.py` owns dimensions, frame rate, logical stage and profiles. Review requests, timeline construction, Pillow frame streaming, Godot manifests, scene validation and final validation use this contract. Godot's project viewport, per-render Movie Maker viewport and runtime window agree. The logical 720×1280 stage keeps character positioning consistent at either output resolution.

Godot 2D uses aspect-preserving background coverage and resolution-scaled Camera2D composition. The hybrid uses perspective Camera3D, physically grounded original animated 2D rigs in transparent SubViewports/Sprite3D, registered environment geometry and soft analytic contact shadows. Shot participants receive head-framing guards during pans. Conversation cuts and two-shots focus speakers rather than compressing an entire cast into each close-up. Unsupported environments retain 2D for the whole episode. Full 3D characters have not been added.

Bengali subtitles retain actual approved speech timing and Unicode shaping, with two lines maximum, resolution-relative font size, 7.5% horizontal margins and 12% bottom clearance. There are no dialogue boxes. The preview uses a 9:16 player constrained to desktop/mobile height. Historical landscape videos are contained in that player without rewriting their files.

FFprobe verifies exact configured dimensions, 30 FPS, H.264/AAC, yuv420p, square pixels and rotation metadata. Final validation also fully decodes the MP4 with FFmpeg and checks timeline duration. Validation failures cannot become completed jobs. NVENC retains CPU fallback; frame streaming, one heavy job and scene caches remain.

Movie Maker termination now counts actual scene process frames rather than CLI startup iterations. A small real capture overrun is trimmed to the exact scene frame count by FFmpeg. This fixes an intermittent short repeated render; missing frames are never padded or accepted.

## Executed media checks

`scripts/render_hybrid_benchmark.py` rendered Nabil, Rayan and Anika speaking the three previously human-approved fresh Chatterbox WAVs. No voice regeneration or transformation was applied. Actual duration is 21.3333 seconds, deliberately shorter than the usual Shorts target for this test.

- `output/flat-portrait-1080p-evaluation.mp4`: native 1080×1920, 30 FPS, H.264/AAC, yuv420p.
- `output/hybrid-portrait-1080p-evaluation.mp4`: same specifications and identical source speech.
- `workspace/portrait-review.jpg`: six time samples from each actual MP4, visually inspected.
- `workspace/portrait-verification.json`: repeatable FFprobe/full-decode checks, sampled hybrid camera/grounding traces and preservation hashes.
- `workspace/*-portrait-1080p/acceptance.json`: actual render metrics, cache reuse and speech hashes. Timings include different cache states and are not a controlled speed comparison.

The final audit verified both MP4s, transparent rig viewports, grounded soles, selected head bounds and Rhubarb cue mapping for all three children, with listener mouths closed. Preservation hashes matched 448 existing assets and 22 prior videos. Desktop/mobile browser playback and downloading the actual MP4 also passed; the browser test uses an explicitly labelled completed-card fixture, not a fabricated production job.

Testing on this installation: the broad 195-test run initially passed 192 tests and exposed the capture-count bug plus two obsolete 24-FPS/resolution expectations. After repair, all three passed in a 32-test targeted run (`workspace/portrait-repaired-tests.log`). A separate 20-test child-rig/director/real-Godot regression run passed (`workspace/portrait-motion-regression.log`). These 52 distinct checks include 18 portrait tests and four hybrid planner tests. The entire suite was not rerun after those repairs. Browser evidence is in `workspace/portrait-browser-verification.json`.

The orchard hybrid is still marked `prototype`: its added low-poly scenery differs visibly from the painted background. It is available explicitly for evaluation, not automatically enabled as a production-quality style. Other environments continue in 2D. Existing front-view rigs and missing adult rigs retain their documented limitations. Demo voice commercial rights remain unverified; evaluation status is unchanged.

Run the native benchmark with `.venv/Scripts/python.exe scripts/render_hybrid_benchmark.py`, then `.venv/Scripts/python.exe scripts/verify_portrait_benchmark.py`. For the low-memory profile add `--low-memory` to the renderer command. Automated portrait contract tests are in `tests/test_portrait.py`. Old historical format-specific reports do not describe the current export contract.
