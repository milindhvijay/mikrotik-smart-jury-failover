"""Check that deployed target mixes still detect broad faults without one-cohort flaps."""
from collections import Counter
from pathlib import Path
import unittest

from jury_monitor import load_targets, score


class InventoryTests(unittest.TestCase):
    def test_single_cohort_outage_does_not_demote_either_isp(self):
        for isp in ('bsnl', 'kv'):
            for family in (4, 6):
                targets = [t for t in load_targets(Path(f'targets_{isp}.csv')) if t.family == family]
                for failed in {t.cohort for t in targets}:
                    with self.subTest(isp=isp, family=family, cohort=failed):
                        samples = {t.ip: [None]*3 if t.cohort == failed else [t.latency]*3 for t in targets}
                        self.assertFalse(score(targets, samples).bad)

    def test_two_largest_cohorts_failing_demotes_either_isp(self):
        for isp in ('bsnl', 'kv'):
            for family in (4, 6):
                with self.subTest(isp=isp, family=family):
                    targets = [t for t in load_targets(Path(f'targets_{isp}.csv')) if t.family == family]
                    failed = {c for c, _ in Counter(t.cohort for t in targets).most_common(2)}
                    samples = {t.ip: [None]*3 if t.cohort in failed else [t.latency]*3 for t in targets}
                    self.assertTrue(score(targets, samples).bad)
