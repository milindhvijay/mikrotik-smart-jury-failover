"""Sample the running monitor and reaped probe children for one minute."""
import json
import os
import re
import sys
import time
from pathlib import Path


def sample():
    matches = []
    for path in Path('/proc').glob('[0-9]*/cmdline'):
        try:
            args = path.read_bytes().split(b'\0')
            if not args[0].rsplit(b'/', 1)[-1].startswith(b'python'):
                continue
            if b'/opt/smart-jury/jury_monitor.py' not in args or b'--apply' not in args:
                continue
            process = path.parent
            stat = (process/'stat').read_text().rsplit(')', 1)[1].split()
            status = (process/'status').read_text()
            matches.append({'pid': int(process.name), 'ticks': sum(int(x) for x in stat[11:15]),
                            'rss_kib': int(re.search(r'VmRSS:\s+(\d+)', status)[1]),
                            'threads': int(re.search(r'Threads:\s+(\d+)', status)[1]),
                            'monotonic': time.monotonic()})
        except FileNotFoundError:
            continue
    assert len(matches) == 1, f'Expected one applying monitor, found {len(matches)}'
    return matches[0]


before = sample()
time.sleep(60)
after = sample()
assert before['pid'] == after['pid'], 'Monitor restarted during measurement'
seconds = after['monotonic'] - before['monotonic']
result = {'pid': after['pid'], 'seconds': seconds, 'rss_kib': after['rss_kib'],
          'threads': after['threads'], 'cpu_percent_one_core_including_reaped_children':
          100*(after['ticks']-before['ticks'])/os.sysconf('SC_CLK_TCK')/seconds}
Path(sys.argv[1]).write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps(result))
