"""Generate candidate-only CSVs and a comparison from completed surveys."""
import csv
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
all_results = {}
lines = ['# Additional WAN probe candidates', '',
         'Initial candidate survey. A subset was subsequently deployed after a longer soak; see [completion notes](../completion.md) and the per-ISP selection JSON files. Eligible CSVs below are historical screening results, not the active configuration.', '',
         'These are candidate inventories, not deployed configuration. Each address received 80 ICMP probes per ISP in four batches, with 1 second spacing and a 1 second timeout. The production timeout is 500 ms. Tests use the dedicated ISP monitor hosts and do not change router routes.', '',
         'A preliminary pass requires zero observed loss, p95 below 150 ms, and p95 no greater than max(30 ms, 1.5 × median). This is a short reachability/jitter screen, not evidence of long-term availability. CSV baselines round the observed median up to the next 5 ms (minimum 10 ms); measure across busy and quiet periods before adoption.', '',
         'Do not add every address as an independent vote. DNS aliases and multiple roots operated by Verisign are correlated; Caasify is a reseller listing, not necessarily a separate underlying network. Prefer one target per operator per family, preserving regional and ISP coverage. Confirm underlying origin ASNs before final balancing. More IPs increase probe traffic even when process count stays unchanged.', '']
def eligible(r):
    return r['loss'] == 0 and r['p95_ms'] < 150 and r['p95_ms'] <= max(30, 1.5*r['median_ms'])
for isp in ('bsnl', 'kv'):
    data = json.loads((HERE / (isp + '-results.json')).read_text())
    all_results[isp] = {r['ip']: r for r in data['targets']}
    passed = [r for r in data['targets'] if eligible(r)]
    lines += [f'## {isp.upper()}', '',
              f"{len(data['targets'])} new addresses tested; {len(passed)} passed the preliminary screen ({dict(Counter(r['family'] for r in passed))}, family 4/6). Window: {datetime.fromtimestamp(data['started'], timezone.utc).isoformat()} to {datetime.fromtimestamp(data['ended'], timezone.utc).isoformat()}.", '']
    with (HERE / (isp + '-eligible.csv')).open('w') as out:
        out.write('# CANDIDATES ONLY: not approved for production; short-window baselines\n')
        writer = csv.writer(out, lineterminator='\n')
        writer.writerow(['# IP', 'LatencyThreshold', 'Name', 'Cohort'])
        for r in passed:
            writer.writerow([r['ip'], max(10, math.ceil(r['median_ms']/5)*5), r['name'], r['cohort']])
    if data['resolution_failures']:
        lines += ['DNS resolution failures: ' + ', '.join(r['host'] for r in data['resolution_failures']), '']
lines += ['## Full comparison', '', 'RTTs are median / p95 in milliseconds. PASS means preliminary screen passed; HOLD needs further investigation; NO REPLY means no ICMP responses during this survey.', '', '| Candidate | IP | BSNL: RTT; loss; result | KV: RTT; loss; result |', '|---|---|---|---|']
def cell(r):
    if r is None:
        return 'Not tested'
    if not r['received']:
        return '-; 100%; NO REPLY'
    return f"{r['median_ms']:.1f} / {r['p95_ms']:.1f}; {r['loss']:.1%}; {'PASS' if eligible(r) else 'HOLD'}"
for ip in sorted(set(all_results['bsnl']) | set(all_results['kv'])):
    b, k = all_results['bsnl'].get(ip), all_results['kv'].get(ip)
    r = b or k
    lines.append(f"| [{r['name']}]({r['source']}) | `{ip}` | {cell(b)} | {cell(k)} |")
(HERE / 'README.md').write_text('\n'.join(lines)+'\n')
print('\n'.join(lines[:22]))
