# CYM project direction — owner-confirmed agent memory

## Identity and boundary

CYM (Cheap Yellow Monster / CYM Laboratorium) remains its own existing multi-board firmware project. ESM (Electro Magnetic Monster) is a separate, independently developed proprietary PinZero Labs flagship, not a CYM rename, a Tab5 fork, or an instruction to merge donor repositories. Work on CYM only changes CYM unless Jim explicitly authorizes another project's scope. Shared concepts do not grant source/artwork reuse rights.

## Requested added tools

- Biscuit protocol support is an additional CYM tool. Current direction is CYM as a touchscreen BLE/GATT client to external Biscuit hardware, including supported control, scan results and wardrive data. Preserve existing CYM tools. This does not mean replacing CYM with Biscuit firmware or promising that Biscuit Manager can control CYM. The canonical backlog already records the satellite plan; refine it rather than creating competing plans.
- MonsterC5 / MonsterRF control is an additional CYM tool. Use the actual accessory's supported UART or SPI host interface. The Tab5 JanOS reference documents UART; SPI between a Monster MCU and its RF chips is not automatically a SPI command interface to CYM. Exact module revision, logic voltage, pinout, baud/framing and commands need qualification for each CYM board.
- Reconcile with the earlier carrier-board and satellite plan in BACKLOG.md and project_satellite_integration.md. Do not declare its prototype pin assignments, mesh behavior, CSV equivalence or zero-coexistence-conflict assumptions hardware-proven. Preserve RF-HAT/display/SD/GPS ownership; adding a satellite must not silently disrupt existing functions.

## References and evidence limits

- Biscuit public integration: https://codehedge.github.io/Biscuit-Wiki/3rd-party-integration/index.html and gatt-reference.html. Read the actual supported BLE/GATT lifecycle and framing; no mandatory ping/hello is implied. Connection timing and Wi-Fi/BLE coexistence still need hardware tests.
- Tab5 controller reference: https://github.com/JimGat/M5MonsterC5-Tab5 (upstream C5Lab/M5MonsterC5-Tab5). It remains a separate reference repository. Its JanOS UART guide is not proof of the enhanced RF fork's complete command contract.
- Jim supplied https://janosrf.neocities.org/ as the binary-only JanOS SubGHz reference. It claims original LAB5 C5Monster + specific CC1101 wiring, a UART-friendly console and subghz_protocols. Advertised registry entries are not measured decoder coverage; BinRAW is explicitly unimplemented and some families are RX-only. No full protocol/pin/baud contract or explicit license was found on that page. Do not transfer another project's MIT license to this binary.

## Execution rules

Read .claude/rules/cym-canonical-workflow.md before firmware work. Use one writer on ESP32-Dev, Jimgat_Dev, and the established affected-board build/packaging workflow. Implement one integration track at a time after its scoped design is approved. Planned capability, compiled capability and physical compatibility are separate claims. This memory records requirements; it does not implement the tools, authorize flashing, publish releases, or authorize source imports.
