# Astra advisory pilot

This manual GitHub Actions pilot reads immutable base/head Git objects and runs
three bounded passes with `gpt-6-astra`: scope, domain audit and evidence challenge.
It saves advisory artifacts. It does **not** post PR comments, approve merges,
create required checks, execute candidate code, operate hardware or replace CI.
The same model performs the three passes; these are not independent reviewers.

## GitHub setup and operation

Use **Settings → Environments → astra-review → Environment secrets** to add
`OPENAI_API_KEY`. Keep this environment restricted to the `main` branch. No local
key or always-on workstation is needed. The API secret is supplied only to the
review step. Use an OpenAI project dedicated to this reviewer for separate usage
accounting; configure its billing/usage controls according to your account.

After this workflow is merged, open **Actions → Astra advisory pilot → Run
workflow**, select `main`, and enter full base and head commit SHAs plus the
stated PR purpose. That purpose is review context, not an instruction that can
override policy. The candidate
must include the chosen base. For an open PR, use its current base/head identities
and refresh a stale branch before reviewing. This pilot does not automatically
fetch PR metadata or detect a later push: check both identities again before
using its report. Historical comparisons deliberately use their historical base.

Start with `prepare` to inspect `snapshot.json`, the complete changed-file list,
coverage gaps and any explicitly selected unchanged caller/contract files. The
`context` input is a JSON array, e.g. `["src/lib/actmain.py"]`. Choose context after
reading the change; the collector does not autonomously discover dependencies.
The optional `profile` input selects a trusted starting point: `ics-ui` includes
the actual information view, menu/widget contracts and activity tests;
`ics-transport` includes discovery, foreground callers, PM3 reservation and
transport tests; `accessory-menu` includes startup, activity lifecycle and
presence tests. `manual` remains the default and preserves existing snapshots.
Profiles are maintained in [profiles.py](profiles.py), with a reason for each
path. They are opt-in: a change anywhere in the large activity module does not
automatically select ICS context. Explicit `context` and `searches` are added
to the profile. The snapshot records the profile version and selection reasons.
Missing paths, unsupported blobs and exceeded budgets fail closed; a profile
never silently drops context. Inspect the prepared inventory and reference hits:
these recipes do not prove a complete dependency graph or replace reading callers.
Offline CI checks that every profile path is still a tracked regular file, so
renaming/removing a dependency prompts a recipe update before a live review.
Then run `review` with the same identities/context. Download the run artifact.
The optional `searches` input is a JSON array of literal reference terms, e.g.
`["menu_order", "ordered_items", "main_menu.json"]`. It searches both immutable
commits and records matching paths, blob IDs, lines and terms. An empty match
list means literal absence in that search scope, not absence of computed names
or dynamic imports. Choose caller context from the results; search hits alone
cannot support formal findings without full source in `files`.

Search covers tracked regular Git blobs, including binary bytes, without filters,
attributes, symlink targets, submodules or the worktree. Non-UTF-8/NUL-containing
matches retain path, blob, line and term metadata with `text_unavailable`; they
are not silently omitted or reported as absence. Inspect them separately if
relevant. Changed binaries still block the full-source review as before.
Search accepts at most 16 terms of 128 characters, with 250 matching
lines and 512 KB output per revision and a 30-second Git timeout. Failed,
malformed or oversized searches create explicit gaps and prevent API calls;
results are never silently truncated into a false claim of absence. Search uses
LF-based Git line numbers; full-source citation validation remains unchanged.

Each live invocation submits at most three generations, no retries, with a 6,000
output-token cap per generation (including reasoning). Default source/bundle
limits are 2 MB total and 1 MB per file. Background submissions are polled every
two seconds against the same response ID; polls do not submit new generations.
The review scheduling deadline remains 360 seconds across all three passes.
An individual generation can therefore exceed the former 120-second synchronous
wait without increasing the overall review budget. HTTP socket timeouts remain
at most 120 seconds, clamped to remaining time. The hosted job retains its
12-minute wall-clock limit. These are work limits, **not a dollar ceiling**.
Inspect recorded token usage and the project's API usage before expanding trials.
The serialized model request also has to fit the bundle's total byte limit,
including numbered source, policy, schema and previous-pass output.

The workflow checks out the reviewed main commit that launched it. Candidate
objects are fetched without checking out their tree. Repository text and prior
model output are untrusted prompt data; the trusted policy comes from main.
The job has only `contents: read` and no publication capability. Prompt separation
and schema validation reduce risks but cannot prove the model ignored an injected
instruction; maintainer evaluation remains necessary.

`PREPARED` means evidence was collected. `ADVISORY_COMPLETE` means all three
responses passed structural, coverage and source-line checks and the final model
response declared its review complete. It does **not** mean no defects, tests
passed, or merge approval. `INCOMPLETE` exits nonzero. Binary blobs, LFS pointers, symlinks,
unsupported modes and exceeded content budgets are explicit gaps; a snapshot
with any gap makes no API call. Refusals, malformed responses, missing/duplicate
file coverage, fabricated source quotes, model substitution and truncation fail
closed. Successful call accounting survives a later failed pass; a network failure
may still incur API usage that the client cannot record.

`attempts` records each planned generation before sending: pass, UTC start time,
effective socket timeout, serialized request bytes and a unique client request ID.
The ID is sent as `X-Client-Request-Id`; an allowlisted `x-request-id` response
header and HTTP status are retained when available. These are correlation IDs,
not retry or deduplication guarantees. `calls` separately records returned response
metadata and token usage, linked by client ID. For `background-v1`, each attempt
also records its bounded `http_requests` (submit/poll/cancel), response ID/status,
poll count and cleanup outcome. Each HTTP operation has its own correlation ID.
`terminal_response` preserves allowlisted accounting even if a late response or
cancellation race prevents accepting that pass. It duplicates `calls` accounting
on success: deduplicate by response/generation identity rather than summing both.
An empty `calls` list does not mean no request or no charge. A failed transport records elapsed time without inventing
usage or persisting raw exceptions, headers, response bodies or credentials.

The CLI atomically checkpoints `report.json` before submitting/polling and after
acknowledging a job/status. A checkpoint failure prevents new work; it does not
prevent an attempt to cancel an already known active job. A lost submission
acknowledgement is never retried: delivery, completion and usage remain unknown.
Earlier validated proposals survive later failures. See
[OpenAI request debugging](https://developers.openai.com/api/reference/overview#debugging-requests).

On deadline, polling failure or a catchable interruption, the adapter attempts
one cancellation of the known active response with a separate ten-second socket
timeout. It records confirmed cancellation, an already terminal job, or an
unconfirmed outcome. It never converts cleanup into review success or retries a
failed generation. A hard process kill may prevent cancellation/checkpointing;
reconcile the last recorded response ID rather than dispatch another generation.
Without a valid response ID, cancellation is impossible. The review deadline is
checked before/after network operations and waits; socket timeouts are inactivity
limits, so a blocked operation can overrun it. Late responses remain incomplete;
the workflow wall-clock limit is the final execution bound.

[Background mode](https://developers.openai.com/api/docs/guides/background) uses
`background: true` with `store: false`. Responses are still temporarily retained
for polling (roughly ten minutes); this is not a promise of zero retention.
Unexpected response IDs, statuses or models fail closed. Background state improves
observability but does not establish the cause of the older synchronous timeouts.

The prompt supplies source lines as `numbered_text`: a 1-based line number, a tab,
then the original line. Quotes must exclude that prefix. `snapshot.json` retains
the original blobs and hashes; citation validation still checks those original
lines. `prompt_format` identifies this rendering. A rejected response records a
fixed `validation_code` and `failure_stage`, not raw API/exception text. For
example, `source_citation` means a quote or line did not match the evidence;
`file_coverage` means the changed-file inventory was not covered exactly.
This aids diagnosis without accepting, repairing or retrying a rejected result.
An `INCOMPLETE` report with a validated `review` and no `error` can instead mean
the model explicitly identified missing context. Inspect `review.limitations`;
a red workflow is not necessarily an API failure. Supply justified context in a
new manual invocation, preserving the previous result. Do not convert that
coverage gap into a pass or automatically retry it.
Allowed cache/reasoning token counts and truncation reasons are retained when
returned by the API; the report is not a billing invoice.

The three passes share a stable policy/schema/source prefix with an explicit
cache breakpoint after the source. The pass instruction and untrusted previous
proposal follow that prefix. This allows reuse without caching each changing
suffix; it does not guarantee a cache hit or reduce the three-pass evidence checks.
In `numbered-source-v3`, identical unchanged base/head blobs are rendered once
on base. Head retains its metadata and a `numbered_source_ref` to that same
path's base lines. Changed files keep both sides explicit. This removes duplicate
prompt text without dropping any source lines or changing `snapshot.json`, its
hashes, citation validation or the existing snapshot/request byte limits. It is
not evidence that request size caused an earlier transport timeout.
Compare recorded cached and cache-write tokens in live trials. See the
[API prompt caching guide](https://developers.openai.com/api/docs/guides/prompt-caching).

## Offline tests and evaluation limits

`Reviewer offline tests` runs on Linux and Windows without any key:

```sh
python -m unittest discover -s tests/auto_review -v
```

Tests use temporary Git repositories and simulated API responses. They verify
collection, evidence validation and failure handling; they do not measure Astra's
review accuracy. They also do not run any candidate test suite. The established
host, package and QEMU workflows remain the deterministic contributor checks.

Before automatic PR invocation or publication, record live trials on historical
accepted and rejected changes, including mixed Lua families, serial ownership,
contributor-only device credits, justified accessory startup work and clean fixes.
Have a maintainer label expected findings independently. Record misses, false
positives, scope decisions, context gaps, token usage and latency. A response
matching the JSON schema is not evidence that its reasoning is correct. The
[calibration corpus](calibration/README.md) preserves predeclared cases,
source-based assessments and final live reports. It is maintained separately
from ordinary contributor tests. Automatic dependency discovery and PR integration
remain follow-up work; semantic quality cannot be inferred from schema validity.

For an optional local run, use `python -m tools.auto_review.cli prepare` or
`review` with `--repo`, `--base`, `--head`, `--purpose`, optional `--profile`, repeated `--context` and
`--search=literal` arguments, and a new `--output`
directory. Only a local `review` needs `OPENAI_API_KEY` in its process environment.
Do not commit keys or private physical-device evidence. The hosted artifacts
contain repository source and review text; use this workflow for this public
repository's source, not confidential external material.

API contract: [Astra model documentation](https://developers.openai.com/api/docs/models/gpt-6-astra)
and [structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses).
Environment setup: [GitHub environment documentation](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments).
