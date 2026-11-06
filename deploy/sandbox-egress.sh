#!/bin/sh
# Setup containers (the step that installs a repo's dependencies) have internet on the
# trace-setup0 bridge. This keeps them away from everything that isn't the public internet:
# private networks, carrier-grade NAT and cloud metadata (169.254.169.254).
# The agent's own container has no network at all and is not affected.
# Installed as a systemd unit by deploy/README.md; safe to run repeatedly.
set -eu
for net in 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16 169.254.0.0/16 100.64.0.0/10; do
  iptables -C DOCKER-USER -i trace-setup0 -d "$net" -j DROP 2>/dev/null \
    || iptables -I DOCKER-USER -i trace-setup0 -d "$net" -j DROP
done
