# OpenCast OS

An open-source research project to replace the legacy LG NetCast experience with a modern, fast and customizable Smart TV system, while preserving the original hardware's essential functions.

**Target:** LG 47LA620S-ZA, owner-reported firmware 04.28.17, confirmed by its network advertisement. **Status:** early research. There is no installable replacement OS or verified boot integration. The physical browser probe executed and returned normally to the Smart menu using Home. Direct D-pad navigation and repeat-load validation remain incomplete.

## What currently works

- Bounded SSDP/UDAP discovery and read-only service descriptions, verified against the target TV.
- Official firmware acquisition, SHA-256 inventory and explicit bounded extraction of its single EPK member. No firmware binaries have been executed.
- A minimal browser capability/remote-control probe and a local server restricted to one peer. Two device reports and owner-confirmed return to the Smart menu were obtained. The experiment server is stopped; complete M3 acceptance remains pending.
- Automated tests for network scope, hostile inputs, firmware inventory/extraction and navigation.

## Run locally

Host requirements: Python 3.10+ on macOS/Linux; Node.js 18+ for JavaScript tests. No third-party runtime packages. Tested with Python 3.13.5 and Node 22.16.0 on Apple Silicon. Node does not run on the TV.

```sh
python3 -m unittest discover -s tests -v
node --test tests/test_navigation.cjs tests/test_probe_client.cjs
python3 -m tools.discovery --help
python3 -m tools.firmware_analysis --help
```

Discover on the owner's local subnet, substituting current addresses:

```sh
python3 -m tools.discovery discover --interface-ip MAC_IP --network LOCAL_SUBNET/24
python3 -m tools.discovery describe --confirmed-target TV_IP --network LOCAL_SUBNET/24 --location ADVERTISED_LOCATION_URL
```

Discovery sends two multicast queries with TTL 1. It never sweeps addresses or automatically fetches responders' descriptors. The description command makes one GET to a confirmed literal IP. No pairing or control commands are implemented. Current scope validation accepts RFC1918 /24 or narrower subnets.

Run the probe for desktop-only development:

```sh
python3 -m tools.probe_server
```

For the physical TV experiment, follow [the deployment protocol](docs/hello-world.md). Never serve the repository or firmware directory directly.

## Engineering record

- [Current handover](docs/handover.md) and [experiments](docs/experiments.md)
- [Hardware evidence](docs/hardware.md) and [firmware triage](docs/firmware.md)
- [Platform and boot research](docs/platform-research.md)
- [Static boot dependency map](docs/boot-dependencies.md) and [agent coordination channel](collaboration/README.md)
- [NetCast development options](docs/research.md), [input routing](docs/input-routing.md) and [compatibility](docs/compatibility.md)
- [Decisions](docs/decisions.md) and [recovery boundaries](docs/recovery.md)
- [Contributor/agent rules](AGENTS.md) and [Claude Code workflow](CLAUDE.md)

## License and publication

[GPLv3](LICENSE), as selected by the owner in the upstream repository. Vendor firmware and third-party components retain their own terms and are not distributed here. Captures, firmware, downloads and generated device reports are ignored by Git. Do not contribute credentials, pairing PINs, unique device identifiers or private dumps.
