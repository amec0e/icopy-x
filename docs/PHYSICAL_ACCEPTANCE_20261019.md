# Physical acceptance: 19 October 2026

One iCopy-XS passed Classic 1K read/exit/re-entry checks and a complete supervised
Windows PC-mode round trip. These results apply to source
`7aef74038a96235df645cc58aefabfa3b0fb4fd4`, application-equivalent to main
`cf9e4be93d5ec251fd66c4492e578e147b439b3f`, from
[build 39171756182](https://github.com/lab-401/icopy-x/actions/runs/39171756182).
The later session below records separate evidence for menu changes #82-85.

Flash IPK SHA-256:
`25a86ee07b5f7cf5a1fdf1f01e427ce3d2324a397ddc3e768a8a41a77c2dea6c`.
The application was reversibly staged with a verified baseline backup; the
standard installer was not tested. No firmware flash or source-card write occurred.

## Observed passes

- The maintained station completed a full Classic 1K read against an independently
  enrolled 1,024-byte reference dump.
- Supplemental device-local tests completed an Auto Copy read/exit and six
  cancellation/re-read cases: scanning, dictionary checking and sector reading
  in both Read and Auto Copy. Cancelled attempts left dump inventory unchanged;
  each subsequent full read matched the reference. Delayed callbacks were observed
  after exit. These samples do not establish worst-case cancellation latency.
- The maintained PC station recorded handover before sending Start once. After
  the operator exchanged the Ethernet hub for direct USB, the matching Windows
  companion passed `hw version` and `hw status` without compatibility warnings.
  Client and ARM reported v4.23346-suspect / `9ce8a4b6c`, FPGA `3s100evq100`, and
  flash initialization OK. Version observations are not firmware readback.
- After physical Stop and hub restoration, application/boot identity was
  unchanged, the bridge exited, one normal PM3 client remained, and a new full
  Classic reference read passed. The session closed and released its device lease.

## Harness failure and remaining limits

The maintained cancellation attempt refused input because a dictionary counter
changed between observation and its exact-text guard. It remains HARNESS_ERROR,
not a pass. An initial supplemental observer had the same failure. Later
supplemental checks kept a Tk connection open and passed with leases, guards,
durable action records and deadlines intact. Those experimental checks do not
establish physical acceptance of the maintained cancellation command.

Raw dumps, identifiers, screenshots and logs remain in the private maintainer
evidence store, indexed by `CLASSIC_ACCEPTANCE_20261019` and
`PC_ACCEPTANCE_20261019`. This public record contains no badge data.

Pending boundaries include real ICS hardware (unavailable), factory/no-flash
hardware, later LF/Ultralight runtime acceptance, standard installation/recovery,
firmware flashing, USB mass-storage transfers, other hosts and endurance. Audio
underruns were observed; audio quality is not certified. See
[validation status](VALIDATION_STATUS.md) for the current work queue.

## Later menu candidate session

The same iCopy-XS was reversibly staged with source
`b6f9751d2fa0fef92a4a130fb15f9b8f63dd2672` from
[build 39236312075](https://github.com/lab-401/icopy-x/actions/runs/39236312075),
application-equivalent to merged main `44169d757e0c92bc5f9f5afa4d81c4c4af65a15a`.
Flash IPK SHA-256:
`6cb9493f5a32a03daf94eb42cb0faad94fb8ecdcf8833918dd02300174abff80`.
The baseline archive was downloaded and its digest verified before activation.
Package application files were verified; installed configuration was preserved,
the install-only version shim removed, and bundled Lua resources linked for the
staged layout. The standard installer and firmware flashing were not exercised.

- All four root-menu pages lacked Move and ICS Decoder with no accessory attached.
  M1 left the menu unchanged. Screenshots and guarded navigation were recorded.
- The maintained station completed a full Classic 1K read matching the independently
  enrolled 1,024-byte reference dump. Return to the read list was observed.
- A subsequent cancellation attempt used the numeric progress guard from #87.
  It observed `ChkDIC...0/32keys`, then the device-side final screen guard refused
  PWR. This remains **HARNESS_ERROR**, not a cancellation pass. The refusal did
  not record the new screen text, so its exact cause is not established.
- SSH subsequently failed. The operator confirmed battery exhaustion. The session
  remains interrupted with its lease and uncertain-action marker preserved; it
  was not marked closed. Battery loss must not be interpreted as application
  acceptance or as proof of a particular cancellation defect.

Private evidence is indexed by `physical-station/menu-read-001`. After recharge,
inspect boot/application identity and the existing lease before any further input;
do not replay the interrupted action. Resolve the session explicitly and repeat
the maintained cancel/read sequence with adequate power. A device-local bounded
phase wait may be needed if SSH latency is shown to miss the requested phase.
This session did not test a genuine ICS accessory or factory/no-flash hardware,
and did not repeat the earlier PC-mode cable exchange.
