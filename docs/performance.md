# Performance acceptance

Owner requirement: fast response on the real LG47LA620S-ZA takes priority over visual effects. No benchmark currently proves the shell is faster than NetCast.

Current evidence: HW-001's25ms measures script initialization, not network-to-paint or usable startup. Two ping samples measure LAN response, not remote latency. Desktop rendering/tests are not TV CPU/GPU/memory evidence. The188345-byte1280×720 landscape requires about3.52MiB for one RGBA decode, before browser/compositor copies.

Provisional engineering targets, to calibrate with real measurements:

| Metric | Target | Required evidence |
| --- | --- | --- |
| Received key to visible focus | p95 under100ms, no queued navigation | Physical observation/capture; handler time alone insufficient |
| Local event handler | p95 under10ms | Bounded samples; clock resolution stated |
| LAN launch to usable screen | under2seconds | Cold/warm measurements including transfer/rendering |
| Stability | No stalls/lost navigation in mixed-action session | Establish actual key delivery first |
| CPU/memory | Budget pending baseline | Real observable vendor baseline and session peak |

Report sample counts,p50,p95,max. Do not claim improvement without comparable baseline tasks. Do not infer freeRAM from firmware/file size.

Implementation: no framework runtime, external assets, per-frame requests/storage, real-time blur dependency or default continuous motion. Avoid repeated layout-read/write cycles; suspend timers/requests when hidden. Bound telemetry and never record typed content or credentials.

Measure static versus optional animated background under the same navigation workload before enabling movement. Remove any effect that causes perceptible latency, irregular frame pacing, excessive memory or instability. A CSS transform or GPU-named library does not establish hardware acceleration.

Consolidate input, layout, repeat-load and exit checks into meaningful owner-assisted sessions. No privileged profiling or TV setting change is implied.


## First packaged-device baseline

CONFIRMED (owner observation, APP-001): the corrected USB launcher renders and accepts arrows/OK. Both opening and navigation are reported very slow; no timings, CPU/GPU or memory samples exist. This is the baseline to improve, not an optimization result. Static audit found duplicated selection work through keydown→choose→focus→onfocus→choose, all-button class rewrites, and selected SVG/icon geometry changes. Full-screen overlay, shadows and blending add possible paint cost, but its contribution is unmeasured.

The next host candidate removes redundant state writes, holds selected geometry fixed and simplifies painting while retaining the same1280×720JPEG. Desktop tests will verify behavior and reduced DOM-write counts; only a new physical comparison can establish speed improvement. Native integration research remains independent: replacing the OS does not automatically remove inefficient UI work or prove graphics compatibility.


### PERF-001 host candidate

The same real-handler synthetic fixture compares one Home→Apps right-arrow movement against the published baseline:18DOM property/attribute writes become3(two classes and changed title), with one focus call in each. Repeated onfocus causes no further writes; clamped movement produces neither writes nor refocusing. These counts measure host-observed program behavior, not the TV rendering pipeline or an equivalent latency percentage.

Candidate CSS fixes icon/SVG geometry across selection and removes full-screen overlay, gradients and shadows. Focus uses solid color and an outline; small static translucent dock/tab backgrounds remain. High Contrast removes the background image for a possible later within-build comparison, but only if the owner chooses it. Nineteen shell tests and five startup-probe tests pass; two source-bundle tests pass. Desktop Home rendering was inspected at1276×603. The baseline landscape asset is unchanged.

A new source-only ZIP is prepared under ignored artifacts/netcast-source/launcher-performance-source.zip; it is not installed or tested on the TV. Regenerate through LG with root index.html, explicitly uploading this source archive to avoid the observed Modify nesting behavior. Suggested physical comparison: time opening until controls respond, then ten isolated left/right presses at roughly one-second intervals, then a short sequence and normal Home return. Record owner observations separately from any handler timing. Do not conflate entry-point correction with a performance improvement.
