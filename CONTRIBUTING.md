# Contributing to iCopy-X

Keep each PR focused on one behavior or independently reviewable correction.
Separate accessory integration, core runtime changes, build/packaging changes,
documentation reorganization and generated artifacts. An accessory may need
startup or USB integration; explain why each core change is necessary for it.
Being outside one file does not by itself make a change out of scope.

Preserve both factory/no-flash and Iceman/flash behavior. Changes to command
translation, PM3 process ownership, cancellation, boot/update/flash paths, Lua
selection, USB gadget modes or build scripts need explicit compatibility evidence
and a recovery plan. Do not merge the two Lua families or change factory branding
as part of unrelated work. Do not commit build outputs, private device logs,
badge dumps or local agent history. Put feature details under `docs/` and keep
the README a project entry point.

Device menus and screens must serve a user task or a diagnostic purpose. Do not
add contributor-specific About/credits submenus, contributor handles, personal
branding or promotional links to feature screens. Keep contributor attribution
in source comments, Git history and GitHub. Preserve required copyright/license
notices and useful device, firmware-version and support information; a screen
named About is not by itself a violation. Review actual content and navigation,
including translations, screen definitions, assets and tests that expect credits.
Passing tests do not justify UI without user value. This rule also applies to
the planned automated reviewer.

## Practical contributor checks

Run the host suite without a device or QEMU image:

```text
python -m pip install -r tests/requirements-host.txt
python -m pytest tests/ui tests/build tests/release_ci tests/physical tests/test_build_ipk_contracts.py
```

CI runs the supported Python/OS matrix, builds the real packages and companion
clients, and tests both exact IPKs in a maintained ARM/Python/Tk environment.
Contributors do not need access to the private factory image or QEMU server.
First-time fork workflows may require GitHub's normal maintainer approval.
The workflow posts QEMU status automatically after the package build finishes.

When a behavior changes, add or update the smallest regression case at the layer
where the failure occurs. Host tests cover logic/protocol ownership; a critical
QEMU case must exercise packaged application behavior with a meaningful result
assertion. Prefer a fault/negative control proving the test detects the old bug.
Do not change mocks to make an incorrect application pass, skip a broken case,
or copy expected output from the same code under test.

## Maintainer review and acceptance

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
read after return. A model reviewer, if later activated, is advisory and cannot
replace these checks or the maintainer's merge decision.

References: [host tests](docs/HOST_TESTS.md), [QEMU CI](docs/QEMU_CI.md),
[physical station](docs/PHYSICAL_TESTING.md), and
[validated releases](docs/RELEASE_PIPELINE.md).
See [validation status](docs/VALIDATION_STATUS.md) for current coverage and
outstanding physical acceptance.
