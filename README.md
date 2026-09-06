# MikroTik Smart Jury Failover

One Python engine and two CSV configurations for the BSNL (`10.1.40.10`, AS9829) and KV (`10.1.40.11`, AS138754) monitors. Python 3.10+ and fping 5.x are required. RouterOS-api is needed only for router control.

Manual invocation defaults to **probe-only**: it does not connect to the router. The existing `monitor_bsnl.py` and `monitor_kv.py` entry points remain, but now require `--apply` to control routes. Do not replace files under a running production service without updating its invocation and dependencies.

```sh
python3 monitor_bsnl.py --cycles 12
python3 monitor_kv.py --cycles 12 --json
python3 -m unittest discover -s tests -v
```

Targets use `IP,LatencyBaselineMs,Name,Cohort`. Literal IPv4/IPv6 addresses are required; duplicates and malformed configurations are rejected. The CSV files were recovered from the deployed monitors, which were newer than the original repository scripts. BSNL has 78 active targets and KV has 79, including 21 and 19 additional targets respectively. Three persistently nonresponsive BSNL endpoints remain commented out. New targets were screened separately on each ISP, then checked in a 72-cycle soak using production probe settings. CSV changes reload atomically after complete validation; an invalid change suspends decisions and resets recovery evidence until corrected.

## Decisions and parameters

| Parameter | Default | Purpose |
| --- | --- | --- |
| Cycle start interval | 5 seconds | Fixed cadence; no overlapping cycles or catch-up bursts |
| Probes per target | 3 | 234 BSNL / 237 KV probes; one fping process for both families |
| Probe spacing / timeout | 500 / 500 ms | Bounded wait, including unreachable targets |
| Global packet spacing | 5 ms | Limits probe bursts |
| Target warning | Any loss, or RTT ≥ max(30 ms, 1.5 × baseline) | Half vote |
| Target failure | Loss ≥40%, or RTT ≥ max(50 ms, 2.5 × baseline) | Zero vote |
| WAN failure | Weighted score <0.58 AND ≥2 cohorts at or below 50% | Requires broad failure |
| Confirmation | 2 consecutive failing cycles | Normally about 6–12 seconds for a complete outage, excluding API delay |
| Recovery | Both families score ≥0.75, fewer than 2 failing cohorts, continuously for 120 seconds | Any marginal/bad/unknown cycle resets the timer |

With three probes, one lost packet is a warning and two are a failure. This is not an accurate estimator of low packet-loss percentages; the decision combines many targets and consecutive cycles. Cohort weights apply per target, so target counts also influence the score. Provider aliases are correlated votes; changing the target inventory needs revalidation.

IPv4 and IPv6 are **coupled**, preserving the deployed policy: either family can demote both; both must qualify for recovery. This deliberately sacrifices working IPv4 if IPv6 fails. There is no random confirmation subset, rolling history, EWMA, or self-adjusting quarantine. Consecutive checks provide confirmation without several overlapping delays; failures cannot be discounted away during a real outage.

A middle score preserves the current route state but cancels pending recovery. Local probe errors and API failures are **unknown**, never synthesised packet loss. Recovery also waits 120 seconds after process start or a monitoring interruption. RTT metrics include received replies only.

## Router contract

Each monitor manages exactly four static default routes, selected by unique comments:

- `AS9829 Primary` / `AS9829 v6 Primary`, with the equivalent AS138754 comments for KV.
- `AS9829 Failover for AS138754` / `AS9829 v6 Failover for AS138754`, reversed for KV.

Healthy: primary distance 1, its ISP's fallback route enabled. Failed: primary distance 3, its ISP's fallback route disabled. All four selectors, routing tables, ISP gateways and fallback distance 2 are validated before writing; changes are read back, and partial writes are retried after reconnection. Stable routes are reconciled every 30 seconds to repair fallback drift without reading four routes on every probe cycle. Health transitions reconcile immediately. An API exception closes the connection and resets observation evidence. A confirmed `running=false` WAN interface demotes both families immediately. Primary routes that are administratively disabled, dynamic, missing, duplicated, or not default routes are rejected.

The router must pin each monitor's IPv4 **and IPv6** traffic to its own WAN even after primary routes are demoted. A monitor that follows the other WAN will report false recovery. Source policy routing, mangle rule order, NAT, fallback distances/tables, and both-WANs-down behaviour must be checked on the actual router before enabling route control. Route updates across families are separate API operations, not an atomic transaction. There is no connection-tracking flush.

## Alpine deployment

The repository contains an OpenRC service template and credential-file example in `deploy/`. Keep credentials outside source control. Example dependency setup (run on the monitor):

```sh
apk add fping py3-pip
python3 -m venv /opt/smart-jury/venv
/opt/smart-jury/venv/bin/pip install -r /opt/smart-jury/requirements.txt
```

Install the engine and the relevant CSV under `/opt/smart-jury/`, credentials under `/etc/smart-jury/<isp>.env` with mode 0600, and `deploy/monitor.openrc` as `/etc/init.d/monitor-<isp>`. The template uses syslog so output does not disappear into `/dev/null`. Validate a probe-only run and the router contract before starting the service. Back up the old script, CSV, service and credentials first. The old executable and Python dependencies must also work for rollback; restoring an old script alone is insufficient after a Python upgrade.

`ROUTER_USER` and `ROUTER_PASS` are required for `--apply`; `ROUTER_HOST` defaults to `10.1.1.1`. `ROUTER_SSL=1` enables certificate-verified API-SSL. Credentials are not needed for probe-only runs. Avoid running two router-writing instances for the same ISP.

## References

- [fping options and machine-readable samples](https://fping.org/fping.8.html)
- [RouterOS-api library](https://github.com/socialwifi/RouterOS-api)
- [Original project story](https://blog.milindhvijay.com/posts/mikrotik-multi-wan-failover/)

The [live router audit](audit/router-audit.md) documents verified monitor pinning, current route compatibility, and remaining server IPv6/LTE/main-table limitations. Both production monitors are active; see [deployment notes](audit/deployment.md). Target selection and the final live checks are recorded in [completion notes](audit/completion.md).
