# Production activation - 2026-09-06

Activation was authorised after the read-only router audit. The user corrected the server IPv6 rule in WinBox; a subsequent API read confirmed that the enabled `201::/64` rule selects `v6-route-as138754` with `lookup-only-in-table`.

Both hosts have persistent installations under `/opt/smart-jury`, an isolated Python environment with RouterOS-api 0.21.0, their existing 60-target CSV inventory, and root-only credentials under `/etc/smart-jury/<isp>.env`.

Backups were created before modifying service definitions:

- BSNL: `/root/jury-backups/20260906-080848`
- KV: `/root/jury-backups/20260906-080849`

Each backup includes the original script, CSV and OpenRC service, plus `rollback.openrc`, adjusted to use the working Python environment and backed-up script/CSV. Both legacy scripts passed import checks under the replacement interpreter. Restore using `deploy/rollback.sh` on the corresponding host. Restoring the old service unchanged would reuse the broken system dependency setup.

The service command is `/opt/smart-jury/venv/bin/python -u /opt/smart-jury/jury_monitor.py --isp <isp> --apply`. OpenRC supervises it and sends logs to syslog under `monitor-bsnl` or `monitor-kv`. Both configured services remain in the default runlevel.

## Activation observations

- BSNL service activated at 08:09:27 UTC. Its API connected successfully and syslog received startup/health messages.
- BSNL's three persistently nonresponsive targets were commented out of the active CSV at 08:12:02 UTC, leaving 57 targets. The files under `/root` and the backup retain the original inventory. Live checks had confirmed repeated total loss on these endpoints while the rest of the link worked. Leaving two dead ISP IPv6 votes in the jury unnecessarily blocked recovery when another cohort became marginal.
- The BSNL service hot-reloaded the revised CSV without restarting and completed its 120-second healthy observation period at 08:14:04 UTC. No route distance change was needed.
- KV service activated at 08:14:16 UTC with all 60 original targets. API connection and syslog output were verified immediately.
- Same-value API writes and readback succeeded for all eight managed routes, without changing any distance or disabled state. These checks establish the API account's ability to execute the required setters, not behaviour during an outage.
- Both old monitor processes were stopped before their replacements started. Both OpenRC services remain enabled in the default runlevel.
- The BSNL active process used approximately 20.3 MiB RSS and one thread. A 149-second sample measured ~0.28% of one core, including waited-for probe children. These production values supersede the lower probe-only memory estimate.

A forced outage was not induced. Failure transitions are covered by deterministic and router-snapshot simulation tests; an actual traffic failover/recovery test remains a separate, potentially disruptive validation step.


## Final checks

At approximately 08:17 UTC, both services were running without logged errors. Both WAN interfaces were up. All four managed primary routes were active at distance 1, and all four cross-ISP backups were enabled at distance 2. KV completed its continuous healthy observation period; BSNL had completed one earlier, then correctly cancelled renewed recovery eligibility during a brief marginal IPv6 sample while retaining its already-normal route state.

The latest logged health samples showed both families healthy on both hosts. Production CPU samples including probe children measured **0.274%** of one core for BSNL over 387 seconds and **0.311%** for KV over 116 seconds. Resident memory was **20,848 KiB** and **20,936 KiB**, respectively, with **one Python thread each**. Supervisor/logger processes add a small amount of memory outside those figures. Detailed observations are in `bsnl-deployment.json` and `kv-deployment.json`.

Both installed engines match local SHA-256 `a08f72deac8ec7609a30365231896c3118e4acbba0c14ad3a512618c80bc88f3`. The 23-test suite passed. Active inventories are 57 BSNL and 60 KV targets; each uses one fping process per cycle. Route/NAT/ISP behaviour outside the eight managed routes was preserved.

For service logs on either host:

```sh
tail -f /var/log/messages
```

For rollback on the affected host:

```sh
/opt/smart-jury/rollback.sh bsnl
# Use kv instead on 10.1.40.11.
```

The rollback procedure was prepared and its legacy imports checked, but was not invoked. After a future major Python upgrade, rebuild the virtual environment and validate imports before restarting the service.

## Subsequent completion

The inventories were expanded and controlled live failover/recovery checks passed on both ISPs. See [completion.md](completion.md) for the final counts, measurements, backups and evidence. Earlier pending-test statements above describe the initial activation only.
