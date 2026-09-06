#!/bin/sh
# Run on the affected monitor as root: sh rollback.sh bsnl (or kv).
set -eu
isp=${1:?Specify bsnl or kv}
case "$isp" in bsnl|kv) ;; *) exit 2 ;; esac
backup_dir=$(cat /opt/smart-jury/backup-path)
[ -r "$backup_dir/rollback.openrc" ]
/opt/smart-jury/venv/bin/python -c 'import routeros_api'
rc-service "monitor-$isp" stop
cp "$backup_dir/rollback.openrc" "/etc/init.d/monitor-$isp"
chmod 755 "/etc/init.d/monitor-$isp"
rc-service "monitor-$isp" start
