# Contributing to iCopy-X

iCopy-X provides an open-source application for existing iCopy-XS devices. People
depend on it with both original manufacturer firmware and upgraded Iceman
firmware. Contributions are welcome; keeping both configurations stable is our
first priority. **Factory means the original manufacturer, not Lab401.**

- **One logical change per PR.** Describe the problem, intended behavior and
  related issue. Split unrelated features, refactors and build changes. Necessary
  USB/startup work can belong with an accessory integration; explain the dependency.
- **Preserve both package families.** No-flash retains factory compatibility and
  Lua 5.1; flash pairs matching Iceman client/firmware and Lua 5.4. Changes to
  translation, PM3 ownership/cancellation, boot, flashing, PC mode or build scripts
  need explicit compatibility evidence and a recovery plan.
- **Submit clean, understandable source.** Review every changed file, including
  AI-generated work. Exclude generated binaries, build relics, local agent files
  and private logs/card dumps. Explain any intentional binary asset and its origin.
  Put feature documentation in `docs/`; keep the README an entry point.
- **Keep the device UI focused on users.** Avoid unrelated menu changes and
  contributor-only credits/About screens or promotion. Attribution belongs in
  source and GitHub. Preserve required legal notices and useful device diagnostics.
- **Show what you tested.** Add a meaningful regression test for changed behavior;
  run the [host tests](docs/HOST_TESTS.md). Report results, firmware/card/accessory
  configuration and anything untested. Do not weaken tests or claim unavailable
  hardware was validated.
- **Use the support provided by review.** CI runs host tests, builds packages and
  checks both IPKs in maintained QEMU; you do not need our private image or server.
  Maintainers help identify appropriate fixtures and physical tests. Astra is
  currently an advisory pilot; its feedback supplements human review. Fork CI
  may require maintainer approval. Passing checks is evidence, not merge approval.

See [maintainer acceptance](docs/CONTRIBUTION_REVIEW.md) and
[current validation coverage](docs/VALIDATION_STATUS.md) for testing limits.
