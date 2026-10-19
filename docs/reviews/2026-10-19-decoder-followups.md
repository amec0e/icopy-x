# Decoder lifecycle follow-up corrections

These four focused changes address the source findings retained in the
[Astra startup assessment](../../tools/auto_review/calibration/20261019-baseline/results.json).
They preserve the requirement to hide ICS Decoder without confirmed hardware,
the reserved internal PM3 port and alias guards, both firmware families, command
translation, build scripts and the existing user-facing menu contents.

| Concern | Correction | Regression evidence |
| --- | --- | --- |
| Swallowed QEMU assertion, [#107](https://github.com/lab-401/icopy-x/pull/107) | Record attempted opens and serial contract violations before raising simulated I/O errors. Assert that evidence outside application exception handlers. | Six controls include disabling the actual PM3 opening guard. The application catches the simulated error, but the evidence still fails. |
| Menu focus, [#108](https://github.com/lab-401/icopy-x/pull/108) | Hide the stale row on return; restore its selection after positive revalidation only if the user has not navigated. A negative result discards restoration intent. | Connected return fails against the old application. Four host cases cover restoration, removal and navigation priority; the ARM/Tk hotplug case now includes pause/resume. |
| Foreground serial handoff, [#109](https://github.com/lab-401/icopy-x/pull/109) | A cancellable session owns the handle through queued UI delivery and reading. Discovery workers publish Python data; a Tk-owned timer delivers it. Failed cleanup retains ownership and remains recoverable after the activity exits. | Holding delivery exposes a second open in the old application. Ten activity/thread cases and eight middleware cases cover both entry paths, Back/destroy, cancellation windows, UI thread affinity, lost references and bounded failed-close recovery. |
| Windows attachment continuity, this change | Optional USB metadata distinguishes replacements; a new menu observation period invalidates cached successes and exhausted retries after a pause. | Both real menu/presence scenarios fail against the old code: replacing a confirmed decoder and reconnecting after exhausted attempts on the same COM name. Eleven added cases also cover missing metadata, enumeration errors, cancelled observations, foreground ownership and unchanged Linux behavior. |

## QEMU evidence and test maintenance

Changes to the trusted harness were tested separately from ordinary PR QEMU,
which intentionally uses `main`. The reviewed candidate branch received a
temporary exact-name runtime exception; each exception was removed after its
worker completed, restoring the main-only policy.

- #107: candidate `d02dafa03fa3a79c6b76fde01e70dff9280c91a7`, build
  `39311861001`, [candidate harness run 39312739396](https://github.com/lab-401/icopy-x/actions/runs/39312739396).
- #108: candidate `4a4efd65829f176a6b731cb180db884537b81162`, build
  `39313381662`, [candidate harness run 39314133709](https://github.com/lab-401/icopy-x/actions/runs/39314133709).

Both candidate runs passed all 23 critical cases for each exact flash/no-flash
IPK (46 per run), with manifest heads and package hashes checked. The profile
size remains 23: this strengthens an existing case rather than adding duplicate
flows. Host regressions additionally prove that the original application fails
the focus, reverse handoff and Windows pause cases.

#109's revised handoff and cleanup implementation passed normal trusted-main
QEMU [run 39318353840](https://github.com/lab-401/icopy-x/actions/runs/39318353840),
using build `39317717840` at `8f55e9c010312c676b24bcceb6d7741d7a2debee`.
Both exact packages passed all 23 cases, with commit and package hashes checked.
The initial Astra review exposed additional cleanup failures; those were fixed
and tested before merging. That earlier paid report is not an approval of the
revised source. The integrated local host suite with the Windows correction
passes 2,832 tests (12 platform skips).

Keep serial evidence outside caught callbacks when extending these fixtures.
The handoff tests use real Python threads and deliberately hold result delivery;
they do not rely on a convenient thread schedule or require a physical port.
The menu tests use the real presence logic with controlled enumeration and
serial replies. These are maintained regression controls, not an exhaustive
concurrency proof or independent model-accuracy evaluation.

## Acceptance limits and physical follow-up

No genuine ICS accessory was available, and native Windows serial hardware
was not exercised.
Acceptance of these source/logic corrections uses host, thread and packaged
ARM/Tk evidence; it does not certify physical USB, RF or credential writes.
No physical device was flashed or badge written for these corrections.

Windows USB metadata is optional under the
[pySerial contract](https://pyserial.readthedocs.io/en/latest/tools.html#serial.tools.list_ports.ListPortInfo).
It can trigger revalidation but never replaces Who/ISE. A complete replug with
identical metadata occurring entirely between uninterrupted enumeration polls
is not observable by this cache. Pause/resume now explicitly invalidates that
uncertain continuity. Linux retains its devnode inode/ctime checks. A serial
close failure retains ownership; failed cleanup must not permit a new open.
Background cleanup stops after three failed close attempts; a user-initiated
read can retry cleanup afterward. The discovery queue changes do not establish
thread safety for the separate legacy read/write workers.

When an ICS accessory becomes available:

1. Enter and leave its activity while connected; confirm selection returns only
   after revalidation. Navigate during that interval and confirm no focus theft.
2. Exit during discovery and immediately re-enter; repeat while unplugging.
   Confirm there are no competing opens, stale UI callbacks or stranded handles.
   Then perform an ordinary PM3 read to check coexistence.
3. On a Windows host, replace/reconnect on the same COM name while the menu is
   paused, including after three failed identity attempts. Verify a fresh
   handshake and correct visibility; record USB descriptors and software versions.

These navigation/discovery checks need no source-card write. Genuine capture,
write/readback, factory-device and installation acceptance remain separate in
[the validation status](../VALIDATION_STATUS.md).
