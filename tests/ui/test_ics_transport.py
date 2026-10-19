"""Regression checks for accessory/PM3 isolation and trustworthy readback.

PM3 fixtures follow RRG v4.23346 cmdlfhid.c/cmdhficlass.c and the
iCopy-X-Community factory client's cmdlfhid.c. No hardware is accessed.
"""
import sys
from types import SimpleNamespace

import pytest

import ics_decoder as decoder
import pm3_compat


@pytest.fixture
def pm3(monkeypatch):
    task = SimpleNamespace(result=1, output='', commands=[])

    def run(command, timeout):
        task.commands.append(command)
        return task.result

    monkeypatch.setitem(sys.modules, 'executor', SimpleNamespace(
        startPM3Task=run, getPrintContent=lambda: task.output))
    return task


@pytest.mark.parametrize('output', [
    'No T55xx chip found', 'T5577 not detected', 'T55xx detection failed',
    'Chip type: unknown', 'Usage: lf t55xx detect', '',
])
def test_negative_t55xx_output_is_not_a_blank(pm3, output):
    pm3.output = output
    assert not decoder.detect_t5577()


@pytest.mark.parametrize('output', [
    'Chip type......... T55x7', 'Chip Type      : T55x7',
    'Valid T55xx chip found',
])
def test_positive_t55xx_evidence(pm3, output):
    pm3.output = output
    assert decoder.detect_t5577()


@pytest.mark.parametrize('output', [
    'block 6: authentication failed', 'block 6: zzzzzzzzzzzzzzzz',
    'block 7/0x07 : 11 22 33 44 55 66 77 88',
    'block 6/0x06 : 11 22 33 44 55 66 77 88\nAuthentication failed',
    'block 0/0x00 : 11 22 33 44 55 66 77 88',
])
def test_hf_detection_requires_authenticated_application_block(pm3, output):
    pm3.output = output
    assert not decoder.detect_target_card()


def test_hf_detection_accepts_eight_hex_bytes(pm3):
    pm3.output = '[+] block   6/0x06 : 11 22 33 44 55 66 77 88'
    assert decoder.detect_target_card()


@pytest.mark.parametrize('output', [
    '', 'Usage: lf hid clone [h] [l] ID', 'Cloning ( fail )',
    'timeout while waiting for reply', 'Done!\nWriting failed',
])
def test_completed_command_is_not_necessarily_success(pm3, output):
    pm3.output = output
    assert not decoder.write_to_t5577(118, 1603)


@pytest.mark.parametrize('fc,cn', [(-1, 1), (256, 1), (1, 65536), (0, 0),
                                     ('no', 1), (None, 1), (1.5, 2), (True, 2)])
def test_invalid_lf_identity_never_sends_a_write(pm3, fc, cn):
    assert not decoder.write_to_t5577(fc, cn)
    assert not pm3.commands


@pytest.mark.parametrize('version,expected', [
    (pm3_compat.PM3_VERSION_ICEMAN, 'lf hid clone -r 2006EC0C86'),
    (pm3_compat.PM3_VERSION_ORIGINAL, 'lf hid clone 2006EC0C86'),
])
def test_known_h10301_vector_uses_existing_variant_translation(pm3, monkeypatch, version, expected):
    # RRG and factory help both use 2006ec0c86 (FC 118, CN 1603).
    pm3.output = '[+] Done!'
    monkeypatch.setattr(pm3_compat, '_current_version', version)
    assert decoder.write_to_t5577(118, 1603)
    assert pm3_compat.translate(pm3.commands[0]) == expected


@pytest.mark.parametrize('output', [
    'raw: 000000000000002006ec0c86',
    'HID Prox - 2006ec0c86 (1603) - len: 26 bit - OEM: 000 FC: 118 Card: 1603',
])
def test_lf_verification_accepts_matching_full_frame(pm3, output):
    pm3.output = output
    assert decoder.verify_target_card('lf_t5577', {'fc': 118, 'id': 1603})[0]


@pytest.mark.parametrize('output', [
    '[H10301] FC: 118 CN: 1603 parity ( fail )',
    'raw: 2006ec0c87',  # Bad parity, identical FC/CN.
    'raw: 4006ec0c86',  # Wrong format/header, identical FC/CN.
    'raw: 2006ec0c86\nraw: 2006ec0c87',
])
def test_lf_verification_rejects_invalid_or_ambiguous_frame(pm3, output):
    pm3.output = output
    assert not decoder.verify_target_card('lf_t5577', {'fc': 118, 'id': 1603})[0]


def test_hf_verification_checks_exact_block_not_only_low_identity_bits(pm3):
    pm3.output = 'block 7/0x07 : 00 00 00 00 02 EC 0C 86'
    source = {'fc': 118, 'id': 1603, 'blk7': '0000800002EC0C86'}
    assert not decoder.verify_target_card('hf_iclass', source)[0]


@pytest.mark.parametrize('result', [-1, 0])
def test_failed_read_cannot_verify_cached_output(pm3, result):
    pm3.result = result
    pm3.output = 'block 7/0x07 : 11 22 33 44 55 66 77 88'
    assert not decoder.verify_target_card('hf_iclass', {'blk7': '1122334455667788'})[0]


def test_wrong_block_number_cannot_verify(pm3):
    pm3.output = 'block 6/0x06 : 11 22 33 44 55 66 77 88'
    assert not decoder.verify_target_card('hf_iclass', {'blk7': '1122334455667788'})[0]


def test_matching_block_seven_verifies(pm3):
    pm3.output = '[+] block 7/0x07 : 11 22 33 44 55 66 77 88'
    assert decoder.verify_target_card('hf_iclass', {'blk7': '1122334455667788'})[0]


def test_decoder_probe_never_opens_internal_pm3(monkeypatch):
    opened = []
    port = SimpleNamespace(reset_input_buffer=lambda: None,
                           write=lambda data: None, readline=lambda size: b'ISE\r\n')
    monkeypatch.setattr(decoder.sys, 'platform', 'linux')
    monkeypatch.setattr(decoder, 'serial', object())
    monkeypatch.setattr(decoder.glob, 'glob', lambda pattern:
                        ['/dev/ttyACM0', '/dev/ttyACM1'] if 'ACM' in pattern else [])
    monkeypatch.setattr(decoder, '_open_serial', lambda path: opened.append(path) or port)
    monkeypatch.setattr(decoder, '_log', lambda message: None)
    monkeypatch.setattr(decoder.time, 'sleep', lambda delay: None)
    assert decoder.detect_decoder() is port
    assert opened == ['/dev/ttyACM1']


def test_decoder_handshake_requires_exact_identity(monkeypatch):
    closed = []
    port = SimpleNamespace(reset_input_buffer=lambda: None, write=lambda data: None,
                           readline=lambda size: b'NOISE\r\n', close=lambda: closed.append(True))
    monkeypatch.setattr(decoder.sys, 'platform', 'linux')
    monkeypatch.setattr(decoder, 'serial', object())
    monkeypatch.setattr(decoder.glob, 'glob', lambda pattern: ['/dev/ttyACM1'])
    monkeypatch.setattr(decoder, '_open_serial', lambda path: port)
    monkeypatch.setattr(decoder, '_log', lambda message: None)
    monkeypatch.setattr(decoder.time, 'sleep', lambda delay: None)
    assert decoder.detect_decoder() is None
    assert closed
