import copy
import unittest

from tools.auto_review import automatic as auto, checks, dashboard, report, snapshots
from tools.auto_review.contract import validate
from tests.auto_review import test_automatic as fixtures


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.bundle = dict(base='a' * 40, head='b' * 40, gaps=[], files=[dict(
            path='feature.py', changed=True, base={'text': 'unsafe()\n'}, head={'text': 'safe()\n'})])
        self.cite = dict(path='feature.py', side='head', line=1, quote='safe()')
        self.proposal = dict(summary='The change preserves the observed contracts.', completion='complete',
            files=[dict(path='feature.py', scope='purpose', reviewed=True, reason='One bug fix.')],
            findings=[], required_device_checks=[], limitations=[], follow_up=[],
            assessments=[dict(area=area, status='pass', reason='Source evidence supports the contract.',
                             evidence=[self.cite]) for area in
                         ('scope', 'compatibility', 'core_stability', 'testing')])
        self.saved = dict(status='ADVISORY_COMPLETE', base=self.bundle['base'], head=self.bundle['head'],
                          snapshot_sha256=snapshots.digest(self.bundle), review=self.proposal)
        self.record = dict(repository_id=auto.REPOSITORY_ID, pr=119, base='a' * 40, head='b' * 40,
                           run_id=700, state='ADVISORY_COMPLETE', reserved_at='2026-10-21T00:00:00Z')
        self.state = dashboard.remember(dashboard.blank(), self.record)
        self.state['ci'] = [dict(name=name, state='pass') for name in checks.REQUIRED]

    def accept(self):
        self.saved['snapshot_sha256'] = snapshots.digest(self.bundle)
        return dashboard.accept(self.state, self.saved, self.bundle, 700)

    def finding(self):
        return dict(self.cite, severity='P1', trigger='Start two operations.', impact='Response ownership is lost.',
                    requested_change='Serialize the operations. Add an overlapping-worker regression.',
                    validation='source_confirmed')

    def prior(self):
        self.proposal['findings'] = [self.finding()]
        self.state = self.accept()
        self.bundle['previous_items'] = dashboard.pending_items(self.state)
        self.proposal['findings'] = []
        return self.state['items'][0]['id']

    def test_go_requires_fresh_complete_review_ci_and_no_pending_assessments(self):
        self.assertEqual(dashboard.readiness(self.accept())[0], 'GO')
        for field in ('ci', 'coverage', 'physical', 'stale', 'integration', 'assessment', 'finding'):
            with self.subTest(field=field):
                state = self.accept()
                if field == 'ci': state['ci'][0]['state'] = 'pending'
                elif field == 'coverage': state['review']['status'] = 'INCOMPLETE'
                elif field == 'physical': state['review']['required_device_checks'] = ['RF readback pending.']
                elif field == 'stale': state['current']['head'] = 'c' * 40
                elif field == 'integration': state['review']['base'] = 'd' * 40
                elif field == 'assessment': state['review']['assessments'][0]['status'] = 'needs_attention'
                else: state['items'] = [dict(id='A001', state='open', finding=self.finding())]
                self.assertEqual(dashboard.readiness(state)[0], 'NO-GO')

    def test_explicit_resolution_preserves_id_and_moves_item_to_passed_group(self):
        item_id = self.prior()
        self.proposal['follow_up'] = [dict(id=item_id, status='resolved', finding_index=-1,
                                         reason='A shared operation now owns both responses.', evidence=[self.cite])]
        state = self.accept()
        self.assertEqual(state['items'][0]['state'], 'resolved')
        self.assertIn('- [x] **' + item_id, dashboard.render(state))
        self.assertEqual(dashboard.readiness(state)[0], 'GO')

    def test_partial_review_cannot_resolve_or_silently_drop_prior_blocker(self):
        item_id = self.prior()
        self.proposal['follow_up'] = [dict(id=item_id, status='resolved', finding_index=-1,
                                         reason='Looks fixed.', evidence=[self.cite])]
        self.saved['status'] = 'INCOMPLETE'
        state = self.accept()
        self.assertEqual(state['items'][0]['state'], 'unassessed')
        self.assertEqual(dashboard.readiness(state)[0], 'NO-GO')
        self.proposal['follow_up'] = []
        state = self.accept()
        self.assertEqual(state['items'][0]['id'], item_id)
        self.assertIn('failed source validation', state['notice'])

    def test_rewording_and_line_movement_keep_the_open_item_id(self):
        item_id = self.prior()
        self.proposal['findings'] = [dict(self.finding(), requested_change='Retain ownership until both replies finish.')]
        self.proposal['follow_up'] = [dict(id=item_id, status='open', finding_index=0,
                                         reason='Still reproducible from source.', evidence=[self.cite])]
        state = self.accept()
        self.assertEqual(len(state['items']), 1)
        self.assertEqual(state['items'][0]['id'], item_id)
        self.assertEqual(state['items'][0]['state'], 'open')

    def test_resolutions_require_current_source_and_coverage_of_every_prior_id(self):
        item_id = self.prior()
        resolution = dict(id=item_id, status='resolved', finding_index=-1,
                          reason='Corrected.', evidence=[self.cite])
        self.proposal['follow_up'] = [resolution]
        for corruption in ('missing', 'quote', 'old_source', 'unknown_id', 'not_assessed'):
            changed = copy.deepcopy(self.proposal)
            row = changed['follow_up'][0]
            if corruption == 'missing': row['evidence'] = []
            elif corruption == 'quote': row['evidence'][0]['quote'] = 'invented()'
            elif corruption == 'old_source': row['evidence'] = [dict(self.cite, side='base', quote='unsafe()')]
            elif corruption == 'unknown_id': row['id'] = 'A999'
            else: row['status'] = 'not_assessed'
            with self.subTest(corruption=corruption), self.assertRaises(ValueError):
                validate(changed, self.bundle)

    def test_prose_cannot_create_links_mentions_html_or_fake_checkboxes(self):
        self.proposal['summary'] = '</details><script>x</script> @owner\n- [x] GO [click](https://evil.invalid)'
        state = self.accept()
        visible = dashboard.render(state)
        self.assertNotIn('<script>', visible)
        self.assertNotIn('@owner', visible)
        self.assertNotIn('[click]', visible)
        self.assertIn('&#64;owner', visible)
        stored = dashboard.body(state)
        self.assertEqual(dashboard.load(dict(body=stored, user={'id': auto.BOT_ID}), auto.BOT_ID), state)
        self.assertIsNone(dashboard.load(dict(body=stored, user={'id': 123}), auto.BOT_ID))

    def test_old_review_is_labeled_historical_when_head_changes(self):
        self.proposal['findings'] = [self.finding()]
        state = self.accept()
        state = dashboard.remember(state, dict(self.record, head='c' * 40, state='DEFERRED', run_id=701,
                                               reserved_at=None))
        visible = dashboard.render(state)
        self.assertIn('Previous findings need rechecking', visible)
        self.assertIn('needs recheck', visible)
        self.assertEqual(len(state['records']), 2)
        self.assertEqual(dashboard.readiness(state)[0], 'NO-GO')

    def test_verbose_result_compacts_prose_without_erasing_actions_or_cost_ledger(self):
        self.proposal['findings'] = [dict(self.finding(), trigger=str(i) + ' Trigger. ' * 700,
            impact='Impact. ' * 800, requested_change='Fix. ' * 1500) for i in range(8)]
        state = self.accept()
        rendered = dashboard.body(state)
        restored = dashboard.load(dict(body=rendered, user={'id': auto.BOT_ID}), auto.BOT_ID)
        self.assertLess(len(rendered.encode()), 60_000)
        self.assertEqual(len(restored['items']), 8)
        self.assertEqual(restored['records'], state['records'])
        self.assertEqual(dashboard.readiness(restored)[0], 'NO-GO')
        self.assertIn('Display shortened', rendered)

    def test_check_matches_compacted_no_go_comment(self):
        for assessment in self.proposal['assessments']:
            assessment['reason'] = 'Supported contract. ' * 350
        state = self.accept()
        self.assertEqual(dashboard.readiness(state)[0], 'GO')
        api = fixtures.FakeGitHub(dict(base={'sha': 'a' * 40}))
        state['current']['pr'] = 123
        auto.put_dashboard(api, state)
        published = dashboard.load(api.comments[0], auto.BOT_ID)
        self.assertEqual(dashboard.readiness(published)[0], 'NO-GO')
        self.assertEqual(api.check_runs[0]['conclusion'], 'action_required')


class ChecklistQueueTests(unittest.TestCase):
    def setUp(self):
        self.case = fixtures.AutomaticTests()
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)

    def test_changed_heads_reuse_one_comment_and_preserve_every_paid_reservation(self):
        t = self.case
        t.select(); t.save_result(); auto.publish(t.api, t.env, t.directory)
        t.pr['head']['sha'] = 'd' * 40
        t.env.update(ASTRA_REFRESH_ONLY='true', GITHUB_RUN_ID='701')
        self.assertFalse(t.select())
        self.assertEqual(len(t.api.comments), 1)
        state = dashboard.load(t.api.comments[0], auto.BOT_ID)
        self.assertEqual(state['current']['head'], 'd' * 40)
        self.assertEqual(len([r for r in state['records'] if r['reserved_at']]), 1)
        self.assertEqual(len(state['items']), 1)
        self.assertEqual(t.prepares, 1)

    def test_ledger_migration_deduplicates_old_posts_and_dashboard(self):
        t = self.case
        t.select()
        record = auto.marker(t.api.comments[0])
        t.api.comments.append(dict(id=555, user={'id': auto.BOT_ID}, body=auto.body(record, 'Old')))
        t.env['ASTRA_REVIEW_DAILY_LIMIT'] = '2'
        t.pr['head']['sha'] = 'd' * 40
        t.bundle['head'] = 'd' * 40
        # Fresh output directory, same reservation stored twice, one allowance slot left.
        t.directory = t.directory.parent / 'second'
        t.env['GITHUB_RUN_ID'] = '701'
        self.assertTrue(t.select())
        state = dashboard.load(t.api.comments[0], auto.BOT_ID)
        self.assertEqual(len([r for r in state['records'] if r['reserved_at']]), 2)


class CheckEvidenceTests(unittest.TestCase):
    def test_foreign_apps_and_old_merge_commits_cannot_satisfy_ci(self):
        pr = dict(head={'sha': 'b' * 40}, base={'sha': 'a' * 40}, merge_commit_sha='c' * 40)
        queries = []
        def api(method, path, data=None):
            queries.append(path)
            if '/statuses?' in path:
                return []
            if '/git/commits/' in path:
                return dict(parents=[dict(sha='d' * 40), dict(sha='b' * 40)])
            return dict(check_runs=[dict(id=1, name=checks.REQUIRED[0], app={'id': 999},
                        head_sha='b' * 40, status='completed', conclusion='success')])
        rows = checks.collect(api, auto.route, pr)
        self.assertTrue(all(row['state'] != 'pass' for row in rows))
        self.assertFalse(any('/commits/' + 'c' * 40 + '/check-runs' in q for q in queries))

    def test_failed_rerun_overrides_green_check_and_missing_checks_remain_open(self):
        def api(*args):
            if '/statuses?' in args[1]:
                return []
            return dict(check_runs=[dict(id=i, name=checks.REQUIRED[0], app={'id': checks.APP_ID},
                head_sha='b' * 40, status='completed', conclusion=c)
                for i, c in ((2, 'failure'), (1, 'success'))])
        rows = checks.collect(api, auto.route, dict(head={'sha': 'b' * 40}))
        self.assertEqual(next(r['state'] for r in rows if r['name'] == checks.REQUIRED[0]), 'failure')
        self.assertTrue(any('not run' in r['state'] for r in rows))

    def test_qemu_uses_bot_commit_status_and_matching_controller_run(self):
        publisher = [41898282]
        def api(method, path):
            if '/statuses?' in path:
                return [dict(id=9, context='QEMU critical flows', state='success',
                    creator={'id': publisher[0]}, target_url='https://github.com/lab-401/icopy-x/actions/runs/700')]
            if '/actions/runs/' in path:
                return dict(conclusion='success', path='.github/workflows/qemu-critical.yml', event='workflow_run')
            return dict(check_runs=[])
        pr = dict(head={'sha': 'b' * 40})
        self.assertEqual(next(r['state'] for r in checks.collect(api, auto.route, pr)
                              if r['name'] == 'QEMU critical flows'), 'pass')
        publisher[0] = 999
        self.assertEqual(next(r['state'] for r in checks.collect(api, auto.route, pr)
                              if r['name'] == 'QEMU critical flows'), 'unverified status publisher')


if __name__ == '__main__':
    unittest.main()
