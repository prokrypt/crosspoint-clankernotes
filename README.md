# crosspoint-clankernotes

Notes for AI coding agents ("clankers") working on CrossPoint-family e-reader
firmware: [CrossPoint Reader](https://github.com/crosspoint-reader/crosspoint-reader),
[CrossInk](https://github.com/uxjulia/crossink), forks of them, and the
[freeink SDK](https://github.com/Free-Ink/freeink-sdk) under them.

Only things that bite or matter. Every note was checked against upstream code.

## Verified against

| Tag | Repo @ commit | Date |
| --- | --- | --- |
| `cp` | crosspoint-reader/crosspoint-reader @ `099e89b` (SDK pin `2339226`) | 2026-10-01 |
| `ci` | uxjulia/crossink `development` @ `9dd334d` (SDK pin `8bbc44c`) | 2026-09-29 |
| `fi` | Free-Ink/freeink-sdk `main` @ `cd6f5b8` | 2026-09-30 |

Citations look like `cp src/main.cpp:445`. Line numbers drift; grep the symbol.
Display-library lines are the same at `fi` and `cp`'s SDK pin.
`[fork]` marks things seen only in downstream forks (CrossDink/CrossInk
forks); measured numbers come from one X4 Pro (ESP32-S3 + UC8179) unless stated.

## Files

- [display.md](display.md): panel safety (DC balance, OTP, VCOM, N2OCP, power, temperature).
- [network.md](network.md): Wi-Fi join, DHCP, TLS, OTA and SD flashing, web server.
- [memory.md](memory.md): heap, PSRAM, stacks, settings persistence, logging, power.
- [app.md](app.md): render-task races and other live app-layer bugs.
- [features.md](features.md): feature ideas upstream lacks, with evidence.
- [tools/lut_balance.py](tools/lut_balance.py): sums net drive of every LUT in an SDK checkout.

## Top rules

1. Every custom waveform LUT must be DC-balanced. Most upstream tables are not; run `tools/lut_balance.py` before touching one. ([display](display.md))
2. Never send UC8179 `0xA0`/`0xA1` (OTP program). `0xA2` is the read. ([display](display.md))
3. Hardware facts come from controller datasheets and measurements, not vendor demo code or wikis.
4. Render runs on its own task. Anything `render()` reads must be written under `RenderLock` or be safe before `onEnter()` returns. ([app](app.md))
5. `new`/`make_unique`/vector growth `abort()` on OOM (`-fno-exceptions`). Use `makeUniqueNoThrow`. ([memory](memory.md))
6. On S3, PSRAM does not rescue internal RAM: task stacks, TLS and small allocs stay internal. ([memory](memory.md))
7. `custom_sdkconfig` does not apply to the X4 Pro env. Verify in the built sdkconfig. ([memory](memory.md))
8. A close-delimited HTTP body is not proof of completeness. Require a length or hash. ([network](network.md))
9. Firmware writes are not hashed during the write pass. Don't add paths that switch boot slots without a hash match. ([network](network.md))
10. Keep shared code C3-safe (~380 KB RAM, no PSRAM) unless capability-gated.
