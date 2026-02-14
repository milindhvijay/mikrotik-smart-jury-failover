import time
import statistics
import routeros_api
from typing import Tuple, Optional, List, Dict
from collections import deque
import signal
import asyncio
import random
import subprocess
import re
import os

ROUTER_HOST = os.environ.get("ROUTER_HOST", "10.1.1.1")
ROUTER_USER = os.environ.get("ROUTER_USER", "")
ROUTER_PASS = os.environ.get("ROUTER_PASS", "")
if not ROUTER_PASS:
    raise ValueError("ROUTER_PASS environment variable must be set")

TARGETS_V4 = [
    {'ip': '218.248.112.1', 'latency': 15, 'name': 'DNS', 'cohort': 'isp'},
    {'ip': '8.8.8.8', 'latency': 20, 'name': 'Google', 'cohort': 'anycast'},
    {'ip': '142.251.43.46', 'latency': 20, 'name': 'Google-Priority', 'cohort': 'priority'},
    {'ip': '1.1.1.1', 'latency': 20, 'name': 'Cloudflare', 'cohort': 'anycast'},
    {'ip': '117.250.238.251', 'latency': 20, 'name': 'BSNL-MAA-Speedtest', 'cohort': 'isp'},
    {'ip': '117.205.67.171', 'latency': 35, 'name': 'BSNL-HYD-Speedtest', 'cohort': 'isp'},
    {'ip': '49.45.64.214', 'latency': 10, 'name': 'JIO-COK-Speedtest', 'cohort': 'regional'},
    {'ip': '152.52.30.118', 'latency': 25, 'name': 'AIRTEL-MAA-Speedtest', 'cohort': 'regional'},
    {'ip': '16.112.0.0', 'latency': 35, 'name': 'AWS-HYD', 'cohort': 'regional'},
    {'ip': '3.6.0.0', 'latency': 50, 'name': 'AWS-BOM', 'cohort': 'regional'},
    {'ip': '62.72.40.91', 'latency': 35, 'name': 'Contabo-BOM', 'cohort': 'regional'},
    {'ip': '148.113.1.33', 'latency': 45, 'name': 'OVH-BOM', 'cohort': 'regional'},
    {'ip': '172.232.96.28', 'latency': 20, 'name': 'Linode-MAA', 'cohort': 'regional'},
    {'ip': '172.105.33.31', 'latency': 40, 'name': 'Linode-BOM', 'cohort': 'regional'},
    {'ip': '9.9.9.9', 'latency': 40, 'name': 'Quad9', 'cohort': 'anycast'},
    {'ip': '208.67.222.222', 'latency': 30, 'name': 'OpenDNS', 'cohort': 'anycast'},
    {'ip': '65.20.66.100', 'latency': 35, 'name': 'Vultr-BOM', 'cohort': 'regional'},
    {'ip': '139.84.130.100', 'latency': 15, 'name': 'Vultr-BLR', 'cohort': 'regional'},
    {'ip': '151.101.0.204', 'latency': 20, 'name': 'Fastly', 'cohort': 'regional'},
    {'ip': '129.159.225.168', 'latency': 50, 'name': 'Oracle-BOM', 'cohort': 'regional'},
    {'ip': '139.162.23.4', 'latency': 55, 'name': 'Linode-SGP', 'cohort': 'regional'},
    {'ip': '45.90.28.0', 'latency': 30, 'name': 'NextDNS', 'cohort': 'anycast'},
    {'ip': '94.140.14.14', 'latency': 60, 'name': 'AdGuard', 'cohort': 'anycast'},
    {'ip': '193.0.14.129', 'latency': 60, 'name': 'K-root', 'cohort': 'anycast'},
    {'ip': '192.5.5.241', 'latency': 20, 'name': 'F-root', 'cohort': 'anycast'},
    {'ip': '199.7.83.42', 'latency': 60, 'name': 'L-root', 'cohort': 'anycast'},
    {'ip': '129.159.225.168', 'latency': 50, 'name': 'Oracle-HYD', 'cohort': 'regional'},
    {'ip': '5.223.7.195', 'latency': 55, 'name': 'Hetzner-SGP', 'cohort': 'regional'},
]

TARGETS_V6 = [
    {'ip': '2001:4490:3ffe:13::4', 'latency': 20, 'name': 'DNS', 'cohort': 'isp'},
    {'ip': '2001:4860:4860::8888', 'latency': 20, 'name': 'Google', 'cohort': 'anycast'},
    {'ip': '2404:6800:4007:834::200e', 'latency': 20, 'name': 'Google-Priority', 'cohort': 'priority'},
    {'ip': '2606:4700:4700::1111', 'latency': 20, 'name': 'Cloudflare', 'cohort': 'anycast'},
    {'ip': '2001:4490:dff4:e00::3', 'latency': 25, 'name': 'BSNL-MAA-Speedtest', 'cohort': 'isp'},
    {'ip': '2001:4490:dff0:600::3', 'latency': 30, 'name': 'BSNL-HYD-Speedtest', 'cohort': 'isp'},
    {'ip': '2405:200:1670:200:49:45:64:d2', 'latency': 10, 'name': 'JIO-COK-Speedtest', 'cohort': 'regional'},
    {'ip': '2404:a800:3a00:1::a3a', 'latency': 25, 'name': 'AIRTEL-MAA-Speedtest', 'cohort': 'regional'},
    {'ip': '2406:da1b:354:a600::ec2', 'latency': 30, 'name': 'AWS-HYD', 'cohort': 'regional'},
    {'ip': '2406:da1a:ddd:7400::ec2', 'latency': 45, 'name': 'AWS-BOM', 'cohort': 'regional'},
    {'ip': '2400:d321:5028:1091::', 'latency': 45, 'name': 'Contabo-BOM', 'cohort': 'regional'},
    {'ip': '2402:1f00:8300:121::', 'latency': 35, 'name': 'OVH-BOM', 'cohort': 'regional'},
    {'ip': '2600:3c08::f03c:93ff:fe7c:11f2', 'latency': 20, 'name': 'Linode-MAA', 'cohort': 'regional'},
    {'ip': '2400:8904::f03c:91ff:fea5:928b', 'latency': 35, 'name': 'Linode-BOM', 'cohort': 'regional'},
    {'ip': '2620:fe::fe', 'latency': 30, 'name': 'Quad9', 'cohort': 'anycast'},
    {'ip': '2620:119:35::35', 'latency': 30, 'name': 'OpenDNS', 'cohort': 'anycast'},
    {'ip': '2401:c080:2400:108b:5400:3ff:fef0:2934', 'latency': 30, 'name': 'Vultr-BOM', 'cohort': 'regional'},
    {'ip': '2401:c080:3000:2048:5400:4ff:fe1d:7185', 'latency': 20, 'name': 'Vultr-BLR', 'cohort': 'regional'},
    {'ip': '2a04:4e42::204', 'latency': 20, 'name': 'Fastly', 'cohort': 'regional'},
    {'ip': '2603:c021:4006:4501:7c42:2b2d:a083:df0a', 'latency': 45, 'name': 'Oracle-BOM', 'cohort': 'regional'},
    {'ip': '2400:8901::f03c:91ff:fe84:541d', 'latency': 50, 'name': 'Linode-SGP', 'cohort': 'regional'},
    {'ip': '2a07:a8c0::', 'latency': 20, 'name': 'NextDNS', 'cohort': 'anycast'},
    {'ip': '2a10:50c0::ad1:ff', 'latency': 50, 'name': 'AdGuard', 'cohort': 'anycast'},
    {'ip': '2001:7fd::1', 'latency': 30, 'name': 'K-root', 'cohort': 'anycast'},
    {'ip': '2001:500:2f::f', 'latency': 20, 'name': 'F-root', 'cohort': 'anycast'},
    {'ip': '2001:500:9f::42', 'latency': 50, 'name': 'L-root', 'cohort': 'anycast'},
    {'ip': '2603:c024:8001:1201:494b:14e8:2a00:f397', 'latency': 50, 'name': 'Oracle-HYD', 'cohort': 'regional'},
    {'ip': '2a01:4ff:2ef::fa57:1', 'latency': 55, 'name': 'Hetzner-SGP', 'cohort': 'regional'},
]

WAN_INTERFACE = "pppoe-as9829"

ROUTE_COMMENT_V4 = "AS9829 Primary"
ROUTE_COMMENT_V6 = "AS9829 v6 Primary"

NORMAL_DISTANCE = 1
FAILOVER_DISTANCE = 10

CHECK_INTERVAL = 2
PING_COUNT = 5
PING_TIMEOUT = 0.15
PING_DELAY = 0.15
LOSS_THRESHOLD = 25

CONSECUTIVE_FAILURES_REQUIRED = 2

STATUS_LOG_INTERVAL = 30

RECOVERY_HOLD_SECONDS = 30

# Weighted cohort scoring + noisy-target quarantine + fast recheck confirmation
COHORT_WEIGHTS = {
    'priority': 2.0,
    'anycast': 1.5,
    'regional': 1.2,
    'isp': 0.8,
}
COHORT_PASS_RATIO = 0.5
FAILOVER_SCORE_THRESHOLD = 0.58
MIN_FAILING_COHORTS = 2
NOISY_STREAK_THRESHOLD = 3
NOISY_QUARANTINE_SECONDS = 90
QUARANTINE_WEIGHT_FACTOR = 0.25
FAST_RECHECK_SAMPLES = 5
FAST_RECHECK_PINGS = 3
FAST_RECHECK_PASS_RATIO = 0.6

# Per-cohort timeout multipliers (all 2.0x for uniform timeout calculation)
TIMEOUT_MULTIPLIERS = {
    'priority': 2.0,
    'anycast': 2.0,
    'regional': 2.0,
    'isp': 2.0,
}

def calculate_latency_threshold(measured_ms: float, cohort: str) -> int:
    """Calculate latency threshold based on measured value and cohort rules.
    
    Rules:
    - If measured < 10ms: round up to next 10
    - If cohort is 'priority' or 'anycast': round up to next 10
    - If cohort is 'regional' or 'isp': round up to next 5
    """
    if measured_ms < 10:
        # Round up to next 10
        return 10
    
    if cohort in ('priority', 'anycast'):
        # Round up to next 10
        return int((measured_ms // 10) + 1) * 10
    else:
        # Round up to next 5 (regional, isp)
        return int((measured_ms // 5) + 1) * 5

def log(msg: str) -> None:
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}")

class HealthTracker:
    def __init__(self, required_failures: int):
        self.required_failures = required_failures
        self.history = deque(maxlen=required_failures)

    def update(self, is_healthy: bool) -> bool:
        self.history.append(is_healthy)
        if len(self.history) < self.required_failures:
            return False
        return len(set(self.history)) == 1

    def get_state(self) -> Optional[bool]:
        if len(self.history) < self.required_failures:
            return None
        if len(set(self.history)) == 1:
            return self.history[0]
        return None

    def clear(self) -> None:
        self.history.clear()


def infer_cohort(target_config: Dict) -> str:
    if 'cohort' in target_config:
        return target_config['cohort']
    name = target_config.get('name', '').upper()
    if 'GOOGLE' in name or 'CLOUDFLARE' in name:
        return 'anycast'
    if 'AWS' in name or 'AIRTEL' in name or 'JIO' in name:
        return 'regional'
    return 'isp'


def _ensure_reputation_entry(reputation_state: Dict[str, Dict[str, float]], target_ip: str) -> Dict[str, float]:
    if target_ip not in reputation_state:
        reputation_state[target_ip] = {
            'bad_streak': 0.0,
            'quarantined_until': 0.0,
        }
    return reputation_state[target_ip]


def _effective_target_weight(target_ip: str, cohort: str, is_healthy: bool,
                             reputation_state: Dict[str, Dict[str, float]], now_ts: float) -> float:
    base_weight = COHORT_WEIGHTS.get(cohort, 1.0)
    state = _ensure_reputation_entry(reputation_state, target_ip)
    if now_ts < state.get('quarantined_until', 0.0) and is_healthy:
        # Quarantine only discounts "healthy" votes; failures keep full weight
        return base_weight * QUARANTINE_WEIGHT_FACTOR
    return base_weight


def _update_reputation(target_ip: str, is_healthy: bool,
                       reputation_state: Dict[str, Dict[str, float]], now_ts: float) -> None:
    state = _ensure_reputation_entry(reputation_state, target_ip)

    if is_healthy:
        state['bad_streak'] = max(0.0, state.get('bad_streak', 0.0) - 1.0)
        return

    state['bad_streak'] = state.get('bad_streak', 0.0) + 1.0
    if state['bad_streak'] >= NOISY_STREAK_THRESHOLD:
        state['quarantined_until'] = max(state.get('quarantined_until', 0.0), now_ts + NOISY_QUARANTINE_SECONDS)
        state['bad_streak'] = 0.0

def _ping_subprocess(target_ip: str, timeout: float) -> Optional[float]:
    try:
        deadline = max(1, int(timeout + 1))
        cmd = ['ping', '-c', '1', '-W', str(deadline)]
        if ':' in target_ip:
            cmd.insert(1, '-6')
        cmd.append(target_ip)
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=deadline + 1
        )
        if result.returncode == 0:
            match = re.search(r'time[=<]\s*(\d+\.?\d*)\s*ms', result.stdout)
            if match:
                return float(match.group(1)) / 1000.0
        return None
    except Exception:
        return None

async def ping_target(target_ip: str, timeout: float) -> Tuple[bool, float]:
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, lambda: _ping_subprocess(target_ip, timeout)
        )
        
        if result is None:
            return False, 9999.0
        else:
            return True, result * 1000
    except Exception:
        return False, 9999.0

async def check_target_async(target_config: Dict, ping_count: int = PING_COUNT) -> Dict[str, object]:
    target_ip = target_config['ip']
    latency_threshold = target_config['latency']
    target_name = target_config['name']
    cohort = infer_cohort(target_config)
    multiplier = TIMEOUT_MULTIPLIERS.get(cohort, 2.0)
    timeout = max(PING_TIMEOUT, (latency_threshold / 1000.0) * multiplier)
    
    loss_count = 0
    latencies = []
    
    for i in range(ping_count):
        success, latency = await ping_target(target_ip, timeout)
        
        if success:
            latencies.append(latency)
        else:
            loss_count += 1
        
        if i < ping_count - 1:
            await asyncio.sleep(PING_DELAY)
    
    loss_pct = (loss_count / ping_count) * 100
    avg_latency = statistics.mean(latencies) if latencies else 9999.0
    
    is_healthy = loss_pct < LOSS_THRESHOLD and avg_latency < latency_threshold

    return {
        'ip': target_ip,
        'name': target_name,
        'cohort': infer_cohort(target_config),
        'healthy': is_healthy,
        'loss_pct': loss_pct,
        'avg_latency': avg_latency,
    }

async def _fast_recheck(targets: List[Dict]) -> Tuple[bool, str]:
    if not targets:
        return True, 'recheck=0/0'

    sample_size = min(FAST_RECHECK_SAMPLES, len(targets))
    sampled = random.sample(targets, sample_size)
    quick_results = await asyncio.gather(*[check_target_async(t, ping_count=FAST_RECHECK_PINGS) for t in sampled])

    pass_count = sum(1 for r in quick_results if bool(r['healthy']))
    pass_ratio = pass_count / sample_size
    return pass_ratio >= FAST_RECHECK_PASS_RATIO, f"recheck={pass_count}/{sample_size}"


async def check_all_targets(targets: List[Dict],
                            reputation_state: Dict[str, Dict[str, float]]) -> Tuple[bool, float, float, str]:
    results = await asyncio.gather(*[check_target_async(t) for t in targets])

    now_ts = time.time()
    total_weight = 0.0
    pass_weight = 0.0
    cohort_totals = {'priority': 0.0, 'isp': 0.0, 'regional': 0.0, 'anycast': 0.0}
    cohort_pass = {'priority': 0.0, 'isp': 0.0, 'regional': 0.0, 'anycast': 0.0}

    for r in results:
        target_ip = str(r['ip'])
        cohort = str(r['cohort'])
        is_healthy = bool(r['healthy'])

        weight = _effective_target_weight(target_ip, cohort, is_healthy, reputation_state, now_ts)
        _update_reputation(target_ip, is_healthy, reputation_state, now_ts)

        total_weight += weight
        cohort_totals[cohort] += weight
        if is_healthy:
            pass_weight += weight
            cohort_pass[cohort] += weight

    health_score = (pass_weight / total_weight) if total_weight > 0 else 0.0

    failing_cohorts = 0
    for cohort, cohort_total in cohort_totals.items():
        if cohort_total <= 0:
            continue
        if (cohort_pass[cohort] / cohort_total) < COHORT_PASS_RATIO:
            failing_cohorts += 1

    suspect_failure = health_score < FAILOVER_SCORE_THRESHOLD and failing_cohorts >= MIN_FAILING_COHORTS

    recheck_note = 'recheck=skip'
    if suspect_failure:
        recheck_passed, recheck_note = await _fast_recheck(targets)
        is_healthy = recheck_passed
    else:
        is_healthy = True
    
    avg_loss = statistics.mean(float(r['loss_pct']) for r in results)
    avg_latency = statistics.mean(float(r['avg_latency']) for r in results)
    
    target_details = ', '.join([f"{r['name']}={float(r['loss_pct']):.0f}%/{float(r['avg_latency']):.0f}ms" for r in results])
    quarantined = sum(1 for s in reputation_state.values() if now_ts < s.get('quarantined_until', 0.0))
    # Reset quarantines if >50% targets quarantined (system lost discrimination)
    if len(targets) > 0 and quarantined > len(targets) * 0.5:
        log(f"QUARANTINE CAP: {quarantined}/{len(targets)} targets quarantined, resetting all")
        for s in reputation_state.values():
            s['quarantined_until'] = 0.0
            s['bad_streak'] = 0.0
        quarantined = 0
    details = (
        f"score={health_score:.2f},cohorts_fail={failing_cohorts},quarantine={quarantined},{recheck_note}"
        f" | {target_details}"
    )
    
    return is_healthy, avg_loss, avg_latency, details

def update_route(api, comment: str, is_healthy: bool, metrics: Tuple[float, float],
                 recovery_start_times: dict) -> Tuple[bool, bool]:
    try:
        resource = api.get_resource('/ipv6/route' if ' v6 ' in comment or 'v6 Primary' in comment else '/ip/route')

        routes = resource.get(comment=comment)
        if not routes:
            log(f"CRITICAL: Route '{comment}' not found!")
            return False, False

        if len(routes) > 1:
            log(f"WARNING: Multiple routes match '{comment}', using first")

        route_id = routes[0]['id']
        current_dist = int(routes[0]['distance'])
        loss, lat = metrics

        target_dist = NORMAL_DISTANCE if is_healthy else FAILOVER_DISTANCE

        if current_dist != target_dist:
            if is_healthy:
                # Recovery hold-down prevents flapping back too quickly
                if comment not in recovery_start_times:
                    recovery_start_times[comment] = time.time()
                    log(f"RECOVERY PENDING [{comment}]: Waiting {RECOVERY_HOLD_SECONDS}s hold-down...")
                    return False, False
                elif time.time() - recovery_start_times[comment] < RECOVERY_HOLD_SECONDS:
                    return False, False
                else:
                    log(f"RECOVERY [{comment}]: Loss={loss:.1f}%, Latency={lat:.2f}ms -> Dist {target_dist}")
                    resource.set(id=route_id, distance=str(target_dist))
                    del recovery_start_times[comment]
                    return True, False
            else:
                log(f"FAILOVER [{comment}]: Loss={loss:.1f}%, Latency={lat:.2f}ms -> Dist {target_dist}")
                resource.set(id=route_id, distance=str(target_dist))
                if comment in recovery_start_times:
                    del recovery_start_times[comment]
                return True, True
        else:
            if comment in recovery_start_times:
                del recovery_start_times[comment]

        return False, False

    except Exception as e:
        log(f"API Error updating {comment}: {e}")
        return False, False

def is_interface_up(api, interface_name: str) -> bool:
    try:
        iface = api.get_resource('/interface')
        result = iface.get(name=interface_name)
        if not result:
            return False
        if result[0].get('running', 'false') != 'true':
            return False
        
        # PPPoE shows 'running=true' before IP is assigned
        v4_addr_resource = api.get_resource('/ip/address')
        v4_addrs = v4_addr_resource.get(interface=interface_name)
        if not v4_addrs:
            return False
        
        return True
    except Exception as e:
        log(f"Error checking interface status: {e}")
    return False


def disconnect_api(connection) -> None:
    if connection:
        try:
            connection.disconnect()
        except Exception:
            pass


def monitor() -> None:
    log("=" * 70)
    log("BSNL (AS9829) Dual-Stack Failover Monitor - NO FLUSH VARIANT")
    log("=" * 70)
    log(f"Router: {ROUTER_HOST}")
    log(f"WAN Interface: {WAN_INTERFACE}")
    log(f"IPv4 Targets: {[t['name'] for t in TARGETS_V4]}")
    log(f"IPv6 Targets: {[t['name'] for t in TARGETS_V6]}")
    log(f"Thresholds: Loss < {LOSS_THRESHOLD}%, Latency per-target")
    log(f"Check Interval: {CHECK_INTERVAL}s | Flap Prevention: {CONSECUTIVE_FAILURES_REQUIRED} failures")
    log(f"Recovery Hold-Down: {RECOVERY_HOLD_SECONDS}s")
    log(
        f"Smart Jury: score<{FAILOVER_SCORE_THRESHOLD}, "
        f"cohorts>={MIN_FAILING_COHORTS}, recheck {FAST_RECHECK_SAMPLES} targets"
    )
    log("=" * 70)

    connection = None
    api = None
    v4_tracker = HealthTracker(CONSECUTIVE_FAILURES_REQUIRED)
    v6_tracker = HealthTracker(CONSECUTIVE_FAILURES_REQUIRED)
    v4_reputation: Dict[str, Dict[str, float]] = {}
    v6_reputation: Dict[str, Dict[str, float]] = {}
    recovery_start_times = {}
    check_counter = 0
    shutdown_requested = False

    def handle_shutdown(signum, frame):
        nonlocal shutdown_requested
        shutdown_requested = True
        log(f"Shutdown signal received ({signum})")

    signal.signal(signal.SIGTERM, handle_shutdown)
    signal.signal(signal.SIGINT, handle_shutdown)

    while not shutdown_requested:
        try:
            if api is None:
                log("Connecting to RouterOS API...")
                connection = routeros_api.RouterOsApiPool(
                    ROUTER_HOST,
                    username=ROUTER_USER,
                    password=ROUTER_PASS,
                    plaintext_login=True
                )
                api = connection.get_api()
                log("API connection established successfully")
                v4_tracker.clear()
                v6_tracker.clear()
                v4_reputation.clear()
                v6_reputation.clear()
                recovery_start_times.clear()
                log("Health trackers reset (syncing with router state)")

            if not is_interface_up(api, WAN_INTERFACE):
                log(f"Interface {WAN_INTERFACE} is down - skipping (MikroTik handles failover)")
                v4_tracker.clear()
                v6_tracker.clear()
                v4_reputation.clear()
                v6_reputation.clear()
                recovery_start_times.clear()
                time.sleep(CHECK_INTERVAL)
                continue

            try:
                v4_healthy, v4_loss, v4_lat, v4_details = asyncio.run(check_all_targets(TARGETS_V4, v4_reputation))
                v4_stable = v4_tracker.update(v4_healthy)
            except Exception as e:
                log(f"IPv4 check error: {e}")
                v4_healthy, v4_loss, v4_lat, v4_details = False, 100.0, 9999.0, "ERROR"
                v4_stable = v4_tracker.update(False)

            try:
                v6_healthy, v6_loss, v6_lat, v6_details = asyncio.run(check_all_targets(TARGETS_V6, v6_reputation))
                v6_stable = v6_tracker.update(v6_healthy)
            except Exception as e:
                log(f"IPv6 check error: {e}")
                v6_healthy, v6_loss, v6_lat, v6_details = False, 100.0, 9999.0, "ERROR"
                v6_stable = v6_tracker.update(False)

            v4_changed = False
            v4_is_failover = False
            v6_changed = False
            v6_is_failover = False

            if v4_stable:
                stable_state = v4_tracker.get_state()
                if stable_state is not None:
                    v4_changed, v4_is_failover = update_route(api, ROUTE_COMMENT_V4, stable_state,
                                              (v4_loss, v4_lat), recovery_start_times)
                    if v4_changed:
                        log(f"IPv4 TARGET DETAILS: {v4_details}")

            if v6_stable:
                stable_state = v6_tracker.get_state()
                if stable_state is not None:
                    v6_changed, v6_is_failover = update_route(api, ROUTE_COMMENT_V6, stable_state,
                                              (v6_loss, v6_lat), recovery_start_times)
                    if v6_changed:
                        log(f"IPv6 TARGET DETAILS: {v6_details}")

            check_counter += 1
            if check_counter % STATUS_LOG_INTERVAL == 0:
                v4_status = 'OK' if v4_healthy else 'FAIL'
                v6_status = 'OK' if v6_healthy else 'FAIL'
                pending = len(recovery_start_times)
                log(f"Status: IPv4 {v4_status} ({v4_details}) | "
                    f"IPv6 {v6_status} ({v6_details})"
                    f"{f' | {pending} recovery pending' if pending else ''}")

        except KeyboardInterrupt:
            log("Shutting down monitor (Ctrl+C received)")
            break
        except Exception as e:
            log(f"Monitor loop error: {e}")
            disconnect_api(connection)
            connection = None
            api = None
            time.sleep(5)
            continue

        time.sleep(CHECK_INTERVAL)

    log("Performing graceful shutdown...")
    disconnect_api(connection)
    log("Monitor stopped.")


if __name__ == "__main__":
    monitor()
