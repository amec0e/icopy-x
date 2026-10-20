# Decoder blank-target polling

Both decoder activities called `detect_target()` directly from a Tk timer.
Its two authenticated HF reads and LF fallback have individual command budgets
of 3, 3 and 5 seconds, before transport cleanup. Slow hardware therefore blocked
Back and other UI events while searching for a blank.

Target polling now uses the UI-owned worker queue introduced in #116.
Only one poll is active per screen; Write is disabled during that poll, while
Back remains available. The existing target display stays visible until a
result is delivered. Missing or incompatible targets retain the existing retry
interval; a ready target still requires a fresh check before writing.

The worker uses the existing `executor.pm3_operation()` boundary across the
whole probe and parsing sequence. Back cancels its event without a global PM3
abort. Cancellation suppresses later key attempts and LF fallback, and immediate
re-entry waits off the UI thread until the previous response is released.
Late results cannot enable writing or replace the new screen's target.
The command translations, detector evidence requirements, build workflows,
discovery reservations and physical writer code are unchanged.

## Evidence

- Six UI/thread regressions fail against main `c20b4d0` and pass with the fix.
- Nineteen focused tests cover both entry paths, M1/PWR during held detection,
  UI-only delivery, single-flight polling, write gating, absent/incompatible
  targets, exceptions/startup failures, queued cancellation and immediate
  re-entry. Real detector/parser/executor tests use strict socket transcripts.
  The QEMU fixture itself also runs on the host against both command formats;
  the separate ARM run supplies the real Tk/runtime evidence.
- Removing only the PM3 operation boundary makes both cancellation tests fail:
  the second HF key and LF fallback are sent after Back. This negative control
  demonstrates why simply moving detection into a thread is insufficient.
- `critical-v8` adds `decoder_target_poll`, bringing packaged ARM/Tk validation
  to 25 cases per flash/no-flash package. It exercises real detection,
  translation, parsing, PM3 ownership, threads and Tk against finite synthetic
  socket replies for both firmware profiles. Persistent violations cannot be
  swallowed by application exception handlers.

Before merge, validate the reviewed candidate harness in addition to ordinary
trusted-main QEMU. Exact-head build, package and harness hashes and run links
are recorded in the PR's validation results.

## Physical boundary

These tests do not prove RF detection, USB behavior or physical abort timing.
A dispatched probe retains ownership until its response or existing transport
timeout unwinds; Back returns without waiting for it. Genuine ICS accessory
and blank-card acceptance remain pending because no accessory is available.
