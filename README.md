# Mikrotik Smart Jury Failover

A Python-based multi-WAN failover monitor for MikroTik RouterOS with weighted cohort scoring, noisy target quarantine, and smart recheck logic.

Read the full story: [Phasing Out pfSense: Building a Smarter Multi-WAN Failover for MikroTik](https://blog.milindhvijay.com/posts/mikrotik-multi-wan-failover/)

## What This Does

RouterOS's native `check-gateway=ping` failover is primitive—it pings a single IP and calls it a day. This script implements a **Smart Jury** system that:

- Monitors **56 targets** (28 IPv4 + 28 IPv6) across four reliability cohorts
- Weighs each cohort differently (Priority 2.0x, Anycast 1.5x, Regional 1.2x, ISP 0.8x)
- Quarantines noisy targets that fail 3 times in a row (90s timeout at 25% weight)
- Performs a **Fast Recheck** (5 random targets, 3 pings each) before triggering failover
- Uses hysteresis: instant failover but 2 consecutive healthy cycles + 30s hold-down for recovery
- Controls MikroTik routing distance directly via RouterOS API

## How It Works

1. **Monitor Loop**: Pings all targets every 2 seconds using asyncio for concurrency
2. **Reputation System**: Tracks bad streaks, quarantines flaky targets
3. **Cohort Scoring**: Calculates weighted health score across 4 cohorts
4. **Failover Decision**: Triggers when score < 0.58 AND ≥2 cohorts failing
5. **Fast Recheck**: Confirms failure isn't transient before acting
6. **API Control**: Updates route distance (1=primary, 10=failover) via RouterOS API

## Target Configuration

Targets are organized by cohort with calculated latency thresholds:

```python
{'ip': '8.8.8.8', 'latency': 20, 'name': 'Google', 'cohort': 'anycast'}
```

Latency thresholds use dynamic calculation:
- Under 10ms → round to 10ms
- Priority/Anycast → round to next 10ms
- Regional/ISP → round to next 5ms
- Timeout = threshold × 2.0
