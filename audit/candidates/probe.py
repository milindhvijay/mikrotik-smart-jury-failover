"""Read-only candidate survey; never updates the active monitor or router."""
import ipaddress
import json
import socket
import statistics
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
records = json.loads((HERE / 'manifest.json').read_text())
existing = set()
for path in Path('/opt/smart-jury').glob('targets_*.csv'):
    for line in path.read_text().splitlines():
        try:
            existing.add(str(ipaddress.ip_address(line.split(',')[0])))
        except ValueError:
            pass
resolved = []
for record in records:
    if 'ip' in record:
        resolved.append(record)
    else:
        try:
            addresses = sorted({str(ipaddress.ip_address(a[4][0])) for a in socket.getaddrinfo(record['host'], 443, type=socket.SOCK_STREAM)})
            resolved.extend(dict(record, ip=ip) for ip in addresses)
        except OSError as error:
            record['resolution_error'] = str(error)
seen = set()
targets = []
for record in resolved:
    ip = str(ipaddress.ip_address(record['ip']))
    if ip in seen or ip in existing or not ipaddress.ip_address(ip).is_global:
        continue
    seen.add(ip)
    targets.append(dict(record, ip=ip, family=ipaddress.ip_address(ip).version))
samples = {r['ip']: [] for r in targets}
started = time.time()
rounds = []
for run in range(4):
    result = subprocess.run(['fping', '-q', '-C', '20', '-p', '1000', '-t', '1000', '-i', '10', *samples], capture_output=True, text=True, timeout=100)
    if result.returncode not in (0, 1):
        raise RuntimeError(result.stderr)
    got = set()
    for line in (result.stdout + '\n' + result.stderr).splitlines():
        address, sep, values = line.partition(' :')
        if not sep:
            continue
        try:
            address = str(ipaddress.ip_address(address.strip()))
        except ValueError:
            continue
        if address not in samples:
            continue
        values = values.split()
        if len(values) != 20:
            raise RuntimeError('Incomplete sample line: ' + line)
        samples[address].extend(None if v == '-' else float(v) for v in values)
        got.add(address)
    if got != set(samples):
        raise RuntimeError('Missing fping results: ' + str(set(samples) - got))
    rounds.append({'round': run + 1, 'completed': time.time()})
    if run < 3:
        time.sleep(10)
for record in targets:
    values = samples[record['ip']]
    good = sorted(v for v in values if v is not None)
    record.update(sent=len(values), received=len(good), loss=1-len(good)/len(values), samples_ms=values,
                  median_ms=statistics.median(good) if good else None,
                  p95_ms=good[int((len(good)-1)*.95)] if good else None,
                  max_ms=max(good) if good else None)
(HERE / 'results.json').write_text(json.dumps({'hostname': socket.gethostname(), 'started': started, 'ended': time.time(), 'rounds': rounds, 'resolution_failures': [r for r in records if 'resolution_error' in r], 'targets': targets}, indent=2))
print('Completed', len(targets), 'candidates', flush=True)
