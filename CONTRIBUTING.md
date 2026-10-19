# Contributing to iCopy-X

First and foremost - a sincere thank you your interest in contributing to this project.
The iCopy-X "Open" project brings a modern, modular update to the very capable iCopy-X devices.

Contributing to this project is an opportunity to write code that will deploy to thousands of devices.
Many users users are professionals who rely on their devices on a daily basis. 

Maintaining stable code, good performance and a uniform UI are the cornerstones of this project.

iCopy-X "Open" has two versions: flash and no-flash. The "flash" version updates the firmware on the internal proxmark module to modern "iceman" firmware - it is pinned to the latest proxmark release. The "no-flash" version retains the original factory firmware on the proxmark module, but brings the open-source advantages to the device.

Some users prefer "no-flash", and some prefer "flash". While these two goals may fork in the future - for now - please bear this in mind when contributing.

## Guidelines for contributions:

- **One logical change per PR.** Describe the problem, intended behavior and
  related issue. Split unrelated features, refactors and build changes. Necessary
  USB/startup work can belong with an accessory integration; explain the dependency.
- **Preserve both package families.** No-flash retains factory compatibility and
  Lua 5.1; flash pairs matching Iceman client/firmware and Lua 5.4. Changes to
  the translation/compat layer, PM3 internals (ownership/cancellation), boot, flashing, PC mode or build scripts
  need explicit compatibility evidence - and a recovery plan if your build breaks users devices.
- **Submit clean, understandable source.** Review every changed file, including
  AI-generated work. Exclude generated binaries, build relics, local agent files
  and private logs/card dumps. Explain any intentional binary asset and its origin.
  Put feature documentation in `docs/`; keep the README an entry point.
- **Keep the device UI focused on users.** Avoid unnecessary menu changes. Do not add personal promotion, or additional "About" screens. Attribution belongs in source and GitHub.
- **Show what you tested.** Add a meaningful regression test for changed behavior;
  run the [host tests](docs/HOST_TESTS.md). Report results, firmware/card/accessory
  configuration and anything untested. Do not weaken tests or claim unavailable
  hardware was validated.
- **Do NOT patch upstream code** - any PRs that patch upstream proxmark code will be immediately rejected. The proxmark project has build-flags for iCopy-X. If you've genuinely found a bug in the proxmark code that requires a specific branch for the iCopy-X - it needs to go into the proxmark project - where you'll also need to have founded justification.
- **Respect licensing** - Preserve required legal notices; ensure that your code respects licenses. If you're porting code from other projects, please understand the license implications. 
- **Use the support provided by review.** CI runs host tests, builds packages and
  IPKs on a fully emulated device - you do not need our private image or server. An automated PR review script will perform analysis on your contribution - and provide rapid feedback. This is AI powered - it is intended as a guide to remove some complexity for you, and give you immediate feedback. A human maintainer will handle the final decision.

## You're making this too complicated
This project has stringent quality requirements: this is not to discourage contributions. It comes from two reasons:

- This is a complex product, and complex project. Seemingly isolated modifications can have large effects elsewhere.
- There are thousands of iCopy-X users - many of them using this firmware. All contributors have a responsibility to ensure, to the best of their ability, that contributions are tested - not only for their scope, but everyone else's scope. This is not a "move fast and break things" project.

The AI review agent is designed to make this process easier. Maintainers perform tests on physical devices before merging. 

If all of this seems too laborious, too onerous, or simply not fun - you have alternatives:

 - Fork the code - and build your own version that meets your needs!
 - Submit an issue on Github, explaining your problem, or your idea - and hopefully someone can pick up the task.

See [maintainer acceptance](docs/CONTRIBUTION_REVIEW.md) and
[current validation coverage](docs/VALIDATION_STATUS.md) for testing limits.
