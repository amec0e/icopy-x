# Pilot evaluation record

19 October 2026. Offline contracts and an initial live integration trial are
recorded separately below; review quality is not yet established.
The 27 contract tests pass on local Windows/Python 3.12. Workflow syntax passes
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

Recorded usage: 666,301 input tokens, 6,884 output tokens, 662,861 cache-write
tokens, 3,431 cached-input tokens and 161.683 API seconds. Larger manually selected
context approximately doubled input usage compared with the first clean trial,
without closing the repository-wide evidence gap.

## Acceptance and next work

The service-account/GitHub execution path works. Nine post-fix Responses passed
validation across three live trials. The known Move regression was identified,
and the two removal trials produced no introduced-defect findings. Their final
semantic coverage remained explicitly incomplete; no live trial has yet earned
`ADVISORY_COMPLETE`. The first pre-fix rejected response remains unexplained.

Before automatic invocation, the next collector work should provide bounded,
source-addressed reference searches and caller context from the immutable Git
objects, with explicit limits and gaps. It must not execute candidate code or
weaken the complete-file inventory/citation checks. Evaluate useful context
selection and prompt-cache reuse before multiplying paid trials: the three passes
currently resend large bundles with very little cache reuse. The labeled Lua,
serial-ownership, contributor-credits, legitimate startup and injection cases
listed above remain required. None of these results is a merge gate, hardware
acceptance, statistical quality score or basis for automatic publication.

The environment secret belongs in GitHub; a developer workstation is not part
of the hosted execution path. Review accuracy, false-positive rate and typical
cost remain unvalidated.
