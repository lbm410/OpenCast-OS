# Risk boundaries and recovery

No independent recovery procedure has been verified for this physical unit. Do not flash, repartition, change boot scripts, modify service-menu settings or install privileged persistent components.

| Level | Scope | Current policy |
| --- | --- | --- |
| 0 | Documentary work, local code, static firmware analysis | Authorized; never execute extracted firmware |
| 1 | Bounded LAN discovery, descriptors and connectivity | Authorized for the identified target; no unrelated devices |
| 2 | Temporary application execution or state changes | Explain effects and exit path, coordinate owner action |
| 3 | Privileged/persistent changes, boot, partitions, service menu | Specific authorization plus verified recovery required |

For the browser probe, the intended return path is the browser's normal Back/Exit/Home control. The page does not call native control APIs or intercept those keys. The owner confirmed that Home returned to the ordinary Smart menu in HW-001. Broader function checks and repeat-load validation remain incomplete. Stop if normal controls behave unexpectedly; do not escalate into service-menu experimentation to force an exit.

Before any persistent proposal, identify the physical hardware and affected files, establish compatibility, evaluate alternatives, document failure modes, prove an independent recovery mechanism, define verification and rollback, and obtain specific owner authorization. A downloaded update package or successful root shell does not satisfy this gate.

Firmware hashes provide reproducibility and CRC detects archive corruption. Neither validates vendor signatures or supplies a trusted boot/recovery chain. Proprietary graphics/media libraries, watchdogs and power-control dependencies may make the original UI process operationally essential.

The probe server binds to one explicit host IP and accepts only the confirmed TV peer. It serves an asset allowlist, never the workspace. No router forwarding, UPnP mapping, public tunnel or external TV service is required. Stop it with Ctrl-C when the experiment is complete.
