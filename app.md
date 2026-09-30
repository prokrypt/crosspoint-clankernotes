# App layer: races and live bugs

Render runs on its own FreeRTOS task at the same priority and core as the
loop, so the loop can be preempted mid-`render()` and vice versa.

## 1. Render can run before `onEnter()` finishes

`ActivityManager` sets `currentActivity`, unlocks, then calls `onEnter()`
(`cp src/activities/ActivityManager.cpp:205-206`, `ci :659-660`); a pending
render notification (`:66-78`) can call the new `render()` meanwhile. Give
members render-safe initial values, or hold `RenderLock` while `onEnter()`
fills state `render()` reads.

## 2. Loop mutates strings that render reads (Calibre)

`CalibreConnectActivity::loop()` reassigns/clears `currentUploadName` and
`lastCompleteName` while `render()` concatenates them
(`cp src/activities/network/CalibreConnectActivity.cpp:141-160` vs `:210-224`;
`ci :146-165` vs `:222-236`). Garbage or use-after-free. Copy under
`RenderLock` or into `char[]`.

## 3. OPDS frees entry lists without RenderLock

`releaseEntries()` swaps away `entries`/`rowItems` on Back/open before state
leaves BROWSING, while a render may hold `data()`/`c_str()` pointers into
them (`cp src/activities/browser/OpdsBookBrowserActivity.cpp:163-189`,
render `:54-67`; `ci` `fetchFeed :545-570`). Lock around swap + state change.
Code path confirmed; timing not reproduced.

## 4. BMP palette read at a fixed offset

The palette is read right after the 40-byte header fields regardless of
`biSize`; V4/V5 (108/124 B) paletted BMPs get garbage grays, and the
`file.read()` result is unchecked (`cp lib/GfxRenderer/Bitmap.cpp:139-145`,
`ci :142-146`). Seek to `14 + biSize` (guard wrap) and check the read.

## 5. Cache format sentinels must never be reused

`ci` `SECTION_FILE_PARTIAL_VERSION = 0xF4` equals an older version's partial
byte (`ci lib/Epub/Epub/Section.cpp:36`, loader `:270-277`,
`docs/file-formats.md:455-476`): a stale partial on SD is accepted and
resumes with wrong page positions. Bump to an unused value; `cp` derives it
in lockstep (`cp lib/Epub/Epub/Section.cpp:76`). After any cache layout
change, bump the version and document it.

## 6. `ci`: sync looks in the wrong section cache

KOReader/Nearby sync build temporary `Section`s with the default cache
suffix, but the reader keys caches by render mode (`_balanced`/`_light`)
(`ci src/activities/reader/KOReaderSyncActivity.cpp:384`,
`lib/KOReaderSync/ProgressMapper.cpp:845`,
`src/activities/reader/NearbyBookPositionSyncActivity.cpp:1182` vs
`EpubReaderActivity.cpp:204-209`). Books with a render-mode override land on
the wrong page. Pass `sectionCacheSuffixForRenderMode(...)`.

## 7. `ci`: read each input edge once per pass

`ci` `wasReleased()` consumes release suppression
(`src/MappedInputManager.cpp:896-902`); `TxtReaderActivity` reads Confirm
twice in one pass (`:238-250`). Store edges in locals.

## 8. `yield()` doesn't let IDLE run

`yield()` only switches to equal/higher priority. Wait loops on loopTask
(`ci src/network/UsbSerialFileTransfer.cpp:103-134`, up to 45 s) starve IDLE
(priority 0): task-WDT risk and delayed freeing of deleted tasks. Use
`vTaskDelay(1)`.

## 9. Debug-path traps

- Serial `CMD:SCREENSHOT` dumps the framebuffer without `RenderLock`
  (`cp src/main.cpp:716-727`, `ci :1613-1619`): shots can be torn. The
  button-combo path locks (`cp :751-754`). Don't trust serial shots taken
  mid-render.
- Crash report "last logs" include the new boot's lines: the RTC ring is read
  only at `checkPanic()` after boot logging (`cp src/main.cpp:445-495`,
  `lib/hal/HalSystem.cpp:174`).
- `GfxRenderer::clearScreen()` clears the display's live buffer, not a
  swapped-in `frameBuffer` (`cp lib/GfxRenderer/GfxRenderer.cpp:1677-1683`).
  Clear offscreen buffers yourself.
