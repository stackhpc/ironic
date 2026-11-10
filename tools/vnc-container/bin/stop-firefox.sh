#!/bin/bash

set -ex

# With host networking (the container-kolla provider) the container's
# ports are ports of the conductor host, so both values must come from
# the per-container environment set by the provider.
connections=$(ss --no-header state established "( dport = :${VNC_PORT:-5900} or sport = :${VNC_PORT:-5900} )" | wc -l)

if [ "$connections" -eq 0 ]; then
    # Signal the main process to gracefully shut down the browser.
    # The main process handles navigating tabs to about:blank
    # (closing console websockets) before killing the browser.
    curl -s -X POST "http://localhost:${SHUTDOWN_HTTP_PORT:-8888}/browser-shutdown"

    # Wait until firefox has actually exited
    while pgrep -x $FIREFOX >/dev/null 2>&1; do
        sleep 1
    done
else
    echo "Active VNC connection detected, deferring $FIREFOX shutdown."
fi
