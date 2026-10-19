# Validation status and remaining acceptance

Updated 19 October 2026. This is the current acceptance boundary; historical
captures and planning notes are not passes for the latest application.

## Contributor CI

Every PR must pass the three Linux/Windows host jobs and **QEMU critical flows**
with an up-to-date main branch. The build compiles the PM3 client and fullimage,
checks required patches and matching source/platform/FPGA metadata, builds both
IPKs and all desktop companions, and packages complete release candidates.
Required build failures prevent QEMU success. No physical device or private
factory image is needed on a contributor's computer.

The trusted QEMU harness runs the exact built flash and no-flash IPKs under ARM
Python 3.8.0 and Tcl/Tk 8.6.5. Its `critical-v6` profile has 23 cases per variant,
46 combinations. It exercises packaged application code, real Tk/threads,
translation/parsing, Reader behavior, cancellation and selected transport faults.
PM3 responses and hardware boundaries are controlled fixtures. It does not run
the physical PM3, boot the device kernel or prove RF/USB/flashing behavior.

The expanded profile passed on main after [#83](https://github.com/lab-401/icopy-x/pull/83)
in [run 39236635642](https://github.com/lab-401/icopy-x/actions/runs/39236635642).
It now checks decoder menu appearance/removal with controlled serial identities,
including isolation of the internal PM3. The subsequent contributor About removal
[#85](https://github.com/lab-401/icopy-x/pull/85) passed the same 23 cases per IPK
in [run 39236856190](https://github.com/lab-401/icopy-x/actions/runs/39236856190).

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
| Timeout/cancellation | [#67](https://github.com/lab-401/icopy-x/pull/67): bounded drain and no implicit replay; six supplemental physical Classic cancellation/re-read cases passed. #87 adds a bounded numeric progress guard | Latest maintained attempt refused input at its final screen guard; battery loss interrupted follow-up. Cause/retest, LF recovery and broader hardware abort timing remain pending. |
| Auto Copy exit | [#70](https://github.com/lab-401/icopy-x/pull/70): timer/callback guards; physical Classic Auto Copy read, exit and re-entry passed on the recorded candidate | Other card families and changed application versions require applicable acceptance. |
| Maintainer station | [#68](https://github.com/lab-401/icopy-x/pull/68): maintained Classic reference read and one complete Windows PC-mode round trip passed; later menu candidate also passed the reference read | Inspect/reconcile the battery-interrupted session, then complete maintained cancellation acceptance. PC-mode evidence does not cover other hosts, endurance or mass-storage transfers. |
| Releases | [#69](https://github.com/lab-401/icopy-x/pull/69): complete candidate archives; publication requires exact build/QEMU/host evidence and asset hashes | Maintainer release decision and change-specific physical evidence. A passing release gate is not hardware certification. |
| ICS Decoder | Host protocol/ownership regressions and QEMU absent/hotplug flows; #82 removes Move, #83 gates presence, #85 removes contributor About. Physical menu sweep confirmed Move absent, M1 inert and ICS hidden without hardware | Accessory unavailable: genuine discovery, capture, disconnect and write/readback remain blocked. Contributor About removal has host/QEMU evidence; absent hardware prevented ordinary physical navigation into that menu. |
| Factory/no-flash | Separate package/Lua/client family and QEMU command fixtures | Real factory-firmware device acceptance; the current physical device does not establish it. |
| Installation/flashing | Package/build checks and earlier reversible staging observations | Standard update/restart/recovery and fullimage flashing on stable power. Not covered by read or PC-mode passes. |

The [19 October physical acceptance record](PHYSICAL_ACCEPTANCE_20261019.md)
identifies the tested application, successful Classic and PC-mode cases, and the
failed harness attempts. Earlier EM410x and USCUID-UL-compatible observations
informed regressions; they do not certify later runtime changes. No physical test is performed automatically
on a public PR runner. No source badge writes are part of the read cases.

The physical station operates a reviewed, already installed application. It is
not an installer, a full filesystem attestation or a wire-level RF analyzer.
UI-phase cancellation is distinguished from precise PM3 command timing. Missing
hardware and an interrupted session remain explicit gaps, never implicit passes.

## Next physical acceptance work

1. After recharging, inspect boot/application identity and the retained lease of
   the interrupted menu session. Resolve it explicitly without replaying input.
   Menu sweep and full Classic read passed before the interruption.
2. Repeat maintained cancel-read against the enrolled Classic reference with
   adequate power. The numeric guard fix is merged, but the final screen mismatch
   in the latest attempt remains unexplained. Preserve unsuccessful cases.
3. Retest EM410x recovery and the supplied Ultralight-compatible tag when present.
4. Schedule factory/no-flash, real ICS and standard installation/flashing checks
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
The [Astra advisory pilot](../tools/auto_review/README.md) from #88 is available as
a manual workflow on trusted main. Updates through #99 have 48 offline
contracts passing on Linux and Windows, with host/build/QEMU checks passed before
merge. [Hosted preparation 39248718899](https://github.com/lab-401/icopy-x/actions/runs/39248718899)
completed without an API key and produced the same immutable snapshot digest as
the local historical-menu trial. This validates hosted collection, not model
quality. The first [live trial](https://github.com/lab-401/icopy-x/actions/runs/39252019439)
confirmed service-account authentication and Astra access, but response/evidence
validation rejected its first response. After fixed diagnostics and numbered
source were added, five live trials completed fifteen validated responses. The
known Move regression was identified twice. Three removal controls found no
introduced defects; the last reached complete advisory source coverage after
bounded reference searches and caller context were supplied in
[run 39261258391](https://github.com/lab-401/icopy-x/actions/runs/39261258391).
Stable source prompts also demonstrated cache reuse on both later review passes.
The subsequent [domain corpus](../tools/auto_review/calibration/README.md)
contains nine original cases and one changed-context follow-up. Eight source
comparisons returned 24 validated responses and found the seeded packaging,
serial-alias and credits defects; an unexpected builder omission led to #95.
Four final reviews retained specific context gaps. Credits remediation was too
permissive about retaining a static feature-version submenu. Both attempts at
the larger accessory-startup comparison timed out before returning a review,
leaving that scope judgment unassessed and their API usage unknown.
Follow-up changes #97-99 preserve failed-attempt diagnostics, add bounded caller
profiles, avoid duplicating identical unchanged source in prompts, and clarify
complete removal of contributor-only submenus. All passed host/reviewer/build
and both-IPK QEMU checks before merge. The repeated alias comparison now reaches
complete advisory source coverage; the credits comparison now recommends full
submenu/state/navigation removal while preserving useful device diagnostics.
The static-version submenu counterexample received the same complete-removal
guidance without inventing contributor branding. The useful-diagnostics control
preserved About and identified a supported gap in its synthetic fallback change;
it is not a finding-free clean-control pass. Four follow-up comparisons returned
twelve validated responses and complete source advisories.
The accessory-startup comparison timed out a third time without response
headers, review or usage, after 120.125 seconds. The cause remains unknown.
These results do not establish general review accuracy or resolve the transport
reliability issue. Complete source coverage is not a test pass, device acceptance
or merge approval. See
[the evaluation record](../tools/auto_review/EVALUATION.md) for exact revisions,
findings and usage. The API key is in the main-only
`astra-review` environment. Automatic invocation/publication and a model gate
remain unimplemented. Human scope review is still required, especially for
boot/update, translation, firmware, Lua selection, USB ownership and build changes.
