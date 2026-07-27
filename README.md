# LLM Inference Lab

A hands-on lab building a miniature version of a university-scale LLM platform:
GPU model serving, an OpenAI-compatible gateway with governance, production-style
monitoring, and a Kubernetes/GitOps deployment — in 8 days.

## Architecture

```
┌─ RunPod A5000 (24 GB) ──────────────┐      ┌─ Local machine (Docker Desktop) ───────────┐
│  vLLM  → Qwen2.5-7B-Instruct        │      │  docker compose:                           │
│  :8000  OpenAI API + /metrics       │◄─────┤   LiteLLM proxy :4000 (keys, budgets,      │
│  Qwen2.5-1.5B (fallback) :8001      │      │   routing, fallback)                       │
│  GPU metrics exporter :9101         │      │   Prometheus :9090 ── Grafana :3000        │
└─────────────────────────────────────┘      │  k3d: same gateway stack as K8s            │
         ▲ SSH tunnel / RunPod proxy         │  manifests, synced by ArgoCD (GitOps)      │
                                             └────────────────────────────────────────────┘
```

## Repository layout

| Path | Contents |
|---|---|
| `serving/` | vLLM startup scripts, benchmark harness, results |
| `gateway/` | LiteLLM proxy config + docker compose stack |
| `observability/` | Prometheus config, alert rules, Grafana dashboard |
| `k8s/` | Kubernetes manifests + ArgoCD application |
| `docs/` | Benchmark report, capacity model, governance, runbook, SLOs, journal |

## Key documents

- [Benchmark report](docs/benchmark-report.md) — latency/throughput sweep on an A5000
- [Capacity model](docs/capacity-model.md) — how many concurrent users per GPU at a given SLO
- [Governance](docs/governance.md) — virtual keys, budgets, rate limits, fallback chains
- [Runbook](docs/runbook.md) — incident response for high latency
- [SLOs](docs/slo.md) — service level objectives derived from measured data
- [Journal](docs/journal.md) — daily build/learn/fail log

*(Documents appear as the lab progresses — see the journal for daily status.)*
