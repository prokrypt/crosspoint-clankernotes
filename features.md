# Feature ideas upstream lacks

Checked against `cp` ROADMAP.md / SCOPE.md: none is on the roadmap. Each
must stay C3-safe unless gated. "Absent" = grep of `cp`, `ci`, `fi`.

| # | Idea | Why | C3 cost | Upstream |
| --- | --- | --- | --- | --- |
| 1 | Compile-time DC-balance gate: every LUT upload goes through a checked type; `static_assert` per policy (transition: WW=KK=0, KW+WK=0; absolute: all rows 0) | Most shipped tables fail it ([display](display.md)) | 0 runtime | Absent: no LUT `static_assert` in `fi src/`, no balance test |
| 2 | Wi-Fi join hint: save last BSSID + channel, fast scan, full scan on failure; plus one early DHCP resend | ~2.4 s + ~0.4 s per connect [fork] | < 16 B, ~0.5 KB flash | Absent ([network](network.md)) |
| 3 | Single-pass firmware flash: header check on select, hash during write, switch slot only on match | Removes 1-2 full reads (~4 s each on S3 [fork]); bad image never boots | ~200 B SHA ctx | Absent |
| 4 | Debounced progress saves + RTC_NOINIT position shadow | `cp` saves (tmp+rename) on every page turn (`src/activities/reader/EpubReaderActivity.cpp:1556-1563`) | ~16 B RTC | `ci` debounces (10 pages / 5 min), no shadow |
| 5 | Kept-alive `SecureHttpClient` per OPDS/KOSync activity + body-idle stall timeout | Saves a 250-470 ms handshake per request; `HTTP_TIMEOUT_MS=60000` today | none | Absent (`fi ResumableFetch.h:113`) |
| 6 | OPDS Back restores parent selection/scroll (store index with each history URL) | Back re-fetches and resets to top; SCOPE welcomes OPDS usability | ~8 B/level | Absent (`cp OpdsBookBrowserActivity.h:29`) |
| 7 | Tunable-constants "knobs" for debug builds (below) | Tune on device without reflashing | 0 in release | Absent |
| 8 | Serial remote for hardware tests (debug only): KEY/TOUCH/SWIPE/WAITIDLE/HEAP beside SCREENSHOT | Lets agents and CI drive a real device | few KB flash, debug only | `cp` has only `CMD:SCREENSHOT` |
| 9 | Boot sweep of orphaned `*.part` / `*.tmp` / `.old` in known folders | Crashed downloads can hold hundreds of MB | one dir walk | `cp` cleans `.part` only on re-download (`src/network/HttpDownloader.cpp:94-131`) |
| 10 | Temperature-aware UC8179 refresh: idle TSC read picks TSSET/frames | Forced 30/90 °C today ([display](display.md)) | small | Absent |

## Knobs pattern (for idea 7)

One X-macro list `X(group, id, type, default, min, max, step, unit)`:
- Debug builds: values in RAM, editable from a settings page and a serial
  command; non-defaults persist to a JSON file on SD. Boot-loop guard: hold
  Back at boot to ignore the file; after 3 consecutive early crashes
  (RTC_NOINIT counter) rename it to `.bad`.
- Release builds: the same list expands to `inline constexpr` values, so the
  binary is unchanged.
- `static_assert` each default against its own grid.
- Never a knob: LUT contents, VCOM, voltages, TSSET, controller power/PSR/CDI
  registers, PLL, CPU/PM config, task stacks, anything that sizes an array.
  Frame counts may only feed DC-balance-checked LUT generators.
