# Historical native runtime artifacts and issuer requirements

Checked 2026-11-14. **Result:** primary vendor material confirms a runtime-specific Marmalade package model and a historically restricted LG target, plus Unity's Union licensing/distribution route. It does **not** supply the exact NetCast 2013 build artifact, loader revision, package layout or a currently available issuer. This narrows the missing contract beyond “compile an ARM ELF”. No tools, source archives or application binaries were downloaded or executed; no account, TV, network-control or Git action occurred.

Read alongside [historical packaging](native-packaging-route.md) and [native execution gates](native-execution-gates.md). The current owner screenshot exposes Web App only; this investigation does not infer hidden backend choices or change that observation.

## Supported evidence

| Source | What it establishes | What it does not establish |
| --- | --- | --- |
| LG deployment guide, printed pp. 5, 10, 13–16 | Historical ZIP upload, portal packaging, USB delivery and a Marmalade/Unity section referring to the Flash submission workflow. Login and account-related USB conditions are documented. | Native archive members, main executable extension, target loader, current native entitlement or successful native upload. |
| Marmalade supported-platforms page, original-site snapshot 2013-08-21 | LG Smart TV support was restricted to Professional licensees and LG-registered developers. | That ordinary LG registration alone sufficed; that the present owner has the runtime entitlement; the target's exact NetCast generation/ABI. |
| Marmalade architecture page, original-site snapshot 2014-03-27 | Compile for a selected CPU architecture, then combine that binary with a platform-specific loader to obtain an installable package. | A generic ELF, Android package or arbitrary Linux build being valid LG input; a verified loader for this television. |
| Unity original newsroom release, 2012-08-22 | LGTV was among Union's platforms. Union licensed developers' games for distribution to platform partners. | Public NetCast export support in an ordinary Unity editor, a build-module download, runtime version or upload schema. |

Sources: [LG deployment PDF](https://webostv.developer.lge.com/assets/netcast/NetCast-Deploying_and_Testing_App_on_Real_TV.pdf), [Marmalade supported platforms](https://web.archive.org/web/20130821093711/http://www.madewithmarmalade.com/marmaladesdk/supported-platforms), [How Marmalade works](https://web.archive.org/web/20140327093048/https://www.madewithmarmalade.com/marmalade/how-marmalade-works), [Unity Union release](https://unity.com/news/unite-2012-unity-technologies-brings-unity-authored-games-union-portfolio).

## Artifact and entitlement distinctions

**CONFIRMED (documentary, historical):** Marmalade described architecture selection separately from platform packaging. Its architecture page lists ARM, x86 and MIPS as possible compilation targets; this is a general workflow, not a CPU assignment to our model. Its LG eligibility wording is “for Professional licensees and LG registered developers”. Those are historical vendor conditions, not proof of current access. [Marmalade architecture](https://web.archive.org/web/20140327093048/https://www.madewithmarmalade.com/marmalade/how-marmalade-works), [platform eligibility](https://web.archive.org/web/20130821093711/http://www.madewithmarmalade.com/marmaladesdk/supported-platforms).

A separate original vendor announcement dated 2013-09-23 says SDK 6.4 introduced activation keys for license holders. This establishes an additional tooling dependency; it neither establishes the current activation service nor identifies 6.4 as the required LG target version. No activation material was requested or read. [Marmalade 6.4 announcement, snapshot 2013-10-02](https://web.archive.org/web/20131002033235/http://www.madewithmarmalade.com/blog/marmalade-64-here).

**CONFIRMED (documentary, historical):** Unity's own release describes Union as licensing games for release on new devices and identifies LGTV among its platforms. Joining was described as free with an 80% developer revenue share. This is evidence for a curated distribution relationship, not a documented self-service native exporter. No present Union availability is asserted. [Unity release, “About Union”](https://unity.com/news/unite-2012-unity-technologies-brings-unity-authored-games-union-portfolio).

**PENDING:** the exact native payload format. LG's Marmalade/Unity paragraph delegates to the Flash upload procedure without defining a native-specific archive layout or main-run-file rule. The Flash section's `.swf` selector must not be transferred to native runtimes. The partner/subtype instructions on pp. 7–8 belong to the Web section, not a recovered native entitlement policy. Historical account-linked USB limits and server-provided decryption material on pp. 14–16 do not establish permission to issue a native package. [LG deployment PDF](https://webostv.developer.lge.com/assets/netcast/NetCast-Deploying_and_Testing_App_on_Real_TV.pdf).

## Availability checked and exact gaps

- **CONFIRMED (retrieval):** the LG PDF, Unity newsroom release and the three timestamped Marmalade original-site snapshots above were readable through the web tool. They are documentary evidence, not software distributions or proof of live vendor support.
- **PENDING:** the original Marmalade technical page `https://docs.madewithmarmalade.com/native/overview/thetwosides.html` returned a retrieval error. The live historical main site and several archive navigation links also failed or returned redirect wrappers. These are tool observations, not proof that all copies or services are gone.
- **PENDING:** no primary source recovered in this bounded search specifies the exact LG deployment-target identifier, compatible SDK/loader version, compiler/sysroot, archive-member schema, native entry contract, signing input or model/firmware matrix. No native SDK artifact was authenticated or downloaded.
- **PENDING:** current legitimate availability of the required target and issuer. The LG SDK 3.0.1 page lists general SDK installers, but the [official SDK introduction, p. 4](https://webostv.developer.lge.com/assets/netcast/NetCast-Using_SDK.pdf) describes IDE/emulators/tools/documents; that does not identify the Marmalade platform loader or Unity NetCast exporter. No large installer download is justified merely by that list.
- **RULED OUT (inference):** the existence of a historic runtime upload label is sufficient evidence that our standalone ARM ELF can be uploaded unchanged. The available documentation does not support that inference. This does not rule out native execution through an independently evidenced route.

Searches also surfaced community forum posts, articles and SDK mirrors. They were used only as leads to original URLs; their artifact, licensing and compatibility assertions were not promoted to confirmed findings. In particular, a discussion hosted on Unity's domain is not automatically an official Unity product statement.

## Next bounded evidence request, without a device action

The useful next acquisition is **a provenance-verifiable LG-target deployment specification or original licensed target bundle**, not another generic compiler:

1. Identify issuer, date/version and explicit NetCast 2013/model applicability. Require the documented CPU/runtime target and loader identity; do not map historical runtime names to recovered firmware enum numbers without evidence.
2. Obtain an authorized sample manifest/archive listing or published specification identifying the main artifact, required runtime files and metadata. Inspect only bounded regular members after provenance review; never execute the runtime merely to identify it.
3. Establish a current authorized issuer/account path for that artifact independently of compiler success. The observed Web-only form remains the current account evidence until a documented alternative is supplied.
4. Only then assess whether a minimal original sample can be built and packaged. Device execution, effective account, graphics ownership, normal return and automatic startup remain separate gates.

If primary artifacts cannot be obtained, keep this route **PENDING**, with the precise blocker “LG runtime target plus current issuer unavailable to this investigation”. Continue independent static integration work; do not fabricate metadata, rename the ELF as a runtime package or alter protections. No owner intervention is needed for the completed documentary work, and no contact message was sent.

## Experiment RUNTIME-001

**Objective:** identify what historic native-runtime submission actually required. **Hypothesis:** an official runtime label represented a specialized build/distribution contract rather than arbitrary ELF admission. **Environment/procedure:** public read-only LG and original-vendor pages, including timestamped archive captures; no account interaction or software acquisition. **Expected:** a precise package specification or a bounded evidence gap. **Observed:** Marmalade's CPU-binary-plus-loader model and historical eligibility are documented; Unity's LG relationship is documented through Union; the exact LG package/toolchain and current issuer remain unresolved. **Conclusion:** native build compatibility and issuer availability must be established separately. **Risks:** applying general runtime marketing to this model, treating archived licensing as current access, or confusing a portal ZIP envelope with its native payload. **Next:** seek the target specification with verified provenance before investing in legacy tool installation.
