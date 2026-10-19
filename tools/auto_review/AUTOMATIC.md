# Automatic advisory PR reviews

`Astra PR review` scans ready, open PRs targeting `main` approximately every
15 minutes. GitHub schedules can be delayed; maintainers can dispatch the workflow
with an optional PR number. It reviews one current base/head pair at a time with
`gpt-6-astra`, then posts findings, scope decisions and explicit coverage gaps in
one PR comment. It never approves, merges, changes code or replaces required CI.

## Configuration

- Keep `OPENAI_API_KEY` in the existing **astra-review environment**, restricted
  to `main`. No workstation key is needed. Only the model job receives it.
- Set repository variable `ASTRA_AUTOMATIC_REVIEW=true` to enable the queue;
  set it to `false` to stop new selections. An already running generation can
  continue; cancellation behavior is described in [README.md](README.md).
- `ASTRA_REVIEW_DAILY_LIMIT` defaults to **3 automatic reviews per rolling
  24 hours** (allowed range 1–20). Each reserves up to three generations. This
  is an invocation allowance, **not a dollar ceiling**. Manual pilot dispatches
  have their own explicit scope and are outside this automatic allowance.
- The generous baseline limits remain: 128,000 output tokens/pass, 90 minutes
  overall, high reasoning, no automatic generation retries. The first two
  measured comparisons returned in 11.53 and 7.05 minutes (~$10.74 and ~$4.68
  estimated). Two cases do not establish production latency or price percentiles.

## Trust and publication

All three jobs check out the immutable trusted `main` revision that launched the
schedule. Candidate objects are fetched from the fixed public repository, read
as Git blobs and passed as untrusted text. Candidate trees, scripts, tests,
dependencies and workflows are never executed in this workflow. Ordinary host,
build and QEMU CI continue to own execution testing.

The selector can reserve/comment but has no API key. The model job has the key
and read-only GitHub access; it cannot publish. The publisher can comment but has
no API key. Inputs record repository ID, PR, current base/head, trusted tool
revision, policy hash and snapshot hash. Each stage verifies the same-run
identity. Current PR state is rechecked after collection, before each generation,
and immediately before publication. A push/close/draft transition makes the old
result stale. The current main SHA is resolved from its Git reference separately:
GitHub's PR metadata can retain an older `base.sha`. Changes to the actual base
also invalidate the result. Obsolete findings are not presented as a review of
the new code. A change
immediately after the final check remains a normal race, so every comment names
the immutable reviewed commits and is never a required merge check.

Source quotes are revalidated before display. Model/source text is rendered
literally, with HTML and mentions escaped; source links use the fixed repository
and immutable commits. Oversized comments explicitly link to the full run
artifact. Incomplete reviews retain validated findings and their limitations.
Missing worker output produces an explicit incomplete result, not an empty pass.

## Queue, deduplication and recovery

The current open-PR list is the queue. This recovers after a delayed/dropped
schedule event and naturally coalesces pushes to the latest head. Drafts are
skipped. A shared concurrency group serializes the automatic workflow and manual
pilot; cancelling a pending schedule does not delete the PR from the next scan.

Bot-owned comments contain a versioned reservation marker. The selector ignores
markers posted by contributors. A reservation is written before the model job
can start, and remains after failures or stale results, so an ambiguous response
does not trigger another paid review. Rerunning a failed Actions job cannot
resubmit a generation. A completed run whose reservation was never finalized is
reconciled to incomplete on a later scan, without retrying. For intentional
repeat evaluation, use the manual pilot after inspecting prior accounting.

The rolling allowance counts durable reservations, including closed PRs and
failed/stale attempts, conservatively even if the API was never reached. A
deferred head gets an explanation and is reconsidered when capacity returns.
Do not delete/edit reservation markers to clean up comments: they are accounting
and deduplication state. Maintainers who deliberately remove them must reconcile
prior usage before re-enabling the queue. Artifact expiry does not erase the
comment ledger. The ledger is bounded to 1,000 entries per API collection; an
overflow or unavailable GitHub API prevents new paid work rather than silently
under-counting usage. A publication outage can delay the final comment; the
workflow artifact and reservation link remain available.

## Scope and maintenance

The collector includes every changed file plus trusted starting contexts for
accessory lifecycle, command translation/ownership, UI and package changes.
Reviewer and contribution-guideline changes also receive the engine and actual
CI workflows so their claims can be checked against implementation.
These recipes are maintained in `automatic.py`; they are not a complete dynamic
call graph. Missing dependencies must remain explicit limitations. Binary,
missing or oversized evidence and stale branches receive a no-API explanation.
They require a focused split, branch update or maintainer source review; an
automated coverage refusal does not certify the PR. The full #77–79 tree is one
such example. The narrow #80–81 tree was reviewed once despite duplicate PRs.

Run `python -m unittest discover -s tests/auto_review -v` when changing the queue,
context, collector or publication boundaries. Tests cover identity races, replay,
budget accounting, spoofed markers, failure recovery, source-only collection and
publication of useful partial results. Keep historical calibration assessments
separate from these deterministic tests. Hardware claims still need appropriate
physical evidence; unavailable equipment remains a coverage gap.

This integration is pinned to lab-401/icopy-x's numeric repository identity.
Fork maintainers must deliberately configure their own trusted identity and
environment before operating a reviewer; untrusted fork PRs cannot change ours.
