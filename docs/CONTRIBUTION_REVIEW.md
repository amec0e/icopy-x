# Maintainer contribution review

Contributor expectations are summarized in [CONTRIBUTING.md](../CONTRIBUTING.md).
This page preserves detailed test and acceptance guidance for reviewers.

When a behavior changes, add or update the smallest regression case at the layer
where the failure occurs. Host tests cover logic/protocol ownership; a critical
QEMU case must exercise packaged application behavior with a meaningful result
assertion. Prefer a fault/negative control proving the test detects the old bug.
Do not change mocks to make an incorrect application pass, skip a broken case,
or copy expected output from the same code under test.

## Acceptance

Required checks are the three host jobs and **QEMU critical flows**, against the
current head with an up-to-date base. A failed build means QEMU cannot pass.
Review the diff and scope as well as the checks. Tests are regression evidence,
not protection against a deliberately dishonest test implementation.

Maintainers own the QEMU pin/harness and small private physical reference kit.
New cards and edge cases should reuse existing fixtures and helpers. Keep a
critical case only when it protects a real contract; review it when that contract
changes. Harness/runtime modifications deserve their own reviewed PR and must
be exercised with the reviewed harness before it becomes the trusted default.
Do not require ordinary contributors to recreate the lab.

Use the change's actual boundary to decide physical acceptance. UI/parser-only
changes can be assessed primarily on host/QEMU evidence. USB, RF, flashing,
accessory and installer changes need relevant physical evidence or an explicit
maintainer decision documenting the gap. An unavailable card/accessory is blocked
coverage, never a passing test. PC mode includes manual cable changes and a normal
read after return. The Astra reviewer is advisory and cannot
replace these checks or the maintainer's merge decision.

References: [host tests](HOST_TESTS.md), [QEMU CI](QEMU_CI.md),
[physical station](PHYSICAL_TESTING.md), and
[validated releases](RELEASE_PIPELINE.md).
See [validation status](VALIDATION_STATUS.md) for current coverage and
outstanding physical acceptance.

Device UI review includes translations, screen definitions, assets, navigation
and tests that expect credits. Passing tests do not justify UI without user
value. Preserve useful device/firmware/support information and required legal
notices; an About title alone is not a violation. See the
[Astra pilot](../tools/auto_review/README.md) for its current capabilities and limits.
