import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit

from tools.auto_review import automatic as auto, snapshots


class FakeGitHub:
    def __init__(self, pr):
        self.pr = pr
        self.comments = []
        self.global_comments = []
        self.writes = []
        self.reads = []
        self.next_prs = []
        self.old_run = {'status': 'completed'}

    def __call__(self, method, route, data=None):
        path = urlsplit(route).path.removeprefix('/repos/' + auto.REPOSITORY)
        self.reads.append((method, path))
        if method == 'GET':
            if path == '':
                return {'id': auto.REPOSITORY_ID, 'default_branch': 'main'}
            if path == '/pulls':
                return [copy.deepcopy(self.pr)]
            if path == '/pulls/123':
                return copy.deepcopy(self.next_prs.pop(0) if self.next_prs else self.pr)
            if path == '/issues/comments':
                return copy.deepcopy(self.global_comments + self.comments)
            if path == '/issues/123/comments':
                return copy.deepcopy(self.comments)
            if path.startswith('/issues/comments/'):
                return copy.deepcopy(next(c for c in self.comments if c['id'] == int(path.rsplit('/', 1)[1])))
            if path.startswith('/actions/runs/'):
                return self.old_run
        self.writes.append((method, path, data))
        if method == 'POST' and path == '/issues/123/comments':
            comment = dict(id=1000 + len(self.comments), body=data['body'], user={'id': auto.BOT_ID})
            self.comments.append(comment)
            return copy.deepcopy(comment)
        if method == 'PATCH' and path.startswith('/issues/comments/'):
            comment = next(c for c in self.comments if c['id'] == int(path.rsplit('/', 1)[1]))
            comment['body'] = data['body']
            return copy.deepcopy(comment)
        raise AssertionError((method, path))


class AutomaticTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name) / 'evidence'
        self.env = dict(GITHUB_REPOSITORY=auto.REPOSITORY, GITHUB_REPOSITORY_ID=str(auto.REPOSITORY_ID),
            GITHUB_REF='refs/heads/main', GITHUB_SHA='c' * 40, GITHUB_EVENT_NAME='schedule',
            GITHUB_RUN_ID='700', GITHUB_RUN_ATTEMPT='1', ASTRA_AUTOMATIC_REVIEW='true',
            OPENAI_API_KEY='not-a-real-key')
        self.pr = dict(number=123, state='open', draft=False, title='Fix an observed bug', body='One purpose.',
            base={'sha': 'a' * 40, 'ref': 'main', 'repo': {'id': auto.REPOSITORY_ID}}, head={'sha': 'b' * 40})
        self.api = FakeGitHub(self.pr)
        self.now = datetime(2026, 10, 19, 18, 0, tzinfo=timezone.utc)
        self.bundle = dict(base='a' * 40, head='b' * 40, gaps=[], files=[dict(path='feature.py',
            changed=True, base=None, head={'text': 'unsafe()\n'})], limits={'max_bytes': 2_000_000})
        self.prepares = 0

    def prepare(self, pr, repo):
        self.prepares += 1
        return copy.deepcopy(self.bundle)

    def select(self):
        return auto.select(self.api, self.env, self.directory, self.prepare, self.now)

    def proposal(self):
        return dict(summary='Returned finding.', completion='incomplete', files=[dict(path='feature.py',
            scope='purpose', reviewed=True, reason='Changed behavior.')], findings=[dict(severity='P2',
            path='feature.py', side='head', line=1, quote='unsafe()', trigger='Call it.', impact='Wrong result.',
            requested_change='Fix it.', validation='source_confirmed')],
            required_device_checks=[], limitations=['Missing caller.'])

    def save_result(self):
        record, bundle, _ = auto.checked_input(self.directory, self.env)
        result = dict(status='INCOMPLETE', advisory=True, base=record['base'], head=record['head'],
            snapshot_sha256=record['snapshot_sha256'], policy_sha256=record['policy_sha256'],
            review=self.proposal(), attempts=[], calls=[])
        (self.directory / 'report.json').write_text(json.dumps(result), encoding='utf-8')
        return result

    def test_trusted_main_only(self):
        for key, value in [('GITHUB_REF', 'refs/pull/123/merge'), ('GITHUB_REPOSITORY_ID', '1'),
                           ('GITHUB_EVENT_NAME', 'pull_request_target'), ('GITHUB_SHA', '--option')]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                auto.trusted(dict(self.env, **{key: value}))

    def test_disabled_and_rerun_selection_make_no_reservation(self):
        for key, value in [('ASTRA_AUTOMATIC_REVIEW', 'false'), ('GITHUB_RUN_ATTEMPT', '2')]:
            self.assertFalse(auto.select(self.api, dict(self.env, **{key: value}), self.directory,
                                         self.prepare, self.now))
        self.assertFalse(self.api.writes)
        self.assertEqual(self.prepares, 0)

    def test_reservation_deduplicates_same_base_and_head(self):
        self.assertTrue(self.select())
        self.api.old_run = {'status': 'in_progress'}
        self.assertFalse(self.select())
        self.assertEqual(self.prepares, 1)
        self.assertEqual(len(self.api.writes), 1)

    def test_finished_abandoned_reservation_becomes_incomplete_without_retry(self):
        self.assertTrue(self.select())
        self.assertFalse(self.select())
        self.assertEqual(self.prepares, 1)
        self.assertEqual(auto.marker(self.api.comments[0])['state'], 'INCOMPLETE')
        self.assertIn('no automatic retry', self.api.comments[0]['body'])

    def test_spoofed_marker_from_contributor_cannot_suppress_review(self):
        record = dict(auto.identity(self.pr), run_id=699, state='ADVISORY_COMPLETE', reserved_at=None)
        self.api.comments.append(dict(id=99, body=auto.body(record, 'Fake'), user={'id': 12345}))
        self.assertTrue(self.select())
        self.assertEqual(self.prepares, 1)

    def test_rolling_budget_counts_closed_pr_reservations(self):
        self.env['ASTRA_REVIEW_DAILY_LIMIT'] = '1'
        record = dict(auto.identity(self.pr), pr=50, run_id=699, state='ADVISORY_COMPLETE',
                      reserved_at='2026-10-19T17:00:00Z')
        self.api.global_comments = [dict(id=99, body=auto.body(record, 'Finished'), user={'id': auto.BOT_ID})]
        self.assertFalse(self.select())
        self.assertEqual(self.prepares, 0)
        self.assertEqual(auto.marker(self.api.comments[0])['state'], 'DEFERRED')
        count = len(self.api.writes)
        self.assertFalse(self.select())
        self.assertEqual(len(self.api.writes), count)
        # Next day the durable queue reconsiders the deferred head.
        later = datetime(2026, 10, 20, 18, 0, tzinfo=timezone.utc)
        self.assertTrue(auto.select(self.api, self.env, self.directory, self.prepare, later))
        self.assertEqual(auto.marker(self.api.comments[0])['state'], 'RESERVED')

    def test_drafts_and_closed_prs_do_not_run(self):
        for field, value in [('draft', True), ('state', 'closed')]:
            api = FakeGitHub(dict(self.pr, **{field: value}))
            self.assertFalse(auto.select(api, self.env, self.directory, self.prepare, self.now))
            self.assertFalse(api.writes)
        self.assertEqual(self.prepares, 0)

    def test_head_change_during_collection_is_not_reserved(self):
        changed = copy.deepcopy(self.pr); changed['head']['sha'] = 'd' * 40
        self.api.next_prs = [self.pr, changed]
        self.assertFalse(self.select())
        self.assertFalse(self.api.writes)

    def test_collection_gaps_return_explanation_without_paid_reservation(self):
        self.bundle['gaps'] = [{'path': 'binary', 'reason': 'binary payload'}]
        self.assertFalse(self.select())
        record = auto.marker(self.api.comments[0])
        self.assertEqual(record['state'], 'INCOMPLETE')
        self.assertIsNone(record['reserved_at'])
        self.assertIn('no API call made', self.api.comments[0]['body'])

    def test_changed_head_before_model_prevents_api_call(self):
        self.select(); self.pr['head']['sha'] = 'd' * 40
        self.assertEqual(auto.run_review(self.api, self.env, self.directory,
                         lambda *a, **kw: self.fail('Paid call on stale head')), 2)

    def test_rerun_of_failed_review_job_cannot_make_another_paid_call(self):
        self.select()
        with self.assertRaisesRegex(ValueError, 'reruns'):
            auto.run_review(self.api, dict(self.env, GITHUB_RUN_ATTEMPT='2'), self.directory,
                            lambda *a, **kw: self.fail('Paid retry'))

    def test_source_identity_and_trusted_revision_checked_before_model(self):
        self.select()
        for env in (dict(self.env, GITHUB_SHA='d' * 40), dict(self.env, GITHUB_RUN_ID='701')):
            with self.assertRaisesRegex(ValueError, 'identity'):
                auto.run_review(self.api, env, self.directory, lambda *a, **kw: self.fail('Wrong identity'))
        self.bundle['files'][0]['head']['text'] = 'changed()'
        (self.directory / 'snapshot.json').write_text(json.dumps(self.bundle), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'identity'):
            auto.run_review(self.api, self.env, self.directory, lambda *a, **kw: self.fail('Wrong source'))

    def test_change_between_passes_stops_future_generation(self):
        self.select()
        def fake_review(bundle, policy, key, checkpoint):
            checkpoint({'attempts': [{}]})
            self.pr['head']['sha'] = 'd' * 40
            with self.assertRaisesRegex(ValueError, 'changed'):
                checkpoint({'attempts': [{}, {}]})
            return {'status': 'INCOMPLETE'}
        self.assertEqual(auto.run_review(self.api, self.env, self.directory, fake_review), 2)

    def test_partial_findings_are_published_and_terminal_identity_is_preserved(self):
        self.select(); self.save_result()
        auto.publish(self.api, self.env, self.directory)
        comment = self.api.comments[0]
        self.assertIn('Wrong result.', comment['body'])
        self.assertIn('Missing caller.', comment['body'])
        self.assertEqual(auto.marker(comment)['state'], 'INCOMPLETE')
        self.assertIsNotNone(auto.marker(comment)['reserved_at'])

    def test_stale_result_does_not_publish_findings_against_new_head(self):
        self.select(); self.save_result(); self.pr['head']['sha'] = 'd' * 40
        auto.publish(self.api, self.env, self.directory)
        self.assertEqual(auto.marker(self.api.comments[0])['state'], 'STALE')
        self.assertNotIn('Wrong result.', self.api.comments[0]['body'])

    def test_missing_result_still_posts_honest_incomplete_outcome(self):
        self.select()
        auto.publish(self.api, self.env, self.directory)
        self.assertEqual(auto.marker(self.api.comments[0])['state'], 'INCOMPLETE')
        self.assertIn('No source-validated advisory', self.api.comments[0]['body'])

    def test_tampered_citation_is_not_published(self):
        self.select(); result = self.save_result()
        result['review']['findings'][0]['quote'] = 'not the source'
        (self.directory / 'report.json').write_text(json.dumps(result), encoding='utf-8')
        auto.publish(self.api, self.env, self.directory)
        self.assertNotIn('Wrong result.', self.api.comments[0]['body'])
        self.assertIn('failed source validation', self.api.comments[0]['body'])

    def test_publication_rejects_reservation_owned_by_other_actor(self):
        self.select(); self.save_result(); self.api.comments[0]['user']['id'] = 1234
        with self.assertRaisesRegex(ValueError, 'reservation'):
            auto.publish(self.api, self.env, self.directory)

    def test_bounded_inventory_fails_instead_of_silently_omitting_prs(self):
        with self.assertRaisesRegex(ValueError, 'inventory exceeds'):
            auto.pages(lambda *a: [{}] * 100, auto.route('/pulls'))

    def test_context_recipes_refer_to_real_tracked_sources(self):
        paths = auto.recipes(['src/middleware/ics_decoder.py', 'src/lib/activity_main.py',
                              'src/middleware/iclasswrite.py', 'tools/build_ipk.py'])
        tracked = set(subprocess.check_output(['git', 'ls-files']).decode().splitlines())
        self.assertFalse(set(paths) - tracked)
        self.assertIn('src/main/rftask.py', paths)
        self.assertIn('tests/ui/activities/test_ics_decoder.py', paths)

    def test_preparation_reads_candidate_blobs_without_executing_them(self):
        root = Path(self.temp.name) / 'repo'; root.mkdir()
        def git(*args):
            return subprocess.check_output(['git', '-C', str(root), *args], stderr=subprocess.PIPE).decode().strip()
        git('init', '-q'); git('config', 'user.email', 'fixture@example.invalid'); git('config', 'user.name', 'Fixture')
        (root / 'feature.py').write_text('# base\n', encoding='utf-8')
        git('add', '.'); git('commit', '-qm', 'base'); base = git('rev-parse', 'HEAD')
        payload = "raise RuntimeError('Candidate code must never execute')\n"
        (root / 'feature.py').write_text(payload, encoding='utf-8')
        git('add', '.'); git('commit', '-qm', 'head'); head = git('rev-parse', 'HEAD')
        pr = copy.deepcopy(self.pr); pr['base']['sha'] = base; pr['head']['sha'] = head
        with patch.object(auto.subprocess, 'run') as fetch:
            bundle = auto.prepare(pr, root)
        self.assertEqual(bundle['files'][0]['head']['text'], payload)
        self.assertEqual(fetch.call_count, 1)
        command = fetch.call_args.args[0]
        self.assertIn('--no-recurse-submodules', command)
        self.assertNotIn('checkout', command)
        self.assertNotIn('OPENAI_API_KEY', fetch.call_args.kwargs['env'])


if __name__ == '__main__':
    unittest.main()
