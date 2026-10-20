# Physical acceptance: 20 October 2026

One iCopy-XS with the enrolled ordinary Classic 1K was inspected after the
operator-confirmed battery interruption. The pinned SSH host key, machine ID
and enrolled application hashes matched; the boot ID had changed. The old lease
still belonged to the interrupted session, and its uncertain action had no
remote action record. The new boot and process inspection established that the
old helper was no longer running. The session and inspection were archived,
the lease released using its original token, and the session explicitly closed
as interrupted. Its earlier PASS and HARNESS_ERROR outcomes were preserved.
No interrupted input was replayed.

The installed application remains source
`b6f9751d2fa0fef92a4a130fb15f9b8f63dd2672`, application-equivalent to main
`44169d757e0c92bc5f9f5afa4d81c4c4af65a15a`, from
[build 39236312075](https://github.com/lab-401/icopy-x/actions/runs/39236312075).
Flash IPK SHA-256:
`6cb9493f5a32a03daf94eb42cb0faad94fb8ecdcf8833918dd02300174abff80`.
It was previously reversibly staged; no application deployment, installation,
firmware flash or source-card write occurred in this session.

## Findings

- A maintained full Classic read matched the independently enrolled UID and
  1,024-byte raw dump.
- The network-inclusive `cancel-read` observed dictionary progress, but the
  final PWR guard found `Successful!` and `File saved`. The durable REFUSED
  record confirms that no cancellation input was attempted. This remains
  HARNESS_ERROR: the requested phase ended during the observation/request gap.
  It is not evidence that the device failed to cancel.
- The explicit `cancel-read-local` mode in
  [#114](https://github.com/lab-401/icopy-x/pull/114) keeps the observer and short
  sequence on the device. Two runs returned to the selected read list in
  0.149 and 0.106 seconds. Each left dump inventory unchanged and completed a
  fresh read matching the same reference. The tested station source was
  `bb7fe642733fa784edea9a7303f44a81ffdf23b0`; its Linux Python 3.8/3.12 helper
  tests had passed before device use.
- The device returned to its main menu; the new sessions closed and released
  their leases with no uncertain actions. The operator was told it could be
  powered off.

The local timing includes the final guard, journal writes, input queuing and
return observation. It excludes SSH transport and is not comparable to the
unchanged network-inclusive deadline. These samples establish neither worst-case
latency nor the exact active RF command. Guards, leases, durable intent and
replay refusal remained enabled. Failed attempts are retained separately.

Private evidence is indexed by `physical-station/menu-read-001`,
`physical-station/classic-recovery-20261020` and
`physical-station/classic-local-20261020`, with the preflight in
`issue-triage-20261020`. Raw identifiers, dump inventories, logs and screenshots
remain outside Git.

This acceptance is specific to the recorded application and Classic fixture.
It does not certify later decoder runtime changes, genuine ICS hardware,
iCLASS writes, LF/Ultralight recovery, factory/no-flash devices or installation.
The previous [PC-mode round trip](PHYSICAL_ACCEPTANCE_20261019.md) was not repeated.
