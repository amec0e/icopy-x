# Reviewer calibration corpus

This directory preserves task-specific expectations and live results separately
from the review policy. It is a small diagnostic corpus, not a statistical
accuracy benchmark or permission to merge a candidate.

## 19 October 2026 method

Nine original cases and one changed-context follow-up in [cases.json](20261019/cases.json)
cover factory/no-flash selection, Lua
archive separation, PM3 serial aliases and handle ownership, contributor-only
credits, necessary accessory/menu startup changes, and one prompt-injection pair.
Expectations were written from source inspection before each case's live run.
Only `base`, `head`, `purpose`, `context` and `searches` were sent to the hosted
workflow. Expected findings, recipes and assessments were not model input.
The source assessor and the hosted Astra calls were separate; this does not
constitute independent human labeling or multiple independent model reviewers.

Five original comparisons use historical commits. Four are clearly labeled synthetic
changes: mixed Lua packaging, weakened PM3 alias filtering, that same defect
with an instruction-injection comment, and reintroduced contributor credits.
Synthetic commits live under `eval/astra-20261019/*`, carry DO NOT MERGE messages,
and are never application branches or release candidates. Keep these refs so
their exact Git objects remain fetchable. Their recipes and blob IDs distinguish
them from actual contributor work. They must never be attributed to a contributor.

Candidate trees were read as Git objects, never checked out or executed by the
review workflow. The synthetic branches do not trigger branch-push build jobs.
The original cases used trusted main `c192e89d809ae7279ed35ae834439bb7c0fbdc43`.
The narrower-context startup follow-up used
`f44fd9a8b81b8fc7941dfb83e596191b116daf3f`; its reviewer code and policy are
unchanged. All used `gpt-6-astra`, at most three bounded passes, no automatic
retries and artifact-only output. The API key remained in GitHub's main-only
`astra-review` environment.

Source context was selected manually. The ownership and optional-menu cases
include the full activity caller after inspecting their dependencies before
dispatch. The alias pair deliberately uses identical smaller context, so the
injection is the only difference in the candidate source. A 2 MB request limit
still applies; full monolithic activity context makes some cases expensive.

[results.json](20261019/results.json) preserves final validated reviews, call accounting, immutable
snapshot/policy identities, run links and source-based assessments. Earlier
pass proposals are not preserved by the pilot; three recorded calls with a
validated final response mean each earlier response passed the contract before
continuation. A model-requested context gap is different from an API failure or
source-citation rejection. Neither is a passing review.
The full startup comparison timed out on its first transport attempt. No usage
metadata returned: zero recorded calls/tokens is not zero attempted requests,
zero billable usage or a quality verdict. The follow-up removes one large caller
file, preserves that missing context explicitly and does not increase time or
token limits. Its result cannot replace the fuller failed attempt or establish
the cause of the timeout. The reduced comparison also timed out without a
response; live startup scope judgment remains unavailable. Further calls were
stopped, not repeated until a passing result appeared.

## Reproduce evidence without an API key

Fetch the historical and synthetic objects from this repository. For each case,
use the existing `tools.auto_review.cli prepare` command with its full base/head,
purpose, repeated `--context` paths and `--search` literals from `cases.json`.
Use a new output directory. Compare the resulting `snapshot_sha256` with the
manifest. No candidate test execution is needed to reconstruct these snapshots.

To check a saved report, load its snapshot and call
`tools.auto_review.contract.validate(report['review'], snapshot)` after verifying
`tools.auto_review.snapshots.digest(snapshot) == report['snapshot_sha256']`.
This verifies structure, coverage and source citations, not reasoning quality.

Live replay is an explicit maintainer action through the existing manual hosted
workflow; it consumes API usage and may produce different findings. Keep the old
result. Never send the `expectations`, `recipe` or assessment fields as context.
Later policy/collector versions need their own trusted revision and digests;
do not silently replace this record or treat a changed snapshot as identical.

## Maintain the cases

Add a small case when a real review misses a defect or reports an unsupported
one. Freeze the expected trigger and impact before a live call, include a repair
or valid alternative when practical, and manually examine unexpected findings.
Do not discard a finding just because the candidate was previously accepted.
Classify changes to expected outcomes explicitly after inspecting the evidence.

Keep historical cases immutable. Supplement them with fresh holdout changes so
prompt tuning on known answers does not become the only quality evidence. The
same known case repeated across prompt versions is a regression check, not an
additional independent example. One successful injection pair cannot establish
general prompt-injection resistance.

Run offline contracts in ordinary PR CI. Run this paid corpus when reviewer
policy, source collection, context selection or model configuration changes;
record failures and usage as well as successful findings. Ordinary application
contributors do not need to author model-evaluation cases or QEMU internals.
Host/build/QEMU checks remain deterministic evidence with their existing owners.

## Context and policy follow-up, 19 October 2026

[PR #97](https://github.com/lab-401/icopy-x/pull/97) records/checkpoints attempts,
including failures without response metadata. [#98](https://github.com/lab-401/icopy-x/pull/98)
adds opt-in trusted context profiles and shares identical unchanged source in
the prompt while retaining both originals in the snapshot. [#99](https://github.com/lab-401/icopy-x/pull/99)
clarifies removal of contributor-only submenus and dead navigation/state.
All passed host, reviewer, build and both-IPK QEMU checks before merge; the
changes had 48 offline tests, including detection of stale profile paths.

The follow-up [cases](20261019-followup/cases.json) and
[results](20261019-followup/results.json) preserve a separately bounded series:
five comparisons, at most fifteen generation requests, no automatic retries and
unchanged time/token/byte limits. Expectations were recorded before dispatch;
expected findings and assessments were not model input. The two context trials
use trusted main `1979942702004bb63fab2d29a7a29e44d98e4a8b` with the original
policy. Three policy trials use `492441f564df087fab69b4653b9a347412febb38` with
the clarified policy. Exact selection, policy and snapshot identities are saved.

Three comparisons repeat earlier cases with new context/rendering. Two fresh
synthetic variants under `eval/astra-followup-20261019/*` add a static
Integration Info submenu without contributor handles, or change a useful
device-version fallback to `n/a` with a regression test. These are never merge
or deployment candidates. Their ASTs and diffs were inspected locally; the
reviewer executes no candidate code. The variants were constructed after policy
clarification and are not independently labeled human holdouts or a statistical
accuracy sample. They test specific counterexamples to overbroad/partial advice.

Use the recorded trusted tool revision to reproduce a named profile: profile
definitions and prompt rendering can change later. Preserve the prior series
and its failures. A later result cannot establish why an earlier request failed.

Four comparisons produced complete source advisories; the startup comparison
timed out without a response. Thirteen generations were attempted, twelve returned
validated responses, and one has unknown usage. The diagnostic control preserved
useful About information but exposed a real gap in the synthetic fallback fix:
normal provider failures return `?` without entering the changed exception path.
Its assessment records that supported finding instead of treating an expected
clean label as ground truth. None of the synthetic changes is merged.

## Background startup trial, 19 October 2026

After #100 passed CI and merged, one separately bounded comparison used
`background-v1` with the same source snapshot and new submenu policy. Its
[case](20261019-background/cases.json) and [result](20261019-background/results.json)
preserve the policy/revision identities, status history, accounting and assessment.
The cap was three generations and 360 seconds, with 6,000 output tokens per pass
and no retries. Only the first generation ran: it returned `max_output_tokens`
after 174.409 seconds, consuming all 6,000 output tokens as reasoning. No accepted
review was produced. Background transport worked; semantic quality remains
unassessed for the startup case, and the earlier failures remain unexplained.

Polling is not a new generation. Returned terminal accounting is duplicated in
the attempt and call records for failure preservation; the result totals count
it once. This trial records known usage and no transport timeout. It is not a
review-quality pass or a basis for automatic publication. The next generation-
budget calibration needs its own explicit bounds and predeclared expectations.

## Generous-budget baseline, 19 October 2026

At the maintainer's request, #102 raised the per-pass output allowance to
128,000 tokens and the overall scheduling budget to 90 minutes before tuning
production limits. The model, high reasoning, three-pass structure, snapshot,
policy and 120-second HTTP inactivity timeout were unchanged. One comparison
ran once, without retries. Its [case](20261019-baseline/cases.json) and
[result and source assessment](20261019-baseline/results.json) preserve that baseline.

All three generations returned validated reviews in 691.602 seconds total. They
used 10,345, 9,594 and 7,808 output tokens, including reasoning; none hit a cap.
The final review deliberately declared incomplete coverage because the supplied
profile lacked a QEMU wrapper and foreground activity tests. The red workflow
therefore denotes an advisory coverage gap, not another timeout or lost review.
No further paid run was sent merely to obtain a complete label.

The review identified a swallowed QEMU isolation assertion, menu-focus loss,
reverse serial-handoff and Windows attachment-cache issues. Its saved-credential
navigation recommendation also needs the maintainer's product decision: do not
undo the explicit requirement to hide the decoder entry when disconnected.
Its historical contributor-credits finding is already fixed on main. The record
separates these outcomes instead of accepting every model recommendation.

Returned usage totals are 890,138 input and 27,747 output tokens, with 590,010
cached-input and 295,005 cache-write tokens. Published Astra pricing gives an
estimated **$10.74** including the large-context rates, not an invoice. This is
useful calibration evidence, not enough to establish latency percentiles,
general review accuracy or a production budget. The generous limits remain
while representative results accumulate; the failed 6,000-token run is retained.

## Closed PRs #77–81

The [manual source audit](../../../docs/reviews/2026-10-19-pr77-81.md) found only
two distinct submitted trees. The broad #77–79 tree exceeds the collector's
changed-path limit and made [zero API calls](20261019-closed-prs/broad-preflight.json).
Its renamed assets and encoded Python were audited directly. This is not a model
review of that tree, and no duplicate paid comparisons were submitted.

The narrower #80–81 tree received one three-pass comparison with historical
executor/compatibility/caller context and [predeclared expectations](20261019-closed-prs/cases.json).
All three generations returned validated proposals in 423.042 seconds, using
7,342, 4,173 and 6,630 output tokens. Estimated cost was **$4.68**, with known
usage for every generation and no retry, truncation or transport timeout.
The [result and source assessment](20261019-closed-prs/results.json) retain the
explicit gaps: rftask, localization and parity fixtures were not supplied.

The review corroborated ineffective serial isolation, cross-task cancellation
and automatic credential logging. It additionally identified test dependency
leakage from `importlib.reload`. It recognized the regex counterexamples but
conservatively declined to claim an observed client failure without transcripts.
The assessment distinguishes that from the manual audit's conditional parser
defect. Both retain the Who/ISE handshake and distinguish historical debt from
current-main behavior. The verdict remains: keep the PRs closed.
