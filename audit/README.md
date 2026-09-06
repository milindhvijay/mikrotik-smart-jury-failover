# Monitor audit - 2026-09-06

## Status

The implementation has since been activated under `/opt/smart-jury` on both hosts; see [deployment.md](deployment.md). The measurements below describe the initial audit and shadow runs. During the initial audit, no production monitor was restarted and no routes were changed. The subsequent authorised read-only router audit is documented in [router-audit.md](router-audit.md). `fping 5.5` was installed on both hosts; a temporary virtual environment with RouterOS-api 0.21.0 was created for candidate testing. Read-only API authentication and route checks have now passed from both hosts; production activation is recorded separately.

## Findings

- The repository scripts were older than deployment. Deployed monitors use 60 CSV targets each, rolling history, EWMA, five failure cycles, coupled IPv4/IPv6 decisions, and a 3,600-second recovery hold. Their source snapshots were inspected with the password assignment redacted; no credentials are included here.
- Deployed ping code starts a process per packet, roughly 300 per complete cycle before rechecks, serialises the two families, and limits concurrent target checks to eight. A nominal five-second interval is a sleep after the work, not a five-second sampling cadence. Sixty packets of history are not sixty seconds of history.
- A recovery timer can survive intermittent bad/marginal samples because route updates run only after stable decisions. An API reconnection also preserves the old timer without proving continuous health.
- Failed fallback writes are swallowed, and a subsequent primary route already at the desired distance can prevent retry. Interface API errors are swallowed as interface-down results, potentially preventing reconnect.
- Quarantine discounts good votes while retaining full failed votes; this penalises recovering targets. Overlapping smoothing, confirmation and recheck layers make failure latency difficult to predict.
- Both live monitor processes run deleted Python 3.12 executables after an OS upgrade. Current system Python is 3.14.5 on BSNL and 3.14.7 on KV; neither system interpreter can import `routeros_api`. A restart with the existing service setup is therefore broken.
- Both processes direct stdout and stderr to `/dev/null`; a running PID is not proof of current API connectivity or successful routing decisions.

## Measurements

Both live CSV inventories contain 60 targets. Full probe-only shadow results are summarised in `bsnl-shadow.json` and `kv-shadow.json`, including per-target packet loss, median RTT and p95 RTT. The first shadow implementation used asyncio only to supervise one fping process; the final engine removes asyncio and uses the same probe command and scoring, with an additional fix making an exactly 50% cohort score count as failing. This prevents widespread partial packet loss from escaping the cohort gate.

| Measurement | BSNL | KV |
| --- | --- | --- |
| Initial shadow cycles | 36 over ~175 seconds | 36 over ~175 seconds |
| Full probe duration | 1.70–1.75 seconds | 1.35–1.76 seconds |
| IPv4 score range | 0.797–0.947 | 0.974–1.000 |
| IPv6 score range | 0.835–0.871 | 0.983–1.000 |
| Bad cycles | 0 | 0 |
| Subsequent synchronous shadow | 12 cycles, no failures | 12 cycles, no failures |
| Synchronous benchmark | 0.143 CPU-seconds / 26.77 elapsed seconds | 0.141 CPU-seconds / 26.41 elapsed seconds |
| Benchmark peak process RSS | 15,012 KiB | 15,192 KiB |

The benchmark ran six cycles and includes startup and child CPU time. It excludes RouterOS API activity. Peak RSS is the OS child resource-accounting maximum, not total simultaneous container memory. These figures are not a controlled CPU comparison against the old process or a guarantee under load. The structural change is 300 to one probe process per cycle (99.7% fewer) and 300 to 180 requests (40% fewer per cycle); the faster cadence means those percentages do not directly describe traffic per second. The new default sends about 36 ICMP requests/second, roughly 4 KB/second at the IP layer, excluding replies.

The following BSNL targets lost all 108 packets during the initial shadow window:

- `117.250.238.251` - BSNL MAA speed test, IPv4.
- `2001:4490:3ffe:13::24` - BSNL DNS, IPv6.
- `2001:4490:dff4:e00::3` - BSNL MAA speed test, IPv6.

No KV target was completely nonresponsive. BSNL's K-root IPv6 p95 was around 68 ms against a 30 ms baseline; Misaka IPv4 was around 101 ms against 60 ms. These merit review, but existing target baselines were retained: a short sample without confirming WAN pinning is insufficient reason to rebaseline or remove ISP targets. The candidate's 30/50 ms absolute latency floors and 1.5×/2.5× factors avoid the repository version's near-baseline failure trigger.

## Initial validation and activation checklist

18 deterministic tests pass locally and on both monitor hosts. They cover partial and complete loss, confirmation, continuous recovery, unknown samples, malformed probe output, probe failures, duplicate or invalid route selectors, API exceptions, idempotent writes, and retry after partial route updates. Additional finite probe runs exercised the final code on both real hosts. Route tests use fake APIs; they do not prove actual MikroTik integration. The OpenRC template has a shell syntax check but has not replaced the production services.

The following was the initial checklist. Deployment and the controlled live checks are now recorded in [completion.md](completion.md):

1. Read RouterOS version, WAN status, four route selectors per ISP, distances, gateways, routing tables and active states.
2. Inspect IPv4/IPv6 policy rules, mangle ordering, source addresses and NAT to prove probes stay on their own ISP when routes demote. Normal successful pings do not establish this.
3. Review both-WANs-down behaviour, route ownership, and any competing scheduler/netwatch/controller.
4. Install the tested dependency environment and logging service persistently, preserve rollback files, and activate one monitor at a time after integration checks.
5. Arrange a controlled failover/recovery test before claiming end-to-end operation. Changing production routes or deliberately interrupting WAN traffic requires the agreed router scope.
