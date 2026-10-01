# Memory, persistence, logging, power

## 1. What survives what

| Storage | esp_restart / panic / WDT | Deep sleep | Power loss |
| --- | --- | --- | --- |
| RTC_NOINIT | kept | kept | lost (garbage on cold boot) |
| PSRAM (S3) | kept | lost | lost |

Gate RTC/noinit data with a magic word and range checks
(`cp lib/Logging/Logging.cpp:12-19`, `cp lib/hal/HalSystem.cpp:20-24`,
`fi libs/hardware/PowerManager/src/PowerManager.cpp:20-32`). On the C3, RTC
FAST memory is also heap (`ALLOW_RTC_FAST_MEM_AS_HEAP`), so every RTC_NOINIT
byte comes out of the heap; the 16x256 log ring alone is 4 KB.

RTC_NOINIT also survives OTA, SD and USB flashes, so the next firmware
(possibly a different fork) reads the old bytes. Magics are shared across
forks with different meanings: silent-restart magic `0xC1EAB007` target 2 is
Settings in `cp` but OTA in `ci` (`cp src/main.cpp:140-147`,
`ci src/SilentRestart.h:11-12`, `ci src/main.cpp:343`); log ring `0xDEADBEEF`
is in both (`ci lib/Logging/Logging.cpp:31`). Safe today only because each
firmware reads and clears at boot. For new RTC data use one struct per
feature with a unique magic, version, size and CRC, and clear it on
`ESP_RST_POWERON`.

## 2. S3 PSRAM address 0 is overwritten every boot

MSPI timing tuning (octal PSRAM > 40 MHz) writes a 64 B test pattern at
physical PSRAM 0, where `EXT_RAM_NOINIT` starts (IDF
`mspi_timing_tuning_configs.h`, `MSPI_TIMING_PSRAM_TEST_DATA_ADDR`). Pad any
noinit PSRAM data. Arduino `psramInit()` maps PSRAM after global
constructors: guard access with `esp_psram_is_initialized()`. Upstream uses
no noinit PSRAM today.

## 3. Settings persistence

- JSON via `PersistableStore`. `fromJson()` calls `requestResave()` only for
  a legacy shape; `loadFromFile()` saves after releasing the mutex, so no
  save-every-boot (`cp lib/Serialization/PersistableStore.h:34-41`, `:108-128`;
  `cp src/CrossPointSettings.cpp:269-271`). Calling `saveToFile()` inside
  `fromJson()` deadlocks.
- `toJson()` builds a fresh document: keys this build doesn't know are
  dropped on the next save (downgrades, forks sharing one file).
- Enums are stored by index: append only (`cp src/CrossPointSettings.h:161-163`).
  Out of range clamps to the default; a parse failure loads defaults and the
  next save overwrites the file.
- `cp` shares `/.crosspoint/settings.json`; its SDK write is tmp+replace
  without `.tmp` recovery (`fi` pin `SDCardManager.cpp:393-418`). `ci` uses
  its own `crossink-settings.json`, migrates from the generic file once, and
  writes tmp → bak → rename with `.bak` recovery
  (`ci src/CrossPointSettings.cpp:40-44`, `ci lib/Serialization/PersistableStore.cpp:18-89`).
  A fork should use its own file name.

## 4. `new` aborts

`-fno-exceptions` (`cp platformio.ini:104`): `new`, `std::make_unique`, and
`std::vector`/`std::string` growth call `abort()` on OOM. Use
`makeUniqueNoThrow<T>()` / `<T[]>()` (`cp lib/Memory/Memory.h:22-34`);
`reserve()` early or check `heap_caps_get_largest_free_block()` before growth.

## 5. On S3, PSRAM doesn't save internal RAM

`xTaskCreatePinnedToCore` stacks, wolfSSL (plain `malloc`) and allocations
under `SPIRAM_MALLOC_ALWAYSINTERNAL` (1024 B, `ci platformio.ini:331`) come
from internal RAM. Upstream never uses `xTaskCreate...WithCaps` or
`wolfSSL_SetAllocators`. [fork] PSRAM stays > 7 MB free while internal
largest block falls to ~65 KB after Wi-Fi; OPDS/KOSync worker stacks are
12-14 KB and TLS 8-15 KB. Check internal largest block, not total free.

## 6. X4 Pro env ignores `custom_sdkconfig`

The X4 Pro env extends `[base]` on the prebuilt `dio_opi` Arduino variant
(needed for TinyUSB MSC), so no `[firmware_tuned]` sdkconfig line applies
(`cp platformio.ini:178-200`, `:330-338`; `cp src/main.cpp:47-53`;
`ci platformio.ini:127-142`, `:389-401`). Use runtime overrides
(`SET_LOOP_TASK_STACK_SIZE`) and check the generated sdkconfig.

## 7. Stacks

- `cp` render task 16 KB with vector fonts else 8 KB
  (`cp src/activities/ActivityManager.cpp:41-57`); loopTask 24 KB on
  vector-font boards, else the FreeInkUI weak default 16 KB.
- `ci` render 24 KB S3 / 16 KB C3 / 8 KB network mode
  (`ci src/main.cpp:349-353`); FreeType's AA rasterizer puts a 16 KB pool on
  the caller's stack.
- esp_timer 4096, FreeRTOS timer 2560 (`cp platformio.ini:192-193`).
- [fork] IDLE0/1 bottom out ~640 B free of 1536: don't add idle hooks.

## 8. Logging is not free

Release builds keep ERR+INF (`LOG_LEVEL=1`, `cp platformio.ini:264`). Each
enabled line `vsnprintf`s into a 256 B stack buffer and is copied into the
RTC ring even with no USB host (`cp lib/Logging/Logging.cpp:39-74`). Disabled
levels compile out and don't evaluate arguments: no side effects inside
`LOG_*`. HWCDC TX timeout is 1 ms on purpose (`cp src/main.cpp:440-441`); don't
raise it. Keep INF out of per-frame and per-page paths.

Release logs miss what you need and keep what you don't:
- OPDS parse errors are DBG only, so a bad feed logs nothing in release
  (`cp lib/OpdsParser/OpdsParser.cpp:57`, `ci :65`).
- `ci` logs HTTP status errors without the URL; 401 and 404 look alike
  (`ci src/network/HttpDownloader.cpp:229`, `:332`).
- `cp` logs the full URL (query included) at ERR, and the ring lands in
  the crash report (`cp src/network/HttpDownloader.cpp:60`). Strip userinfo
  and query before logging URLs.

## 9. Images re-decoded every render

`PixelCache::begin` clamps `wantRows` to image height `h`, then fails when
`wantRows < maxBlockDstRows`. Short images whose decode block is taller than
the image are never cached ("Cache band too small (67 < 121 rows)")
(`cp lib/Epub/Epub/converters/PixelCache.h:72-87`; `ci :85`). Compare against
`min(maxBlockDstRows, h)`.

## 10. Power

Upstream idle saving only lowers the CPU clock (80 MHz S3 / 10 MHz C3 after
3 s idle, never with Wi-Fi up) (`cp lib/hal/HalPowerManager.cpp:34-66`).
No `esp_pm_configure` / light sleep anywhere. If you add PM, the loop tick
rate sets the wake rate [fork: ~30 wakes/s on an idle transfer screen], and
power saving must never add input or draw latency on interactive screens.

X4 Pro has no VBUS pin (`usbDetect` unassigned, `fi BoardConfig.h:1667`).
A PC shows up only through native-USB enumeration; a wall charger shows up
only through charger STAT on GPIO21, high while charging (`:1665`). STAT
reads not-charging once the battery is full, so `cp` (which falls back to
"USB connected = charging") reports a full device on a charger as unplugged
(`cp lib/hal/HalGPIO.cpp:271-279`). Don't use it to gate charger-only logic.
