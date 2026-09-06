# Completion - 6 September 2026

The shared engine and expanded inventories are deployed on both monitors. Controlled live probe faults exercised the running services, actual RouterOS route changes and forwarded HTTPS traffic in both IP families.

## Deployed targets

| ISP | Previous | Added | Active | IPv4 / IPv6 |
| --- | ---: | ---: | ---: | --- |
| BSNL | 57 | 21 | 78 | 41 / 37 |
| KV | 60 | 19 | 79 | 41 / 38 |

An initial survey tested 63 additional addresses from each ISP, 80 packets per address. A later 72-cycle soak tested the proposed complete inventories at production settings: three probes per target, 500 ms spacing and timeout, five-second cycle starts. Every soak cycle was recoverable on both families for both ISPs. Each prospective target received another 216 probes.

New targets with observed loss or excessive jitter were excluded. `139.84.138.108` passed the initial survey but lost all 216 soak probes on both ISPs, so it was not deployed. New baselines use the greater median from the two windows, rounded up to 5 ms with a 10 ms minimum. This avoids tuning to one unusually fast sample; it is not a long-term availability guarantee.

Provider selection avoids adding the alternate Google/Cloudflare DNS aliases or both Verisign roots. The additions include distinct DNS/root operators, E2E Noida, DigitalOcean Singapore and Hetzner Singapore. Akamai Chennai and Singapore additions extend regional coverage but share AS63949 with existing Akamai targets; the additional Vultr Singapore endpoint also shares an existing operator. Origin-AS lookups are recorded in `candidates/*-origins.json` using the [RIPEstat Network Info API](https://stat.ripe.net/docs/data-api/api-endpoints/network-info). ASN diversity is not proof of disjoint upstream paths.

Final selections and rejected entries are in `candidates/bsnl-selection.json` and `candidates/kv-selection.json`. The original eligible CSVs remain historical candidate lists. The authoritative deployed inventories are the repository-root CSVs.

## Live failover and recovery

| Fault | Forwarded traffic during fault | Failover observed | Recovery after clearing |
| --- | --- | ---: | ---: |
| BSNL IPv4 echo requests blocked | IPv4 and IPv6 via KV | 9.89 s | 127.17 s |
| KV IPv6 echo requests blocked | IPv4 and IPv6 via BSNL | 10.05 s | 127.28 s |

Tests ran sequentially. A temporary RouterOS raw rule dropped only the tested monitor’s IPv4 echo requests (BSNL) or IPv6 echo requests (KV). The other family remained available, proving the coupled decision policy in each direction. A separately verified router scheduler could clear the fault after 45 seconds if the test process stopped.

Two temporary destination-specific policy rules sent HTTPS requests from the monitor through its managed client tables. Their Cloudflare endpoints were excluded from the active probe inventory. TLS-verified `/cdn-cgi/trace` requests showed both public exit addresses change to the other ISP and then return. Route readback independently confirmed the alternate PPPoE gateway became active. These were forwarded, NATed connections through the router, not just simulated route dictionaries or router-originated pings.

The live monitor performed all eight demotion/recovery setters per ISP. Primary distances changed 1 → 3 → 1; the tested ISP’s fallback entries changed enabled → disabled → enabled. The healthy peer stayed normal. The monitor-only and LTE route configurations were unchanged. Temporary raw rules, policy rules and schedulers were removed and their absence verified from both hosts.

This tests a reachable PPP session with loss of upstream probes. It does not test physical cable removal, PPP re-authentication or migration of existing NAT sessions. Main-table, VPN-underlay and LTE policy remain outside the monitors’ managed route contract.

## Final verification

- Both OpenRC services are running and enabled in the default runlevel. CSV reloads required no restart.
- Both PPPoE interfaces are running. All four primary routes are active at distance 1; all four cross-ISP backups are enabled at distance 2.
- Each monitor’s IPv4 and IPv6 source rules still use its own `nofailover` table with `lookup-only-in-table`.
- The enabled server `201::/64` rule uses `v6-route-as138754`.
- Local and installed engine/CSV SHA-256 digests match.
- All 25 tests pass locally and on both monitors, including real-inventory cohort-failure checks and detached router snapshot tests.

| ISP | RSS | Threads | CPU, one core | Requests per second |
| --- | ---: | ---: | ---: | ---: |
| BSNL | 20.39 MiB | 1 | 0.367% | 46.8 |
| KV | 20.52 MiB | 1 | 0.367% | 47.4 |

CPU samples cover 60 seconds and include reaped fping children. RSS is the Python process only; supervisor, logger and the transient fping process are additional. Each cycle still starts only one fping process. Additional targets increase packet volume; no persistent workers or polling processes were added.

## Evidence and rollback

Per-host completion JSON contains activation times, checksums, final route state, public exit observations, resource samples, test output and production logs. These supersede the earlier audit’s pending activation and live-test notes.

- BSNL target backup: `/root/jury-backups/targets-20260906-132900/targets_bsnl.csv`. Restore via a validated temporary CSV and atomic rename to `/opt/smart-jury/targets_bsnl.csv`; the service reloads automatically.
- KV target backup: `/root/jury-backups/targets-20260906-132918/targets_kv.csv`. Restore via a validated temporary CSV and atomic rename to `/opt/smart-jury/targets_kv.csv`; the service reloads automatically.

The earlier full service rollback remains available through `/opt/smart-jury/rollback.sh <isp>`. It was prepared and import-checked, not executed.
