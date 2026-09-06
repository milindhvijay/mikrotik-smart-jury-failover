import subprocess
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import jury_monitor as m

GOOD = m.Health(1, 0, 0, 20, False, True)
BAD = m.Health(0, 5, 100, None, True, False)
GRAY = m.Health(.65, 1, 20, 30, False, False)


class Decisions(unittest.TestCase):
    def test_total_outage_and_continuous_recovery(self):
        d = m.Decision(recovery_seconds=30)
        self.assertIsNone(d.update([GOOD, BAD], 0))
        self.assertFalse(d.update([GOOD, BAD], 5))
        self.assertFalse(d.update([GOOD, GOOD], 10))
        self.assertFalse(d.update([GOOD, GRAY], 39))
        self.assertFalse(d.update([GOOD, GOOD], 40))
        self.assertFalse(d.update([GOOD, GOOD], 69))
        self.assertTrue(d.update([GOOD, GOOD], 70))

    def test_one_bad_sample_aborts_recovery_even_without_failover_streak(self):
        d = m.Decision(recovery_seconds=30)
        d.update([GOOD], 0)
        d.update([BAD], 29)
        self.assertIsNone(d.update([GOOD], 30))
        self.assertIsNone(d.update([GOOD], 59))
        self.assertTrue(d.update([GOOD], 60))
        self.assertIsNone(d.update([GRAY], 61))

    def test_unknown_or_reconnect_resets_evidence(self):
        d = m.Decision(recovery_seconds=30)
        d.update([GOOD], 0)
        d.reset()
        self.assertIsNone(d.update([GOOD], 100))
        self.assertIsNone(d.update([GOOD], 129))

    def test_isolated_transient_does_not_failover(self):
        d = m.Decision()
        for now, health in enumerate([BAD, GOOD, BAD, GOOD]):
            self.assertIsNone(d.update([health], now))


class Probes(unittest.TestCase):
    def setUp(self):
        self.targets = m.load_targets(Path('targets_kv.csv'))

    def test_ipv6_summary_and_losses(self):
        t = self.targets[-1]
        result = m.parse_fping(f'{t.ip} : 12.3 - 13.1\n', [t], 3)
        self.assertEqual(result[t.ip], [12.3, None, 13.1])

    def test_corrupt_or_incomplete_measurement_is_unknown(self):
        t = self.targets[0]
        for text in ['', f'{t.ip} : 1 2', f'{t.ip} : nan - -', f'{t.ip} : -1 - -']:
            with self.subTest(text=text), self.assertRaises(m.ProbeError):
                m.parse_fping(text, [t], 3)

    def test_complete_outage_cannot_be_quarantined_away(self):
        data = {t.ip: [None] * 3 for t in self.targets}
        for _ in range(100):
            self.assertTrue(m.score(self.targets, data).bad)

    def test_broad_partial_loss_is_not_hidden_by_half_vote_boundary(self):
        data = {t.ip: [10, None, 10] for t in self.targets}
        self.assertTrue(m.score(self.targets, data).bad)

    def test_one_cohort_failure_does_not_trigger_failover(self):
        data = {t.ip: [None] * 3 if t.cohort == 'regional_in' else [1] * 3 for t in self.targets}
        self.assertFalse(m.score(self.targets, data).bad)

    def test_health_and_metrics_exclude_unreachable_rtts(self):
        data = {t.ip: [10] * 3 for t in self.targets}
        data[self.targets[0].ip] = [None] * 3
        h = m.score(self.targets, data)
        self.assertFalse(h.bad)
        self.assertTrue(h.recoverable)
        self.assertEqual(h.rtt_ms, 10)

    def test_duplicate_and_empty_csv_rejected(self):
        for contents in ['', '1.1.1.1,20,CF,anycast\n1.1.1.1,20,CF,anycast\n']:
            with tempfile.NamedTemporaryFile(mode='w') as f:
                f.write(contents)
                f.flush()
                with self.assertRaises(ValueError):
                    m.load_targets(Path(f.name))

    def test_local_fping_error_is_not_packet_loss(self):
        result = subprocess.CompletedProcess([], 4, '', 'socket permission denied')
        with patch.object(subprocess, 'run', return_value=result):
            with self.assertRaises(m.ProbeError):
                m.probe(self.targets)

    def test_timeout_propagates_as_unknown(self):
        with patch.object(subprocess, 'run', side_effect=subprocess.TimeoutExpired('fping', 4)):
            with self.assertRaises(subprocess.TimeoutExpired):
                m.probe(self.targets)


class Resource:
    def __init__(self, family, asn='9829'):
        prefix = f'AS{asn}' + (' v6' if family == 6 else '')
        self.rows = [dict(id='1', comment=prefix+' Primary', distance='1', disabled='false'),
                     dict(id='2', comment=prefix+' Failover for AS138754', distance='2', disabled='false')]
        for row in self.rows:
            row['dst-address'] = '::/0' if family == 6 else '0.0.0.0/0'
        for role, row in zip(('primary', 'fallback'), self.rows):
            table_asn = asn if role == 'primary' else '138754'
            row['routing-table'] = ('v6-' if family == 6 else '') + f'route-as{table_asn}'
            row['gateway'] = f'pppoe-as{asn}'
        self.calls = []
        self.fail_once = False

    def get(self, comment):
        return [dict(r) for r in self.rows if r['comment'] == comment]

    def set(self, id, **values):
        if id == '2' and self.fail_once:
            self.fail_once = False
            raise OSError('connection lost after primary change')
        self.calls.append((id, values))
        next(r for r in self.rows if r['id'] == id).update(values)


class Routes(unittest.TestCase):
    def setUp(self):
        self.router = m.Router('bsnl')
        self.v4, self.v6 = Resource(4), Resource(6)
        self.router.api = unittest.mock.Mock()
        self.router.api.get_resource.side_effect = lambda path: self.v6 if path == '/ipv6/route' else self.v4

    def test_idempotent_and_repairs_fallback_even_when_distance_correct(self):
        self.assertTrue(self.router.reconcile(False))
        self.assertFalse(self.router.reconcile(False))
        self.v4.rows[1]['disabled'] = 'false'
        self.assertTrue(self.router.reconcile(False))
        self.assertEqual(self.v4.rows[1]['disabled'], 'true')

    def test_partial_failure_retried(self):
        self.v4.fail_once = True
        with self.assertRaises(OSError):
            self.router.reconcile(False)
        self.assertEqual(self.v4.rows[0]['distance'], '3')
        self.assertTrue(self.router.reconcile(False))
        self.assertEqual(self.v4.rows[1]['disabled'], 'true')
        self.assertEqual(self.v6.rows[0]['distance'], '3')

    def test_all_routes_validated_before_any_write(self):
        self.v6.rows.append(dict(self.v6.rows[0]))
        with self.assertRaises(RuntimeError):
            self.router.reconcile(False)
        self.assertEqual(self.v4.calls, [])

    def test_wrong_destination_and_disabled_primary_rejected(self):
        for key, value in [('dst-address', '10.0.0.0/8'), ('disabled', 'true'), ('dynamic', 'true')]:
            with self.subTest(key=key):
                old = self.v4.rows[0].copy()
                self.v4.rows[0][key] = value
                with self.assertRaises(RuntimeError):
                    self.router.reconcile(False)
                self.v4.rows[0] = old

    def test_wrong_table_or_gateway_cannot_target_monitor_routes(self):
        for key, value in [('routing-table', 'route-as9829-nofailover'), ('gateway', 'pppoe-as138754')]:
            with self.subTest(key=key):
                old = self.v4.rows[0].copy()
                self.v4.rows[0][key] = value
                with self.assertRaises(RuntimeError):
                    self.router.reconcile(False)
                self.assertEqual(self.v4.calls, [])
                self.v4.rows[0] = old

    def test_unexpected_backup_priority_rejected_before_writes(self):
        self.v6.rows[1]['distance'] = '4'
        with self.assertRaises(RuntimeError):
            self.router.reconcile(False)
        self.assertEqual(self.v4.calls, [])

    def test_omitted_false_disabled_flag_is_valid(self):
        for resource in (self.v4, self.v6):
            resource.rows[0].pop('disabled')
        self.assertEqual(len(self.router.routes()), 4)

    def test_interface_api_error_propagates(self):
        self.router.api.get_resource.side_effect = OSError('API unavailable')
        with self.assertRaises(OSError):
            self.router.interface_up()


if __name__ == '__main__':
    unittest.main()
