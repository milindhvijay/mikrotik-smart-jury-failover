"""Bounded live failover check, explicitly invoked on one monitor at a time.

Credentials come from the service environment. A RouterOS scheduler clears the
probe fault independently of this process. No PPP session is disconnected.
"""
import argparse
import datetime as dt
import ipaddress
import json
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, '/opt/smart-jury')
from jury_monitor import Router, load_targets


def run(isp, family, output):
    router = Router(isp)
    router.connect()
    api = router.api
    other = Router('kv' if isp == 'bsnl' else 'bsnl')
    other.api = api
    tag = 'Jury-live-check-' + isp
    sources = {'bsnl': ['10.1.40.10/32', '204::be24:11ff:fed7:5d96/128'],
               'kv': ['10.1.40.11/32', '204::be24:11ff:fe06:69fa/128']}[isp]
    destinations = ['1.0.0.1/32', '2606:4700:4700::1001/128']
    data = {'isp': isp, 'blocked_family': family, 'started': time.time(), 'events': []}

    def event(name, **details):
        row = dict(event=name, time=time.time(), **details)
        data['events'].append(row)
        output.write_text(json.dumps(data, indent=2)+'\n')
        print(json.dumps(row), flush=True)

    def cleanup(path, key, value):
        resource = api.get_resource(path)
        for row in resource.get(**{key: value}):
            resource.remove(id=row['id'])

    def schedule(suffix, seconds, body):
        name = tag + '-' + suffix
        clock = api.get_resource('/system/clock').get()[0]
        now = dt.datetime.fromisoformat(clock['date'] + 'T' + clock['time'])
        when = now + dt.timedelta(seconds=seconds)
        api.get_resource('/system/scheduler').add(**{
            'name': name, 'start-date': when.date().isoformat(),
            'start-time': when.time().isoformat(), 'interval': '0s',
            'policy': 'read,write,test', 'on-event': body +
            f'; /system scheduler remove [find where name="{name}"]'})
        assert len(api.get_resource('/system/scheduler').get(name=name)) == 1
        return name

    def routes():
        return [dict(row) for instance in (router, other) for _, _, row in instance.routes()]

    def normal(instance):
        return all(str(row.get('distance')) == '1' if role == 'primary'
                   else row.get('disabled', 'false') == 'false'
                   for _, role, row in instance.routes())

    def trace():
        result = []
        for address in destinations:
            host = address.split('/')[0]
            url_host = '[' + host + ']' if ':' in host else host
            text = urllib.request.urlopen('https://' + url_host + '/cdn-cgi/trace', timeout=8).read().decode()
            result.append(dict(line.split('=', 1) for line in text.splitlines()
                               if line.startswith(('ip=', 'colo='))))
        return result

    def protected():
        result = {}
        for path in ('/ip/route', '/ipv6/route'):
            result[path] = [{k: r.get(k, 'false' if k == 'disabled' else '')
                            for k in ('id', 'comment', 'routing-table', 'gateway', 'dst-address', 'distance', 'disabled')}
                           for r in api.get_resource(path).get()
                           if 'nofailover' in r.get('routing-table', '') or 'LTE' in r.get('comment', '')]
        return result

    fault_cleanup = (f'/ip firewall raw remove [find where comment="{tag}"]; '
                     f'/ipv6 firewall raw remove [find where comment="{tag}"]')
    all_cleanup = fault_cleanup + f'; /routing rule remove [find where comment="{tag}"]'
    setup = False
    try:
        # Refuse overlap or stale test objects rather than removing unknown work.
        for path in ('/ip/firewall/raw', '/ipv6/firewall/raw', '/routing/rule'):
            assert not any(r.get('comment', '').startswith('Jury-live-check-')
                           for r in api.get_resource(path).get()), 'Another live check exists'
        assert not any(r.get('name', '').startswith('Jury-live-check-')
                       for r in api.get_resource('/system/scheduler').get()), 'Stale live-check scheduler'
        assert normal(router) and normal(other), 'Both ISPs must start in normal state'
        assert router.interface_up() and other.interface_up(), 'Both WANs must be running'
        active_ips = {t.ip for t in load_targets(Path('/opt/smart-jury/targets_' + isp + '.csv'))}
        assert all(d.split('/')[0] not in active_ips for d in destinations)
        before_protected = protected()
        event('before', routes=routes(), trace=trace(), protected=before_protected)
        # Verify autonomous execution before creating any traffic-affecting rule.
        setup = True
        canary = schedule('canary', 5, ':local juryCanary true')
        time.sleep(8)
        assert not api.get_resource('/system/scheduler').get(name=canary), 'Scheduler canary did not execute'
        event('watchdog_verified')
        schedule('cleanup', 600, all_cleanup)
        rules = api.get_resource('/routing/rule')
        first = rules.get()[0]['id']
        for version, source, destination in zip((4, 6), sources, destinations):
            rules.add(**{'src-address': source, 'dst-address': destination,
                         'action': 'lookup-only-in-table', 'table': ('v6-' if version == 6 else '') + 'route-as' + router.asn,
                         'comment': tag, 'place-before': first})
        event('client_path_ready', trace=trace())
        assert normal(router) and normal(other)
        schedule('fault', 45, fault_cleanup)
        path = '/ip/firewall/raw' if family == 4 else '/ipv6/firewall/raw'
        raw = api.get_resource(path)
        first_raw = next(r['id'] for r in raw.get() if r.get('dynamic', 'false') == 'false')
        raw.add(**{'chain': 'prerouting', 'src-address': sources[family == 6],
                   'protocol': 'icmp' if family == 4 else 'icmpv6',
                   'icmp-options': '8:0' if family == 4 else '128:0',
                   'action': 'drop', 'comment': tag, 'place-before': first_raw})
        fault_at = time.monotonic()
        event('fault_started')
        while time.monotonic() - fault_at < 30:
            rows = router.routes()
            failed = all(str(row.get('distance')) == '3' if role == 'primary'
                         else row.get('disabled') == 'true' for _, role, row in rows)
            if failed:
                break
            time.sleep(1)
        assert failed, 'Monitor did not demote all four routes'
        assert normal(other), 'Healthy peer was unexpectedly demoted'
        switched = trace()
        baseline = data['events'][0]['trace']
        assert all(a['ip'] != b['ip'] for a, b in zip(baseline, switched)), 'Egress did not change in both families'
        for resource_path, table_prefix in [('/ip/route', ''), ('/ipv6/route', 'v6-')]:
            active = [r for r in api.get_resource(resource_path).get()
                      if r.get('routing-table') == table_prefix + 'route-as' + router.asn
                      and r.get('dst-address') in ('0.0.0.0/0', '::/0') and r.get('active') == 'true']
            assert len(active) == 1 and active[0]['gateway'] == 'pppoe-as' + router.other
        event('failed_over', seconds=round(time.monotonic()-fault_at, 2), trace=switched, routes=routes())
        cleanup(path, 'comment', tag)
        recovered_at = time.monotonic()
        cleanup('/system/scheduler', 'name', tag + '-fault')
        event('fault_cleared')
        while time.monotonic() - recovered_at < 420:
            if normal(router):
                break
            time.sleep(5)
        assert normal(router), 'Monitor did not recover within seven minutes'
        assert time.monotonic() - recovered_at >= 115, 'Recovery hold-down was bypassed'
        assert normal(other)
        restored = trace()
        assert [r['ip'] for r in restored] == [r['ip'] for r in baseline], 'Egress did not return to original ISP'
        assert protected() == before_protected, 'Monitor-only or LTE routes changed'
        event('recovered', seconds=round(time.monotonic()-recovered_at, 2), trace=restored, routes=routes())
        data['passed'] = True
    except Exception as error:
        data['passed'] = False
        event('error', error=str(error))
        raise
    finally:
        if setup:
            # The scheduler remains a fallback if this API connection fails.
            for path in ('/ip/firewall/raw', '/ipv6/firewall/raw', '/routing/rule'):
                cleanup(path, 'comment', tag)
            for suffix in ('fault', 'cleanup', 'canary'):
                cleanup('/system/scheduler', 'name', tag + '-' + suffix)
            event('temporary_objects_removed')
        data['ended'] = time.time()
        output.write_text(json.dumps(data, indent=2)+'\n')
        router.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--isp', choices=['bsnl', 'kv'], required=True)
    parser.add_argument('--family', type=int, choices=[4, 6], required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(args.isp, args.family, args.output)
