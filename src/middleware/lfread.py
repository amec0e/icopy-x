##########################################################################
# Required Notice: Copyright ETOILE401 SAS (http://www.lab401.com)
#
# Initial author: ETOILE401 SAS & https://github.com/quantum-x/ as of April 16, 2026
#
# Since this date, each contribution is under the copyright of its respective author.
#
# Copyright of each contribution is tracked by the Git history. See the output of git shortlog -nse for a full list or git log --pretty=short --follow <path/to/sourcefile> |git shortlog -ne to track a specific file.
#
# A mailmap is maintained to map author and committer names and email addresses to canonical names and email addresses.
# If by accident a copyright was removed from a file and is not directly deducible from the Git history, please submit a PR.
#
#
# This software is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this software for commercial purposes.
#
# A copy of the license is available at:
# https://polyformproject.org/licenses/noncommercial/1.0.0
#
# This entire header "Required Notice" must remain in place.
##########################################################################

"""lfread -- LF tag reading for 20+ card types.

Reimplemented from lfread.so (iCopy-X v1.0.90).
Ground truth: archive/lib_transliterated/lfread.py

Iceman-native command forms (P3.5 refactor, 2026-04-17):
  - Every per-tag dispatcher uses iceman `lf <tag> reader` spelling
    (matrix L1213-1237 consolidated 19-row section).  Iceman source:
    /tmp/rrg-pm3/client/src/cmdlf<tag>.c dispatch tables — each entry
    `{"reader", Cmd<Tag>Reader, IfPm3Lf, ...}`.  Matrix verifies:
      - lf em 410x reader   cmdlfem410x.c:891    (matrix L1075)
      - lf hid reader       cmdlfhid.c:723       (matrix L1160)
      - lf indala reader    cmdlfindala.c:1102   (matrix L1225)
      - lf awid reader      cmdlfawid.c:605      (matrix L998)
      - lf io reader        cmdlfio.c:373        (matrix L1226)
      - lf gproxii reader   cmdlfguard.c:417     (matrix L1227)
      - lf securakey reader cmdlfsecurakey.c:300 (matrix L1228)
      - lf viking reader    cmdlfviking.c:248    (matrix L1229)
      - lf pyramid reader   cmdlfpyramid.c:451   (matrix L1230)
      - lf fdxb reader      cmdlffdxb.c:908      (matrix L1110)
      - lf gallagher reader cmdlfgallagher.c:386 (matrix L1144)
      - lf jablotron reader cmdlfjablotron.c:317 (matrix L1223)
      - lf keri reader      cmdlfkeri.c:375      (matrix L1231)
      - lf nedap reader     cmdlfnedap.c:569     (matrix L1232)
      - lf noralsy reader   cmdlfnoralsy.c:291   (matrix L1224)
      - lf pac reader       cmdlfpac.c:401       (matrix L1233)
      - lf paradox reader   cmdlfparadox.c:477   (matrix L1234)
      - lf presco reader    cmdlfpresco.c:363    (matrix L1235)
      - lf visa2000 reader  cmdlfvisa2000.c:306  (matrix L1236)
      - lf nexwatch reader  cmdlfnexwatch.c:585  (matrix L1237)
  - Parsers consume `lfsearch.REGEX_*` (refactored to iceman-native in
    P3.1; see lfsearch.py header) via the shared `read()` / `readCardIdAndRaw`
    / `readFCCNAndRaw` helpers.
  - Per-tag FC/CN shape caveats (iceman-native Raw: always present,
    FC/CN sometimes omitted — matrix L1213): Gallagher emits
    `Facility: %u Card No.: %u` not `FC: %u Card: %u` (cmdlfgallagher.c:88),
    KERI emits `Internal ID: %u, Raw:` not `Card:` (cmdlfkeri.c:176),
    NEDAP emits `ID: %05u subtype: %1u customer code:` (cmdlfnedap.c:146),
    Presco emits `Site code:/User code:` (cmdlfpresco.c:114), NexWatch
    emits only `" Raw : <hex>"` with a space before the colon
    (cmdlfnexwatch.c:247).  `lfsearch.REGEX_RAW` now uses `\\s*:` to
    tolerate both the tight `Raw:` and the NexWatch space-before-colon
    form, so raw capture works for every per-tag demod.  Callers accept
    empty FC/CN; fallback to `Raw:` via `lfsearch.REGEX_RAW` keeps
    success status truthy when a raw field is present.  See gap log
    P3.5.
"""

import os

try:
    import executor
except ImportError:
    try:
        from . import executor
    except ImportError:
        executor = None

try:
    import lfsearch
except ImportError:
    try:
        from . import lfsearch
    except ImportError:
        lfsearch = None

try:
    import lft55xx
except ImportError:
    try:
        from . import lft55xx
    except ImportError:
        lft55xx = None

try:
    import lfem4x05
except ImportError:
    try:
        from . import lfem4x05
    except ImportError:
        lfem4x05 = None

TIMEOUT = 10000

# ---------------------------------------------------------------------------
# Dump directory mapping: type ID -> (appfiles dir name, display prefix)
# ---------------------------------------------------------------------------
_DUMP_DIRS = {
    8:  ('em410x',    'EM410x'),
    9:  ('hid',       'HID-Prox'),
    10: ('indala',    'Indala'),
    11: ('awid',      'AWID'),
    12: ('ioprox',    'IOProx'),
    13: ('gproxii',   'GProxII'),
    14: ('securakey', 'Securakey'),
    15: ('viking',    'Viking'),
    16: ('pyramid',   'Pyramid'),
    28: ('fdx',       'FDX'),
    29: ('gallagher', 'Gallagher'),
    30: ('jablotron', 'Jablotron'),
    31: ('keri',      'KERI'),
    32: ('nedap',     'NEDAP'),
    33: ('noralsy',   'Noralsy'),
    34: ('pac',       'PAC'),
    35: ('paradox',   'Paradox'),
    36: ('presco',    'Presco'),
    37: ('visa2000',  'Visa2000'),
    45: ('nexwatch',  'NexWatch'),
}


def createRetObj(uid, raw, ret):
    return {'return': ret, 'data': uid, 'raw': raw}


def _save_txt(typ, uid, raw):
    """Save LF read result as .txt in the correct dump directory.

    Naming convention (verified from real device):
      Raw ID types:   <Type>-ID-<hexid>_N.txt   e.g. PAC-ID-8HEXID_1.txt
      FC/CN types:    <Type>-ID_FC,CN=<fc>,<cn>_N.txt  e.g. KERI-ID_FC,CN=002,171223_1.txt
    """
    try:
        import appfiles
        dir_name, prefix = _DUMP_DIRS.get(typ, ('lf', 'LF'))
        dump_dir = os.path.join(appfiles.PATH_DUMP, dir_name, '')
        os.makedirs(dump_dir, exist_ok=True)

        # Build the filename stem based on what data we have
        # All types use underscore separator: <Type>-ID_<data>
        # e.g. PAC-ID_AABA517B, KERI-ID_FC,CN=002,171223, HID-Prox-ID_200499aadc
        if uid:
            stem = '%s-ID_%s' % (prefix, uid.replace(' ', ''))
        elif raw:
            stem = '%s-ID_%s' % (prefix, raw.replace(' ', ''))
        else:
            return

        n = 1
        while os.path.exists(os.path.join(dump_dir, '%s_%d.txt' % (stem, n))):
            n += 1
        with open(os.path.join(dump_dir, '%s_%d.txt' % (stem, n)), 'w') as f:
            f.write((raw or uid or '') + '\n')
    except Exception:
        pass


def read(cmd, uid_regex, raw_regex, uid_index=0, raw_index=0, typ=None, save=True):
    """Generic LF per-tag reader driver.

    Sends `cmd` (an iceman-native `lf <tag> reader` string; see module
    docstring citations), parses cached PM3 response with the shared
    iceman-native regex patterns in lfsearch.

    Regex patterns imported via `lfsearch.REGEX_*` are iceman-native as of
    P3.1 refactor (see lfsearch.py module header):
      REGEX_RAW     r'(?:Raw|raw)\\s*:\\s*([xX0-9a-fA-F ]+)' matches iceman
                    `, Raw: <hex>` (cmdlf*.c demod emission), NexWatch's
                    `" Raw : <hex>"` space-before-colon form
                    (cmdlfnexwatch.c:247), and iceman HID lowercase
                    `raw: <hex>` (cmdlfhid.c:235).
      REGEX_CARD_ID r'(?:Card|ID|UID)[\\s:]+([xX0-9a-fA-F ]+)' matches
                    iceman `Card: %u` (Jablotron/Noralsy/Paradox/PAC),
                    `Card %X` (Viking, space-no-colon), `ID: %u` (Paradox
                    Internal ID), `UID... %s` (Indala).
      REGEX_EM410X  r'EM 410x(?:\\s+XL)?\\s+ID\\s+([0-9A-Fa-f]+)' matches
                    iceman `EM 410x ID %010llX` (cmdlfem410x.c:115) and
                    XL variant at :118.
      REGEX_HID     r'raw:\\s+([0-9A-Fa-f]+)' matches iceman
                    `raw: %08x%08x%08x` (cmdlfhid.c:235).
      REGEX_ANIMAL  r'Animal ID\\.+\\s+([0-9\\-]+)' matches iceman
                    `Animal ID........... %03u-%012llu` (cmdlffdxb.c:572/578).

    Args:
        save: If True (default), save a .txt dump on successful read.
              Pass False for inline verify reads (post-write) to avoid
              creating spurious dump files.
    """
    ret = executor.startPM3Task(cmd, TIMEOUT)
    if ret == -1:
        return createRetObj(None, None, -1)
    content = executor.getPrintContent()
    if not content or executor.isEmptyContent():
        return createRetObj(None, None, -1)
    uid_group = uid_index if uid_index else 0
    raw_group = raw_index if raw_index else 0
    uid = executor.getContentFromRegexG(uid_regex, uid_group)
    raw = executor.getContentFromRegexG(raw_regex, raw_group)
    if uid:
        uid = lfsearch.cleanHexStr(uid.strip())
    if raw:
        raw = lfsearch.cleanHexStr(raw.strip())
    if uid or raw:
        if save and typ is not None:
            _save_txt(typ, uid, raw)
        return createRetObj(uid, raw, 1)
    return createRetObj(None, None, -1)


def readCardIdAndRaw(cmd, uid_index=0, raw_index=0, typ=None, save=True):
    """Iceman-native per-tag: parse `Card|ID|UID` + `Raw:` from cache.

    Used by: Viking, ProxIO, Jablotron, Nedap, Noralsy, PAC, Presco,
    Visa2000, NexWatch.  Shape spec: lfsearch.REGEX_CARD_ID /
    REGEX_RAW (iceman-native, see lfsearch.py module header).

    Args:
        save: If True (default), save a .txt dump on successful read.
              Pass False for inline verify reads to avoid spurious dumps.
    """
    return read(cmd, lfsearch.REGEX_CARD_ID, lfsearch.REGEX_RAW,
                uid_index=uid_index, raw_index=raw_index, typ=typ, save=save)


def readFCCNAndRaw(cmd, uid_index=0, raw_index=0, typ=None, save=True):
    """Iceman-native per-tag: parse `FC: %d Card: %u` + `Raw:` from cache.

    Used by: AWID (cmdlfawid.c:248), GProx-II (cmdlfguard.c:186),
    Securakey (cmdlfsecurakey.c:113), Pyramid (cmdlfpyramid.c:161),
    Keri (cmdlfkeri.c:176 — `Internal ID:` only, no FC/CN),
    Gallagher (cmdlfgallagher.c:88 — `Facility:`/`Card No.:` not
    `FC:`/`Card:`), Paradox (cmdlfparadox.c:224).

    Iceman-native FC/CN regex lives in lfsearch.py:
      _RE_FC = r'FC:\\s+([xX0-9a-fA-F]+)'
      _RE_CN = r'(CN|Card(?:\\s+No\\.)?)[\\s:]+([0-9A-Fa-f]+)' (hex-tolerant)

    Per matrix L1213 + iceman source audit: Keri/Gallagher/Nedap/Presco/
    NexWatch emit alternative field labels; lfsearch._RE_FC won't match
    `Facility:` (Gallagher) and `_RE_CN` won't match `Internal ID:`
    (Keri) or `ID:` alone (Nedap, plus subtype/customer).

    Success gate: EITHER `parseFC()`/`parseCN()` extracted something
    (FC/CN regex hit), OR `REGEX_RAW` extracted a hex string.  We
    CANNOT rely on `getFCCN()`'s string truthiness because it returns
    the literal sentinel `'FC,CN: X,X'` when both FC and CN are empty
    (lfsearch.py:267) — a non-empty placeholder that would always
    evaluate truthy and produce spurious success on any non-empty
    response.  Callers still receive the formatted `'FC,CN: ...'`
    string in `data` (callers expect that shape), but only after we've
    verified real FC/CN or Raw data was actually captured.
    """
    ret = executor.startPM3Task(cmd, TIMEOUT)
    if ret == -1:
        return createRetObj(None, None, -1)
    content = executor.getPrintContent()
    if not content or executor.isEmptyContent():
        return createRetObj(None, None, -1)
    # Check FC/CN extraction directly — do NOT rely on getFCCN() truthiness
    # (it returns the 'FC,CN: X,X' sentinel even when both fields missed).
    fc = lfsearch.parseFC()
    cn = lfsearch.parseCN()
    raw = executor.getContentFromRegexG(lfsearch.REGEX_RAW, 1)
    if raw:
        raw = lfsearch.cleanHexStr(raw.strip())
    if fc or cn or raw:
        # At least one of FC/CN/Raw actually parsed — success.
        # Data carries the formatted FC/CN (sentinel X,X if both missed
        # but Raw present), preserving caller-expected 'FC,CN: xxx,yyy'
        # shape.
        uid = lfsearch.getFCCN()
        if save and typ is not None:
            _save_txt(typ, uid, raw)
        return createRetObj(uid, raw, 1)
    return createRetObj(None, None, -1)


def readEM410X(listener=None, infos=None, save=True):
    return read('lf em 410x reader', lfsearch.REGEX_EM410X, lfsearch.REGEX_RAW,
                uid_index=1, raw_index=0, typ=8, save=save)


def readHID(listener=None, infos=None, save=True):
    return read('lf hid reader', lfsearch.REGEX_HID, lfsearch.REGEX_RAW,
                uid_index=1, raw_index=0, typ=9, save=save)


def readIndala(listener=None, infos=None, save=True):
    return read('lf indala reader', lfsearch.REGEX_RAW, lfsearch.REGEX_RAW,
                uid_index=1, raw_index=1, typ=10, save=save)


def readAWID(listener=None, infos=None, save=True):
    return readFCCNAndRaw('lf awid reader', typ=11, save=save)


def readProxIO(listener=None, infos=None, save=True):
    return readCardIdAndRaw('lf io reader', typ=12, save=save)


def readGProx2(listener=None, infos=None, save=True):
    return readFCCNAndRaw('lf gproxii reader', typ=13, save=save)


def readSecurakey(listener=None, infos=None, save=True):
    return readFCCNAndRaw('lf securakey reader', typ=14, save=save)


def readViking(listener=None, infos=None, save=True):
    return readCardIdAndRaw('lf viking reader', typ=15, save=save)


def readPyramid(listener=None, infos=None, save=True):
    return readFCCNAndRaw('lf pyramid reader', typ=16, save=save)


def readT55XX(listener=None, infos=None, save=True):
    """Read T55XX — detect + chk + dump, return dict for read.so success path."""
    if lft55xx is None:
        return createRetObj(None, None, -1)
    result = lft55xx.chkAndDumpT55xx(listener)
    if isinstance(result, dict):
        return result
    return createRetObj(None, None, -1)


def readEM4X05(listener=None, infos=None, save=True):
    """Read EM4X05 — info + dump, return dict for read.so success path."""
    if lfem4x05 is None:
        return createRetObj(None, None, -1)
    return lfem4x05.infoAndDumpEM4x05ByKey()


def readFDX(listener=None, infos=None, save=True):
    return read('lf fdxb reader', lfsearch.REGEX_ANIMAL, lfsearch.REGEX_RAW,
                uid_index=1, raw_index=0, typ=28, save=save)


def readGALLAGHER(listener=None, infos=None, save=True):
    return readFCCNAndRaw('lf gallagher reader', typ=29, save=save)


def readJablotron(listener=None, infos=None, save=True):
    return readCardIdAndRaw('lf jablotron reader', typ=30, save=save)


def readKeri(listener=None, infos=None, save=True):
    """Read a KERI tag and save the dump.

    cmdlfkeri.c:176 emits:
        "KERI - Internal ID: %u, Raw: %08X%08X"
    Internal ID is decimal; Raw is 16 hex chars.

    readFCCNAndRaw cannot be used here because KERI does not emit FC:/CN:
    labels — it emits "Internal ID:" which matches neither _RE_FC nor _RE_CN.
    The result was a sentinel filename KERI-ID_FC,CN=X,X_N.txt.

    This dedicated function captures Internal ID via REGEX_KERI_ID (decimal)
    as uid, and Raw via REGEX_RAW as raw, producing correct filenames like
    KERI-ID_2164260_N.txt with raw hex as file content.
    """
    ret = executor.startPM3Task('lf keri reader', TIMEOUT)
    if ret == -1:
        return createRetObj(None, None, -1)
    content = executor.getPrintContent()
    if not content or executor.isEmptyContent():
        return createRetObj(None, None, -1)
    uid = executor.getContentFromRegexG(lfsearch.REGEX_KERI_ID, 1)
    raw = executor.getContentFromRegexG(lfsearch.REGEX_RAW, 1)
    if raw:
        raw = lfsearch.cleanHexStr(raw.strip())
    if uid or raw:
        if save:
            _save_txt(31, uid, raw)
        return createRetObj(uid, raw, 1)
    return createRetObj(None, None, -1)


def readNedap(listener=None, infos=None, save=True):
    return readCardIdAndRaw('lf nedap reader', typ=32, save=save)


def readNoralsy(listener=None, infos=None, save=True):
    return readCardIdAndRaw('lf noralsy reader', typ=33, save=save)


def readPAC(listener=None, infos=None, save=True):
    return readCardIdAndRaw('lf pac reader', typ=34, save=save)


def readParadox(listener=None, infos=None, save=True):
    return readFCCNAndRaw('lf paradox reader', typ=35, save=save)


def readPresco(listener=None, infos=None, save=True):
    return readCardIdAndRaw('lf presco reader', typ=36, save=save)


def readVisa2000(listener=None, infos=None, save=True):
    return readCardIdAndRaw('lf visa2000 reader', typ=37, save=save)


def readNexWatch(listener=None, infos=None, save=True):
    return readCardIdAndRaw('lf nexwatch reader', typ=45, save=save)


READ = {
    8: readEM410X,
    9: readHID,
    10: readIndala,
    11: readAWID,
    12: readProxIO,
    13: readGProx2,
    14: readSecurakey,
    15: readViking,
    16: readPyramid,
    23: readT55XX,
    24: readEM4X05,
    28: readFDX,
    29: readGALLAGHER,
    30: readJablotron,
    31: readKeri,
    32: readNedap,
    33: readNoralsy,
    34: readPAC,
    35: readParadox,
    36: readPresco,
    37: readVisa2000,
    45: readNexWatch,
}
