# Design: LLM Inference Lab — Lernprojekt zur FernUni-Hagen-Bewerbung

**Datum:** 2026-07-27 · **Status:** Vom Nutzer freigegeben („let's go")

## Kontext & Ziel

Bewerbung auf **KI-Engineer / KI-Anwendungsbetreuer:in (w/m/d)**, FernUniversität in
Hagen, Zentrum für Digitalisierung und IT (ZDI). E13 TV-L, unbefristet.
**Bewerbungsfrist: 06.08.2026.** Submit-Ziel: **Di 04.08.2026** (2 Tage Puffer).

Das Projekt baut in 8 Tagen eine Mini-Version der Plattform, die die Stelle
betreibt, und erzeugt daraus die Bewerbungsunterlagen. Zwei Endprodukte:

1. **Öffentliches GitHub-Repo `llm-inference-lab`** — GPU-Serving (vLLM),
   OpenAI-kompatibles Gateway mit Governance (LiteLLM), Monitoring mit SLOs
   (Prometheus/Grafana), K8s/GitOps-Nachbau (k3d + ArgoCD). Mit Benchmark-Report,
   Capacity Model und Runbook in `docs/`.
2. **Abgeschickte Bewerbung** — Konzeptpapier (DE, 3–4 Seiten), Anschreiben mit
   Repo-Link, CV. Liegt privat in `..\Bewerbungsunterlagen`, nicht im Repo.

## Anforderungsprofil ↔ Projektabdeckung

| Anforderung (Ausschreibung) | Abdeckung im Projekt |
|---|---|
| LLM-Inferenz-Stacks (vLLM, KServe, OpenShift AI) | vLLM auf A5000, Benchmark-Sweep |
| API-Gateway, OpenAI-kompatibel (LiteLLM genannt) | LiteLLM-Proxy, virtual keys |
| Routing, Quotas, Governance | Budgets, Rate-Limits, Fallback-Routing, governance.md |
| Metriken: Latenz, Token-Durchsatz, GPU-Util, Kosten | Benchmark-Harness + Grafana-Dashboard |
| Monitoring & Betrieb produktiver Systeme | Prometheus, SLOs, Alert-Rules, Runbook |
| OpenShift/Kubernetes | k3d-Deployment + OpenShift-Begriffsbrücke (light) |
| GitOps | ArgoCD synct `k8s/` aus dem GitHub-Repo (light) |
| MLOps-Konzepte | implizit über den gesamten Stack, im Konzeptpapier benannt |
| KI in der Hochschullehre (Wunsch) | Rahmung: Studierenden-Szenarien im Capacity Model |

## Randbedingungen

- Nutzer ist **Docker/K8s-Einsteiger** → ich führe, erkläre am lebenden System;
  entscheidende Befehle/Konfigs gehen durch die Hände des Nutzers.
- **RunPod A5000 (24 GB)** ist gemietet. RunPod-Pods sind selbst Container →
  kein Docker-in-Docker; vLLM läuft nativ (pip/Template) auf dem Pod.
- Gateway + Monitoring laufen **lokal** (Windows, Docker Desktop + WSL2, Compose) —
  deckt „compose-from-zero" ab und hält Pod-Kosten niedrig.
- **Pod-Disziplin:** Pod stoppen, wenn nicht in Arbeit (~0,20–0,30 $/h; Ziel <25 $ gesamt).

## Architektur

```
┌─ RunPod A5000 (24 GB) ──────────────┐      ┌─ Windows-PC (Docker Desktop) ──────────────┐
│  vLLM  → Qwen2.5-7B-Instruct        │      │  docker compose:                           │
│  :8000  OpenAI-API + /metrics       │◄─────┤   LiteLLM-Proxy :4000 (Keys, Budgets,      │
│  Zweitmodell Qwen2.5-1.5B (Fallback)│      │   Routing, Fallback)                       │
│  GPU-Metrik-Exporter (nvidia-smi)   │      │   Prometheus :9090 ── Grafana :3000        │
└─────────────────────────────────────┘      │  k3d (So 02): Stack als K8s-Manifeste      │
         ▲ RunPod-Proxy-URL / SSH            │  + ArgoCD → GitOps                         │
                                             └────────────────────────────────────────────┘
```

Entscheidungen:
- **Modell: Qwen2.5-7B-Instruct** (kein Gating, passt in 24 GB; Llama bräuchte
  Meta-Freigabe). Fallback-Ziel: Qwen2.5-1.5B auf demselben Pod.
- Prometheus scrapt LiteLLM lokal und vLLM `/metrics` + GPU-Exporter übers Netz.

## Repo-Struktur

```
llm-inference-lab/
├── serving/          # vLLM-Start-Skripte, Benchmark-Harness, Ergebnisse (CSV)
├── gateway/          # litellm config.yaml, docker-compose.yml
├── observability/    # prometheus.yml, Grafana-Dashboards (JSON), Alert-Rules
├── k8s/              # Manifeste + ArgoCD-Application
└── docs/             # benchmark-report.md, capacity-model.md, governance.md,
                      # runbook.md, journal.md, openshift-bruecke.md
```

Repo-Sprache: Englisch (öffentlich); Konzeptpapier/Anschreiben: Deutsch (privat).

## Tagesplan mit Definition of Done

| Tag | Block | Done wenn… |
|---|---|---|
| Mo 27 | Setup + Docker-Crashkurs | SSH zum Pod steht; vLLM antwortet auf curl-Chat-Request; Docker Desktop lokal läuft; Repo initialisiert |
| Di 28 | Serving I | Benchmark-Harness: Sweep Concurrency 1→32; misst TTFT, Latenz, Tokens/s, GPU-Util; Ergebnisse als CSV |
| Mi 29 | Serving II | benchmark-report.md mit Diagrammen + capacity-model.md („n gleichzeitige Studierende pro A5000"; provisorisches SLO: P95 TTFT < 2 s, P95 Inter-Token < 100 ms — wird Sa 01 anhand echter Daten nachgeschärft) |
| Do 30 | Gateway I | LiteLLM via Compose vor vLLM; virtuelle Keys pro „Fakultät" mit Budgets/Rate-Limits |
| Fr 31 | Gateway II | Fallback-Routing (7B → 1.5B) nachweislich ausgelöst; governance.md |
| Sa 01 | Betrieb | Grafana-Dashboard (P95-Latenz, Durchsatz, GPU, Kosten/1k Tokens); 2 Alert-Rules; 1 Runbook; SLOs schriftlich |
| So 02 | K8s + GitOps | k3d lokal; LiteLLM als Deployment/Service/ConfigMap; ArgoCD synct aus GitHub; openshift-bruecke.md |
| Mo 03 | Bewerbung I | Konzeptpapier-Entwurf (DE) + Anschreiben-Entwurf |
| Di 04 | Bewerbung II | Feinschliff, CV, **Submit übers Portal** |

**Puffer-Regel:** Mi 05 + Do 06 bleiben frei. Läuft ein Block über, fällt zuerst
der ArgoCD-Teil von So 02 — **niemals der Bewerbungsblock.**

## Arbeitsweise

- Lernjournal `docs/journal.md`: 5 Zeilen pro Tag (gebaut / gelernt / schiefgegangen).
  Rohmaterial für Konzeptpapier und Vorstellungsgespräch.
- Jeder Tag endet mit Commit + Abgleich gegen Definition of Done.

## Konzeptpapier (Skizze, Detail am Mo 03)

These: *„Zentrale LLM-Serving-Plattform für die Lehre: Kapazität, Governance und
Betrieb — Erkenntnisse aus einem Praxisprojekt."* Kapitel spiegeln die Aufgaben
der Ausschreibung (Serving → Gateway/Quotas → Metriken → Betrieb), jedes Kapitel
mit echten Zahlen aus dem Lab. Anschreiben verlinkt das Repo.

## Fehlerbehandlung / Risiken

- **Pod-Ausfall/Region weg:** Alle Skripte idempotent im Repo; Pod neu provisionieren
  kostet <30 min. Volume für Modell-Cache nutzen.
- **Docker Desktop/WSL2-Probleme am PC:** Fallback = Gateway+Monitoring auch auf
  einem zweiten billigen CPU-Pod möglich; Entscheidung erst bei Auftreten.
- **LiteLLM-Metriken teils Enterprise-only:** dann Basis-Metriken + vLLM-Metriken;
  Kosten/1k Tokens notfalls aus Benchmark-Daten abgeleitet.
- **Zeitverzug:** Puffer-Regel oben; Bewerbungsblock ist unantastbar.
