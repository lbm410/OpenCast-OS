# Public host checks

`.github/workflows/ci.yml` runs on pull requests, pushes to `main` and manual dispatch. It uses Ubuntu 24.04 with two isolated Python environments:

- Python 3.11, standard-library baseline; optional cryptographic tests may skip.
- Python 3.13, installing the exact versions in `requirements-firmware.txt` from binary distributions into a job-local virtual environment.

Both entries run Python unittest discovery, Node 22 tests, a host C11 build/test of the disconnected native lifecycle model, local-profile knowledge validation and `tools.knowledge_view --check`. Python checks use synthetic data and loopback fixtures. No firmware download, real-TV discovery, native target execution, credential input or private artifact is required. Runtime setup and optional Python package installation still require the normal public package services.

Permissions are restricted to `contents: read`; checkout does not persist credentials. No repository secret, deployment, upload or repository write step is configured. Node dependency caching is explicitly disabled. Superseded runs for the same branch/PR are cancelled, and each job has a 15-minute timeout.

## Action provenance

The official `actions` repositories and their pinned `action.yml` files were checked through the GitHub connector on 2026-11-14. Their then-current documentation used v7, and all three pinned actions declare the Node 24 action runtime; Node 22 is separately installed for project tests. GitHub reported valid signatures on these commits; that is a provenance observation, not a full source audit.

| Action | Fixed commit | Official source |
| --- | --- | --- |
| checkout, v7.0.1 | `3d3c42e5aac5ba805825da76410c181273ba90b1` | [Commit](https://github.com/actions/checkout/commit/3d3c42e5aac5ba805825da76410c181273ba90b1), [action definition](https://github.com/actions/checkout/blob/3d3c42e5aac5ba805825da76410c181273ba90b1/action.yml) |
| setup-python, v7 | `6d4fd22b20465ccc0f7354476588e8df7c9ca0e0` | [Commit](https://github.com/actions/setup-python/commit/6d4fd22b20465ccc0f7354476588e8df7c9ca0e0), [action definition](https://github.com/actions/setup-python/blob/6d4fd22b20465ccc0f7354476588e8df7c9ca0e0/action.yml) |
| setup-node, v7.1.0 | `949feb2413d6458794dcd2491c4babbbce0c15c1` | [Commit](https://github.com/actions/setup-node/commit/949feb2413d6458794dcd2491c4babbbce0c15c1), [action definition](https://github.com/actions/setup-node/blob/949feb2413d6458794dcd2491c4babbbce0c15c1/action.yml) |

## Validation status

**CONFIRMED (local, 2026-11-14):** YAML parsing and checks of the matrix, permission settings, 40-character action pins and credential/cache options pass. The integrated tracked Python suite ran269tests successfully with seven optional-crypto skips; the unfinished dependency-graph module was excluded. The initial custom selection command failed three fixture imports because it omitted the tests directory from the search path; correcting that runner invocation produced the passing run without source changes. Standard unittest discovery already supplies that directory. The40Node tests and9native C test groups pass. The knowledge bundle validates with16concepts and no issues/unresolved links.

**CONFIRMED (clean local snapshot):** commit `10c556decb5e3343d8704096d935cfab14046688` passes285Python tests with optional cryptography enabled and no skips,40Node tests,9native C groups, knowledge validation and generated-view checks. The snapshot was exported from Git without private firmware or uncommitted dependency-graph work.

**CONFIRMED (GitHub-hosted):** [run43600750961](https://github.com/lbm410/OpenCast-OS/actions/runs/43600750961) for that exact commit completed successfully. Both Ubuntu jobs passed: Python3.11 without optional crypto and Python3.13 with it. The GitHub connector confirmed Python, Node, host C, knowledge validation and generated-view steps succeeded in both jobs; the dependency installation step was intentionally skipped only in the baseline job. This is host validation, not a physical TV result.

**CONFIRMED (later integrated snapshot):** clean commit10048b421ea871e767570f328ff0264d793e2118, including the reviewed dependency graph, passes349Python tests with optional cryptography/no skips,40Node tests,9host C groups and both knowledge checks. [GitHub run43601838134](https://github.com/lbm410/OpenCast-OS/actions/runs/43601838134) passes both matrix jobs; the connector confirmed every required test step succeeded. Later documentation-only commits do not change this exact tested code identity.

**CONFIRMED (native-probe/segments snapshot):** exact commit`bf34028aada003ad8d357cc60c29da154c50393e` passes360Python tests with optional cryptography/no skips,40Node tests,9host C groups and knowledge/view checks in a clean Git archive. [GitHub run43603431682](https://github.com/lbm410/OpenCast-OS/actions/runs/43603431682) completed both Ubuntu matrix jobs successfully, including every required test step. Native-probe tests validate structural contracts with fixtures; actual ARM assembly/linking and independent instruction inspection were separately performed on the documented Mac toolchain. CI does not execute the ARM output or prove TV compatibility.

**CONFIRMED (branch-index snapshot):** exact commit`78c36323605484e4a3f06419392317be89c09680` passes372Python tests with optional cryptography/no skips and both knowledge checks in a clean local archive. The independent branch-index oracle covers10,023 synthetic words. [GitHub run43604326807](https://github.com/lbm410/OpenCast-OS/actions/runs/43604326807) completed both Ubuntu matrix jobs successfully, including Python, Node, host C and knowledge steps. No target-code execution or physical TV result follows.

**CONFIRMED (window-ownership snapshot, mixed CI outcome):** exact commit`5e3e22276db6b4612248c3ae94311daee34fd4aa`, [run43607370779](https://github.com/lbm410/OpenCast-OS/actions/runs/43607370779): the Python3.13/crypto job passed every required step, including the new Linux ASan/UBSan lifecycle check, Node, host C and knowledge validation. The Python3.11 baseline job failed one of372Python tests (seven optional skips): `test_failed_atomic_publication_leaves_no_temporary_or_partial_report` observed a `.pending-*` file after a500response. Its later steps were skipped. This run is not an overall pass. The server sends its error response inside `except` before the `finally` removes the temporary file, permitting a client observation before cleanup; a new reply-boundary regression deterministically fails on the old implementation and passes after moving the500response after cleanup. The corrected local suite passes373tests with optional crypto/no skips; hosted baseline verification remains pending. The Linux sanitizer pass is separate from the Mac sanitizer environment limitation and establishes no TV behavior.
