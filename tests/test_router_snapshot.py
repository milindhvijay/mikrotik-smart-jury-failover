"""Detached simulation using read-only RouterOS 7.24.2 snapshot; no network calls."""
import copy
import json
from pathlib import Path
import unittest

from jury_monitor import Router


class SnapshotAPI:
    def __init__(self, snapshot):
        self.snapshot = copy.deepcopy(snapshot)
        self.writes = []

    def get_resource(self, path):
        parent = self

        class Resource:
            def get(self, comment):
                return [dict(r) for r in parent.snapshot[path] if r.get('comment') == comment]

            def set(self, id, **values):
                row = next(r for r in parent.snapshot[path] if r['id'] == id)
                parent.writes.append((path, row['comment'], values))
                row.update(values)

        return Resource()


class LiveSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = json.loads(Path('audit/router-routes.json').read_text())
        self.api = SnapshotAPI(self.snapshot)

    def test_both_isps_healthy_have_no_drift(self):
        for isp in ('bsnl', 'kv'):
            router = Router(isp)
            router.api = self.api
            self.assertFalse(router.reconcile(True))
        self.assertEqual(self.api.writes, [])

    def test_failover_recovery_preserve_all_monitor_tables_and_lte(self):
        for isp in ('bsnl', 'kv'):
            router = Router(isp)
            router.api = self.api
            self.assertTrue(router.reconcile(False))
            self.assertFalse(router.reconcile(False))
            self.assertTrue(router.reconcile(True))
        self.assertEqual(len(self.api.writes), 16)
        for path in ('/ip/route', '/ipv6/route'):
            for before, after in zip(self.snapshot[path], self.api.snapshot[path]):
                if 'nofailover' in before['routing-table'] or 'LTE' in before.get('comment',''):
                    self.assertEqual(before, after)
                self.assertEqual(before.get('distance'), after.get('distance'))
                self.assertEqual(before.get('disabled','false'), after.get('disabled','false'))


if __name__ == '__main__':
    unittest.main()
