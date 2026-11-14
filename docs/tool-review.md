# Local tool review — ELF inventory and V2 report ingestion

Review date: 2026-11-14. Scope: `tools/elf_inventory.py`, `tools/probe_server.py`, their tests, and the actual V2 client output. This review used synthetic files, temporary directories and loopback-only HTTP integration tests. No TV request, LAN server, firmware execution or persistent device action occurred.

The integrator implemented the production fixes after the reviewer sent reproducible findings. The reviewer changed this document and added only `tests/test_elf_review.py` and `tests/test_probe_review.py` for the review follow-up. This is a bounded code review, not a claim of complete security or platform compatibility.

## Findings and verified disposition

### R1 — Invalid Unicode could leave partial reports outside the save quota

**Initial severity: medium. Status: CONFIRMED (local reproduction), RESOLVED (regression verified).**

The original `validate_report` accepted a user-agent string containing a JSON-escaped unpaired surrogate, such as `\ud800`. Persistence used `json.dump(..., ensure_ascii=False)` after opening the final report filename. The UTF-8 writer then raised `UnicodeEncodeError`. A local reproduction left a 14-byte partial file. The successful-report counter had not yet incremented, so the 32-report quota did not bound these partial artifacts. The uncaught handler exception could also bypass the intended quiet error handling.

Fix locations: `tools/probe_server.py`, user-agent validation around line 61 and publication around lines 162–173. The validator rejects surrogate code points. Serialization and UTF-8 encoding happen before creating a temporary file, followed by complete-file publication with a non-overwriting hard link. Storage errors return HTTP 500 and temporary output is cleaned up.

Verified: malformed-surrogate submission returns HTTP 400 without creating any file; simulated link failure and a partial temporary-write failure both return HTTP 500, leave no final or temporary report, and do not increment the quota counter. A valid retry then succeeds and yields parseable V2 JSON. Tests: all three cases in `test_probe_review.py`, plus the integrator's validator regression.

### R2 — Regular-file rejection occurred after a blocking FIFO open

**Initial severity: medium. Status: CONFIRMED (local reproduction), RESOLVED (regression verified).**

The original `inspect_file` called blocking `os.open(..., O_RDONLY)` before checking `fstat`. Opening a temporary FIFO without a writer blocked indefinitely rather than reaching the intended regular-file error. A bounded subprocess reproduction was terminated after 500 ms.

Fix location: `tools/elf_inventory.py`, `inspect_file` around line 153 and the tree header-read path. Opens now include `O_NONBLOCK` and `O_NOFOLLOW`, followed by regular-file verification. The integrator's FIFO test returns immediately with `ValueError`; the complete ELF suite passes.

### R3 — Traversal failures were reported as a complete inventory

**Initial severity: medium. Status: CONFIRMED (local reproduction), RESOLVED (regression verified).**

The original `os.walk` had no error callback. A temporary unreadable directory containing an ELF was skipped, returning `status=ok`, `visited=0`, `complete=true`, and no errors. This could turn missing dependency evidence into a false claim of a complete firmware inventory.

Fix location: `tools/elf_inventory.py`, `scan_tree` around line 177. Streaming `scandir` traversal now records directory and entry errors and returns `partial` with `complete=false` when errors remain.

Verified: a real temporary directory with mode `000` is reported as an unreadable relative path and an incomplete inventory. The regression restores its permissions in `finally`. It explicitly skips when the executing account bypasses permission restrictions; it ran without skipping in this review.

### R4 — File count did not bound traversal or practical aggregate resource use

**Initial severity: medium. Status: CONFIRMED (local reproduction), RESOLVED for the tested budgets.**

The original scan counted filenames but not directories. Fifty empty directories with `limit=1` still returned a successful result with zero visited entries. File hashing was bounded per file, but not across the inventory. Expanded metadata could also be much larger than its source: a synthetic 65,536-byte ELF containing 4,093 references to one 4,095-byte string produced 16,760,835 bytes of dependency names. Retaining many such reports amplified memory use despite the per-file input bound.

Fix locations: `tools/elf_inventory.py`, expanded-name accounting around lines 120–139 and tree accounting around lines 177–223. Directory entries now count toward the traversal limit. Defaults bound cumulative input accounting to 2 GiB, expanded names to 256 KiB per ELF, and aggregate serialized file metadata to 16 MiB. Budget exhaustion returns an explicit incomplete status. The existing 1 GiB file-size ceiling and individual ELF table bounds still apply.

Verified: the original long-name amplification fixture is rejected before producing its expanded report and produces a partial tree result. Sixty-five individually accepted metadata-heavy synthetic files trigger `metadata_limit_reached` before all reports are retained. The integrator's directory-count and cumulative-input regressions also pass. These are bounded host fixtures; no vendor binary is executed.

### R5 — Contradictory ARM float flags were silently collapsed to hard float

**Initial severity: low. Status: CONFIRMED (local reproduction), RESOLVED (regression verified).**

The original conditional gave the hard-float bit precedence. A synthetic ARM ELF with both mask bits set (`e_flags=0x05000600`) was labeled `hard`, losing the contradictory soft-float bit. This is a metadata-reporting issue; it does not establish the actual TV ABI.

Fix location: `tools/elf_inventory.py`, ARM flag interpretation around line 147. The report now explicitly labels this combination `conflicting`. The integrator's regression passes. Real ARM ABI identification still requires evidence beyond an ELF flag summary.

## Client/server compatibility check

**CONFIRMED (local):** the actual `prototypes/netcast-web/probe.js` was executed through the existing deterministic DOM/XHR fixture with focus on `focusButton` and four arrow down/up pairs. Its emitted 1,560-byte V2 JSON, containing ten retained events, was accepted by `validate_report` without schema transformation. Thus this check covers the real client serializer rather than only independently hand-authored Python sample dictionaries.

The contract retains `keyEvents == eventCounts.keydown`, strict field sets, boolean feature flags, bounded integers, a 16-event tail and sanitized element labels. The server keeps its explicit asset allowlist, one-peer restriction, 8,192-byte request limit and `physical_tv_confirmed=false` assignment. A successful desktop or loopback report never confirms execution on the TV.

## Verification summary

The initial existing suites passed while the defects were still present; their missing cases motivated the additional regressions. After integration, the targeted suites passed:

```sh
python3 -m unittest discover -s tests -p 'test_elf*.py' -v
# 11 tests passed
python3 -m unittest discover -s tests -p 'test_probe*.py' -v
# 14 tests passed
```

Six of these tests are the independent follow-up cases in the two review files. No production code was changed by the reviewer during this task; changes were communicated to and applied by the integrator.

## Remaining scope limits

The ELF inventory is a metadata reader, not a loader or full ABI validator. It does not identify the TV architecture without actual compatible firmware evidence, and its dependency list does not resolve libraries or prove a runnable process. Resource budgets intentionally permit partial output; downstream decisions must inspect `status`, `complete`, and `errors`.

The tree reader should operate on a stable analysis tree. Per-file non-following opens and `fstat` checks do not constitute a complete filesystem isolation boundary against adversarial concurrent ancestor-directory replacement. Firmware extraction isolation and a controlled working tree remain separate responsibilities.

The report server is a temporary single-peer research service. Schema validation constrains recorded data but cannot establish that input was physically generated by a remote or that a client report is truthful. Interrupted storage and error paths are tested; power-loss durability, arbitrary filesystem failures and every legacy-browser HTTP behavior are not proven by these tests.
