# Decoder worker lifecycle correction

The follow-up audit found that decoder read, write and verification workers
called Tk's `after()` from background threads. Some write paths also cancelled
UI timers there. Caught Tk errors could silently strand the screen. The legacy
reader instead performed serial reads on the UI thread. Both entry paths could
continue from target detection into a write or verification after being closed.

Both activities now use a UI-owned completion timer and a Python result queue.
Workers return data and errors; the UI alone changes result fields, timers and
screens. Write and verification inputs are copied before launch. Back/retry and
destruction invalidate old work. Cancellation is checked before starting work
and between target detection and the next write/verification command.
Discovery ownership, internal-PM3 exclusion, credential compatibility checks and
command translation retain their existing behavior.

## Regression evidence

- Ten initial real-thread cases fail against main `a5e7642` and pass with this
  correction. Assertions recorded outside application exception handlers catch
  swallowed Tk violations.
- The expanded 26-case worker suite covers both activities, held UI delivery,
  device exceptions, failed thread startup, input snapshots, queued cancellation,
  exit during detection, already-dispatched I/O and stale read completion.
  Existing HF/LF compatibility, parsing, saved-credential and serial-handoff
  tests remain in place; asynchronous tests explicitly run and deliver workers.
- `critical-v7` adds `decoder_worker_lifecycle` to packaged ARM/Tk validation:
  24 cases per flash/no-flash package. The new case uses real threads, Tk,
  decoder read/parser code and held result delivery for both activities.
  It records UI-thread violations outside production catches, and checks that
  closing during held target detection prevents a subsequent write.

The candidate harness must be exercised before merging: ordinary PR QEMU uses
trusted main and cannot validate a harness change. Exact-head run and package
evidence belong in the PR's validation record.

## Limits

The QEMU decoder serial stream and target/write/verification hardware responses
are controlled fixtures. These checks prove application lifecycle behavior,
not genuine accessory operation, RF writes, or physical cancellation.
Cancellation cannot undo a hardware call already dispatched; such a call may
finish, while its late UI result is discarded. No implicit replay or global PM3
abort was added.

Target polling while waiting for a blank still runs detection synchronously on
the UI thread. That separate responsiveness issue remains to be assessed.
Serial close behavior and real accessory read/write/verify acceptance also
remain physical validation boundaries; no ICS Decoder is currently available.
