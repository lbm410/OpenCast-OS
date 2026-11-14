# Target hardware evidence

Date: 2026-11-14. Network identity matched one responding device to the exact owner-provided model and firmware. Network announcements are self-reported, not cryptographic attestation.

| Item | Evidence | Status |
| --- | --- | --- |
| LG 47LA620S-ZA, 47-inch Full HD panel, 2013, NetCast | Owner supplied model/panel/year; exact model also appears in UDAP | CONFIRMED owner-reported; model additionally device-reported |
| Installed firmware 04.28.17 | Owner and UDAP SERVER advertisement agree | CONFIRMED device-reported |
| Displayed SDK 03.05 | Owner's product information; EPK header contains 03.05.000 | CONFIRMED owner-reported and local artifact string; relationship requires interpretation |
| Kernel Linux/3.0.13 | UDAP SERVER value and decoded official kernel banner; uImage CRCs verified | CONFIRMED device-reported and static firmware; see lz4p-analysis.md |
| MTK5398 / M13 family | Official EPK filename; matching community research | LIKELY, physical SoC not verified |
| Firmware userspace architecture / ABI / endianness | Selected official firmware ELF headers, including RELEASE and lginit | CONFIRMED static firmware: ARM32 little-endian EABI5; float ABI unresolved; physical SoC not independently inspected |
| Firmware loader / libc | ld-2.12.2.so, libc-2.12.2.so; ELF interpreter /lib/ld-linux.so.3 | CONFIRMED static filenames/ELF metadata; full ABI symbol versions pending |
| RAM, active flash layout, GPU, bootloader behavior, MICOM | Partition metadata and graphics components under static investigation; no physical runtime inspection | PENDING; shipped metadata is not proof of active layout or usable recovery |
| SSH, Telnet, ADB | Not tested or assumed | PENDING |

## Verified network surface

Local private captures are stored under artifacts/diagnostics/ and excluded from Git. Current IPs belong in that operational record, not in a public hardware inventory.

- UDAP TCP 8080: advertised rootservice descriptor returned HTTP 200. Device type TV; manufacturer LG Electronics; model string 47LA620S-ZA_96.
- DLNA TCP 1985: advertised descriptor returned HTTP 200. MediaRenderer with ConnectionManager, RenderingControl and AVTransport service descriptions. No SOAP commands invoked.
- UDAP services: netrcu, mobilehome, smartText and AppToApp. Their presence does not establish permission to execute arbitrary local apps or launch at boot.
- Two ICMP probes returned, 0% packet loss; RTT 4.050–7.694 ms, mean 5.872 ms. Small connectivity sample, not a navigation latency benchmark.

The first successful discovery sent two datagrams and found both descriptions on the same IP. No unrelated hosts were probed and no port sweep was performed.

## Next evidence to collect

ELF headers and dynamic dependencies, verified firmware partition metadata, kernel build configuration, init chain and process responsibilities. Later device observation must distinguish storage capacity from free memory and a family specification from the actual unit.
