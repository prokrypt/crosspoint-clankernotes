# Display / panel safety

Paths are under `fi libs/display/FreeInkDisplay/src/`. Datasheet: UltraChip
UC8179c rev C0.6 (printed page numbers). A DC-unbalanced drive leaves net
charge in the ink; repeated, it can cause lasting ghosting or damage.

## 1. Most upstream register LUTs are not DC-balanced, and nothing checks

Rule: for true-OLD-plane transition LUTs, WW = KK = 0 and KW + WK = 0. For
absolute / direct-gray / complement-OLD LUTs, every row nets 0. Upstream has
no gate; the only related code is an unasserted rebalance of the UC8279X4
quality bank (`driver/Uc8279X4Driver.cpp:156-172`).

Net frames per row (VDH/VSH1 = +1, VDL/VSL = -1), from `tools/lut_balance.py`:

| Table | Net | Where |
| --- | --- | --- |
| SSD1677 `lut_grayscale` / `_sticky` (X4 AA) | light +7, gray -9, dark -6; no revert pass | `lut/Ssd1677Luts.h:11-46` |
| UC8179 AA `kGrayLuts` + `kDarkGrayLut` (absolute) | WW -1, KW -2, WK -1 | `driver/Uc8179Driver.cpp:57-71` |
| UC8179 `kGrayPreBwMid` | WW -1, KK +4 | `driver/Uc8179Driver.cpp:77-83` |
| UC8279X4 AA02 / AA68 | WW +1, KW -2/-3, WK -2/-3, KK -1 | `driver/Uc8279X4Driver.cpp:50-76` |
| UC8279X4 / UC8279 X3 PreBwMid | WW -1, KK +4 | same; `lut/Uc8279X3Luts.h` |
| UC8253 X3 `half` | WW -24, KK +24 (24 of 25 frames one-way) | `lut/Uc8253X3Luts.h` |
| UC8253 X3 `fast` (every page turn) | WW -2, KK +2 | same, used at `driver/Uc8253X3Driver.cpp:234` |
| UC8253 X3 `full` | rows 0/±24, but run from a white DTM1 (`Uc8253X3Driver.cpp:224-225`): held black gets +24 | same |
| UC8279 X3 `XtfAa` | KW -5, WK -2 | `lut/Uc8279X3Luts.h` |

Balanced: SSD1677 `lut_factory_quality`, UC8179 direct gray, UC8279 X3 `BwGc`/`Xth4`.
UC8253 encoding assumed to be the UltraChip 6-byte group format (not checked
against a UC8253 datasheet).

Do: sum any table you add or edit; if it is one-way, pair it with an equal
opposite pass or don't ship it. Don't copy upstream AA tables into new drivers.

## 2. UC8179 OTP: never send 0xA0 / 0xA1

`0xA0` PGM enters program mode (only a hardware reset leaves it); `0xA1` APG
starts OTP programming (burns OTP when VPP is present). `0xA2` ROTP is the
read. Upstream never sends them (grep `fi`, `cp`, `ci`). Datasheet pp.36-37.
OTP holds 12 temperature ranges, each with its own voltages and VCOM_DC
(p.51, VCOM_DC at TR+0x05). [fork] One unit read -1.4 V to -2.4 V across
ranges, so a single VCOM is wrong for part of the temperature span.

## 3. UC8179 custom-LUT refreshes run at reset-default voltages

The B/W path never writes PWR (0x01) or VDCS (0x82); only direct gray does
(`driver/Uc8179Driver.cpp:188-198`), then `bus.reset()` (`:211`, `:232`)
restores defaults. AA and PreBwMid REG=1 refreshes (`:528-553`, `:701-731`)
therefore run at reset defaults (R01 14.0 V p.13; R82 -0.10 V p.35) while
the gray packet uses -2.00 V. Unmeasured; whether an OTP refresh latches the
TR VCOM into R82 is undocumented. Treat as open.

## 4. UC8179 N2OCP and the DTM1 re-stream

CDI (R50h) bit D3 = N2OCP: the controller copies NEW to OLD after a refresh.
Upstream CDI bytes 0x29 (active) / 0xA9 (idle) both set it
(`driver/Uc8179Driver.cpp:98-99`, p.27), yet upstream re-streams DTM1 after
every refresh (`:466`, `:268`, `:742-743`). That is redundant but safe.
[fork] Skipping it was verified only for full-frame upload + balanced DU +
PTIN on one unit. Upstream uses no partial windows (PTL is the full 800x600,
`:518-527`); a windowed upload plus a skipped re-stream leaves OLD wrong
outside the window, so don't combine them.

## 5. UC8179 "Half" is a complement-OLD scrub

Half loads DTM1 with the complement of the target (`driver/Uc8179Driver.cpp:394-398`;
UC8279X4 `:413-445`), so the OTP GC waveform drives a full transition into
every pixel. Its net charge depends on OTP rows the code can't see.

## 6. Panel power between refreshes

After a refresh, VCOM gets 2 frames of VCOM_DC then floats, and sources go
to 0 V (p.43, pp.44-45). Upstream keeps PON between refreshes and POFs only
on `turnOff`, gray and deep sleep (`driver/Uc8179Driver.cpp:471-475`,
`:736-737`, `:495-501`). Low risk per datasheet; POF+PON costs ~82+128 ms
[fork, measured], so don't add POF-per-refresh to interactive screens.
EVS (0x52) is only written on the direct-gray path (`:184`).

## 7. UC8179 runs at a forced temperature

CCSET 0x02 (TSFIX) + TSSET 0x1E (30 °C) Full / 0x5A (90 °C) Fast
(`driver/Uc8179Driver.cpp:94-96`, `:419-422`). The real temperature never
picks the waveform or VCOM range; TSC (R40h) is never read. If you add a
TSC read: 0x00 = 0 °C and 0xFF = -1 °C (p.24), so stuck bus values look
valid; cross-check with a second read. [fork] TSC costs ~106 ms BUSY: keep
it off the page-turn path.

## 8. SSD1677 shadow path leaves RED one frame behind

`fi` `displayFinish` re-seeds RAM only for `blackPulseClean` boards
(`driver/Ssd1677Driver.cpp:425-439`; `ci`'s SDK pin has none). The facade's
shadow path writes RED = previous frame (`FreeInkDisplay.cpp:675-681`), so a
following blocking Fast (`:602`, `:707`) re-drives pixels already at target.
`cp`/`ci` avoid it by calling `displayBufferAsyncNoShadow`
(`cp lib/hal/HalDisplay.cpp:70-76`). Don't switch the HAL to the shadow path.

## 9. One device, several controllers

X4 / X4 Pro batches ship SSD1677, UC8179 or UC8279; X3 ships UC8253 or
UC8279d. The boot probe (VER 0x70) picks the driver
(`FreeInkDisplay.cpp:129-170`, `BoardConfig.h:131-155`). Test a display
change on every driver the target can load.

## 10. BUSY discipline

UC8179 drops LUT/DTM/DRF writes while BUSY: wait first
(`driver/Uc8179Driver.cpp:665-666`). A second PON on a powered UC8253 gives
no BUSY edge, so a two-phase wait burns its 1 s timeout
(`driver/Uc8253X3Driver.cpp:236-237`). From code comments; not bench-tested.
