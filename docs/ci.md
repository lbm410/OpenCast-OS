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

**PENDING:** actual Python3.11/Ubuntu execution and GitHub-hosted workflow results after publication. No hosted CI result is claimed by creating this file. Before publication, test the exact committed snapshot, including optional cryptography, without uncommitted agent files or private firmware. The workflow discovers every committed Python test.
