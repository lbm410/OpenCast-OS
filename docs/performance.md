# Performance acceptance

Owner requirement: fast response on the real LG47LA620S-ZA takes priority over visual effects. No benchmark currently proves the shell is faster than NetCast.

Current evidence: HW-001's25ms measures script initialization, not network-to-paint or usable startup. Two ping samples measure LAN response, not remote latency. Desktop rendering/tests are not TV CPU/GPU/memory evidence. The97188-byte landscape requires about3.52MiB for one RGBA decode, before browser/compositor copies.

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
