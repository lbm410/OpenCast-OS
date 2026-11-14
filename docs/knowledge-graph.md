# Explore the OpenCast knowledge graph

**16 concepts · 63 directed relationships · 4 groups.** Built from the actual OKF bundle, not a hand-drawn architecture claim.

[Open the bundle index](../knowledge/index.md) or [download the interactive graph](../knowledge/graph.html). GitHub displays the HTML source; save the repository and open `knowledge/graph.html` locally for search, filters and selectable connections. No hosting, CDN, installation or network fetch is required. Keep the repository layout for its manual Markdown/report links.

The navigation overview below includes all concepts and 15 actual relationships selected as a spanning forest. Arrow direction is preserved. The local viewer contains all 63 relationships and shows only the selected node's connections to keep the map readable. A link means a knowledge relationship; its surrounding concept prose explains the dependency or evidence context.

All current summaries are draft and unverified in OKF's review-event sense. Their evidence labels distinguish physical observations, static results and open hypotheses; they do not imply a working replacement OS.

```mermaid
flowchart LR
  subgraph product["Product"]
    n14["OpenCast replacement shell"]
    n15["Deferred Siri bridge"]
  end
  subgraph execution["Execution"]
    n2["NetCast application deployment"]
    n3["Physical browser probe"]
    n4["Read-only LAN surface"]
    n5["Recovery gate"]
  end
  subgraph platform["Platform"]
    n6["Firmware ABI"]
    n7["Boot and init chain"]
    n8["Official firmware evidence"]
    n9["Graphics and input boundary"]
    n10["Kernel image"]
    n11["Partition-map evidence"]
    n12["RELEASE system application"]
    n13["Target television"]
  end
  subgraph engineering["Engineering"]
    n0["Bounded knowledge loading"]
    n1["Evidence and validation scopes"]
  end
  n0 --> n14
  n2 --> n14
  n3 --> n14
  n4 --> n14
  n5 --> n14
  n7 --> n14
  n9 --> n14
  n12 --> n14
  n15 --> n14
  n0 --> n1
  n6 --> n2
  n13 --> n4
  n10 --> n5
  n5 --> n11
  n8 --> n1
  click n0 "../knowledge/engineering/knowledge-loading.md" "Open concept"
  click n1 "../knowledge/engineering/validation.md" "Open concept"
  click n2 "../knowledge/execution/app-deployment.md" "Open concept"
  click n3 "../knowledge/execution/browser.md" "Open concept"
  click n4 "../knowledge/execution/local-control.md" "Open concept"
  click n5 "../knowledge/execution/recovery.md" "Open concept"
  click n6 "../knowledge/platform/abi.md" "Open concept"
  click n7 "../knowledge/platform/boot.md" "Open concept"
  click n8 "../knowledge/platform/firmware.md" "Open concept"
  click n9 "../knowledge/platform/graphics-input.md" "Open concept"
  click n10 "../knowledge/platform/kernel.md" "Open concept"
  click n11 "../knowledge/platform/partitions.md" "Open concept"
  click n12 "../knowledge/platform/release.md" "Open concept"
  click n13 "../knowledge/platform/target.md" "Open concept"
  click n14 "../knowledge/product/shell.md" "Open concept"
  click n15 "../knowledge/product/siri.md" "Open concept"
```

If a renderer disables Mermaid click actions, use these ordinary links:

## Product

- [OpenCast replacement shell](../knowledge/product/shell.md) — A modern shell over retained vendor services is the leading unproven integration architecture.
- [Deferred Siri bridge](../knowledge/product/siri.md) — Voice control is a separate local-adapter investigation, not a completed feature.

## Execution

- [NetCast application deployment](../knowledge/execution/app-deployment.md) — Official app packaging is a useful comparison route with unresolved end-to-end availability.
- [Physical browser probe](../knowledge/execution/browser.md) — Own code ran on the TV, while direct D-pad input and repeat-load acceptance remain incomplete.
- [Read-only LAN surface](../knowledge/execution/local-control.md) — Discovery established UDAP and DLNA descriptions, not tested television control actions.
- [Recovery gate](../knowledge/execution/recovery.md) — Persistent integration requires a demonstrated recovery procedure for this exact hardware.

## Platform

- [Firmware ABI](../knowledge/platform/abi.md) — ARM executable evidence without claiming an established native deployment environment.
- [Boot and init chain](../knowledge/platform/boot.md) — Shipped startup paths and the gaps before asserting live process supervision.
- [Official firmware evidence](../knowledge/platform/firmware.md) — Container identity, integrity coverage and preserved offline analysis inputs.
- [Graphics and input boundary](../knowledge/platform/graphics-input.md) — Static graphics/runtime evidence and the unresolved path to native remote navigation.
- [Kernel image](../knowledge/platform/kernel.md) — Decoded Linux image evidence and unresolved board-level dependencies.
- [Partition-map evidence](../knowledge/platform/partitions.md) — Static paired storage regions do not establish active banks or automatic rollback.
- [RELEASE system application](../knowledge/platform/release.md) — The main executable is coupled to television services, not proven to be a disposable launcher.
- [Target television](../knowledge/platform/target.md) — Exact target identity and the boundary between owner, network and physical hardware evidence.

## Engineering

- [Bounded knowledge loading](../knowledge/engineering/knowledge-loading.md) — Load one task concept and its immediate neighbors before opening detailed reports.
- [Evidence and validation scopes](../knowledge/engineering/validation.md) — Host tests, static firmware results and physical observations answer different questions.

## Rebuild the views

```sh
python3 -m tools.knowledge_view
python3 -m tools.knowledge_view --check
python3 -m unittest discover -s tests -p 'test_knowledge_view.py' -v
```

The generator reads concepts and graph edges without fetching source resources. Concept text is displayed as text, never interpreted as HTML. Generated views are deterministic; detailed reports remain the evidence record.

The initial 2026-11-14 export passed six generator tests covering script-termination injection, unsafe links, deterministic HTML/Markdown/SVG, real graph counts and malformed concept relationships. Local isolated Chrome checks confirmed search, category filtering, node selection and neighbor navigation, with no JavaScript exceptions. Desktop (1600 × 1150) and mobile-width (390 × 844) screenshots were inspected; neither layout had horizontal overflow. These checks validate the documentation viewer on the host, not the TV runtime.
