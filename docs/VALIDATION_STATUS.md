# Validation status and remaining acceptance

Updated 20 October 2026. This is the current acceptance boundary; historical
captures and planning notes are not passes for the latest application.

## Contributor CI

Every PR must pass the three Linux/Windows host jobs and **QEMU critical flows**
with an up-to-date main branch. The build compiles the PM3 client and fullimage,
checks required patches and matching source/platform/FPGA metadata, builds both
IPKs and all desktop companions, and packages complete release candidates.
Required build failures prevent QEMU success. No physical device or private
factory image is needed on a contributor's computer.

The trusted QEMU harness runs the exact built flash and no-flash IPKs under ARM
Python 3.8.0 and Tcl/Tk 8.6.5. Its `critical-v7` profile has 24 cases per variant,
48 combinations. It exercises packaged application code, real Tk/threads,
translation/parsing, Reader behavior, cancellation and selected transport faults.
PM3 responses and hardware boundaries are controlled fixtures. It does not run
the physical PM3, boot the device kernel or prove RF/USB/flashing behavior.

The earlier 23-case profile passed on main after [#83](https://github.com/lab-401/icopy-x/pull/83)
in [run 39236635642](https://github.com/lab-401/icopy-x/actions/runs/39236635642).
It now checks decoder menu appearance/removal with controlled serial identities,
including isolation of the internal PM3. The subsequent contributor About removal
[#85](https://github.com/lab-401/icopy-x/pull/85) passed the same 23 cases per IPK
in [run 39236856190](https://github.com/lab-401/icopy-x/actions/runs/39236856190).

The later [decoder corrections](reviews/2026-10-19-decoder-followups.md)
(#107–110) strengthen the PM3-open assertion, restore menu focus after positive
revalidation, retain serial ownership through UI handoff and failed-close
recovery, and invalidate uncertain Windows attachment continuity. Host tests
include negative controls and deliberately held worker completions. Each change
passed exact-package QEMU checks before merge using that 23-case profile.
These checks do not certify genuine ICS hardware or every remaining UI worker.

These tests have caught application defects. In [run 39169035713](https://github.com/lab-401/icopy-x/actions/runs/39169035713),
both profiles rejected a late Auto Copy animation after its canvas was destroyed.
[PR #70](https://github.com/lab-401/icopy-x/pull/70) disposes timers, stops owned
workers and rejects late UI callbacks. Eight focused host regressions also cover
the warning that could reopen after exit. The QEMU test was not weakened.

The required profile is a maintained subset. The larger legacy flow inventory
still contains stale navigation and expectation problems and is not certified
as passing. Promote a useful case only after validating its assertions and
proving a relevant negative control. Ordinary contributors should add the
smallest useful host regression; maintainers own shared QEMU fixtures and pins.

## Delivery and physical testing

| Area | Implemented evidence/control | Still required |
| --- | --- | --- |
| PM3 build integrity | [#65](https://github.com/lab-401/icopy-x/pull/65): matching source/platform/FPGA checks; one physical Iceman client/device version/status pair passed on 19 October | Not full firmware readback or flashing acceptance. FPGA bitstreams are verified upstream inputs, not newly synthesized HDL. |
| Ultralight dumps | [#66](https://github.com/lab-401/icopy-x/pull/66): header, UID, length/capacity and partial-data assertions on host/QEMU | Retest the supplied compatible tag; genuine Ultralight/NTAG coverage is separate. An earlier intermittent empty reply remains unexplained. |
| Timeout/cancellation | [#67](https://github.com/lab-401/icopy-x/pull/67): bounded drain and no implicit replay; six supplemental Classic cases. #87 adds numeric guards; #113 records refusals; #114 adds an explicit device-local cancellation mode with two physical cancel/reference-reread passes | Network-inclusive cancellation missed the busy phase and remains HARNESS_ERROR. Local timing excludes SSH. LF/iCLASS recovery and broader hardware abort timing remain pending. |
| Auto Copy exit | [#70](https://github.com/lab-401/icopy-x/pull/70): timer/callback guards; physical Classic Auto Copy read, exit and re-entry passed on the recorded candidate | Other card families and changed application versions require applicable acceptance. |
| Maintainer station | [#68](https://github.com/lab-401/icopy-x/pull/68): maintained Classic reference read and one Windows PC-mode round trip. The interrupted session was explicitly reconciled; full read and the new local cancellation mode passed on 20 October | PC-mode evidence does not cover other hosts, endurance or mass-storage transfers. Physical passes apply to their recorded application and fixture, not every later runtime revision. |
| Releases | [#69](https://github.com/lab-401/icopy-x/pull/69): complete candidate archives; publication requires exact build/QEMU/host evidence and asset hashes | Maintainer release decision and change-specific physical evidence. A passing release gate is not hardware certification. |
| ICS Decoder | Host protocol/ownership regressions and QEMU absent/hotplug flows; #82 removes Move, #83 gates presence, #85 removes contributor About. Physical menu sweep confirmed Move absent, M1 inert and ICS hidden without hardware | Accessory unavailable: genuine discovery, capture, disconnect and write/readback remain blocked. Contributor About removal has host/QEMU evidence; absent hardware prevented ordinary physical navigation into that menu. |
| Factory/no-flash | Separate package/Lua/client family and QEMU command fixtures | Real factory-firmware device acceptance; the current physical device does not establish it. |
| Installation/flashing | Package/build checks and earlier reversible staging observations | Standard update/restart/recovery and fullimage flashing on stable power. Not covered by read or PC-mode passes. |

The [19 October record](PHYSICAL_ACCEPTANCE_20261019.md) identifies the tested
application and Classic/PC-mode cases. The
[20 October follow-up](PHYSICAL_ACCEPTANCE_20261020.md) records interruption
recovery, the reproduced screen-guard refusal and separate device-local
cancellation acceptance. Failed harness attempts remain preserved.
Earlier EM410x and USCUID-UL-compatible observations
informed regressions; they do not certify later runtime changes. No physical test is performed automatically
on a public PR runner. No source badge writes are part of the read cases.

The physical station operates a reviewed, already installed application. It is
not an installer, a full filesystem attestation or a wire-level RF analyzer.
UI-phase cancellation is distinguished from precise PM3 command timing. Missing
hardware and incomplete tests remain explicit gaps, never implicit passes.

The [issue #10 follow-up](reviews/2026-10-20-update-sidecars.md) reproduces the
reported orphaned macOS metadata layout against both current and pre-fix code.
Current selection and the inspected v1.1.7 package contain the fix; an older
installed updater can still fail while choosing a newer package. This is
filesystem/package-selection evidence, not physical installation acceptance.

The [current-code audit of #58–61](reviews/2026-10-20-open-issue-audit.md)
separates historical claims from reproducible defects. Added iCLASS contracts
exercise both firmware families through the real writer, translation, executor,
TCP and daemon-reader layers with controlled child output. They verify supported
success responses, first-block failure, cancellation/timeout and fresh-command
recovery without replay. Physical iCLASS write-abort recovery remains unverified.
The [decoder worker correction](reviews/2026-10-20-decoder-workers.md) moves
read/write/verify completion and timer changes onto the UI thread, snapshots
inputs and discards cancelled work. Host regressions and a dedicated ARM/Tk
case cover held completions and exit during detection. Synchronous blank-target
polling and genuine accessory acceptance remain separate limits.

## Next physical acceptance work

1. Retest EM410x recovery and the supplied Ultralight-compatible tag when present.
   The Classic read/local-cancel/re-read baseline is now recorded; repeat the
   applicable cases when deploying changes to those runtime paths.
2. Schedule factory/no-flash, real ICS, iCLASS write-abort and standard
   installation/flashing checks
   separately with appropriate hardware and stable power. Do not flash merely to
   accumulate coverage. The completed PC-mode round trip need not be repeated for
   menu-only changes; changed USB/PC behavior requires relevant new evidence.

Follow [PHYSICAL_TESTING.md](PHYSICAL_TESTING.md) for commands and interruption
recovery. Raw UID/dump/log evidence stays outside Git.

## Maintenance

The weekly build checks upstream PM3 drift even without an open PR. A failure
requires investigation; it must not be bypassed by dropping a patch or accepting
partial assets. The release gate keeps draft assets private until every digest
matches. See [RELEASE_PIPELINE.md](RELEASE_PIPELINE.md) for dry runs and recovery.

[PR #95](https://github.com/lab-401/icopy-x/pull/95) also closes a standalone
builder gap found during reviewer calibration: missing, empty or non-file inputs
for the selected PM3 client/Lua pair now fail before writing a package, including
dry runs. Both families retain separate inputs and an existing output survives
these preflight failures. The new regression reproduced a successful incomplete
build before the fix. All host/build/reviewer checks and
[QEMU run 39266710824](https://github.com/lab-401/icopy-x/actions/runs/39266710824)
passed for tested head `a39985c530dd3fbc573dcdb53d9c93dd8d8becb6`; the merge tree
matched it. This presence/size check does not replace provenance checks or
physical firmware acceptance.

The device's old interpreter and pinned runtime remain compatibility constraints;
passing tests do not remove their dependency advisories. Modern host tooling uses
patched pins, and Dependabot checks test/station requirements and Actions weekly.
Legacy dependency alerts remain open; see [TEST_DEPENDENCIES.md](TEST_DEPENDENCIES.md).
These changes are separate from a device-runtime migration.

The [automatic Astra advisory](../tools/auto_review/AUTOMATIC.md) is enabled.
It scans ready, open PRs targeting main approximately every 15 minutes, subject
to GitHub scheduling delays. The configured allowance is three automatic
reviews per rolling 24 hours. Durable reservations prevent duplicate paid
attempts; failed and stale reservations also count. This is an invocation
allowance, not a monetary ceiling. Manual pilot dispatches remain separate.

Selection, generation and publication run in separate jobs on trusted main.
The API key stays in the main-only `astra-review` GitHub environment; no
maintainer workstation is required. Candidate code is inspected as untrusted
source and never executed by the reviewer. Publication rechecks source identity,
retains validated partial findings and reports stale or missing results
explicitly. The model cannot approve or merge.

The [calibration corpus](../tools/auto_review/calibration/README.md) has produced
useful findings about menu changes, packaging, serial aliases and contributor
credits; an unexpected builder omission led to #95. Caller/context follow-ups
and the clarified submenu policy improved coverage and remediation. A useful
About control was preserved but exposed a supported gap in its synthetic
fallback change. This small, selected, partly synthetic corpus is not an accuracy
estimate. Complete advisory source coverage is not a test or hardware pass.

The early timeout and 6,000-token failures remain in the evaluation history.
The subsequent [startup baseline](https://github.com/lab-401/icopy-x/actions/runs/39297199836)
and [closed-PR review](https://github.com/lab-401/icopy-x/actions/runs/39298351294)
each returned all three validated passes, in 11.53 and 7.05 minutes respectively.
Both reported incomplete source coverage and useful findings; neither timed out
or hit the enlarged cap. A returned review with explicit gaps is not a complete
audit. Current limits are 128,000 output tokens per pass, 90 minutes overall and
a 100-minute model job, with no automatic generation retries. These two
measurements do not establish production reliability or a cost percentile.

See [the evaluation record](../tools/auto_review/EVALUATION.md) for exact
revisions, findings, usage and remaining work. Fresh scope-splitting, translation
and boot/recovery cases and continued assessment of real PR findings are still
needed. The four decoder follow-ups above correct actual source findings from
the startup evaluation; reviewer delivery alone did not establish those fixes.
The advisory is not a merge gate. Deterministic CI and human scope review remain
the merge criteria, especially for boot/update, translation, firmware, Lua
selection, USB ownership and build changes.
