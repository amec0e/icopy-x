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
| Menu reordering introduction from #32 | Base `28e817ff1fad1607122ab662b302f2dd9beaf142`, head `1d9f84a85d7ba68a211c49d65b79753c6cdf0516`; context `src/lib/widget.py`; purpose “Add persistent menu reordering” | `PREPARED`, no gaps. Expected: identify the new global Move/M1 behavior as conflicting with the current maintainer UI policy, with a source citation. This isolated commit has a coherent purpose; do not invent mixed-scope changes outside the supplied snapshot. |
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
The diagnostic update adds fixed failure stages/codes and numbered source lines
without relaxing evidence checks, plus full-request byte budgeting and allowed
cache/reasoning usage details. These changes require a new live trial; they do
not retrospectively explain the first failure. Clean-change controls and the
broader labeled evaluation above remain necessary before automatic invocation.

The environment secret belongs in GitHub; a developer workstation is not part
of the hosted execution path. Review accuracy, false-positive rate and typical
cost remain unvalidated.
