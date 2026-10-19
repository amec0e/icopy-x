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
Then run `review` with the same identities/context. Download the run artifact.
Each live invocation makes at most three API requests, no retries, with a 6,000
output-token cap per request (including reasoning). Default source/bundle limits
are 2 MB total and 1 MB per file. The job has a 12-minute wall-clock limit; API
socket timeouts are 120 seconds. These are work limits, **not a dollar ceiling**.
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
matching the JSON schema is not evidence that its reasoning is correct. Live
quality evaluation and an automatic PR integration are still pending this pilot.

For an optional local run, use `python -m tools.auto_review.cli prepare` or
`review` with `--repo`, `--base`, `--head`, `--purpose`, repeated `--context` and a new `--output`
directory. Only a local `review` needs `OPENAI_API_KEY` in its process environment.
Do not commit keys or private physical-device evidence. The hosted artifacts
contain repository source and review text; use this workflow for this public
repository's source, not confidential external material.

API contract: [Astra model documentation](https://developers.openai.com/api/docs/models/gpt-6-astra)
and [structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses).
Environment setup: [GitHub environment documentation](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments).
