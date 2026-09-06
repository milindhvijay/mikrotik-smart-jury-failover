"""Compact a finite probe run without discarding target quality statistics."""
import json
import statistics
import sys
from pathlib import Path

root = Path(sys.argv[1])
rows = [json.loads(line) for line in (root / 'soak.jsonl').read_text().splitlines()]
assert len(rows) == 72, 'Wait for the complete six-minute soak'
result = {'cycles': len(rows), 'started': rows[0]['time'], 'ended': rows[-1]['time'],
          'health': [{k: v for k, v in row.items() if k != 'samples'} for row in rows], 'targets': {}}
for ip in rows[0]['samples']:
    values = [v for row in rows for v in row['samples'][ip]]
    good = sorted(v for v in values if v is not None)
    result['targets'][ip] = {'sent': len(values), 'received': len(good),
        'loss': 1-len(good)/len(values), 'median_ms': statistics.median(good) if good else None,
        'p95_ms': good[int(.95*(len(good)-1))] if good else None,
        'max_ms': max(good) if good else None}
(root / 'soak-summary.json').write_text(json.dumps(result, indent=2)+'\n')
print('Summarised', len(rows), 'cycles')
