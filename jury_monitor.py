"""Low-overhead, dual-stack RouterOS monitor. Probe-only unless --apply is explicit."""
from __future__ import annotations

import argparse
import subprocess
import csv
import ipaddress
import json
import logging
import math
import os
from pathlib import Path
import signal
import time
from dataclasses import dataclass

LOG = logging.getLogger('jury')
WEIGHTS = {'priority': 2.0, 'isp': 1.8, 'anycast': 1.5,
           'regional_in': 1.4, 'regional_apac': 1.2, 'regional_eu': 1.1,
           'regional': 1.4}
ASNS = {'bsnl': '9829', 'kv': '138754'}


@dataclass(frozen=True)
class Target:
    ip: str
    latency: float
    name: str
    cohort: str
    family: int


def load_targets(path: Path) -> list[Target]:
    targets, seen = [], set()
    with path.open() as source:
        for number, row in enumerate(csv.reader(source), 1):
            if not row or not row[0].strip() or row[0].lstrip().startswith('#'):
                continue
            if len(row) != 4:
                raise ValueError(f'{path}:{number}: expected four CSV columns')
            ip, latency, name, cohort = (x.strip() for x in row)
            addr = ipaddress.ip_address(ip)  # Literal IPs avoid DNS/WAN dependency.
            latency = float(latency)
            if not math.isfinite(latency) or latency <= 0 or cohort not in WEIGHTS:
                raise ValueError(f'{path}:{number}: invalid latency or cohort')
            ip = str(addr)
            if ip in seen:
                raise ValueError(f'{path}:{number}: duplicate IP {ip}')
            seen.add(ip)
            targets.append(Target(ip, latency, name, cohort, addr.version))
    for family in (4, 6):
        subset = [t for t in targets if t.family == family]
        if len(subset) < 5 or len({t.cohort for t in subset}) < 3:
            raise ValueError(f'IPv{family} requires at least five targets in three cohorts')
    return targets


class ProbeError(RuntimeError):
    """Local measurement failure; never interpreted as WAN failure."""


def parse_fping(output: str, targets: list[Target], count: int) -> dict[str, list[float | None]]:
    expected = {t.ip for t in targets}
    samples = {}
    for line in output.splitlines():
        host, separator, values = line.partition(' :')
        if not separator:
            continue
        try:
            host = str(ipaddress.ip_address(host.strip()))
        except ValueError:
            continue
        if host not in expected:
            continue
        tokens = values.split()
        if len(tokens) != count or host in samples:
            raise ProbeError(f'Invalid fping sample count or duplicate row for {host}')
        try:
            data = [None if x == '-' else float(x) for x in tokens]
        except ValueError as exc:
            raise ProbeError(f'Invalid fping output for {host}') from exc
        if any(x is not None and (not math.isfinite(x) or x < 0) for x in data):
            raise ProbeError(f'Invalid RTT for {host}')
        samples[host] = data
    if samples.keys() != expected:
        raise ProbeError(f'Incomplete fping output: {len(samples)}/{len(expected)} targets')
    return samples


def probe(targets: list[Target], count: int = 3) -> dict[str, list[float | None]]:
    # fping itself multiplexes both families; Python needs no event loop or threads.
    # Timeout <= period; fping discards late replies. Rate limited across targets.
    command = ['fping', '-q', '-C', str(count), '-p', '500', '-t', '500', '-i', '5']
    deadline = count * max(0.5, len(targets) * 0.005) + 2
    result = subprocess.run(
        command + [t.ip for t in targets], capture_output=True, text=True,
        timeout=deadline, env={**os.environ, 'LC_ALL': 'C'})
    # subprocess.run kills and reaps its child on timeout or interruption.
    if result.returncode not in (0, 1):
        raise ProbeError(f'fping exit {result.returncode}: {result.stderr[:300]}')
    return parse_fping(result.stdout + result.stderr, targets, count)


@dataclass(frozen=True)
class Health:
    score: float
    failing_cohorts: int
    loss_pct: float
    rtt_ms: float | None
    bad: bool
    recoverable: bool


def score(targets: list[Target], samples: dict[str, list[float | None]]) -> Health:
    total = passed = lost = probes = 0
    cohorts = {}
    rtts = []
    for target in targets:
        values = samples[target.ip]
        received = [v for v in values if v is not None]
        loss = 1 - len(received) / len(values)
        rtt = sum(received) / len(received) if received else math.inf
        # One loss out of three is a warning; repeated majority loss is critical.
        vote = (0.0 if loss >= 0.4 or rtt >= max(50, 2.5 * target.latency)
                else 0.5 if loss > 0 or rtt >= max(30, 1.5 * target.latency) else 1.0)
        weight = WEIGHTS[target.cohort]
        total += weight
        passed += weight * vote
        tally = cohorts.setdefault(target.cohort, [0.0, 0.0])
        tally[0] += weight * vote
        tally[1] += weight
        lost += len(values) - len(received)
        probes += len(values)
        rtts.extend(received)
    value = passed / total
    failing = sum(good / weight <= 0.5 for good, weight in cohorts.values())
    return Health(value, failing, 100 * lost / probes,
                  sum(rtts) / len(rtts) if rtts else None,
                  value < 0.58 and failing >= 2,
                  value >= 0.75 and failing < 2)


@dataclass
class Decision:
    failures: int = 2
    recovery_seconds: float = 120
    bad_streak: int = 0
    healthy_since: float | None = None
    desired: bool | None = None

    def reset(self) -> None:
        self.bad_streak = 0
        self.healthy_since = None
        self.desired = None

    def update(self, health: list[Health], now: float) -> bool | None:
        bad = any(h.bad for h in health)
        healthy = all(h.recoverable for h in health)
        self.bad_streak = min(self.failures, self.bad_streak + 1) if bad else 0
        if not healthy:
            self.healthy_since = None
            # Do not retry a pending recovery through a degraded/unknown sample.
            if self.desired is True:
                self.desired = None
        elif self.healthy_since is None:
            self.healthy_since = now
        if self.bad_streak >= self.failures:
            self.desired = False
        elif self.healthy_since is not None and now - self.healthy_since >= self.recovery_seconds:
            self.desired = True
        return self.desired


class Router:
    def __init__(self, isp: str):
        self.asn = ASNS[isp]
        self.other = ASNS['kv' if isp == 'bsnl' else 'bsnl']
        self.pool = None
        self.api = None

    def connect(self) -> None:
        import routeros_api  # Probe-only mode needs only the standard library.
        password = os.environ.get('ROUTER_PASS', '')
        user = os.environ.get('ROUTER_USER', '')
        if not password or not user:
            raise ValueError('ROUTER_USER and ROUTER_PASS must be set for --apply')
        self.pool = routeros_api.RouterOsApiPool(
            os.environ.get('ROUTER_HOST', '10.1.1.1'), username=user, password=password,
            plaintext_login=True, use_ssl=os.environ.get('ROUTER_SSL') == '1')
        self.pool.socket_timeout = 3
        self.api = self.pool.get_api()
        LOG.info('Router API connected')

    def close(self) -> None:
        if self.pool:
            try:
                self.pool.disconnect()
            except Exception:
                pass
        self.pool = self.api = None

    def interface_up(self) -> bool:
        rows = self.api.get_resource('/interface').get(name=f'pppoe-as{self.asn}')
        if len(rows) != 1:
            raise RuntimeError('WAN interface missing or ambiguous')
        # API errors propagate for reconnect; they are not evidence of link failure.
        return str(rows[0].get('running')).lower() == 'true'

    def routes(self) -> list:
        result = []
        for family, path in ((4, '/ip/route'), (6, '/ipv6/route')):
            resource = self.api.get_resource(path)
            prefix = f'AS{self.asn}' + (' v6' if family == 6 else '')
            for role, comment in (('primary', f'{prefix} Primary'),
                                  ('fallback', f'{prefix} Failover for AS{self.other}')):
                rows = resource.get(comment=comment)
                if len(rows) != 1:
                    raise RuntimeError(f'Expected exactly one route: {comment}; got {len(rows)}')
                row = rows[0]
                table_asn = self.asn if role == 'primary' else self.other
                expected_table = ('v6-' if family == 6 else '') + f'route-as{table_asn}'
                if row.get('routing-table') != expected_table or row.get('gateway') != f'pppoe-as{self.asn}':
                    raise RuntimeError(f'Unexpected routing table or gateway: {comment}')
                if role == 'fallback' and str(row.get('distance')) != '2':
                    raise RuntimeError(f'Unexpected fallback distance: {comment}')
                if row.get('dst-address') != ('0.0.0.0/0' if family == 4 else '::/0'):
                    raise RuntimeError(f'Not a default route: {comment}')
                if str(row.get('dynamic', 'false')).lower() == 'true':
                    raise RuntimeError(f'Refusing dynamic route: {comment}')
                if role == 'primary' and str(row.get('disabled', 'false')).lower() == 'true':
                    raise RuntimeError(f'Primary route administratively disabled: {comment}')
                result.append((resource, role, row))
        return result

    def reconcile(self, healthy: bool) -> bool:
        # Validate all four routes before the first write. Re-read after partial errors
        # and each reconciliation; never assume a successful primary set fixed fallback.
        rows = self.routes()
        changed = False
        for resource, role, row in rows:
            key = 'distance' if role == 'primary' else 'disabled'
            desired = ('1' if healthy else '3') if role == 'primary' else ('false' if healthy else 'true')
            if str(row.get(key)).lower() != desired:
                resource.set(id=row['id'], **{key: desired})
                changed = True
                LOG.warning('%s: %s=%s', row['comment'], key, desired)
        if changed:
            for _, role, row in self.routes():
                key = 'distance' if role == 'primary' else 'disabled'
                expected = ('1' if healthy else '3') if role == 'primary' else ('false' if healthy else 'true')
                if str(row.get(key)).lower() != expected:
                    raise RuntimeError('Route write verification failed')
        return changed


def run(args) -> None:
    targets = load_targets(args.targets)
    stamp = args.targets.stat().st_mtime_ns
    decision = Decision(args.failures, args.recovery_seconds)
    router = Router(args.isp) if args.apply else None
    def shutdown(signum, frame):
        raise KeyboardInterrupt

    for signum in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, shutdown)
    cycles = 0
    next_log = 0.0
    last_state = None
    reconciled = None
    next_reconcile = 0.0
    LOG.info('%s mode: %s targets, interval=%ss, recovery=%ss, coupled=True',
             'APPLY' if router else 'PROBE ONLY', len(targets), args.interval, args.recovery_seconds)
    try:
        while True:
            started = time.monotonic()
            try:
                new_stamp = args.targets.stat().st_mtime_ns
                if new_stamp != stamp:
                    # Commit only a fully valid replacement; an invalid file makes
                    # this cycle unknown and resets the recovery observation period.
                    replacement = load_targets(args.targets)
                    targets, stamp = replacement, new_stamp
                    decision.reset()
                    LOG.info('Reloaded %s targets', len(targets))
                samples = probe(targets, args.count)
                health = [score([t for t in targets if t.family == f], samples) for f in (4, 6)]
                now = time.monotonic()
                desired = decision.update(health, now)
                if router:
                    if router.api is None:
                        router.connect()
                        router.routes()  # Check selectors immediately, including during hold-down.
                    if not router.interface_up():
                        decision.reset()
                        desired = False  # Physical down is authoritative.
                    if desired is not None and (desired != reconciled or now >= next_reconcile):
                        router.reconcile(desired)
                        reconciled, next_reconcile = desired, now + 30
                state = tuple((h.bad, h.recoverable) for h in health), desired
                if args.json or now >= next_log or state != last_state:
                    payload = {'time': time.time(), 'cycle_seconds': round(now - started, 3),
                               'desired': desired, 'ipv4': vars(health[0]), 'ipv6': vars(health[1])}
                    if args.json:
                        payload['samples'] = samples
                        print(json.dumps(payload), flush=True)
                    else:
                        LOG.info('%s', json.dumps(payload))
                    next_log, last_state = now + 30, state
            except Exception as exc:
                LOG.error('Cycle unknown (%s): %s', type(exc).__name__, exc)
                decision.reset()
                if router:
                    router.close()
                    reconciled, next_reconcile = None, 0.0
                if args.cycles:
                    raise  # Finite validation runs must fail visibly.
            cycles += 1
            if args.cycles and cycles >= args.cycles:
                break
            time.sleep(max(0.05, args.interval - (time.monotonic() - started)))
    except KeyboardInterrupt:
        LOG.info('Stopping monitor')
    finally:
        if router:
            router.close()


def main(isp: str | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--isp', choices=ASNS, default=isp, required=isp is None)
    parser.add_argument('--targets', type=Path)
    parser.add_argument('--apply', action='store_true', help='Enable RouterOS reads/writes (default: probes only)')
    parser.add_argument('--cycles', type=int, default=0, help='Stop after N cycles; 0 runs continuously')
    parser.add_argument('--json', action='store_true', help='Emit each cycle and individual RTT samples')
    parser.add_argument('--interval', type=float, default=5)
    parser.add_argument('--count', type=int, default=3)
    parser.add_argument('--failures', type=int, default=2)
    parser.add_argument('--recovery-seconds', type=float, default=120)
    args = parser.parse_args()
    if (not math.isfinite(args.interval) or args.interval < 2 or args.count < 3 or args.count > 10
            or args.failures < 2 or not math.isfinite(args.recovery_seconds)
            or args.recovery_seconds < args.interval or args.cycles < 0):
        parser.error('Invalid timing/count parameters (interval>=2, count=3..10, failures>=2, recovery>=interval)')
    args.targets = args.targets or Path(__file__).with_name(f'targets_{args.isp}.csv')
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    run(args)


if __name__ == '__main__':
    main()
