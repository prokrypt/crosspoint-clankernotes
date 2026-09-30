# Network, TLS, OTA

## 1. Every join forces an all-channel scan (~2.4 s)

`WiFi.setScanMethod(WIFI_ALL_CHANNEL_SCAN)` before each `WiFi.begin`
(`cp src/activities/network/WifiSelectionActivity.cpp:475`, `ci :694`).
[fork] Passing the saved BSSID + channel with a fast scan took association
from ~2.45 s to 60-100 ms; fall back to the full scan on failure.

## 2. The first DHCP DISCOVER is usually lost

[fork, 88 of 90 logged joins] lwIP's first DISCOVER after association gets
no answer; the retry waits for lwIP's 500 ms timer, so DHCP takes ~515 ms.
Resending once ~100 ms after STA_CONNECTED gave ~114 ms. Call `dhcp_start()`
on the tcpip thread (`tcpip_callback`), only while the client is SELECTING
with tries == 1. If you disable modem sleep for the join, restore it on the
failure path too. Upstream has neither (`cp :460-494`, `ci :660-708`; no
LWIP_DHCP options in either `platformio.ini`). Root cause unknown.

## 3. Firmware writes are not verified while writing

`FirmwareFlasher` erases and writes the inactive slot with
`esp_partition_write`, hashes nothing during the write and reads nothing
back; `ota_boot::switchTo` then writes otadata by hand
(`cp src/network/FirmwareFlasher.cpp:318-350`, `ci :291-318`;
`src/network/OtaBootSwitch.cpp:65`). SHA-256 / XOR / board tag are checked only in a
separate validation pass. App rollback is off (no `esp_ota_mark_app_valid*`).
- SD update reads the image twice before writing (select + TOCTOU re-check in
  `flashFromSdPath`), synchronously on the loop
  (`cp src/activities/settings/SdFirmwareUpdateActivity.cpp:58`, `:165-169`; `ci :59`, `:166-170`).
- `ci` OTA stages to SD and reads it three times (`ci src/network/OtaUpdater.cpp:228-266`, `:480-525`)
  and sets `CONFIG_BOOTLOADER_SKIP_VALIDATE_ON_POWER_ON=y` (`ci platformio.ini:154`).
Safer shape: hash during the single write pass, `switchTo` only on match.

## 4. Truncated close-delimited bodies count as complete

With no Content-Length and no chunking, `readUntilClose` returns true once
the socket is closed, and `SecureClient::read` clears `_connected` on every
failure (close_notify, FIN/RST, MAC error, MEMORY_E). `fetchResumable` then
sets `complete = true` (`fi libs/network/SecureNet/src/SecureClient.cpp:40-44`,
`:198-222`; `SecureHttpClient.h:536-550`; `ResumableFetch.h:189-192`).
Fixed-length and chunked bodies are fine. Don't save a close-delimited body
as a complete file without a length or hash.

## 5. 2 KB read buffers on the stack

`readFixed` / `readUntilClose` declare `uint8_t buf[2048]`
(`fi SecureHttpClient.h:515`, `:537`, `:579`; same in both pins). Every body
callback (OPDS parse, KOSync) runs 2 KB deeper. Size the calling task for it
or move the buffer to the heap.

## 6. TLS cost

- wolfSSL only: the prebuilt mbedTLS lacks TLS 1.3, which is also why
  `esp_https_ota` isn't used (`cp src/network/OtaUpdater.cpp:144-148`).
- `fetchResumable` builds a new client per call (`fi ResumableFetch.h:113`):
  a full handshake each time, ~250-470 ms [fork]. Keep one `SecureHttpClient`
  alive per activity to reuse the connection; session resumption saved only
  ~35 ms [fork].
- The SDK asks for 2 KB records (max_fragment_length) to shrink wolfSSL's
  RX buffer on the C3 (`SecureClient.cpp:120-127`): a throughput cost on S3.
- Heap floors: `cp` `MIN_TLS_FREE_HEAP=40000` (`src/network/HttpDownloader.h:34`);
  `ci` KOSync 35000 free / 20000 largest block.

## 7. Network sessions reboot to get heap back

`ci` silently restarts into a minimal network boot before OTA, OPDS, KOSync,
File Transfer and Manage Fonts, and again on exit (`ci src/SilentRestart.h:10-44`,
`src/main.cpp:449-460`), on S3 too. `cp` restarts on exit, and on entry only
on boards without touch (`cp src/main.cpp:202-215`). Reason [fork, S3]: after
the first Wi-Fi session the largest internal block drops ~123 KB to ~65 KB
and ~23 KB never returns, even after WIFI_OFF. Don't remove the restarts
without replacing that heap.

## 8. Blocking network work on the loop

KOSync runs on the loop with a 15 s default timeout and no retry
(`cp src/activities/reader/KOReaderSyncActivity.cpp:128-142`,
`fi SecureHttpClient.h:614`). The first-ever join runs up to 5 s of NTP
inline (`cp WifiSelectionActivity.cpp:526`). The UI freezes meanwhile.

## 9. Web server

- `handleClient()` runs from the loop and writes SD inline via a 4 KB buffer
  (`cp src/network/CrossPointWebServer.cpp:391-411`). No LWIP_TCP_WND tuning
  upstream. [fork, S3] 32 KB TCP window with lwIP in PSRAM + an SD writer
  task on core 1 raised upload 441 → ~650 KB/s. Don't copy the window to C3.
- File list JSON entries go through a 512 B buffer and are skipped (DBG log
  only) when longer (`cp :627-641`, `ci :753`, `:793-797`); long FAT names
  (up to 765 B UTF-8) vanish from File Transfer.
