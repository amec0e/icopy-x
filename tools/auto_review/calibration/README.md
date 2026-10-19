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
