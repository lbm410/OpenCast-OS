---
{
  "type": "Deployment Route",
  "title": "NetCast application deployment",
  "description": "Official app packaging is a useful comparison route with unresolved end-to-end availability.",
  "tags": [
    "netcast",
    "deployment"
  ],
  "status": "draft",
  "sources": [
    {
      "id": "deploy",
      "resource": "../../docs/app-deployment.md"
    },
    {
      "id": "native-issuer",
      "resource": "../../docs/native-packaging-route.md"
    }
  ],
  "opencast_evidence": [
    "CONFIRMED: documentary workflow",
    "CONFIRMED: owner-downloaded package, physical rendering and arrows/OK",
    "PENDING: successful-launch exit, repeat timing and AV continuity"
  ]
}
---

# NetCast application deployment

Both the ordinary browser and the official USB-packaged launcher have executed on the physical TV. LG documents downloadable and hosted web application tests. The owner downloaded a portal-generated package whose six source assets matched locally; protected metadata remains opaque. The first physical launch stayed black and Home returned normally. A later nested package was rejected locally. After an explicit source re-upload and relative-entry correction, the correctly nested eight-file package was copied to USB and read-back verified; it renders with owner-confirmed arrows and OK. Opening and movement are slow. This demonstrates packaged execution, not detailed entitlement semantics, acceptable performance or boot integration.[^deploy]

The IDE Run on TV workflow depends on prior USB launch; it is not an independent sideload route. webOS Developer Mode and IPK procedures are not documented NetCast deployment mechanisms. The owner operated the registration/download flow and physical launch. Successful-launch Home return, repeated timings and AV continuity remain pending.[^deploy]

A coordinated comparison can now measure the lighter candidate and repeat the exit checks. [Browser remote behavior](/execution/browser.md) and application input routing are distinct contexts. This is an intermediate step toward the [replacement shell](/product/shell.md), not an autostart solution. Persistent or privileged deployment remains gated by [recovery](/execution/recovery.md).

[^deploy]: Official workflow review and explicit availability limits.

LG also historically documented Marmalade/Unity App Test uploads. Current account availability, valid build artifact and native entitlement remain unverified; a Web package is not an arbitrary ELF loader.[^native-issuer]

[^native-issuer]: Official historical non-Web workflow and current inspection limits.
