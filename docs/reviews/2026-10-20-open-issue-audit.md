# Current-code audit of issues #58–#61

Assessed against main `0da3fe031759980c837a694c8c02b8c4f9c51cd0`.
The reports describe earlier code and include proposed fixes; neither the
reported root cause nor the proposed patch is assumed correct.

| Issue | Current evidence | Disposition |
| --- | --- | --- |
| [#58: iCLASS write success](https://github.com/lab-401/icopy-x/issues/58) | The quoted `Wrote block 6 / 0x06 ( ok )` is accepted. Factory `Wrote block 06 successful` is translated to the canonical shape before parsing. New tests use the real writer, compatibility layer, executor, TCP server and daemon reader with controlled child-process output. Both families pass, including ANSI/prefix cleanup. | No production change for the stated reproducer. Require the actual client/firmware version and full response for claimed uppercase or alternate-spacing variants; do not broaden success recognition without evidence. |
| [#59: write abort](https://github.com/lab-401/icopy-x/issues/59) | `writeDataBlocks()` already stops at the first failure. Executor/daemon ownership and bounded recovery were changed after the report's stated release. New tests verify complete errors, UART timeout without a prompt, cancellation, refusal while the old command is outstanding, and a fresh command after the late response drains. No write is replayed and no next block is sent. | The suggested extra `stopPM3Task()` after return does not establish hardware recovery. Software regressions pass; retain physical iCLASS write-abort acceptance as unverified. Request reproduction on a known current installation before changing core recovery. |
| [#60: decoder enumeration](https://github.com/lab-401/icopy-x/issues/60) | Current detection excludes internal `/dev/ttyACM0` and aliases at the opening boundary, requires exact Who/ISE identity, and serializes probing/foreground ownership. Existing regression suites cover these guards and Windows observation gaps. | Software concern addressed by the merged decoder fixes. Do not replace protocol validation with the report's unverified USB VID/PID list. Genuine accessory coexistence remains pending. |
| [#61: truncated key logging](https://github.com/lab-401/icopy-x/issues/61) | The alleged `key_bytes`, `%.2s`/two-character logging expression and named logging functions do not exist in current `ics_decoder.py`. Parsing preserves raw bytes/text and all reported fields; valid 16-hex-character block 7 data is retained. Existing capture/save/reload tests pass. | Not reproducible at the stated path. Obtain an installed version and exact source/log location before changing logging. Do not invent a credential-logging requirement to repair an absent statement. |

The focused host run passes 386 tests, including eight added iCLASS transport
cases. Its fake PM3 child emits bytes across real TCP; it does not simulate RF
or certify a physical co-processor reset. No source badge was written.

The separate [issue #10 sidecar assessment](2026-10-20-update-sidecars.md)
checks the newly reported orphaned metadata layout and a published release.

This audit also identified worker-side Tk dispatch in decoder read/write/verify,
outside the discovery path fixed by #109. The subsequent
[lifecycle correction](2026-10-20-decoder-workers.md) covers those paths with
held-completion tests. These transport tests alone do not certify the UI or
physical accessory behavior.
