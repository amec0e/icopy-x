# Maintainer physical test station

`tools/physical/station.py` controls a **reviewed, already installed** application.
It provides pinned SSH, framebuffer capture, visible Tk text, all named short
button events, known-card read/repeat/cancel checks, and a resumable PC-mode
handover. It never installs an IPK, writes a badge or flashes PM3. Run it locally,
not on a contributor's PR runner. Profiles and evidence are private lab data.

The maintained station has completed a Classic reference read and one supervised
Windows PC-mode round trip on the recorded candidates. Its cancellation command
has not yet completed physical acceptance. See the dated, configuration-specific
[physical acceptance record](PHYSICAL_ACCEPTANCE_20261019.md); calibrate a new
station's screen strings, USB descriptors and companion-client output independently.
Neither this controller nor QEMU certifies RF behavior for every card family.

## Setup and enrollment

Use Python 3.10+ on the maintainer station (the remote helper remains Python 3.8 compatible) and `python -m pip install -r tools/physical/requirements.txt`.
Copy `tools/physical/examples/profile.json` **outside the checkout**. Supply the
SSH address and an independently verified `SHA256:` host-key fingerprint. Use a
password environment variable or `key_file`; authentication does not fall back
to arbitrary local keys or agent identities. Never add credentials to the repo.
RSA/SHA-1 and DSA signatures are explicitly disabled for both host and client
authentication. The observed device uses an Ed25519 host key. A legacy-only SSH
server is refused rather than silently weakening this policy. The station uses Paramiko 5.1.0 and also blocks these algorithms explicitly at
connection setup.

All examples below abbreviate this command as `station`:

```text
python tools/physical/station.py --profile /private/profile.json --session /private/session-001 OPERATION
```

1. Run `inspect` (read only, no lease). Compare the reported machine, application
   file hashes and active service to the intended reviewed installation. Fill
   `machine_id` and `application_files` in the profile. Inspection does not prove
   provenance: retain the source revision and exact IPK digest separately.
2. Enroll USB VID/PID and, when exposed, serial number/location from this device.
   The station also requires exactly one matching port **absent before handover**.
   An ambiguous or reused port is a blocked test, not permission to guess.
3. Extract the matching release companion client with all adjacent resources and
   DLLs. Record its executable SHA-256. Set `style` to `iceman` (flash) or `factory`
   (no-flash). Never mix the two Lua families. Inspect `hw version` and `hw status`
   output during calibration and choose nonempty expected **device response**
   identifiers, including firmware/FPGA, not generic client banners.
4. Run `begin`. A per-device lease remains until `finish`, including across
   controller restarts. No automatic expiry permits a second operator to take
   over a device that may still be in a test. `resume-begin` resumes an interrupted
   initial connection with the same session ID; it does not send a button.

The profile is immutable for a session. A changed machine, boot or observed
application hash stops the run. Deliberate reboot/deployment starts a new session.
The installed identity set is intentionally small; this is not a full filesystem
attestation or a substitute for validating the package before installation.

## Observation, buttons and card cases

`observe` saves a 240x240 RGB565 framebuffer as PNG and an atomic visible-Tk-text
snapshot. Tcl's application interpreter is `tk`, X display is `:0`, framebuffer
is `/dev/fb1`, and HMI input is `/dev/ttyS0`; these are the observed iCopy-XS
profile, not portable assumptions for other devices.

`key --key DOWN --expect "Read"` sends one short button event only if every
`--expect` string is currently visible. Named keys are UP, DOWN, LEFT, RIGHT, OK,
M1, M2, PWR and ALL. This uses TIOCSTI in the existing HMI receive queue. It does
not send bytes to the GD32 and does not test the physical button switches.
Use observation between navigation steps; there is no blind menu macro.

For a reference card, copy `examples/card.json` outside the checkout. Record its
private UID, a verified raw-dump SHA-256 and length, suffix, and exact visible
strings for selected type, busy phase and success. Enroll from independent known
data or manually validate a baseline dump. Do not automatically bless a dump just
because the application said it succeeded. Choose a stable raw `.bin`/`.eml`
representation; timestamp-bearing formats need a future semantic validator.

For a changing counter, enroll a numeric template explicitly, for example
`"busy_texts": [{"template": "ChkDIC...{n}/32keys"}]`. Only `{n}` varies (1-10
ASCII digits); punctuation, surrounding text and the enrolled total remain exact.
Multiple expectations must all match. Ordinary string expectations remain exact.
Do not replace the busy guard with a generic title shared by idle/result screens.
Both host polling and the device's last input check use the same matcher. A phase
change still refuses input; there is no automatic retry or relaxed fallback.

* `read --fixture /private/card.json` starts from the explicitly selected Read
  type, waits at most the fixture deadline, and requires the expected UID, success
  texts and exactly one newly written matching dump of the correct size/hash.
* `cancel-read --fixture /private/card.json` cancels when the selected busy screen
  is observed, requires return within five seconds without a changed dump, then
  performs a complete fresh read. The five seconds start before requesting PWR,
  so a delayed input acknowledgement cannot restart the recovery clock. SSH and
  observation latency count towards this bound; it is not pure device UI latency.
  This is a UI-phase cancellation test; it does
  not prove which RF command was active. QEMU/host tests supply deterministic
  transport-fault coverage. Precise wire-phase cancellation remains separate.
* Repeat after returning to the selected type. A failed/missing response, wrong
  UID, zero/truncated/wrong dump or stale file cannot pass.

Missing card fixtures are **not run**, not passes. Use the ordinary Classic 1K,
EM410x and supplied Ultralight-compatible tag first. ICS Decoder is unavailable;
its USB/accessory tests remain blocked. No writes to source cards are authorized
by these read cases. Manually requested button navigation can reach other app
functions, so the operator must inspect its screen precondition.

## PC-mode session procedure

The first complete supervised round trip passed; see the
[19 October acceptance record](PHYSICAL_ACCEPTANCE_20261019.md). Use this
procedure for later PC-mode acceptance, with fresh sessions and exact identities.

Charge the device, attach the Ethernet hub, and prepare the matching host client
and a known read fixture. Start a session and perform one normal `read` first.

1. Navigate to the idle **PC-Mode / Start** screen using observed short buttons.
2. Run `pc-start`. The station saves preflight/service/process/log evidence on
   both the host and `/home/pi/icopy-validation/<session>` on the root filesystem.
   It records HANDOVER before injecting M1. SSH loss is expected; **do not retry
   the switch**. Existing systemd/socat logs continue while SSH is unavailable.
3. On the physical screen confirm PC mode is running. Swap the Ethernet hub for
   a direct USB cable to the station. Run `pc-usb --operator-confirmed`.
   The station selects one newly enumerated matching serial port, verifies the
   host executable hash, and runs only `hw version` and `hw status`, each bounded
   to 30 seconds. Exit zero alone is insufficient: expected response identifiers
   must be present, and known communication/FPGA mismatch errors are rejected
   even if the expected version banner was printed. No client script or
   automatic firmware flashing is invoked.
4. Use the physical button to stop/exit PC mode. Restore the Ethernet hub and
   wait for connectivity, then run `pc-return --operator-confirmed`. This checks
   machine/boot/application identity, active service, captures the screen and
   collects process/journal/socat evidence. A failed USB test can still use this
   recovery path; it cannot become a passing USB test.
5. Navigate back to the selected Read type and run `read` with the same known
   fixture. Run `finish`. PC mode is PASS only when USB checks **and this return
   read** passed. `report` prints the durable case journal.

The serial port is a **PM3 protocol bridge, not a Linux shell**. Cable changes and
physical exit are operator steps. An acknowledgement flag records an actual
observation; elapsed time is not acknowledgement. A later device-local exit
helper can remove one manual step after we validate the simpler handover.

## Interruptions and evidence

Every input has a host intent record and a durable device action ID. A lost
reply leaves it uncertain even if it ran. Resume by observing; only after checking
the resulting screen use `acknowledge --operator-confirmed`. The PC handover
commands resolve their own expected disconnect through operator observation and
new USB identity. They never resend the switch.

SSH uses absolute deadlines, simultaneous stdout/stderr draining and output
limits. Device helpers have a 30-second alarm, even if the host disappears.
Host PM3 processes are bounded and killed/reaped on timeout. No background key
sender survives an interrupted run. The kernel lock prevents concurrent device
operations; a host `controller.lock` prevents concurrent local invocations.

If the controller was killed, check its PID is no longer running before removing
**only that session's** `controller.lock`. Preserve `session.json`. Do not delete
or change the device `owner.json` to evade a live owner. If initial enrollment was
wrong, stop and inspect the machine/profile; a maintainer can release a stranded
lease over SSH after confirming no other controller is using it. This is manual
recovery, never an automated takeover.

Reports distinguish PASS, FAIL, HARNESS_ERROR and INCOMPLETE; interruption leaves
the case INCOMPLETE. A completed session may contain failed cases. Inspect them
all; CLOSED means ownership was released, not that the product passed. Raw logs,
UIDs, dump hashes and screenshots can be sensitive. Keep them outside Git and
publish only sanitized results, artifact identities and measured limits.

## What remains physical/manual

The station does not install or temporarily replace applications. Use a reviewed
release's normal update path in a separately planned installation session, or
the existing reversible staging procedure with verified backups and restoration.
Neither method is covered by a read/PC-mode pass. Fullimage flashing requires
stable power, a recovery plan and before/after firmware identity; never flash
bootrom just for test coverage. Factory/no-flash hardware acceptance needs a
device actually running factory firmware, not merely the no-flash QEMU profile.

Maintainers own the small private reference kit. Contributors run host tests;
CI supplies both exact-package QEMU profiles. Change a hardware fixture only
when its card/application boundary changes, and preserve negative controls that
reject wrong identities, stale/corrupt dumps and missing return evidence.
