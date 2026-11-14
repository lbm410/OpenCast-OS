# NetCast development research

Initial review: 2026-11-14. Links are evidence sources, not instructions to execute historical installers or device payloads.

## Official application path

The [SDK 3.0.1 page](https://webostv.developer.lge.com/more/netcast/sdk-v301) targets 2013 and later NetCast models, but lists historical macOS/Java/VirtualBox requirements. Compatibility with modern Apple Silicon is unverified; Rosetta alone cannot reproduce an old OS or x86 VM environment. The SDK shown by the TV is not automatically the downloadable SDK version.

The [real-TV deployment guide](https://webostv.developer.lge.com/assets/netcast/NetCast-Deploying_and_Testing_App_on_Real_TV.pdf) describes USB deployment through LG DRM packaging, an application-ID directory under lgapps/installed, TV account sign-in and retrieval of decryption keys. It also describes LG IDE/Inspector debugging. These are historical documented capabilities, not a verified working service today. The [App Test endpoint](https://developer.lge.com/apptest/retrieveApptestOSList.dev) returned a page, but authenticated packaging and TV login have not been tested.

The [FAQ](https://webostv.developer.lge.com/more/netcast/netcast-faq) provides additional USB, DIAL and historical TLS information. DIAL/UDAP launch APIs do not establish arbitrary-app installation, full native API access or boot autostart. Fullscreen app behavior and original-remote integration remain target-specific experiments.

## Browser path

The [platform specifications](https://webostv.developer.lge.com/more/netcast/platform-specifications) describe NetCast 4.0 profiles with WebKit 537.1+, partial HTML5/CSS3 and recommended 720p graphics. These are a conservative design starting point, not measured unit capabilities. HW-001 uses classic HTML/CSS, system fonts and dependency-free JavaScript to obtain actual browser/input evidence.

A normal browser page may lack native APIs available to packaged apps. The probe checks only whether selected symbols exist; it never invokes them. No support is claimed for current commercial streaming clients, DRM, TLS or codecs.

## Local protocol

The [UDAP specification](https://webostv.developer.lge.com/assets/netcast/NetCast-UDAP.pdf), pp.7–11, defines SSDP-style discovery and descriptor retrieval. The target has now responded to that path. B-SEARCH is documented but not implemented; the successful multicast test makes a fallback unnecessary for this run.

The [open remote-control project](https://github.com/JosephDoesLinux/lg-netcast-remote) was inspected at HEAD 3a43fdf0fe22969ff431cc15badcf00761838278. Review covered its tree, Net.kt and recent history; this was not a complete audit. HTTP parser resource limits deserve scrutiny before reuse. It was not executed or incorporated into our code. A remote-control application does not replace the TV launcher.

## Deeper system replacement

See [platform research](platform-research.md) and [firmware evidence](firmware.md). Prioritize identifying the real boot and service graph before selecting a graphics runtime/toolchain. Whether the visual shell can be separated from essential TV services is still a hypothesis.

Additional official references: [NetCast overview](https://webostv.developer.lge.com/more/netcast), [Using SDK](https://webostv.developer.lge.com/assets/netcast/NetCast-Using_SDK.pdf), [LG exact-model applicability list](https://www.lg.com/hr/podrska/proizvod/lg-47LA620S.AEE). The Using SDK manual has only been partially reviewed; documentation review is ongoing.
