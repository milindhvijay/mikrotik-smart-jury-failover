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

## Quick Start

### Prerequisites

- MikroTik RouterOS 7.x device
- Python 3.8+
- `routeros_api` library: `pip install routeros_api`
- API user configured on your MikroTik with write access to `/ip/route` and `/ipv6/route`

### Configuration

Set environment variables for your router connection:

```bash
export ROUTER_HOST="192.168.88.1"
export ROUTER_USER="api-monitor"
export ROUTER_PASS="your-secure-password"
```

Or create a `.env` file and use `python-dotenv`.

### Running

```bash
# For BSNL/AS9829 connection
python3 monitor_bsnl_noflush_clean_github.py

# For Kerala Vision/AS138754 connection
python3 monitor_kv_noflush_clean_github.py
```

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

## Files

- `monitor_bsnl_noflush_clean_github.py` — BSNL/AS9829 monitor
- `monitor_kv_noflush_clean_github.py` — Kerala Vision/AS138754 monitor
- `check_latency_bsnl.py` / `check_latency_kv.py` — Latency measurement utilities
- `smart-jury-flowchart.mmd` — Mermaid diagram of the decision logic

## RouterOS Setup

The RouterOS side needs:

1. **API-SSL enabled**: `/ip service enable api-ssl`
2. **API user** with password and `write` policy
3. **Routing rules** to direct traffic via specific routing tables
4. **Routes** with comments matching `ROUTE_COMMENT_V4` and `ROUTE_COMMENT_V6`

See the blog post for complete configuration details.

## License

MIT License — feel free to adapt for your own homelab or production use.

## Acknowledgements

Built with guidance from [Anurag Bhatia](https://anuragbhatia.com/) who has been running production network automation far longer. His Prometheus-based approach is the blueprint for doing this at scale:
- [Event driven automation with Prometheus](https://anuragbhatia.com/post/2025/01/event-driven-automation-with-prometheus/)
- [Distributed latency monitoring](https://anuragbhatia.com/post/2023/07/distributed-latency-monitoring/)

