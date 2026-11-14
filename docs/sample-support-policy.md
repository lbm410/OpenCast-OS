# Sample-support policy behind the AppInfo path

Date: 2026-11-14. **Independently reviewed. CONFIRMED (local static):** the imported sample-support wrapper constructs a framework query; a matching method/handler pointer pair occurs in RELEASE; its handler normalizes a predicate over three process-global words. **PENDING:** active method dispatch, live field values and their writers/authority, authenticated access, AppInfo provenance and native admission. No device request, setting change, target execution or protected-package access occurred.

## Question and bounded inputs

The reviewed [AppInfo provenance](appinfo-provenance.md) requires storage3, a nonzero app ID, a successful `HOA_IO_CheckSampleSetIsSupported` return and a nonzero output flag. This investigation follows that exact imported symbol, rather than assuming the portal's Developer CP Service checkbox has the same meaning.

| Input | Bytes | SHA-256 |
| --- | ---: | --- |
| `firmware/lab/lgli-api-selected/liblgopenapi.so.0.0.0` | 1,323,828 | `538ec51bd5bee6c3c7f8f77717b6588a2bf42a29724f9505feef4c93df260a54` |
| `artifacts/boot-triage/decoded/RELEASE.elf` | 23,591,000 | `e37751653de2b79744f1246361439e8a6b37694e2c345ec87c2445c9281a556c` |

Existing symbol inventories supply the exact exported ranges. The reviewed host disassembler captures only the following four ranges; this neither loads the libraries nor executes target instructions.

| Defined symbol | Range, exclusive end | Bytes |
| --- | --- | ---: |
| `HOA_IO_CheckSampleSetIsSupported` | `0x5b4c0–0x5b590` | 208 |
| `BROAD_HNDL_CheckSampleSet` | `0x2294e0–0x229558` | 120 |
| `BROAD_SEND_CheckSampleSet` | `0x22eebc–0x22ef50` | 148 |
| `OSA_MD_IsSupportSampleSet` | `0x28aaac–0x28aae4` | 56 |

These532bytes contain literal pools as well as instructions. All133displayed words match mapped bytes;20immediate branch/call destinations were independently calculated. The explicit host LLVM hash is `bb7793802ccffe8e0613ce326f6fe8caacbd626e5318bbcf73e820a5c027aca4`. ARM decoding is an assumption of this selected analysis, not a physical CPU measurement.

## Client query and checked result

PC-relative arithmetic gives base `0x1403ac`. Four directly demonstrated call arguments identify a technical destination/object/interface/method tuple passed to `SCF_BUS_Message_Create_Method`; the method string is exactly `HOA_IO_CheckSampleSetIsSupported`. The selected-data record retains these technical strings privately. PLT words and type22 relocations independently resolve the imports; no packet was constructed or sent.

The wrapper saves its caller's output pointer in r7 and initializes its local result-status word at SP+12 to zero. It obtains a process send connection, calls `SCF_BUS_Message_Send_And_Wait_Reply` with the message and third argument `0xffffffff`, and checks whether the returned reply pointer is nonzero. The timeout meaning of that argument is not established here.

For a nonzero reply, `SCF_BUS_Message_Get_Any` receives two selector values `0x62` and pointers to SP+8 and SP+12, followed by a zero terminator. Its return value is not checked in this wrapper. Only if the second output word equals1 is the first word copied into the caller's output pointer. The wrapper returns0 for that second-word value, otherwise-1; it unreferences the reply when present and the original message. Message-creation failure handling, decoder guarantees and actual transport authentication remain outside this slice. A returned status is not the same as a true support flag.

## Matching receiver record and handler

A bounded exact-string search in the pinned RELEASE file finds one method-name string at file `0xe008d4`, VA `0xe088d4`. An aligned pointer reference at file `0x12c4bb4`, VA `0x12d4bb4`, is immediately followed by handler address `0x2294e0`. This is a concrete static method/handler pair; the dispatcher that consumes the record and the physical process's active dispatch have not been traced here. Symbol names alone are not the connection evidence.

The handler initializes a support-output word to zero, then calls imported `SCF_BUS_Message_Get_Any` on its request with selector zero. A zero decoder result branches to a reply carrying support0 and status0, followed by handler return-1. A nonzero result calls `OSA_MD_IsSupportSampleSet`, normalizes any nonzero predicate value to1, and replies with that support word and status1 before returning0. Both branches pass their original connection/request values to the same sender.

The sender constructs a method return using the two selector values `0x62`, attempts to send it, unreferences it, and returns0. It does not visibly inspect the create/send outcomes. Consequently handler success is not proof that a reply was delivered or that the client accepted it.

## Exact predicate; runtime policy still unknown

The selected predicate reads the following linked addresses, without inspecting their contents in this investigation:

- A: word at `0x12e3840 + 0x28c` (`0x12e3acc`).
- B: word at `0x030d4664`.
- C: word at `0x12e3840 + 0x2c4` (`0x12e3b04`).

If A is nonzero and B is nonzero, it returns1. Otherwise it returns C unchanged; the caller subsequently normalizes C to a Boolean. No configuration field names, manufacturer-device classes or user-adjustable controls are inferred from these offsets.

A and C fall in file-backed load-segment storage; B is in zero-fill-only load-segment storage. This describes ELF initialization geometry, not the current process values. No pointed-to field contents, write sites, physical memory, environment values, credentials or service-menu data were read. Zero-filled initial storage does not imply a permanently false B, and static file data would not establish live A/C.

The result narrows the missing policy edge to concrete internal state and its producers. It does not show that the owner's TV supports the sample route, establish how AppInfo files are produced/authenticated, admit arbitrary native executables, or authorize altering those fields. The working Web application can instead use the protected fallback described in the earlier report.

## Reproduction, accounting and next step

Ignored `artifacts/sample-support-policy/` contains four captures, input/tool identities, selected PLT/relocation and pointer evidence, arithmetic verification and a hash manifest. Reproduce the same bounded captures with:

```sh
PYTHONPATH=. python3 artifacts/sample-support-policy/capture.py
PYTHONPATH=. python3 artifacts/sample-support-policy/receiver_capture.py
PYTHONPATH=. python3 artifacts/sample-support-policy/selected_data.py
PYTHONPATH=. python3 artifacts/sample-support-policy/receiver_data.py
```

The two capture scripts compare existing immutable captures instead of overwriting them. The data readers print only their selected metadata. Additional selected data consists of ten12-byte PLT entries, the8-byte method/handler pair and four96-byte technical-string windows. Policy and client literal words are already inside the captured ranges. Exact method-string/pointer searches and ELF symbol/relocation mapping inspect the pinned files within the64MiB reader limit; these are targeted evidence searches, not a claim that only532bytes were read from disk.

**Experiment SAMPLE-POLICY-001:** objective: identify the implementation behind the imported sample-support query. Hypothesis: it depends on vendor policy state rather than a portal checkbox. Procedure: pin two existing selected ELFs, capture four symbol-bounded ranges, map imports and exact method-pointer evidence, verify arguments/branches and classify the three storage locations without reading their values. Observed: client result-status gate, matching handler pair, normalized three-word predicate and unchecked sender outcomes. Conclusion: static policy structure is identified; live admission and authoritative policy producers remain unknown. Risks: confusing static table adjacency with active dispatch, initialization with runtime state or a support query with a safe writable configuration API. Next: independent review passed; any producer/dispatcher investigation needs a separately justified scope. No owner action or TV test is needed now.

Independent review passed without corrections: all four symbol extents,532bytes/133words,20branch targets, ten PLT/relocation mappings, PIC argument arithmetic, the exact method/handler pair and predicate storage classification were verified. No A/B/C values, added functions or device state were read. Evidence: ignored `artifacts/sample-support-policy-review/`.
