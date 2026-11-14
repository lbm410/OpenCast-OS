# Legitimate NetCast application deployment

Checked on 2026-11-14 against the public LG endpoints. Target: LG 47LA620S-ZA, firmware 04.28.17. The owner has now reached an application detail page in the Mac browser (screenshot evidence). Download, terms acceptance, TV installation and native TV commands remain unverified.

## Current conclusion

The ordinary browser is the only execution route physically demonstrated in this project. LG still publishes a USB App Test link and downloadable source examples. The owner has now registered the launcher and downloaded a portal-generated package, whose source assets match locally. TV-side entitlement and physical application launch have **not** been demonstrated. A working packaged-app test remains a useful next experiment, but cannot yet be scheduled as a guaranteed deployment path.

| Route | Evidence status | Current decision |
| --- | --- | --- |
| Ordinary browser → local HTTP probe | CONFIRMED (physically observed): page and click interactions work; arrow keys currently move its cursor. | Continue bounded input research. This is not the NetCast app runtime or final shell. |
| App Test → downloadable web app → USB | CONFIRMED (documentary); PENDING end-to-end availability. | Portal package downloaded and inspected; USB prepared. Physical launch remains pending. |
| App Test → hosted URL-based web app → USB launcher | CONFIRMED (documentary); PENDING packaging, LAN URL acceptance and launch. | Potentially easier iteration, but still depends on App Test and entitlement. |
| LG IDE “Run on TV” | Documented workflow requires prior USB launch. | Not an independent sideload channel or packaging bypass. |
| webOS Developer Mode / IPK tooling | RULED OUT as a documented NetCast deployment route. | Do not apply webOS instructions to this TV. |

The input-runtime distinction is detailed in [input-routing.md](input-routing.md). LG's [2023 response about another NetCast model](https://forum.webostv.developer.lge.com/t/32lf580u-za-developer-mode/1952) explicitly excludes the webOS Developer Mode app; it does not prove this model's USB entitlement currently works.

## What actually responds today

CONFIRMED (local HTTP observation): the [legacy NetCast page](https://webostv.developer.lge.com/more/netcast) links USB App Test to:

`https://developer.lge.com/apptest/retrieveApptestOSList.dev`

A bounded HTTPS GET with certificate validation and redirects disabled returned HTTP 200 and a 15,085-byte HTML document. This document contains `body onload="fncGotoLogin();"`; that function submits the page's return form to `/secure/RedirectEmpFront.dev`. No App Test list or usable app-registration form was present in this unauthenticated response. The form was **not** submitted. No session cookies, credentials or headers were saved.

The source also defines a function containing the message `Service Unavailable.`. It is not the function selected by the observed body-load handler. Its mere presence is **not** evidence that App Test has closed. Conversely, HTTP 200 is **not** evidence that packaging works. The browser automation host was unavailable, so no visual browser/login-flow result is claimed.

CONFIRMED (owner-reported, 2026-11-14): the owner opened the App Test page on the Mac and reports that **New App Test** is visible. This establishes that the application-management entry point is reachable in the owner's browser; the form contents and account state have not been independently inspected.

CONFIRMED (owner-provided screenshots): the registration form accepts a Web source ZIP (advertised maximum100MB) and a square JPG/GIF/PNG icon (recommended greater than200×200, maximum100KB). The subsequent detail page displays LauncherTest, Web > All, our supplied launcher icon, in-app purchase Disabled and a Download DRM applied file section with Terms and Conditions and Download controls. The exact submitted URL/entry value and uploaded file bytes have not been inspected. The Progress95% value appears under CP Option Information; it is not evidence of packaging progress.

PENDING: successful DRM package download, package content/entry validation and TV entitlement retrieval. A public-document search found no verified shutdown notice resolving these questions. Absence of a notice is not evidence of service health.

## Documented submission and launch contract

CONFIRMED (documentary): [LG's deployment guide, printed pages 3–9 and 14–19](https://webostv.developer.lge.com/assets/netcast/NetCast-Deploying_and_Testing_App_on_Real_TV.pdf) describes:

- A downloadable Web application uploads a ZIP and supplies an HTML entry path relative to its root, such as `index.html`. A hosted application supplies its server URL instead of source ZIP content.
- The form requests an application title, Web type, subtype and icon; nonpartners select subtype `All`.
- App Test produces the DRM package. Its numbered application directory is placed under `lgapps/installed/` on USB, then opened through MyApps/USB after TV account sign-in.
- TV launch depends on receiving decryption entitlement from LG's SDP service; a local HTML ZIP alone does not satisfy that requirement.
- LG IDE run/debug still depends on launching through USB first. The guide warns that an unnecessary LG Inspector directory can disrupt Back/Home and freeze the application.

These historical instructions describe a supported mechanism, not current backend availability. They do not authorize changing region, updating firmware or weakening TLS to restore an old service. A hosted app loaded through the application launcher has a different entry context from typing the same URL in the ordinary browser.

## Official source samples: available and inspected

CONFIRMED (local): both ZIP files linked by [LG Tools and Samples](https://webostv.developer.lge.com/more/netcast/tools-samples) downloaded successfully with HTTP 200. Downloads were bounded to 5 MB and 1.5 MB respectively, with redirects disabled. They remain under ignored `artifacts/app-research/`. No JavaScript from them was executed, no files were installed and no archive-wide extraction was performed.

| Official resource | Download size | SHA-256 |
| --- | ---: | --- |
| [ImageViewer source](https://webostv.developer.lge.com/assets/netcast/webappsample_imageviewer.zip) | 3,618,723 bytes | `70e2c309e2c67b736b59cf0a29e88dd4e4aa1d14d73b7df7d2a747dbc74831cb` |
| [ImageViewer framework](https://webostv.developer.lge.com/assets/netcast/webappsample_imageviewerframework.zip) | 829,274 bytes | `27aad6c8f3625d87bf0382668cb9bd4617ad58a62c61ae0d6c3aac85b2e90f74` |

ZIP inventories contain 45 entries / 3,960,865 expanded bytes and 57 entries / 1,003,245 expanded bytes. Selected, size-checked text members were read directly from the archives:

```text
app/index.html
app/css/style.css
app/js/main.js
app/js/jquery-1.8.2.min.js
lge/framework/ImageViewer/api/api.js
lge/framework/ImageViewer/util/keycode.js
```

The sample HTML references its sibling `lge/` framework. `main.js` registers a document keydown handler and guards calls to NetCast Back/Exit methods. The keycode file defines the expected arrows, OK and Back. Neither archive contains a manifest/config/appinfo-named member. These are source examples, **not** portal-generated USB packages; this observation does not establish that a generated package has no metadata.

The [official ImageViewer quick-start guide, printed pages 7–8](https://webostv.developer.lge.com/assets/netcast/web_app_development_quick_start_guide_webappsample_imageviewer.pdf) likewise describes ordinary HTML/CSS/JavaScript under the IDE's WebContent directory and permits using a general editor. Therefore, installing the entire legacy IDE is unnecessary for preparing our own source-only test ZIP. The old sample's jQuery/framework dependencies are reference material, not dependencies selected for OpenCast OS.

A candidate submission can be assembled from our own probe with `index.html`, its local CSS/JavaScript and no Inspector. The portal entry path must match the ZIP root. This source ZIP would be an **input to App Test**, never a claimed ready-to-install package. Portal-generated files must subsequently be inventoried and reviewed before USB use.

## SDK availability versus host compatibility

CONFIRMED (local/documentary): the [SDK 3.0.1 page](https://webostv.developer.lge.com/more/netcast/sdk-v301) still serves public metadata for seven installer parts/variants. Linux64 is advertised at about 1,649 MB and Mac64 at about 1,621 MB. Its public page code opens a download modal carrying terms and a file identifier. No terms were accepted and no installer was downloaded; advertised metadata is not verified payload availability.

LG lists historical Intel-era operating systems, JRE 1.6 and VirtualBox 4.1/4.2 requirements. No compatibility with Apple Silicon/macOS Tahoe is established. Avoid installing an old VM, Java runtime or privileged installer merely to create HTML files. The [2022 forum notice that download links were repaired](https://forum.webostv.developer.lge.com/t/netcast-sdk-downloads/395) is historical evidence, not a current end-to-end download test.

LG's [technical notes](https://webostv.developer.lge.com/more/netcast/technical-notes) exclude certain later LH55–LH58 lightweight products from USB testing. That exception must not be transferred to the LA620S without model-specific evidence.

## Proposed experiment APP-001: availability before installation

- **Objective:** establish whether legitimate packaging is still reachable, independently of TV execution.
- **Hypothesis:** owner authentication exposes the historical App Test list and New App Test workflow.
- **Environment:** owner's normal desktop browser and LG account; no TV state change.
- **Minimum owner action:** open the exact USB App Test URL above, sign in personally if requested, and report whether a NetCast application list/New App Test form or a specific error appears. No password or session export is needed. Do not create an account or accept new terms solely to satisfy this probe without reviewing them.
- **Procedure after a positive result:** prepare the tiny source ZIP and separate icon locally; review the actual form against the historical contract. Coordinate any upload/terms step explicitly, obtain the generated package and inspect its bounded inventory. Do not place a raw source ZIP under `lgapps/installed` as if it were the DRM output.
- **Expected result:** a genuine app-management form; later, a generated package. A successful sign-in alone is insufficient.
- **Observed result:** public login-routing HTML was captured locally. The owner subsequently reports seeing **New App Test** in the Mac browser; form inspection and packaging remain PENDING.
- **Conclusion and risks:** account interaction is the remaining availability boundary, not a reason to stop firmware or browser research. No credentials are needed by the agent. TV sign-in/USB launch, normal return and entitlement behavior form a separate coordinated reversible experiment.
- **Next step:** if the service is unavailable after authentication, record the exact non-sensitive error and stop retrying. Continue the browser focus/event experiment and static native-platform analysis. Do not invent an offline signer, sideload bypass or service-menu route.

## Local evidence and reproducibility

Ignored `artifacts/app-research/` contains the unauthenticated public HTML, SDK/tools pages, the SDK page's public script, both unchanged sample ZIPs, their JSON member inventories and `local-inventory.json` with sizes/hashes. Repeating only the listed public GETs is sufficient to reproduce the unauthenticated findings. Dynamic page hashes may change; sample hashes identify this inspection. Do not publish captured page bodies or vendor archives as project source.


## Prepared source bundles (local only)

`tools/netcast_source.py` builds deterministic source ZIPs from fixed project asset lists. It never walks the repository, includes vendor files, signs an application, uploads data or contacts the TV. ZIP timestamps and file modes are fixed; JPEG content is stored without recompression. The portal entry path is `index.html` at the ZIP root.

```sh
mkdir -p artifacts/netcast-source
python3 -m tools.netcast_source probe --output artifacts/netcast-source/input-probe-source.zip
python3 -m tools.netcast_source shell --output artifacts/netcast-source/launcher-source.zip
```

Output paths must be new; existing files are never overwritten. Current generated artifacts (2026-11-14) are ignored:

| Source | Bytes | SHA-256 |
| --- | ---: | --- |
| Input probe | 15429 | `91ce6ceb24bc5190b46df1bb6559c9289e9a0104e3aa97fe103239dcf4c7e874` |
| Launcher | 214097 | `b0b305112ec1bc9bc6a5a8a7416e25219c64fffa2f8d5299ea2665621d9d3dac` |

Two local tests verify deterministic ZIP bytes/root entry/current-asset completeness and exclusion of unlisted or symlinked input. These are source inputs only, **not USB-installable DRM packages**. These source bundles were prepared before the owner registered the launcher. The later portal package and USB preparation are recorded below; source ZIPs themselves remain unsuitable for direct installation.


## APP-001 download result

CONFIRMED (local, 2026-11-14): the owner downloaded the portal output into Downloads. The222489-byteZIP has SHA-256 `67eeeb5b0c025b831948092732291a8ad46ebf98989e5d4f240269b6a3b51143`,14entries and240501expanded bytes. All six launcher source assets match the submitted local source byte-for-byte. Additional entries comprise four generated icons, a one-byte developer.test marker and a1570-byte manifest.xml beginning with `NCGFILE_HEADER`. The manifest was not decrypted; entry-path semantics and TV entitlement remain unverified. ZIP-level encryption flags are absent; this does not imply that the manifest is plaintext.

A fixed allowlist of the12regular files was read with size limits and CRC verification, then copied into a new ignored staging tree under `artifacts/netcast-source/usb-ready/lgapps/installed/`. No general archive extraction, target-code execution or USB/device write occurred. The numbered application directory is preserved locally. The owner has been asked whether a USB drive is available; no formatting is proposed.


## Authorized USB preparation

CONFIRMED (local): the owner explicitly requested erasing the connected USB drive, including its old BIOS file, and copying the application. The sole external physical disk matched the owner's description: a4GB USB removable TDK Trans-It volume named BIOS. Device identity, size, external/physical status and mount were rechecked immediately before `diskutil eraseDisk`. No other disk was modified.

The drive was formatted FAT32 with an MBR partition map and label OPENCAST. The portal-generated application's12files were copied beneath `lgapps/installed/<portal-app-id>/`, then each file was read back and compared byte-for-byte with the inspected package (240501bytes total). The drive was successfully ejected. The private per-file verification report is in ignored `artifacts/netcast-source/usb-copy-verification.json`. No TV execution has occurred; the next step is owner-coordinated USB discovery and launch with Home as the intended return path.


## Revised download: nested package rejected before USB replacement

CONFIRMED (local): after the owner reports setting index.html and downloading again, the224096-byte ZIP has SHA-256 `460e208d0e4687e26570ae0597b8680049b4d2730a4d5db06dbe47a8a149d9af`. It contains17entries. All12files from the first portal output, including its old protected manifest, reappear byte-identically under an extra app-ID directory. The new outer directory contains a new1580-byte protected manifest and developer.test, but no index.html. Thus the requested relative entry index.html does not match the new visible package layout. The precise portal/input cause is unknown; do not infer a user mistake or decrypt/patch the manifest.

No USB file was changed. The original six-asset source ZIP still has index.html at root and no vendor manifest. The next correction is to explicitly upload that original source ZIP again in Modify, use the form's File Upload action, check that the source tree shows index.html directly at root, retain URL index.html and save/download. The resulting package must be rechecked before replacing USB content.


### APP-001 source re-upload and corrected USB package

CONFIRMED (local): the next owner download is196778bytes, SHA-256 `d348ae50f8e059449fee3d3569b0a9df490c44f5cfe4f708ef2479777b2d42d2`. Its10ZIPentries contain a single app-ID directory, assets directory and8files totaling215044bytes. index.html is directly under the app root; all six launcher source assets match byte-for-byte. The new protected manifest is retained intact. This output contains no separate generated icon files; do not invent or patch protected metadata to add them.

The existing USB app's12files matched the prior verification report. Additional AppleDouble sidecars were bounded and recognized before removal. Only the app folder was replaced, with a temporary rollback directory during copying; all8new files were read-back verified. Cleanup handled macOS automatically removing paired sidecars when deleting their data files. The rollback directory was removed and disk ejection succeeded. No formatting occurred. The verification report is ignored artifacts/netcast-source/usb-copy-v2-verification.json. Next: owner repeats launch and observes rendering, remote navigation and Home return. Successful TV execution remains pending.
