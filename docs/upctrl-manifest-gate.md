# upctrl manifest production and protection gates

Date: 2026-11-14. **CONFIRMED (local, firmware-static):** the app-ID handler first tries to construct a manifest from local AppInfo metadata. Only on failure does it use the protected downloaded-manifest path. That fallback requires the NCG classification and successful key retrieval, size/read operations and a named verification call. **PENDING:** which branch the physical USB-test app uses, the provenance of AppInfo, the cryptographic verifier's actual policy, and authorization of a native package. This is not an arbitrary-native execution route.

This extends [native-manifest-admission.md](native-manifest-admission.md), which connected USB-test storage 3 to the app-ID provider request. No owner-protected package, credentials or key material was read; no decryption, IPC, TV/network operation or target execution occurred. The routines described below were inspected as bytes, never invoked.

## Input and bounded method

Existing `artifacts/firmware-lab/open-inventory.json` lists the exact regular member `bin/upctrl`, mode `-rwxr-xr-x`, 350,380 bytes. The reviewed SquashFS helper selected only that member from `firmware/lab/packages/open.pak`, whose SHA-256 is `d89a800371ea6d2681813c974e4975be92730d10cccd77788945a88a4be33a48`.

Selected copy: `firmware/lab/upctrl-selected/bin/upctrl`, mode `0444`, SHA-256 `5cc04d10a43926a843c27c15f8928a6e2400a968f7e1a3e5bde93175ff787e4f`. It is ELF32 little-endian ARM ET_EXEC, EABI5, flags `0x5000002`, entry `0x16f68`, interpreter `/lib/ld-linux.so.3`. `DT_NEEDED` includes `libncg_agent.so.1`; dependency naming alone does not establish the runtime symbol provider or verifier behavior.

The reviewed [bounded disassembler](static-disassembly.md) used Apple LLVM 17.0.0, executable SHA-256 `bb7793802ccffe8e0613ce326f6fe8caacbd626e5318bbcf73e820a5c027aca4`. Ten explicit captures total 4,444 bytes, below the 16-KiB task budget; all ten reproduced with the same selected-byte and normalized-disassembly hashes. Imported calls were resolved through ARM PLT instructions, GOT slots and type-22 ELF relocation entries, rather than guessed from nearby strings.

All code addresses below are linked virtual addresses; file offset is address minus `0x8000` for these ranges. Half-open bounds include local literal pools, whose words are data rather than executable instructions.

| Capture | Range | Bytes |
| --- | --- | ---: |
| App-ID handler | `0x19908..0x19b38` | 560 |
| File-path handler | `0x19b38..0x19d08` | 464 |
| AppInfo reader | `0x2bac0..0x2bc34` | 372 |
| Manifest from AppInfo | `0x2bc34..0x2be10` | 476 |
| Downloaded protected manifest | `0x2c384..0x2c60c` | 648 |
| Downloaded dispatcher | `0x2c60c..0x2c78c` | 384 |
| File-path protected manifest | `0x2c78c..0x2c930` | 420 |
| File-path dispatcher | `0x2ca70..0x2cba4` | 308 |
| Protected-buffer wrapper | `0x46374..0x465c8` | 596 |
| Protection classifier | `0x465c8..0x466a0` | 216 |

## The two provider handlers are identified

The method table pairs `AC_SEND_GetManifestBuffer` with `UC_API_GetManifastBuffer` at `0x19908`: string file offset `0x410d4`, pointer record file offset `0x53694`. The file variant pairs `AC_SEND_GetManifestBufferFromFile` with `UC_API_GetManifastBufferFromFile` at `0x19b38`: string offset `0x410f0`, record offset `0x536a8`. The spelling `Manifast` is in the vendor symbols. These are the method names identified on the appctrl sending side in the previous report.

The app-ID handler decodes two integer fields, then passes them and output buffer/length pointers to `UC_APPUTIL_GetManifestBufferFromAppInfo` at call `0x1999c`. Return zero branches at `0x199a4` to a successful reply status. Only a nonzero return reaches `UC_APPUTIL_GetManifestBufferDownloadApp` at `0x199b8`; its status is retained for the reply. The handler constructs a status-plus-byte-array response and frees its temporary buffer. A failure branch can construct a short placeholder buffer while preserving failure status; buffer presence alone is not acceptance.

The file-path handler decodes a string and calls `UC_APPUTIL_GetManifestBufferFromFilePath` at `0x19bb4`, retaining its result for the reply. No service method was called by this research. The whole service dispatcher and its peer authorization are outside this slice.

## First path: manifest synthesized from local AppInfo

`UC_APPUTIL_GetManifestBufferFromAppInfo` resolves a path through `UC_PATH_GetAppInfoFilePath` at `0x2bcec`, requires success, then calls `_UC_APPUTIL_GetAppInfoFromFile` at `0x2bd4c` and rejects nonzero return. The selected reader uses `fopen`, `fscanf`, `fgets` and `fclose`; it does not call the protection functions in this inspected body.

The caller compares one parsed numeric field with 2 at `0x2bd5c`, chooses one of two internal formatting fragments and constructs a larger buffer using `snprintf` at `0x2bdc0`. It returns that buffer with `strlen + 1` at `0x2bdc8..0x2bdd8`. The internal templates were not copied into this report or used to fabricate metadata.

**CONFIRMED (static):** this handler has a successful local-metadata construction path before the downloaded protection path. **PENDING:** whether the path helper accepts storage 3, the precise AppInfo location/format, who creates or updates it, its integrity/ownership protections and whether it represents previously admitted content. The numeric comparison is a formatting choice; it is not a demonstrated native admission allowlist. Absence of a cryptographic call in these two bodies does not prove absence of an earlier installation gate or owner control of this metadata.

## Fallback: downloaded protected manifest

`UC_APPUTIL_GetManifestBufferDownloadApp` obtains a manifest path at `0x2c680`, then calls `APPSEC_DRM_IsEncryptFile` at `0x2c68c`. A helper failure rejects it; a false classification also returns failure (`0x2c700..0x2c720`). Only a true classification calls `_UC_APPUTIL_GetManifestBufferDownloadedDRM` at `0x2c6d0`.

The classifier calls imported `NCG_IsNCGFile` at `0x46618`, translating exactly result 1 into true. That is file classification, not demonstrated signature or entitlement verification.

The downloaded protected helper contains these gates:

| Gate | Evidence | Meaning and limit |
| --- | --- | --- |
| Content-key retrieval | `APPSEC_DRM_GetCEK`, call `0x2c418` | Zero proceeds; failure enters a separate recovery branch. The helper's internals and any key material were not inspected. |
| Conditional signed-in/licensing branch | `UC_UTIL_IsSignedIn` at `0x2c4a4`; `UC_UTIL_GetServerURL` at `0x2c4b0`; `APPSEC_DRM_GetLicenseURLAndRO` at `0x2c4c8` | Entered only after initial key retrieval fails. False sign-in or license-helper failure rejects; success retries key retrieval at `0x2c4dc`. Exact entitlement criteria and network behavior remain untraced. |
| Declared size | `APPSEC_DRM_GetDecryptFileSize`, call `0x2c42c` | Failure rejects; success sizes an allocated temporary buffer. The helper body is outside this slice. |
| Protected read | `APPSEC_DRM_DecryptFileToBuffer`, call `0x2c468` | Failure frees/rejects; success publishes buffer and size at `0x2c474..0x2c47c`. |

Thus it is incorrect to claim that every manifest retrieval needs a live LG account/server request: both the earlier AppInfo path and the initial successful key-retrieval branch precede the conditional licensing branch. It is equally incorrect to infer that current native entitlement is available. No account, licensing or connectivity experiment was performed.

## Verification boundary inside the protected read

The bounded body of `APPSEC_DRM_DecryptFileToBuffer` establishes concrete return-value gates:

- Imported `NCG_OpenAndVerifyFile`, call `0x46410`, must return zero; branch `0x46418` rejects failure. The import is resolved through PLT `0x16844`, GOT `0x63268`, relocation file offset `0xe190`.
- `NCG_GetContentsSize`, call `0x46424`, must return zero.
- After supplying the caller's key buffer to the NCG API, `NCG_Read`, call `0x46470`, must return zero. The returned byte count must equal the obtained content size (`0x4647c..0x46488`).
- The successful path returns zero; failure paths return `-1` and share handle cleanup/unlocking.

**CONFIRMED (static):** a successful call to the named NCG verifier precedes content output on this protected path. **PENDING:** the verifier implementation, cryptographic algorithm, trusted issuer, authenticated byte coverage, device/model/developer binding and license policy. A named verifier plus checked result is stronger evidence than a string, but it does not establish those security properties. This investigation stops at that library boundary and provides no means to bypass it.

## File-path route differs and is not the proven USB-test route

`UC_APPUTIL_GetManifestBufferFromFilePath` classifies the path at `0x2cac4`: true calls the protected file helper at `0x2cb04`; false calls `_UC_APPUTIL_GetManifestBufferFromFilePathNonDRM` at `0x2cb38`. The latter body was not inspected. The protected file helper requires size/key retrieval and the same protected-buffer wrapper (`0x2c7e8`, `0x2c7fc`, `0x2c838`); it contains no counterpart to the downloaded helper's signed-in/license retry.

This separate branch cannot be substituted for the USB-test chain: the preceding report connected USB-test list/storage to the **app-ID** handler. File-path existence, a non-DRM branch or service registration does not demonstrate arbitrary external callers, native admission or privileged execution.

## Follow-up: AppInfo is gated by sample support

The later [AppInfo provenance trace](appinfo-provenance.md) establishes that the path builder accepts only storage3 with a nonzero app ID and requires a successful imported sample-support query with a nonzero result flag. A diagnostic calls this CP Box, but the underlying policy and the owner's device result remain unknown. Failure takes the protected downloaded fallback. No immediate producer was identified. This qualifies the earlier AppInfo-first description: it is not a general unprotected alternative, and it must not be equated with the portal's Developer CP Service checkbox.

## Remaining execution gap and next bounded experiment

No Web-only restriction was established in these selected provider bodies, but no native permit was established either. Appctrl's type/path conversion remains downstream of successful provider output and XML parsing; later execution conditions, filesystem execution permissions, process account and lifecycle ownership remain unresolved.

The highest-value next static slice is AppInfo provenance: inspect `UC_PATH_GetAppInfoFilePath` and its demonstrated path-builder callees, determine storage-3 handling, then locate only the writer(s) of the resulting metadata. This can distinguish an installation-generated record from a route actually usable by USB-test content without touching the protected package. Independently, appctrl's later `_APPCTRL_CheckExecuteCondition` remains relevant to native class acceptance. Do not invent a manifest, reuse a system identity, invoke list loading as a query or treat these findings as authorization to alter the device.

## Reproduction and experiment record

Ignored `artifacts/upctrl-manifest-gate/` contains `selection.json`, `elf.json`, symbol inventory, ten bounded captures, `manifest.json` and selected method/relocation evidence. `capture.py` pins the input hash and budget; run from the repository root with `PYTHONPATH=. python3 -B artifacts/upctrl-manifest-gate/capture.py`. The first reproduction attempt without `PYTHONPATH` failed at the host import; the corrected invocation reproduced all ten captures. Originals and selected target bytes remained unchanged.

Public-tool reproduction for a representative gate; use the exact table bounds for other captures:

```sh
python3 -m tools.arm_disassembly firmware/lab/upctrl-selected/bin/upctrl \
  --objdump /Applications/Xcode.app/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/bin/llvm-objdump \
  --start 0x46374 --end 0x465c8
```

**Objective:** locate acceptance checks before upctrl returns a manifest. **Hypothesis:** provider-mediated retrieval contains protection/entitlement gates missed by appctrl-only tracing. **Environment:** selected official upctrl and bounded host static tools. **Procedure:** validate/extract one regular member; match method records; follow ten explicit function ranges and selected import relocations; reproduce captures. **Expected:** a concrete success/failure chain or a precise provider boundary. **Observed:** AppInfo-first construction, protected downloaded fallback, conditional sign-in/licensing branch and checked NCG verification/read calls; file-path handling differs. **Conclusion:** the protection boundary is narrower and more conditional than an all-manifests-DRM assumption, while legitimate native admission remains unproven. **Risks:** mistaking local metadata for owner-controlled input, classification for cryptographic verification, or compiled branches for active device behavior. **Next step:** bounded AppInfo provenance and subsequent execution-condition analysis, preserving device state.
