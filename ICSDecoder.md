# ICS Decoder

ICS Decoder is an **external USB accessory** connected to the iCopy-XS.
The source card goes on the accessory; the target blank goes on the
iCopy-XS Proxmark coil. The accessory handles source-card communication
and returns credential data over serial. The application receives,
displays and optionally saves that data, then uses the existing PM3
middleware to write a compatible target after explicit confirmation.

See the [project README](README.md) for installation and the distinction
between flash and no-flash releases. This feature does not change that
distinction: no-flash uses the factory PM3 client and its Lua scripts;
flash uses the matching Iceman client, firmware and Lua scripts.

## Compatibility and limitations

The author of [PR #14](https://github.com/lab-401/icopy-x/pull/14) reported
device testing with the [DIY ICS Decoder](https://github.com/Dysonian-Lab/icopy-x-ics-decoder).
Compatibility with the original iCopy-X/Nikola accessory has not been
established by that report. See the accessory repository for its build
instructions. Software tests alone do not establish hardware compatibility.

| Source evidence | Target | Available operation |
|---|---|---|
| Decoder-reported nonzero, eight-byte `Blk7#` | Compatible iClass Legacy/Picopass blank | Write legacy application data |
| Decoder-reported 26-bit `WIEData#` whose parity and FC/CN agree | T5577 | Write H10301 HID Prox |
| Unsupported, incomplete or malformed data without valid legacy evidence | None | Inspect or save only |

HF detection requires an authenticated read of application block 6 using
either the standard HID key (`AFA785A7DAB33378`) or Picopass transport key
(`2020666666668888`). A UID read alone does not establish write access.
Authentication also does not prove that every target block is writable.

Only H10301 is supported by this integration's LF write path. Other
Wiegand formats may be valid LF formats, but this integration does not
infer them from an arbitrary SEOS payload or raw legacy block.

## Using the accessory

1. Connect the accessory by USB. **ICS Decoder** appears in the main menu
   after it answers the identity handshake; open that entry.
2. Choose **Read Credential** and place the source card on the accessory.
3. At **Credential Result**, inspect the fields, view the original response,
   or save the capture with a name.
4. Choose **Write Credential**, then place a compatible blank on the PM3 coil.
5. Confirm **Write**. The application checks source eligibility and target
   family again before sending a write command.
6. After **Write OK**, choose **Verify** for a fresh readback. A completed
   write command alone is not a verified clone.

The HF path calls the existing `iclasswrite.make_se_data` and
`writeDataBlocks` helpers. It writes **blocks 6, 7, 8 and 9**, not just
block 7. Use an appropriate blank. HF verification currently compares
block 7 exactly; it does not verify the other three blocks or demonstrate
acceptance by an access-control reader. LF verification compares the full
HID transport frame, including format/header and parity bits.

Saved credentials are JSON files under
`/mnt/upan/dump/ics_decoder/credentials/`. They include the original
response bytes (base64), response text, reported fields and derived data.
The application revalidates source evidence before enabling a saved
credential for writing. This is consistency checking, not authentication
of a file edited outside the device.

## Serial protocol and lifecycle

The bridge opens a serial port at 115200 baud with bounded read and write
timeouts. It sends `Who\r\n` and requires an exact `ISE` response. It sends
`RD\r\n` to request a card. `OK`/`??` without a frame means no capture;
credential data is enclosed by `$A_CARD_START$` and `$A_CARD_STOP$`.

On the iCopy-XS, `/dev/ttyACM0` is reserved for the internal PM3 and is
excluded from accessory probing. The integration does not reassign the
PM3 port. USB enumeration with the accessory connected before boot,
hot-plugging, disconnects and PC-mode transitions needs device testing.

The main menu starts with the accessory entry hidden. While the menu is
active, a background worker checks attached serial devices approximately
once a second. Only an exact `ISE` reply to `Who` makes the entry visible;
a serial port or USB bridge ID alone is insufficient. Discovery excludes
the internal PM3 path and aliases resolving to it. Windows discovery uses
the enumerated inventory and never guesses COM port numbers.

A verified attachment is cached until its device node disappears or changes.
An unresponsive attachment gets at most three probes, allowing for firmware
startup; unplug/replug to retry after that. Temporary discovery handles are
closed, polling stops while a child activity is open, and late results cannot
update a paused menu. Adding/removing the entry preserves the selected action
where it remains available. Detection is bounded by serial timeouts and is
not an instantaneous disconnect notification.

There is no verified USB VID/PID list covering the original accessory and all
DIY builds. Discovery therefore retains the existing external ACM/USB serial
candidate scope on Linux and USB serial scope on macOS; it can send `Who`
to another external serial device. The proposed IDs in issue #60 do not
establish accessory identity. A stricter candidate allowlist needs genuine
accessory descriptors and hardware testing before it can replace this policy.

Detection and source reading run in background threads. Stale source-read
callbacks are rejected when the user exits or restarts reading, and the
serial handle is closed on exit. These are accessory integration concerns;
installing or swapping the whole application is a separate boot concern.

## Credential parsing

`WIEData#` is decoded as H10301 only when it contains exactly 26 binary
digits and agrees with the decoder's bit length, FC, card number and
calculated parity. Unknown fields and the original response are preserved.

For explicitly identified 26-bit `SIO#`, `PACS#` or `HEX#` payloads, the
parser can interpret a leading padding-count byte followed by a big-endian
bitstream and check the resulting frame's parity. This fallback can supply
display fields; it does **not** by itself authorize an LF write.
`SIO_CONTAINER` is retained as opaque source data, not decrypted by the
application. Do not treat arbitrary ASN.1 container bytes as decoded
credentials.

## PM3 commands and results

The bridge emits Iceman-style commands and uses the project's existing
translation layer for the factory client:

| Command | Purpose |
|---|---|
| `hf iclass rdbl --blk 6 -k <key>` | Authenticated HF target detection |
| `hf iclass wrbl --blk <block> -d <data> -k <key>` | HF application writes through `iclasswrite` |
| `hf iclass rdbl --blk 7 -k <key>` | Exact HF credential readback |
| `lf t55xx detect` | LF blank detection |
| `lf hid clone -r <raw>` | H10301 HID transport write |
| `lf hid reader` | Fresh LF readback |

The raw HID value includes the bit-37 header, bit-26 length sentinel,
and the 26-bit Wiegand frame with parity. The PM3 example FC 118 / CN 1603
is `2006EC0C86`. The factory adapter converts this to
`lf hid clone 2006EC0C86` and converts `lf hid reader` to `lf hid read`.

`executor.startPM3Task` returns `1` for a completed command and `-1` for
a transport/task failure. Completion alone does not prove card detection
or a successful write: those require positive output evidence. Avoid
`hf iclass info` for detection; the existing Iceman compatibility layer
blocks it because of the project's documented hardware hang.

Diagnostic logs are written under `/mnt/upan/dump/ics_decoder/` in numbered
files. Saved captures and diagnostic logs are separate files.

## Further validation

Test both flash and no-flash variants with the accessory absent, present
at boot, hot-plugged and disconnected during a read. Check that ordinary
PM3 scanning still works, Back remains responsive, failed writes are
reported accurately, and verification rejects a different target or
altered data. Test HF blocks 6–9 and LF H10301 with real blanks; report
the client/firmware versions and accessory firmware used.

Additional credential formats and original-accessory support should be
separate changes backed by protocol captures and device tests.
