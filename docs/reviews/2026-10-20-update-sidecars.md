# Update sidecar follow-up: issue #10

The [20 October report](https://github.com/lab-401/icopy-x/issues/10#issuecomment-6281125193)
describes `newest.ipk`, `._newest.ipk` and an orphaned `._older.ipk` after deleting
the older package. This does not reproduce on current `main`: `update.search()`
skips every dot-prefixed entry before considering packages. A sidecar does not
need a corresponding real file to be excluded.

The fix is commit `e619c000d94dd69ca137c08931b048a62e112176`, included in tags
v1.1.4 through v1.1.7. The published v1.1.7 flash IPK was also inspected:

- Its SHA-256 matches GitHub's asset digest:
  `cf3b281b74f2d8e67776362893ab0c87019357d171d4986945ddb6efe563d10d`.
- `lib/update.py` exactly matches the tagged fixed source; there is no
  `lib/update.so` that could take import precedence.
- Seven update-search tests pass, including the exact reported layout with
  a structurally valid package and a sidecar-only rescan after deleting a
  previously selected package. Both new cases fail against the pre-fix updater.

Package selection is performed by the **already installed application**, before
it can load the replacement package. Copying a fixed release to an older device
does not first update that selection code. The reporter subsequently said the
previously installed version was uncertain and could predate the fix.

No production change is justified by this reproduction. Keep #10 closed unless
a new report identifies the installed updater version and reproduces the problem
after the fix. For an older installation, remove AppleDouble sidecars from the
update directory before its one-time upgrade. This is filesystem/package-selection
evidence, not a macOS Finder transfer or physical installation acceptance test.
