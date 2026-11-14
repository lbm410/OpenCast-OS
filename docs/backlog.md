# Deferred product investigations

## VOICE-001 — Siri control through a local bridge

Requested by the owner on 2026-11-14. **Deferred; do not interrupt boot/firmware research or request physical tests for this now.**

Desired behavior: invoke Siri to select a TV HDMI input, launch an installed application such as Netflix where available, and potentially control volume/power. HDMI selection means changing the television input, not configuring a video output.

Feasibility: **HYPOTHESIS, promising for a separate local control adapter.** The target already advertises UDAP netrcu and mobilehome services, including application execution, but no pairing or control command has been tested. An advertised action does not establish its successful execution or permitted app IDs. Netflix availability/playback remains a separate unverified commercial-service compatibility issue; launching an app cannot repair expired service, DRM or certificate support.

Candidate route: Siri → Apple Shortcut → authenticated local bridge → verified UDAP action. Consider Home Assistant as an existing bridge before implementing another daemon. HomeKit presentation is a separate candidate requiring capability checks, not an assumed feature. Do not change router settings or expose TV/bridge endpoints publicly. A bridge needs an available host; a sleeping Mac cannot be assumed to serve it.

Primary references checked 2026-11-14:

- [Apple: run shortcuts with Siri](https://support.apple.com/guide/shortcuts/run-shortcuts-with-siri-apd07c25bb38/ios): documented voice invocation of shortcuts. Device/lock-state behavior must be evaluated for the owner's chosen Siri device.
- [Home Assistant: LG Netcast integration](https://www.home-assistant.io/integrations/lg_netcast/): existing Netcast integration to evaluate, not evidence of successful pairing or complete HDMI/application support on this exact unit.
- [LG UDAP protocol](https://webostv.developer.lge.com/assets/netcast/NetCast-UDAP.pdf): protocol basis for action-by-action verification.

Later acceptance: identify the desired Siri device and bridge host; pair locally with owner involvement; verify explicit HDMI selection and installed-app enumeration/launch; assess wake-from-standby separately; authenticate bridge requests and allowlist supported actions; report unavailable apps truthfully; test normal manual control after commands. No implementation, installation or TV state change was made for this backlog entry.
