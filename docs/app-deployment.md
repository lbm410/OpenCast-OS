# Legitimate NetCast application deployment

Checked on 2026-11-14 against the public LG endpoints. Target: LG 47LA620S-ZA, firmware 04.28.17. No account login, upload, terms acceptance, TV installation or native TV command occurred.

## Current conclusion

The ordinary browser is the only execution route physically demonstrated in this project. LG still publishes a USB App Test link and downloadable source examples. The unauthenticated App Test response routes visitors toward account login; a functioning packaging backend and TV-side entitlement service have **not** been demonstrated. A working packaged-app test remains a useful next experiment, but cannot yet be scheduled as a guaranteed deployment path.

| Route | Evidence status | Current decision |
| --- | --- | --- |
| Ordinary browser → local HTTP probe | CONFIRMED (physically observed): page and click interactions work; arrow keys currently move its cursor. | Continue bounded input research. This is not the NetCast app runtime or final shell. |
| App Test → downloadable web app → USB | CONFIRMED (documentary); PENDING end-to-end availability. | Preferred packaged comparison if owner login exposes the real service. |
| App Test → hosted URL-based web app → USB launcher | CONFIRMED (documentary); PENDING packaging, LAN URL acceptance and launch. | Potentially easier iteration, but still depends on App Test and entitlement. |
| LG IDE “Run on TV” | Documented workflow requires prior USB launch. | Not an independent sideload channel or packaging bypass. |
| webOS Developer Mode / IPK tooling | RULED OUT as a documented NetCast deployment route. | Do not apply webOS instructions to this TV. |

The input-runtime distinction is detailed in [input-routing.md](input-routing.md). LG's [2023 response about another NetCast model](https://forum.webostv.developer.lge.com/t/32lf580u-za-developer-mode/1952) explicitly excludes the webOS Developer Mode app; it does not prove this model's USB entitlement currently works.

## What actually responds today

CONFIRMED (local HTTP observation): the [legacy NetCast page](https://webostv.developer.lge.com/more/netcast) links USB App Test to:

`https://developer.lge.com/apptest/retrieveApptestOSList.dev`

A bounded HTTPS GET with certificate validation and redirects disabled returned HTTP 200 and a 15,085-byte HTML document. This document contains `body onload="fncGotoLogin();"`; that function submits the page's return form to `/secure/RedirectEmpFront.dev`. No App Test list or usable app-registration form was present in this unauthenticated response. The form was **not** submitted. No session cookies, credentials or headers were saved.

The source also defines a function containing the message `Service Unavailable.`. It is not the function selected by the observed body-load handler. Its mere presence is **not** evidence that App Test has closed. Conversely, HTTP 200 is **not** evidence that packaging works. The browser automation host was unavailable, so no visual browser/login-flow result is claimed.

PENDING: authenticated page accessibility, new-app creation, DRM output generation, download and TV entitlement retrieval. A public-document search found no verified shutdown notice resolving these questions. Absence of a notice is not evidence of service health.

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
- **Observed result:** public login-routing HTML only; authenticated behavior PENDING.
- **Conclusion and risks:** account interaction is the remaining availability boundary, not a reason to stop firmware or browser research. No credentials are needed by the agent. TV sign-in/USB launch, normal return and entitlement behavior form a separate coordinated reversible experiment.
- **Next step:** if the service is unavailable after authentication, record the exact non-sensitive error and stop retrying. Continue the browser focus/event experiment and static native-platform analysis. Do not invent an offline signer, sideload bypass or service-menu route.

## Local evidence and reproducibility

Ignored `artifacts/app-research/` contains the unauthenticated public HTML, SDK/tools pages, the SDK page's public script, both unchanged sample ZIPs, their JSON member inventories and `local-inventory.json` with sizes/hashes. Repeating only the listed public GETs is sufficient to reproduce the unauthenticated findings. Dynamic page hashes may change; sample hashes identify this inspection. Do not publish captured page bodies or vendor archives as project source.
