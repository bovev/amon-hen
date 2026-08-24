- Checkpoint A: PASSED
- Container names:
    - prometheus: monitoring-prometheus-1
    - grafana: monitoring-grafana-1
    - llama-server: llm-server
- Scrape target (confirmed working): llm-server:8080
- Docker DNS: llm-server resolves to 172.18.0.5 on ai-net
- Prometheus scrape result:
    up{instance="llm-server:8080", job="llama_cpp"} => 1
- Auth: unauthenticated request to 172.18.0.5:8080/metrics returns 401 Unauthorized;
  Prometheus authenticates via /run/secrets/llama_api_key
- Grafana: published on 127.0.0.1:3001 only (loopback)
- Prometheus: no published ports; attached to ai-net (external)
- Troubleshooting:
    - Initial target "llama-server" did not resolve; live container name is "llm-server"
    - Alias added at runtime: docker network connect --alias llm-server ai-net llm-server
    - wget in Prometheus image reports "bad address" for hostnames even when DNS resolves;
      nslookup and the Prometheus scrape itself confirm resolution works
- Follow-up:
    - Persist the llm-server network alias in the external Compose file for the llama container
      so it survives container recreation
