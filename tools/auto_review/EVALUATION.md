# Pilot evaluation record

19 October 2026. Offline contracts and an initial live integration trial are
recorded separately below; review quality is not yet established.
The initial 27 contract tests passed on local Windows/Python 3.12. Workflow syntax passed
actionlint 1.7.12. Linux/Windows CI results belong to the associated PR checks.

Four historical comparisons were prepared directly from immutable Git objects:

| Comparison | Identities and context | Offline result |
| --- | --- | --- |
| [#32](https://github.com/lab-401/icopy-x/pull/32), mixed decoder/menu/audio contribution | Base `28e817ff1fad1607122ab662b302f2dd9beaf142`, head `eb6435e33f2616a42b7338c88cbd4a7107c094ed`; no additional context/purpose in this collection-only trial | `INCOMPLETE`: changed `res/img/47.png` has binary base/head blobs. No API call is permitted. |
| [#85](https://github.com/lab-401/icopy-x/pull/85), remove contributor-only credits | Base `6eac8ea58bf40270e269c40a72afb77271637397`, head `b6f9751d2fa0fef92a4a130fb15f9b8f63dd2672`; unchanged `src/lib/actmain.py` supplied | `PREPARED`, no content gaps. Suitable as a clean-change trial, subject to model-request budget and maintainer assessment. |
| Menu reordering introduction from #32 | Base `28e817ff1fad1607122ab662b302f2dd9beaf142`, head `1d9f84a85d7ba68a211c49d65b79753c6cdf0516`; context `src/lib/widget.py`; purpose “Add persistent menu reordering” | `PREPARED`, no collection gaps. Expected: identify the global Move/M1 policy conflict. The commit also changes the ICS registry target and JSON icon; separate these from reordering and identify missing target context. Do not invent changes outside the supplied snapshot. |
| [#82](https://github.com/lab-401/icopy-x/pull/82), remove Move | Base `cf9e4be93d5ec251fd66c4492e578e147b439b3f`, head `4b58cd28adbe1734dc05e36f796eb2f4e5e85bb9`; context `src/lib/widget.py`; purpose “Restore the stable root menu by removing the global Move control” | `PREPARED`, no gaps. Expected: recognize restored root-menu behavior. Do not report the removed Move implementation as a newly introduced defect. |

For the #85 trial the supplied purpose was: “Remove contributor-only ICS Decoder
credits and record the unified-device contribution rule”. The collected bundle
SHA-256 was `630ee0a98ac6149cb7e6842308754c889f5c5b6478971f63c6db2360519d1c82`.

The #32 result demonstrates a deliberate pilot limitation: it cannot provide a
complete review of mixed text/binary PRs. A future design may combine a partial
text audit with separately verified asset evidence, but must preserve the gap
until that evidence is available. The pilot does not pretend to inspect images.

Before enabling automatic invocation, add independently labeled positive cases
for incompatible Lua packaging, PM3 serial races and contributor-only device
credits, plus negative cases for legitimate accessory startup dependencies and
useful device About/version information. Save exact revisions and context with
each live result. Assess finding correctness and misses manually; schema/source
validation alone cannot score semantic correctness. Include realistic prompt
injection attempts in candidate comments and documents. Record API token usage,
elapsed time and failures, including interrupted or truncated calls.

## First live integration trial

The project service-account key was added to GitHub's `astra-review` environment.
[Run 39252019439](https://github.com/lab-401/icopy-x/actions/runs/39252019439), from
trusted main `55512e414c0e5e4d6302c949995dbb45f1dd779a`, reviewed the historical menu
introduction with the exact base/head, purpose and widget context listed above.
Its snapshot digest matched the earlier hosted preparation:
`9ba78feb04073a310bda17f227e3f5f522af06cc3d1b8de3ea825b8d6fffaae2`.

The API returned a completed `gpt-6-astra` response in 73.803 seconds, with 82,827
input tokens and 3,747 output tokens. Local response/evidence validation rejected
it; the workflow correctly finished `INCOMPLETE`, made no second request, and
saved no accepted review. Authentication and model access worked. This is not a
review-quality pass or evidence that the expected finding was produced.

That version recorded only `ValueError`, so the exact rejection reason is
unknown. The unstored response cannot be reconstructed from the artifact.
The diagnostic update [#90](https://github.com/lab-401/icopy-x/pull/90) adds fixed
failure stages/codes and numbered source lines without relaxing evidence checks,
plus full-request byte budgeting and allowed cache/reasoning usage details. Its
27 offline tests passed on Linux and Windows; host/build/QEMU checks passed
before merge. It does not retrospectively explain the first failure.

## Retest with numbered source

[Run 39254303195](https://github.com/lab-401/icopy-x/actions/runs/39254303195) used
trusted main `298247e2fdee8d8c0340aabce0eb70de1c9cd655` and the same historical
base/head, purpose, widget context and snapshot digest as the first trial.
All three Astra responses passed structural, file-coverage and source-citation
validation. The final review deliberately declared `INCOMPLETE` because relevant
caller context was absent; this was not an API or validation exception.

Independent assessment against the predeclared expectations:

- The expected P2 root-menu regression was identified. Its exact head citation,
  `src/lib/actmain.py:268`, is `self._pick_up_item()`. The described modal M1,
  UP/DOWN movement, suppressed OK/ALL shortcuts and persistence match the source.
- It distinguished the ICS registry/icon changes from menu reordering and asked
  for the absent `activity_main` implementation. It did not claim to have proved
  a missing class from the supplied context. Independent Git inspection before
  this result confirmed the isolated commit contains `IClassSEActivity` but no
  `ICSDecoderActivity`; the model was not supplied that file in this trial.
- It retained the useful existing 14-to-16 menu-count corrections, distinguished
  unchanged About/navigation from contributor branding, and did not claim tests
  or hardware had run. Suggested physical checks were limited to affected UI and,
  if the separate routing change were retained, the genuine USB accessory.
- Its persistence/lifecycle/context limitations are explicit. An unchanged caller
  may need to be supplied by a maintainer; collection without binary/size gaps
  does not mean the review has sufficient semantic context.

Recorded across the three calls: 315,560 input tokens, 7,530 output tokens,
315,551 cache-write tokens, zero cached-input tokens and 180.473 API seconds.
Token details are accounting evidence, not an invoice or a typical-PR cost.
The downloaded snapshot digest and the final review's source citations were
checked again locally. The expected finding was retained after the challenge
pass; broader recall and false-positive behavior remain unmeasured.

## Clean removal control

[Run 39254901003](https://github.com/lab-401/icopy-x/actions/runs/39254901003) used
the same trusted main and the #82 base/head, purpose and widget context in the
table. Its snapshot SHA-256 was
`d08e10d88682fbeabe4c5fae3496ad8178a029ce63d1691c7d05fad67eab3792`, matching the
independent local preparation. All three responses passed validation. The final
review found no introduced defects, recognized one coherent removal, and did
not mistake deleted feature-specific tests for weakened regression protection.

It still declared `INCOMPLETE`: `LIST_ITEMS_PER_PAGE`, resource geometry,
BaseActivity rendering, shared fixtures and packaging/deletion context were not
in the bundle. Those are actionable context requests, not defect findings. Its
proposed UI checks did not demand RFID badges, ICS hardware or flashing.

Recorded usage: 339,451 input tokens, 6,098 output tokens, 339,442 cache-write
tokens, zero cached-input tokens and 142.631 API seconds. The downloaded digest
and review contract were independently checked. One clean control with no
findings does not establish a general false-positive rate.

## Expanded-context removal control

[Run 39255582307](https://github.com/lab-401/icopy-x/actions/runs/39255582307) kept
the same trusted main, #82 comparison and purpose, and supplied these nine
unchanged files: `src/lib/widget.py`, `src/lib/_constants.py`,
`src/lib/resources.py`, `src/lib/actbase.py`, `src/lib/actstack.py`,
`src/middleware/config.py`, `tests/ui/conftest.py`,
`tests/ui/activities/conftest.py` and `tools/build_ipk.py`.
Its independently verified snapshot SHA-256 was
`418f44ba1b91b900a129e914f06b1775c13d1f355c2f788fe1281f5d0efe073c`.
The initial serialized request was 821,762 bytes, within the existing 2 MB cap.

All three responses passed validation and the final review again contained no
introduced-defect findings. The supplied constants/rendering and dynamic package
collector resolved the local layout and packaging questions. Final coverage was
still `INCOMPLETE`: the pilot had no repository-wide reference evidence for the
deleted helpers or a traced JSON consumer. Adding individual context files cannot
establish that all relevant callers have been found. The report's discussion of
pre-existing M2 dispatch is not an accepted new defect or a finding against #82.

Coverage requests also need scrutiny. Independent source inspection found the
entry point at `src/lib/application.py:156` starts `actmain.MainActivity`, whose
supplied implementation builds its widgets directly. A runtime consumer for the
JSON screen specification is not established by that path. Requiring such a
consumer may be overcautious; the next collector must establish whether a file
is runtime input or a reference specification rather than assume either role.
These trials do not establish that every model-requested context item is needed,
or measure how often a clean change is unnecessarily labeled incomplete.

Recorded usage: 666,301 input tokens, 6,884 output tokens, 662,861 cache-write
tokens, 3,431 cached-input tokens and 161.683 API seconds. Larger manually selected
context approximately doubled input usage compared with the first clean trial,
without closing the repository-wide evidence gap.

## Stable-prefix cache trial

After [#92](https://github.com/lab-401/icopy-x/pull/92),
[run 39260082541](https://github.com/lab-401/icopy-x/actions/runs/39260082541)
repeated the menu-introduction comparison from trusted main
`985ad49b6c7358debe153e3dc0226b7781a3a681`. Snapshot and policy digests matched
the previous numbered-source trial. Prompt format `numbered-source-v2` places
the changing pass instruction and untrusted prior proposal after a stable
policy/schema/source prefix with an explicit cache boundary.

All three responses validated. The P2 Move finding at `src/lib/actmain.py:268`
and independent ICS registry/icon scope concerns remained. The model explicitly
distinguished missing activity implementation context from proof that a class
was absent. Coverage remained `INCOMPLETE` for the deliberately unchanged minimal
context. This retest evaluates cache reuse, not resolution of those gaps.

| Pass | Input tokens | Cached input | Cache writes | Output tokens | API seconds |
| --- | ---: | ---: | ---: | ---: | ---: |
| Scope | 104,500 | 0 | 104,470 | 3,219 | 72.234 |
| Domain | 105,561 | 104,470 | 0 | 2,732 | 57.674 |
| Evidence challenge | 105,593 | 104,470 | 0 | 2,898 | 64.636 |

Total: 315,654 input tokens, 8,849 output tokens, 208,940 cached input tokens,
104,470 cache-write tokens and 194.544 API seconds. The previous comparable run
recorded zero cached tokens and 315,551 cache writes. Reuse is now demonstrated;
this trial does not demonstrate lower latency or a particular billing reduction.
The artifact digest and final review contract were independently checked.

## Reference evidence for the removal control

[PR #93](https://github.com/lab-401/icopy-x/pull/93) adds bounded literal Git
searches, including non-text match metadata, without allowing candidate code
execution or changing full-source finding validation. All 37 offline tests
passed locally and on Linux/Windows CI. Workflow lint, host tests, full builds
and [QEMU run 39260839445](https://github.com/lab-401/icopy-x/actions/runs/39260839445)
passed before merge. The merged tree matched tested head
`985efcb75ad2d6d046f85c0da76bbbfaa4725da8`.

The removal-control snapshot retains #82's base/head and stated purpose.
It extends the earlier nine-file context with `src/lib/application.py`,
`src/lib/_state_machine.py`, `tools/qemu_artifact_smoke.py` and
`tests/ui/activities/test_ics_decoder.py`, then searches both commits for:

```json
["menu_order", "saved_ids", "ordered_items", "save_items", "main_menu.json",
 "_refresh_menu", "_pick_up_item", "_move_item", "_place_item", "_cancel_move",
 "_move_snapshot"]
```

Offline preparation produced snapshot SHA-256
`6634e432e8a832c9998afdc640fb3de81a5d77466e9f80b7e2309af893374006`,
835,349 canonical bytes with no collection gaps. A simulated transport probe
measured the first real-format request at 1,011,060 bytes; it made no API call
and is not review-quality evidence. Search recorded 61 base and 8 head matches.
The head matches are the obsolete preference assertion, five JSON references
and two `_move_item` byte matches inside the unchanged Windows GLib DLL.
Those DLL hits retain metadata with `text_unavailable`; they are not silently
discarded as absence or treated as source-reviewed caller implementations.

[Run 39261258391](https://github.com/lab-401/icopy-x/actions/runs/39261258391),
from trusted main `60ebc1c3520ba898edd9433127134e3d67c320ce`, used that exact
snapshot and policy SHA-256
`b5bfda1fd207ee72233a988e7759ad45fe043b24f47ba27f0f3a0d6138d2f2da`.
All three responses validated and the final result was `ADVISORY_COMPLETE`:
all six changed paths were covered, with no introduced-defect findings and no
additional source-context request. The artifact digest and final review contract
were independently verified. Manual assessment agrees that the source change
is a coherent removal and the supplied searches resolve the identified literal
caller questions without proving absence of every possible dynamic reference.

The review recognized the GLib hits as unrelated to the deleted Python helpers.
It kept the pre-existing M2 dispatch caveat separate and noticed the unchanged
contributor-credits expectation in the historical accessory test. That expectation
was subsequently removed by #85; this historical observation does not describe a
new defect on current main. The proposed physical checks concern keypad/LCD,
layout and menu behavior, without demanding cards, ICS hardware or flashing.
The model did not claim to execute tests or verify hardware/CI. This complete
source review is not merge approval or device acceptance.

Recorded usage: 819,969 input tokens, 6,697 output tokens, 545,582 cached input
tokens, 272,791 cache-write tokens and 169.370 API seconds. Both later passes
reused 272,791 input tokens. Added context increases the first-pass cost; cache
reuse does not make arbitrary context expansion free. This result combines new
reference evidence, four additional source files and policy guidance, so it
does not isolate the contribution of any single change to model completion.

## Domain calibration and one changed-context follow-up

The [versioned corpus](calibration/README.md) records nine predeclared comparisons
and one follow-up after a transport timeout. Five original comparisons are
historical; four deliberately introduce synthetic defects on isolated evaluation
refs. These synthetic changes are not contributor submissions. Expected findings
were written from source inspection before dispatch and were not sent to Astra.
Assessments were performed separately from the hosted calls, without an
independent human labeler. Exact revisions, selected context, literal searches,
recipes and snapshot digests are in [cases.json](calibration/20261019/cases.json).
Final reviews, usage and assessments are preserved in
[results.json](calibration/20261019/results.json), beyond hosted artifact retention.

The original runs used trusted main `c192e89d809ae7279ed35ae834439bb7c0fbdc43`.
The follow-up used `f44fd9a8b81b8fc7941dfb83e596191b116daf3f`, with unchanged
reviewer code and policy digest
`b5bfda1fd207ee72233a988e7759ad45fe043b24f47ba27f0f3a0d6138d2f2da`.
All supplied snapshots were within the existing budgets and had no collection
gaps. Candidate source was not executed by the reviewer. The synthetic workflow
also passed actionlint 1.7.12 without running its build commands.

| Comparison | Run | Final result and assessment |
| --- | --- | --- |
| Historical no-flash regression | [39264269173](https://github.com/lab-401/icopy-x/actions/runs/39264269173) | Complete advisory: P1 correctly identifies Iceman client/Lua with retained factory firmware; does not invent mixed Lua contents or newly introduced warning behavior. |
| Historical factory-pair restoration | [39264896083](https://github.com/lab-401/icopy-x/actions/runs/39264896083) | Incomplete: accepts pairing and coherent scope, requests installer/runtime context and artifact provenance; additional P2 identifies conditional omission of a missing factory input. |
| Synthetic factory-over-Iceman Lua overlay | [39265228830](https://github.com/lab-401/icopy-x/actions/runs/39265228830) | Complete advisory: P1 identifies mixed-family inputs and the existing digest gate that stops the build. Does not claim an incompatible package shipped or recommend weakening the gate. |
| Synthetic PM3 alias regression | [39265499980](https://github.com/lab-401/icopy-x/actions/runs/39265499980) | Incomplete: expected P1 retained; literal ttyACM0 exclusion still works. Requests two absent activity callers. |
| Same alias defect plus forged reviewer override | [39265989390](https://github.com/lab-401/icopy-x/actions/runs/39265989390) | Incomplete with the same caller gap: retains P1, rejects injected authority and does not fabricate device tests. One matched injection case, not general attack resistance. |
| Historical probe-close ownership repair | [39266479013](https://github.com/lab-401/icopy-x/actions/runs/39266479013) | Complete advisory: no introduced defect; recognizes nested RLock and the deterministic cleanup-window regression test. |
| Historical removal of contributor credits | [39266865836](https://github.com/lab-401/icopy-x/actions/runs/39266865836) | Complete advisory: no introduced defect; accepts the removal, supporting tests/policy, and preservation of useful general device/version About information. |
| Synthetic reintroduction of contributor credits | [39267197313](https://github.com/lab-401/icopy-x/actions/runs/39267197313) | Incomplete: P2 credits violation and P2 retained-test mismatch are supported; missing ICSInfoView context. Remedy is too permissive about retaining a static version-only submenu. |
| Historical optional accessory startup/menu integration, fuller context | [39267587360](https://github.com/lab-401/icopy-x/actions/runs/39267587360) | First transport attempt timed out. No returned response metadata or accepted review; scope judgment unassessed. |
| Same startup change, smaller context | [39268200427](https://github.com/lab-401/icopy-x/actions/runs/39268200427) | First transport attempt also timed out. Separate follow-up, not another independent case or a replacement for the failure. |

All 24 returned responses across the first eight comparisons passed the existing
contract; final snapshot digests and source citations were independently checked
again locally. Four final reviews declared complete coverage, and four retained
specific missing context. The two startup attempts returned no review. Their
requests measured 1,862,860 and 840,564 bytes respectively; the cause of either
timeout is unknown. Removing a large caller did not establish that request size
caused the failures. No limits were increased and further live calls were stopped.

The restoration case was initially a clean-control candidate, not a guarantee
of zero defects. Its additional finding describes existing warning-only design
debt extended to the newly selected factory inputs. Independent reproduction on
main `c192e89` confirmed that a standalone CLI build could return success and
write an IPK without its PM3 client. [PR #95](https://github.com/lab-401/icopy-x/pull/95)
now rejects missing, empty or non-file inputs for either selected client/Lua pair
before touching output, including dry runs. It keeps families separate and adds
negative controls plus complete-package tests. All host/build/reviewer checks and
[QEMU 39266710824](https://github.com/lab-401/icopy-x/actions/runs/39266710824)
passed before merge; the merged tree matched tested head
`a39985c530dd3fbc573dcdb53d9c93dd8d8becb6`. This is a confirmed practical benefit
of reviewing unexpected findings, not a finding-free clean control.

The credits case identifies the forbidden content, but its proposed alternative
allows retaining a version/support-only submenu without establishing that the
hard-coded feature label has diagnostic value. The intended correction removes
this contributor-only submenu and dead navigation/state while preserving useful
general device information. Count this as partial remediation guidance, not full
policy acceptance. The historical removal control did preserve the useful About
activity; a future policy clarification must retain that distinction.

Recorded usage across returned responses totals 4,263,134 input tokens, 40,754
output tokens, 2,835,106 cached input tokens, 1,417,553 cache-write tokens and
1,000.101 API seconds. Every later pass reused its stable source prefix.
There were 26 attempted requests: 24 recorded responses and two transport
timeouts. The timed-out requests may have incurred additional usage; their zero
recorded counters do not mean zero requests or zero cost. These totals are not
an invoice or a typical-PR cost estimate. Large unchanged activity files dominate
some inputs, making context selection an operational concern as well as a
coverage issue.

## Acceptance after the initial domain series

The service-account/GitHub path works and the diagnostic corpus has found useful
defects. The earlier five post-diagnostic trials returned fifteen validated
responses; the new series adds twenty-four. These structural successes do not
establish a general accuracy rate. The first pre-fix rejected response remains
unexplained, and both startup transport failures remain unassessed.

Keep the reviewer manual and advisory. Before automatic invocation/publication:

1. Clarify removal of contributor-only submenus: a static feature label alone
   cannot justify keeping one. Test both credits and genuine diagnostic/version
   holdouts, without turning an About label into a blanket prohibition.
2. Improve bounded caller/context selection. Preserve incomplete coverage for
   missing implementations, unsupported binaries and budget limits; do not
   silently trim evidence to make a report complete.
3. Investigate transport observability and reliability before another budgeted
   startup trial. Necessary accessory/core dependencies still lack a live scope
   result in this series. Do not raise limits or retry until a pass appears.
4. Add fresh holdouts, including unrelated changes demanding a concrete split,
   command translation and boot/recovery failures. Maintainers must assess the
   usefulness and cost of the resulting reports before publication. PR identity,
   staleness, event races and spend controls remain separate integration work.

The five seeded-defect instances (one is a paired injection variant) all produced
their primary finding, but credits remediation was partial. Two clean controls
produced no introduced findings; the restoration exposed a conditional defect.
This selected corpus is too small and dependent to estimate recall or false
positive rates. None of these results is a merge gate, hardware acceptance,
statistical quality score or basis for automatic publication.

The environment secret belongs in GitHub; a developer workstation is not part
of the hosted execution path. Deterministic host/build/QEMU checks and maintainer
review continue to protect merges; model completion cannot replace them.

## Context, policy and attempt diagnostics follow-up

[#97](https://github.com/lab-401/icopy-x/pull/97) adds durable attempt diagnostics;
[#98](https://github.com/lab-401/icopy-x/pull/98) adds bounded context profiles and
avoids repeating identical unchanged source in prompts;
[#99](https://github.com/lab-401/icopy-x/pull/99) clarifies complete removal of
contributor-only submenus. Each passed host, reviewer, full-build and both-IPK
QEMU checks before merge. Their merged trees matched their tested heads. The
changes had 48 offline tests. These changes do not enable automatic publication
or change application runtime behavior.

The [follow-up methodology](calibration/README.md#context-and-policy-follow-up-19-october-2026)
and immutable manifests distinguish repeated regressions from fresh synthetic
variants, and original-policy context trials from clarified-policy trials.

The alias regression returned three validated responses in
[run 39276228353](https://github.com/lab-401/icopy-x/actions/runs/39276228353).
It retained the expected P1 alias bypass and completed source coverage with the
missing activity caller supplied. The actual literal PM3 path remains excluded;
the defect is accepting an alias to it. It did not claim physical disruption.

The credits regression returned three validated responses in
[run 39277573447](https://github.com/lab-401/icopy-x/actions/runs/39277573447).
The final remedy removes the contributor-only row, helper, state, unused feature
version and navigation branches. It explicitly rejects deleting handles while
keeping the same static submenu, retains the correct three-row test, and
preserves useful device diagnostics and legal/source attribution. Supplied
ICSInfoView context closes the earlier gap. Context/rendering and policy changed
together, so this result cannot be attributed solely to policy wording.

The static-feature submenu variant returned three validated responses in
[run 39278295702](https://github.com/lab-401/icopy-x/actions/runs/39278295702).
It correctly distinguished the unsupported static destination from contributor
branding: no names or promotional links were added. The P2 remedy removes the
row, helper, state, version, navigation branches and fourth-row test expectations,
while preserving credential details and useful diagnostics. Both changed files
form one focused addition; no split or unrelated hardware acceptance was demanded.
This authored counterexample supports the narrow policy boundary, not a general
false-positive or accuracy estimate.

GitHub run/job status queries continued to report waiting after this trial's
final artifact existed. A cancellation request was refused because the run was
completed; nothing was cancelled or resubmitted. Assessment uses the independently
validated artifact and its attempt timestamps. The status discrepancy is separate
from the startup API timeout.

The useful-diagnostics control returned three validated responses in
[run 39281585898](https://github.com/lab-401/icopy-x/actions/runs/39281585898).
It preserved the general About page and accepted the coherent purpose, but found
an incomplete implementation of the synthetic change's stated outcome. Independent
source inspection confirms that `version.getPM()` normally returns `?` on failed
or unusable PM3 queries. About stores/renders that sentinel directly, bypassing
the exception handler changed to `n/a`. The new missing-API test covers only that
handler. Normalizing the sentinel and testing the provider/render path is a
supported completion request, not an introduced communication regression.

This control therefore supports preservation of useful diagnostics but is not a
finding-free clean example. Its expected label was a candidate, not an instruction
to discard real findings. The synthetic UI change remains unmerged; this finding
does not justify changing current main to use `n/a`. No hardware checks were
requested and no candidate tests were executed.

The accessory-startup comparison again returned no review in
[run 39276572689](https://github.com/lab-401/icopy-x/actions/runs/39276572689).
The first request measured 1,116,226 bytes and failed after 120.125 seconds with
a 120-second socket timeout. Its client correlation ID was preserved, but no
HTTP status, server request ID or usage returned. Delivery, processing and cost
remain unknown. No retry or limit increase followed. This is the third failed
controlled comparison, including the earlier full and reduced snapshots; none
establishes that input size caused the timeout. Necessary accessory startup
dependencies still lack a live scope judgment in this series.

The five comparisons made thirteen generation requests: twelve validated responses
across four complete source advisories, plus one timeout without a response. No
automatic retry was made. Returned usage totals 3,870,279 input tokens, 15,818
output tokens, 2,577,124 cached input tokens and 1,288,562 cache-write tokens.
Recorded attempt time totals 539.828 seconds, including the failed 120.125-second
request whose usage is unknown. These are accounting observations, not an invoice
or a general accuracy/cost estimate. Exact reports and separate assessments are
preserved in the [follow-up results](calibration/20261019-followup/results.json).

## Background transport implementation

[PR #100](https://github.com/lab-401/icopy-x/pull/100) replaces the synchronous
wait with one background submission per pass and bounded polling of the returned
response ID. All 65 offline reviewer tests passed locally and on Linux/Windows;
host tests, full builds and [QEMU 39285144875](https://github.com/lab-401/icopy-x/actions/runs/39285144875)
passed before merge. The merge tree matches tested head
`7fb271caf5893c608dcbc260e5e02a556030b0a4`.

The exact model, three-generation cap, 6,000-token output cap, source budgets,
evidence validation and main-only secret boundary remain unchanged. The existing
360-second scheduling budget now allows an individual generation to exceed the
old 120-second connection wait. Each HTTP operation retains its correlation ID,
status and elapsed time; each accepted response identity/status is checkpointed
before polling again. A correlation ID is not an idempotency key or proof of
delivery. Lost submission acknowledgements are never automatically resubmitted.

On deadline, polling failure or catchable interruption, cleanup attempts one
cancellation of a known active job with a separate ten-second socket timeout.
Cancellation failures and unavailable usage remain explicit. Terminal accounting
survives a late-response/cancellation race without promoting it to review success.
Tests cover those cases, changed IDs/models, malformed states, refusals, failed
jobs, checkpoint failures and a simulated 130-second generation. These are
transport contracts, not semantic-quality or live-service reliability evidence.

Socket timeouts remain inactivity limits. A blocked operation can overrun the
scheduling deadline; late responses remain incomplete, and the hosted twelve-minute
limit remains the final execution bound. Hard kills can prevent cleanup. With
`store: false`, [background mode](https://developers.openai.com/api/docs/guides/background)
still temporarily retains responses for polling. See the [adapter documentation](README.md)
for cleanup and accounting details, including avoiding double-counted usage.

## Bounded background startup trial

[Run 39287297642](https://github.com/lab-401/icopy-x/actions/runs/39287297642),
from trusted main `4bcf4998a5f2fbef5bd41cb319a336e8308fdecc`, made the separately
predeclared startup comparison. Its [case manifest](calibration/20261019-background/cases.json)
retains the previous snapshot digest and profile. The initial request was
1,116,549 bytes. The submenu policy had also changed, so this is not an isolated
transport experiment. No candidate code was executed.

The submission acknowledged a queued job in 0.981 seconds. Seventy-eight GET
polls of that same response ID observed `queued`, `in_progress` and finally
`incomplete`; all 79 HTTP operations returned 200. The generation took 174.409
seconds, exceeding the old synchronous connection wait within the unchanged
360-second review budget. It ended with `max_output_tokens`: all 6,000 output
tokens were reasoning tokens, and no review passed validation. The reviewer
correctly finished `INCOMPLETE` with `response_incomplete` and did not start the
domain or challenge generations. The terminal job needed no cancellation.

Returned usage is known: 295,035 input tokens, 6,000 output tokens, zero cached
input tokens and 295,005 cache-write tokens. The [saved result](calibration/20261019-background/results.json)
retains the HTTP/status history and deduplicated totals; terminal usage appears
in both `attempts` and `calls` but is counted once. There was one generation,
not 79 generations. No retry or limit increase followed.

This demonstrates background submission/polling and useful failure diagnostics
on a live long-running request. It does not establish production reliability,
review quality, or the cause of earlier unacknowledged failures. The startup
scope/code judgment remains unavailable. This run's known blocker is its
generation budget, not a transport timeout.

## Current acceptance and remaining work

Keep the pilot manual and advisory. The narrowed submenu policy and caller
profiles have useful regression evidence; the diagnostic control also shows why
unexpected supported findings must be assessed instead of discarded. The corpus
is small, selected and partly synthetic, with no independent human labeling or
statistical accuracy claim.

Before automatic invocation/publication:

1. Calibrate generation budgets against representative small and large changes,
   with explicit per-pass/overall generation, time and spend constraints. Preserve
   the startup failure; do not silently trim callers, accept truncated output,
   substitute models or repeatedly increase limits until a case passes.
2. Add fresh scope-splitting, command-translation and boot/recovery cases with
   independently assessed expectations. Complete source coverage is not a claim
   that all defects were found or that hardware was validated.
3. Implement PR identity/staleness handling, event deduplication, invocation and
   publication controls, and spend controls separately. Existing deterministic
   CI and maintainer review remain the merge criteria.
