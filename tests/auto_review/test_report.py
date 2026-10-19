import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.auto_review import report, snapshots


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.bundle = dict(base='a' * 40, head='b' * 40, gaps=[], files=[dict(
            path='feature.py', changed=True, base=None, head={'text': 'unsafe()\n'})])
        self.proposal = dict(summary='A supported finding.', completion='complete',
            files=[dict(path='feature.py', scope='purpose', reviewed=True, reason='Changed behavior.')],
            findings=[dict(severity='P1', path='feature.py', side='head', line=1, quote='unsafe()',
                trigger='Call it.', impact='Wrong result.', requested_change='Fix it.',
                validation='source_confirmed')], required_device_checks=[], limitations=[])
        self.saved = dict(status='ADVISORY_COMPLETE', base=self.bundle['base'], head=self.bundle['head'],
            snapshot_sha256=snapshots.digest(self.bundle), review=self.proposal, calls=[], attempts=[])

    def test_partial_advisory_survives_later_failure(self):
        self.saved.update(status='INCOMPLETE', error='TimeoutError', failure_stage='deadline')
        rendered = report.render(self.saved, self.bundle)
        self.assertIn('Partial result', rendered)
        self.assertIn('Wrong result.', rendered)
        self.assertIn('TimeoutError', rendered)
        self.assertIn('not merge approval', rendered)

    def test_model_declared_gap_remains_visible(self):
        self.saved['status'] = 'INCOMPLETE'
        self.proposal.update(completion='incomplete', limitations=['Missing caller source.'])
        rendered = report.render(self.saved, self.bundle)
        self.assertIn('Model coverage declaration: **incomplete**', rendered)
        self.assertIn('Missing caller source.', rendered)

    def test_source_citation_and_snapshot_revalidated_before_display(self):
        for corrupt in ('quote', 'digest', 'head'):
            with self.subTest(corrupt=corrupt):
                saved = copy.deepcopy(self.saved)
                if corrupt == 'quote':
                    saved['review']['findings'][0]['quote'] = 'not in source'
                elif corrupt == 'digest':
                    saved['snapshot_sha256'] = 'f' * 64
                else:
                    saved['head'] = 'c' * 40
                rendered = report.render(saved, self.bundle)
                self.assertIn('saved review failed source validation', rendered)
                self.assertNotIn('Wrong result.', rendered)

    def test_untrusted_html_markdown_and_mentions_are_literal(self):
        self.proposal['summary'] = '</pre><script>bad()</script>\n@maintainer\n[click](https://evil.invalid)'
        rendered = report.render(self.saved, self.bundle)
        self.assertIn('&lt;/pre&gt;&lt;script&gt;', rendered)
        self.assertNotIn('<script>', rendered)
        self.assertNotIn('@maintainer', rendered)
        self.assertIn('&#64;maintainer', rendered)
        self.assertIn('<pre>&lt;/pre&gt;', rendered)

    def test_accounting_counts_terminal_response_once_and_preserves_unknown(self):
        call = dict(id='resp_one', usage=dict(input_tokens=100, output_tokens=25,
                    input_tokens_details={'cached_tokens': 80}, output_tokens_details={'reasoning_tokens': 20}))
        self.saved.update(calls=[call], attempts=[dict(response_id='resp_one', terminal_response=call,
            outcome='response_received'), dict(client_request_id='lost', outcome='transport_error'),
            dict(client_request_id='never', outcome='not_sent')])
        actual = report.accounting(self.saved)
        self.assertEqual(actual['reported_tokens']['input_tokens'], 100)
        self.assertEqual(actual['reported_tokens']['output_tokens'], 25)
        self.assertEqual(actual['reported_tokens']['reasoning_tokens'], 20)
        self.assertEqual(actual['generations_with_metadata'], 1)
        self.assertEqual(actual['unknown_usage_generations'], 1)

    def test_late_terminal_without_accepted_call_still_has_usage(self):
        self.saved['attempts'] = [dict(response_id='resp_late', outcome='transport_error',
            terminal_response=dict(id='resp_late', usage=dict(input_tokens=50, output_tokens=10)))]
        actual = report.accounting(self.saved)
        self.assertEqual(actual['reported_tokens']['output_tokens'], 10)
        self.assertEqual(actual['unknown_usage_generations'], 0)

    def test_failed_collection_has_no_false_clean_review(self):
        rendered = report.render(dict(status='INCOMPLETE', error='ValueError'))
        self.assertIn('No source-validated advisory', rendered)
        self.assertNotIn('No findings were returned', rendered)

    def test_complete_label_cannot_override_missing_or_partial_review(self):
        self.assertNotIn('**ADVISORY_COMPLETE**', report.render(dict(status='ADVISORY_COMPLETE')))
        self.proposal['completion'] = 'incomplete'
        self.assertNotIn('**ADVISORY_COMPLETE**', report.render(self.saved, self.bundle))

    def test_cli_creates_readable_artifact_and_github_summary_without_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'report.json').write_text(json.dumps(self.saved), encoding='utf-8')
            (root / 'snapshot.json').write_text(json.dumps(self.bundle), encoding='utf-8')
            with patch.dict(os.environ, {'GITHUB_STEP_SUMMARY': str(root / 'summary.md')}, clear=True):
                self.assertEqual(report.main(['--directory', str(root)]), 0)
            rendered = (root / 'review.md').read_text(encoding='utf-8')
            self.assertEqual(rendered, (root / 'summary.md').read_text(encoding='utf-8'))
            self.assertIn('/blob/' + 'b' * 40 + '/feature.py#L1', rendered)

    def test_missing_evidence_produces_honest_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {}, clear=True):
                report.main(['--directory', tmp])
            self.assertIn('readable evidence was unavailable',
                          (Path(tmp) / 'review.md').read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
