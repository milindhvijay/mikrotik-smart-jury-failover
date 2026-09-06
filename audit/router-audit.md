# Read-only MikroTik audit - 2026-09-06

Historical inspection. The server IPv6 policy was subsequently corrected and the monitors activated. See [completion.md](completion.md) for the final live checks.

The user authorised use of the monitors' existing API credentials for a read-only audit. Both hosts authenticated successfully. No router settings, routes, NAT rules, interfaces, or production services were changed. The account was used only for resource reads; its write permission was not exercised.

## Core integration checks

Router: RB5009UG+S+, RouterOS **7.24.2 stable**, uptime approximately 2 days 16 hours at inspection. Both `pppoe-as9829` and `pppoe-as138754` were running. Both DHCPv6 clients were bound.

| Monitor | Observed source | First applicable Internet policy table |
| --- | --- | --- |
| BSNL IPv4 | 10.1.40.10 | route-as9829-nofailover |
| BSNL IPv6 | 204::be24:11ff:fed7:5d96 | v6-route-as9829-nofailover |
| KV IPv4 | 10.1.40.11 | route-as138754-nofailover |
| KV IPv6 | 204::be24:11ff:fe06:69fa | v6-route-as138754-nofailover |

These enabled host-specific rules precede the general Proxmox subnet rules. The Linux-selected IPv6 source on each monitor matches the router's /128 selector. All four tables contain only the matching ISP default and a distance-254 blackhole default. The rules use `lookup-only-in-table`. No active mangle rule changes routing marks; mangle rules adjust TCP MSS. FastTrack is limited to internal-to-internal traffic, so these Internet ICMP probes are not candidates for FastTrack.

**Configuration conclusion:** managed primary-route demotion does not alter the monitor-only tables. An ISP outage therefore cannot cause these monitor probes to use the other ISP through the inspected rules. This is a configuration analysis, not an induced-outage packet capture. It assumes the observed monitor source addresses and routing configuration remain unchanged. [MikroTik documents lookup-only-in-table and the precedence of mangle routing marks](https://help.mikrotik.com/docs/spaces/ROS/pages/59965508/Policy%20Routing).

All eight managed routes are unique static defaults with the expected PPPoE gateway and table. Primaries are at distance 1; cross-ISP fallbacks are enabled at distance 2. The candidate's healthy-state reconciliation requires **zero writes** against this snapshot. The candidate now also validates table, gateway and fallback distance before it may write, preventing an accidentally reused comment from targeting a monitor-only route.

Current IPv4 Netmap/EIM mappings match the addresses assigned to the respective WANs. IPv6 Netmap66 addresses match the respective WAN IPv6 addresses and delegated prefixes. Each WAN has the expected interface-list membership. Monitor source subnets are included in the internal NAT address lists.

## Policy limitations found

1. **Server IPv6 bypassed failover (subsequently corrected).** The `201::/64` rule has comment `Server v6 -> AS138754` but selects `v6-route-as9829-nofailover`. Except for earlier host-specific rules, those servers stay on BSNL and do not use the managed failover table. This may be intentional, but the comment is misleading. If KV with BSNL backup is desired, the target table would be `v6-route-as138754`; no change was made.
2. **LTE does not beat a degraded-but-up primary.** Both IPv6 managed tables have an LTE route at distance 4. A primary demoted to 3 still wins if its PPPoE session remains up and no lower-distance usable alternative exists. LTE was not running, and both LTE routes were inactive. The candidate retains the deployed 1/3 distances. Making LTE a usable third option requires a separate policy decision and verification of its connectivity.
3. **Main-table and VPN-underlay traffic are outside monitor control.** The router's main defaults are dynamic PPPoE/DHCP routes. AirVPN endpoint /32 routes have their own gateway checks. Neither is one of the eight managed routes. Client policy tables can fail over on detected degradation while router-originated traffic or VPN underlay routes continue preferring a WAN whose PPPoE session remains up.
4. **Both ISPs degraded is best-effort behaviour.** If both monitors demote their own primaries and disable their own fallback entries, each managed table retains its own primary at distance 3. This avoids declaring all routes unusable but does not provide service through a healthy third WAN. If both sessions physically fail, their interface gateways become unavailable.
5. **Existing connections are not migrated.** NAT state remains tied to the original connection. New connections can use the alternate WAN, but existing sessions may need to reconnect; no conntrack flush is planned.

A daily BSNL PPPoE reset is enabled at 02:30 router time. PPP profiles invoke NAT-update scripts; no Netwatch entries or inspected scripts that directly modify routes were found. The NAT scripts contain a suspicious extra closing brace at the end, but RouterOS reports `invalid=false` and recent `last-started` values. No matching error was present in the available log buffer. This read-only audit does not establish successful execution after every renewal; do not treat the script formatting alone as a confirmed failure or auto-edit it. Current NAT mappings were correct.

## Verification

- Read-only API authentication and interface/route contract validation passed from **both** monitor hosts.
- 21 deterministic tests passed locally and on both monitors after adding table/gateway/distance checks.
- Two additional detached snapshot tests bring the suite to **23**, passing locally and on both monitor hosts. They verify zero healthy-state drift and simulated failover/recovery for both ISPs, preserving monitor-only and LTE routes.
- `router-routes.json` is the reduced read-only routing snapshot used by those tests. All simulated mutations happen only to deep-copied Python dictionaries; no API write method was invoked.
- Production monitors and routes remain unchanged. Successful route writes and user traffic during an actual failover/recovery are still unverified.

## Activation plan (subsequently executed; see deployment.md)

Install the shared engine and the existing 60-target CSV inventory per ISP under `/opt/smart-jury`, use an isolated environment with RouterOS-api 0.21.0 and fping 5.5, and enable syslog through the prepared OpenRC template. Preserve the old scripts, CSVs and service definitions first, and prepare a rollback service using a working Python/API environment rather than the deleted system interpreter.

Activate **one monitor at a time**. The service uses coupled IPv4/IPv6 decisions, five-second cycle starts, two failing cycles, 120 continuously healthy seconds for recovery, and the existing primary distances 1/3 and backup distance 2. It can modify only the validated primary/fallback routes for its own ISP. Observe its logs and actual route state before proceeding to the second host. Keep the server IPv6 rule, LTE priorities, main-table defaults and VPN routes unchanged until their intended policies are decided.

Activation enabled router writes under the user’s subsequent approval; results are in [deployment.md](deployment.md). A deliberate outage test also needs an agreed window/scope. No claim of end-to-end failover success should precede that test.
