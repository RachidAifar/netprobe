# Runbook

What to do when a NetProbe alert fires. Each section matches an alert in
`monitoring/prometheus/alerts.yml`.

## TargetDown

**Meaning:** a probe has failed for 2 minutes in a row.

1. Check what NetProbe sees:
   `curl -s localhost:8080/targets | jq '.[] | select(.last.up == false)'`
   (in Kubernetes: `kubectl -n netprobe port-forward svc/netprobe 8080:80` first).
2. Read the `detail` field:
   | Detail | Likely cause | Next check |
   |---|---|---|
   | `timeout` | Firewall drops packets, or the host is overloaded | `nc -vz -w 5 <host> <port>`, `traceroute <host>` |
   | `error: Connection refused` | Host is up, but nothing listens on that port | Is the service running? `ss -ltnp` on the host |
   | `error: Name or service not known` | DNS cannot resolve the name | `dig <name>`, check `/etc/resolv.conf` or CoreDNS |
   | `HTTP 5xx` | The application is failing | Application logs |
   | `HTTP 4xx` | Wrong URL or authentication | Check the target address in the config |
3. If **every** target is down at once, the problem is probably NetProbe's own network
   (egress firewall, NetworkPolicy, DNS in the pod), not the targets:
   `kubectl -n netprobe exec deploy/netprobe -- python -c "import socket; print(socket.getaddrinfo('example.com', 443))"`

## TargetSlow

**Meaning:** the 95th-percentile probe time has been above 1 second for 10 minutes.

1. Open the Grafana *NetProbe* dashboard and look at **Probe latency p95**. Is one target slow or all of them?
2. One target: check that service's load and network path (`mtr <host>`).
3. All targets: check NetProbe's node (CPU throttling, `kubectl top pod -n netprobe`) and the cluster's egress.

## NetProbeNotRunning

**Meaning:** Prometheus cannot scrape NetProbe at all.

1. `kubectl -n netprobe get pods` — are pods running and ready?
2. `kubectl -n netprobe describe pod <pod>` — look for image pull errors, OOMKilled, failed probes.
3. `kubectl -n netprobe logs deploy/netprobe` — JSON logs; config errors appear on startup.
4. Check the ServiceMonitor matches the service: `kubectl -n netprobe get servicemonitor netprobe -o yaml`.
5. Check the NetworkPolicy allows the `monitoring` namespace to reach port 8080.
