# LLM Inference Lab — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task (inline execution — this project requires interactive work with the user's RunPod account and local machine). Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** In 8 Tagen eine Mini-LLM-Plattform (vLLM → LiteLLM → Prometheus/Grafana → k3d/ArgoCD) bauen und daraus die Bewerbung für die FernUni-Hagen-Stelle (Frist 06.08.) erzeugen.

**Architecture:** vLLM serviert Qwen2.5-7B auf einem RunPod-A5000-Pod (nativ, kein Docker-in-Docker). Gateway (LiteLLM + Postgres) und Monitoring (Prometheus + Grafana) laufen lokal auf Windows via Docker Compose und sprechen den Pod über SSH-Tunnel oder RunPod-Proxy an. Am K8s-Tag wird derselbe Gateway-Stack als k3d-Deployment mit ArgoCD-Sync nachgebaut.

**Tech Stack:** vLLM, Qwen2.5-7B/1.5B-Instruct, LiteLLM Proxy, Postgres, Prometheus, Grafana, Docker Desktop + Compose, k3d, ArgoCD, RunPod A5000.

## Global Constraints

- **Submit-Deadline: Di 04.08.2026** (Frist 06.08.; Mi 05 + Do 06 sind Puffer). Läuft ein Block über, fällt zuerst der ArgoCD-Teil (Task 10), **niemals** Tasks 12–13 (Bewerbung).
- Nutzer ist Docker/K8s-Einsteiger. **Arbeitsmodus (Nutzer-Vorgabe vom 27.07.): Der Nutzer führt JEDEN Schritt selbst aus** (UI-Aktionen, Terminal-Befehle, Configs). Claude liefert Schritt-für-Schritt-Anleitung mit Begründung, verifiziert jedes Ergebnis über MCP/SSH/API und stellt nach jedem Block 2–3 Verständnisfragen auf Bewerbungsgespräch-Niveau. Kern-Artefakte schreibt der Nutzer, Claude reviewt; nur Boilerplate (Journal-Format, Commits) macht Claude.
- Pod stoppen, wenn nicht in Arbeit. `HF_HOME=/workspace/hf` (Volume), damit Modelle den Stop überleben.
- vLLM-Endpoint ist öffentlich erreichbar → **immer** mit `VLLM_API_KEY` absichern.
- Jeder Task endet mit Commit + Journal-Eintrag in `docs/journal.md` (gebaut / gelernt / schiefgegangen).
- Repo-Inhalte Englisch (öffentlich auf GitHub), Konzeptpapier/Anschreiben Deutsch (privat in `..\Bewerbungsunterlagen`, NIE ins Repo).
- Keine Secrets ins Repo: `.env`-Dateien und Keys sind gitignored.

---

### Task 1 (Mo 27): Lokale Voraussetzungen + Repo-Grundgerüst

**Files:**
- Create: `README.md`, `.gitignore`, `docs/journal.md`

- [ ] **Step 1: Prüfen was da ist:** `git --version`, `docker --version`, `wsl --status`, `gh --version`, `Test-Path ~\.ssh\id_ed25519.pub`
- [ ] **Step 2: Fehlendes installieren:** Docker Desktop via `winget install Docker.DockerDesktop` (braucht WSL2; danach Neustart von Docker Desktop, verifizieren mit `docker run --rm hello-world`). `gh` via `winget install GitHub.cli`, dann `gh auth login` (macht der Nutzer interaktiv mit `!`-Prefix).
- [ ] **Step 3: SSH-Key:** Falls keiner existiert: `ssh-keygen -t ed25519`. Public Key in RunPod → Settings → SSH Public Keys eintragen (Nutzer, im Browser).
- [ ] **Step 4: `.gitignore`** anlegen:

```gitignore
.env
*.key
__pycache__/
serving/benchmark/results/*.json
```

- [ ] **Step 5: `README.md`-Skeleton** (EN: Projektziel, Architektur-ASCII aus der Spec, Ordnerübersicht) und `docs/journal.md` (Kopfzeile + Eintrag Tag 1) anlegen.
- [ ] **Step 6: GitHub-Repo:** `gh repo create llm-inference-lab --public --source . --push`
- [ ] **Step 7: Commit** `chore: repo skeleton, gitignore, journal`

### Task 2 (Mo 27): SSH zum Pod + vLLM läuft

**Files:**
- Create: `serving/start_vllm_7b.sh`, `serving/README.md`

**Interfaces:**
- Produces: vLLM OpenAI-API auf Pod-Port 8000, geschützt mit `$VLLM_API_KEY`; Modellname `Qwen/Qwen2.5-7B-Instruct`.

- [ ] **Step 1: SSH-Verbindung:** Nutzer holt den SSH-Befehl aus RunPod → Pod → Connect (Form: `ssh root@<ip> -p <port>` oder `ssh <podid>@ssh.runpod.io`). Verbindung testen: `ssh ... nvidia-smi` → muss die A5000 zeigen. Läuft der Pod schon mit fremdem Template ohne unseren Key: Key über RunPod-Webterminal in `~/.ssh/authorized_keys` nachtragen oder Pod einmal neu starten.
- [ ] **Step 2: vLLM installieren** (auf dem Pod): `pip install -U vllm` (im PyTorch-Template vorhanden: python3.11+cuda). Prüfen: `vllm --version`.
- [ ] **Step 3: Startskript** `serving/start_vllm_7b.sh` schreiben (liegt im Repo, wird per scp/Copy-Paste auf den Pod gebracht):

```bash
#!/usr/bin/env bash
export HF_HOME=/workspace/hf
export VLLM_API_KEY="${VLLM_API_KEY:?set VLLM_API_KEY first}"
vllm serve Qwen/Qwen2.5-7B-Instruct \
  --port 8000 \
  --api-key "$VLLM_API_KEY" \
  --max-model-len 8192 \
  --gpu-memory-utilization 0.90 \
  2>&1 | tee /workspace/vllm_7b.log
```

- [ ] **Step 4: Starten** in tmux (`tmux new -s vllm`), Modell-Download abwarten (~15 GB, dank `HF_HOME` nur einmal).
- [ ] **Step 5: Verifizieren** (auf dem Pod):

```bash
curl -s http://127.0.0.1:8000/v1/chat/completions \
  -H "Authorization: Bearer $VLLM_API_KEY" -H "Content-Type: application/json" \
  -d '{"model":"Qwen/Qwen2.5-7B-Instruct","messages":[{"role":"user","content":"Sag Hallo auf Deutsch."}],"max_tokens":30}'
```

Expected: JSON mit `choices[0].message.content`. Zusätzlich `curl -s -H "Authorization: Bearer $VLLM_API_KEY" http://127.0.0.1:8000/metrics | head` → Prometheus-Metriken sichtbar (merken, ob /metrics den Key verlangt — relevant für Task 10).
- [ ] **Step 6: Erreichbarkeit von außen:** SSH-Tunnel vom PC testen: `ssh -N -L 8000:127.0.0.1:8000 <pod>` und lokal denselben curl gegen `http://127.0.0.1:8000`. Alternativ RunPod-HTTP-Proxy (`https://<podid>-8000.proxy.runpod.net`), falls Port 8000 im Pod als HTTP-Port exponiert ist.
- [ ] **Step 7: Commit + Journal** `feat(serving): vllm startup script for qwen2.5-7b on a5000`

### Task 3 (Di 28): Benchmark-Harness + Sweep

**Files:**
- Create: `serving/benchmark/sweep.sh`, `serving/benchmark/gpu_log.sh`, `serving/benchmark/results/` (CSV/JSON)

**Interfaces:**
- Produces: pro Concurrency-Stufe ein JSON `results/c<N>.json` (vllm bench Format: enthält u.a. `mean_ttft_ms`, `p95_ttft_ms`, `mean_itl_ms`, `output_throughput`), plus `results/gpu_c<N>.csv` (nvidia-smi-Samples).

- [ ] **Step 1: `sweep.sh`** (läuft AUF dem Pod gegen 127.0.0.1 — Netzwerk-Rauschen raus):

```bash
#!/usr/bin/env bash
set -e
export OPENAI_API_KEY="$VLLM_API_KEY"
mkdir -p results
for c in 1 2 4 8 16 32; do
  nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader,nounits -l 1 > results/gpu_c${c}.csv &
  GPU_PID=$!
  vllm bench serve --backend openai-chat \
    --model Qwen/Qwen2.5-7B-Instruct \
    --host 127.0.0.1 --port 8000 --endpoint /v1/chat/completions \
    --dataset-name random --random-input-len 512 --random-output-len 256 \
    --num-prompts $((c*10)) --max-concurrency $c \
    --save-result --result-filename results/c${c}.json
  kill $GPU_PID
done
```

- [ ] **Step 2: Probelauf** nur mit `c=1`, Ergebnis-JSON inspizieren, Feldnamen gegen das erwartete Interface prüfen (vllm-Versionen benennen Felder leicht unterschiedlich — Abweichungen im Journal notieren und in Task 4 verwenden).
- [ ] **Step 3: Vollen Sweep fahren** (~30–45 min). Parallel dem Nutzer erklären: TTFT vs. ITL vs. Durchsatz, Continuous Batching, warum Durchsatz mit Concurrency steigt bis KV-Cache/Compute sättigt.
- [ ] **Step 4: Ergebnisse ins Repo** holen (`scp -r`), committen: `feat(serving): concurrency sweep 1-32 with gpu sampling`

### Task 4 (Mi 29): Benchmark-Report + Capacity Model

**Files:**
- Create: `serving/benchmark/analyze.py`, `docs/benchmark-report.md`, `docs/capacity-model.md`, `docs/img/*.png`

**Interfaces:**
- Consumes: `results/c<N>.json`, `results/gpu_c<N>.csv` aus Task 3.

- [ ] **Step 1: VOR dem ersten Diagramm das `dataviz`-Skill laden** (Pflicht laut Skill-Trigger).
- [ ] **Step 2: `analyze.py`:** liest alle JSONs → pandas DataFrame → vier PNGs: TTFT-P95 vs. Concurrency, ITL-P95 vs. Concurrency, Tokens/s vs. Concurrency, GPU-Util vs. Concurrency.
- [ ] **Step 3: `docs/benchmark-report.md`** (EN): Setup-Tabelle (GPU, Modell, vLLM-Version, Parameter), die vier Diagramme, 5 Bullet-Findings.
- [ ] **Step 4: `docs/capacity-model.md`** (EN): Provisorisches SLO **P95 TTFT < 2 s, P95 ITL < 100 ms** → aus den Kurven die maximale Concurrency ablesen, die das SLO hält. Übersetzung in Lehr-Szenarien: n gleichzeitige Chat-Nutzer ≈ Concurrency × Faktor (Annahme: aktiver Request nur ~1/6 der Sitzungszeit → dokumentieren!). Kosten: $/h der A5000 ÷ Tokens/h = $/1M Tokens. Skalierungsabschnitt: was ändert sich mit 2×A5000 (Replikas hinter Gateway) vs. größerer GPU.
- [ ] **Step 5: Commit** `docs(serving): benchmark report and capacity model`

### Task 5 (Do 30): Gateway-Compose — LiteLLM + Postgres

**Files:**
- Create: `gateway/docker-compose.yml`, `gateway/config.yaml`, `gateway/.env.example`

**Interfaces:**
- Consumes: vLLM-Endpoint aus Task 2 (Tunnel `127.0.0.1:8000` → im Container `host.docker.internal:8000`).
- Produces: OpenAI-kompatibles Gateway auf `http://localhost:4000` mit Master-Key `$LITELLM_MASTER_KEY`; Modellalias `qwen-7b`.

- [ ] **Step 1: `gateway/config.yaml`:**

```yaml
model_list:
  - model_name: qwen-7b
    litellm_params:
      model: hosted_vllm/Qwen/Qwen2.5-7B-Instruct
      api_base: http://host.docker.internal:8000/v1
      api_key: os.environ/VLLM_API_KEY
general_settings:
  master_key: os.environ/LITELLM_MASTER_KEY
  database_url: os.environ/DATABASE_URL
```

- [ ] **Step 2: `gateway/docker-compose.yml`:**

```yaml
services:
  litellm:
    image: ghcr.io/berriai/litellm:main-stable
    ports: ["4000:4000"]
    volumes: ["./config.yaml:/app/config.yaml:ro"]
    command: ["--config", "/app/config.yaml", "--port", "4000"]
    env_file: .env
    environment:
      DATABASE_URL: postgresql://litellm:litellm@db:5432/litellm
    depends_on: [db]
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: litellm
      POSTGRES_PASSWORD: litellm
      POSTGRES_DB: litellm
    volumes: [pgdata:/var/lib/postgresql/data]
volumes:
  pgdata: {}
```

`.env.example` mit `LITELLM_MASTER_KEY=sk-...` und `VLLM_API_KEY=...` (echte Werte nur in `.env`, gitignored).
- [ ] **Step 3: Hochfahren + Smoke-Test:** `docker compose up -d`, dann curl gegen `http://localhost:4000/v1/chat/completions` mit Master-Key und `"model":"qwen-7b"` → Antwort kommt vom Pod durch das Gateway. Dem Nutzer dabei Compose-Konzepte erklären (Services, Volumes, env_file, Netzwerk).
- [ ] **Step 4: Virtuelle Keys:** Für zwei fiktive Fakultäten Keys erzeugen (Nutzer tippt):

```bash
curl -s http://localhost:4000/key/generate -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{"key_alias":"fakultaet-informatik","max_budget":5.0,"tpm_limit":20000,"rpm_limit":30,"models":["qwen-7b"]}'
```

Zweiter Key `fakultaet-jura` mit engeren Limits. Verifizieren: Request mit Fakultäts-Key funktioniert; `rpm_limit` durch schnelle Request-Serie reißen → 429.
- [ ] **Step 5: Commit** `feat(gateway): litellm proxy with virtual keys, budgets, rate limits`

### Task 6 (Fr 31): Zweitmodell + Fallback-Routing

**Files:**
- Create: `serving/start_vllm_1_5b.sh`
- Modify: `serving/start_vllm_7b.sh` (gpu-memory-utilization 0.90 → 0.72), `gateway/config.yaml`

**Interfaces:**
- Produces: Modellalias `qwen-1_5b` (Pod-Port 8001); Fallback-Kette `qwen-7b → qwen-1_5b`.

- [ ] **Step 1: `start_vllm_1_5b.sh`** — wie 7b-Skript, aber `Qwen/Qwen2.5-1.5B-Instruct`, `--port 8001`, `--gpu-memory-utilization 0.15`; 7b-Skript auf `0.72` senken, beide (nacheinander!) neu starten. Zweiten Tunnel `-L 8001:127.0.0.1:8001` aufbauen.
- [ ] **Step 2: `config.yaml` erweitern:** zweiter `model_list`-Eintrag (`api_base: http://host.docker.internal:8001/v1`) plus:

```yaml
router_settings:
  fallbacks:
    - qwen-7b: ["qwen-1_5b"]
  num_retries: 1
  timeout: 30
```

- [ ] **Step 3: Fallback beweisen:** 7B-vLLM in tmux stoppen → Request an `qwen-7b` durchs Gateway → Antwort muss von `qwen-1_5b` kommen (im Response-Body/Logs nachweisen). Screenshot/Log-Auszug für `docs/governance.md` sichern. 7B wieder starten.
- [ ] **Step 4: `docs/governance.md`** (EN): Key-Hierarchie (Master → Fakultäts-Keys), Budget/Rate-Limit-Matrix als Tabelle, Fallback-Kette, was davon in der FernUni-Realität RBAC/Mandanten wären.
- [ ] **Step 5: Commit** `feat(gateway): fallback routing 7b->1.5b, governance doc`

### Task 7 (Sa 01): Monitoring-Stack

**Files:**
- Create: `observability/docker-compose.yml`, `observability/prometheus.yml`, `observability/alerts.yml`, `observability/grafana/dashboard.json`, `serving/gpu_exporter.py`

**Interfaces:**
- Consumes: vLLM `/metrics` (8000, Bearer nötig falls in Task 2 festgestellt), LiteLLM `/metrics` (4000), GPU-Exporter (9101 via Tunnel).
- Produces: Grafana auf `http://localhost:3000` mit Dashboard „LLM Platform".

- [ ] **Step 1: `serving/gpu_exporter.py`** (läuft auf dem Pod, `pip install prometheus_client`):

```python
import subprocess, time
from prometheus_client import Gauge, start_http_server

util = Gauge("gpu_utilization_percent", "GPU utilization from nvidia-smi")
mem = Gauge("gpu_memory_used_mib", "GPU memory used from nvidia-smi")
start_http_server(9101)
while True:
    out = subprocess.check_output(
        ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used",
         "--format=csv,noheader,nounits"]).decode()
    u, m = out.strip().split(", ")
    util.set(float(u)); mem.set(float(m))
    time.sleep(5)
```

Dritten Tunnel `-L 9101:127.0.0.1:9101` ergänzen (alle Tunnel in ein Skript `serving/tunnel.ps1` bündeln).
- [ ] **Step 2: `observability/prometheus.yml`:** Jobs `vllm` (host.docker.internal:8000, ggf. `authorization.credentials`), `litellm` (host.docker.internal:4000), `gpu` (host.docker.internal:9101); `rule_files: [alerts.yml]`. Falls LiteLLM-Prometheus-Metriken Enterprise-gated sind: Job drin lassen, im Runbook vermerken, Dashboards auf vLLM-Metriken stützen (`vllm:e2e_request_latency_seconds`, `vllm:num_requests_running`, `vllm:generation_tokens_total`).
- [ ] **Step 3: Compose** mit `prom/prometheus` + `grafana/grafana` (anonymous admin ok, nur lokal), Prometheus als Datasource provisionieren.
- [ ] **Step 4: Dashboard** „LLM Platform": P50/P95/P99-Latenz, Token-Durchsatz (rate über `generation_tokens_total`), laufende/wartende Requests, GPU-Util & VRAM, abgeleitete Kosten/1k Tokens (Konstante $/h ÷ Durchsatz). Last mit Sweep-Skript (kleine Stufe) erzeugen, damit die Panels leben. Export als `dashboard.json`.
- [ ] **Step 5: `alerts.yml`:** 2 Regeln — `P95TTFTHigh` (>2 s für 5 min) und `GPUMemoryPressure` (>95 % für 10 min).
- [ ] **Step 6: `docs/runbook.md`** (EN): „Alert: P95 latency high" — Diagnosepfad (Grafana → laufende Requests → GPU-Util → vLLM-Log), 3 Sofortmaßnahmen (Rate-Limits senken via LiteLLM, Fallback erzwingen, Replika/Restart), Eskalation. `docs/slo.md`: finale SLOs anhand echter Daten aus Task 3/4 nachgeschärft.
- [ ] **Step 7: Commit** `feat(observability): prometheus+grafana stack, alerts, runbook, slos`

### Task 8 (Sa 01, Abschluss): Compose-from-zero-Übung

- [ ] **Step 1:** Nutzer fährt beide Stacks runter (`docker compose down` in gateway/ und observability/) und bringt sie **ohne in die Dateien zu schauen** wieder hoch; erklärt mir dabei jede Zeile der Compose-Files mündlich. Lücken → kurz nacharbeiten. (Das ist der „compose-from-zero"-Beweis aus dem ursprünglichen Nutzer-Plan.)
- [ ] **Step 2:** Journal-Eintrag.

### Task 9 (So 02): k3d-Cluster + Gateway als K8s-Deployment

**Files:**
- Create: `k8s/base/namespace.yaml`, `k8s/base/litellm-deployment.yaml`, `k8s/base/litellm-service.yaml`, `k8s/base/litellm-configmap.yaml`, `k8s/base/kustomization.yaml`

**Interfaces:**
- Produces: LiteLLM erreichbar via `kubectl port-forward svc/litellm 4100:4000 -n llm` (bewusst 4100, Compose-Stack auf 4000 kann weiterlaufen).

- [ ] **Step 1: Tools:** `winget install k3d kubectl` (bzw. `winget install Kubernetes.kubectl SUSE.k3d`). Cluster: `k3d cluster create lab --agents 1`. Verifizieren: `kubectl get nodes` → 2 Ready.
- [ ] **Step 2: Manifeste schreiben** — ConfigMap trägt dieselbe `config.yaml` wie das Compose-Gateway (ohne DB: `database_url` weglassen, Keys-Feature entfällt in der K8s-Demo — im README als bewusste Vereinfachung dokumentieren). Deployment (1 Replica, Image `ghcr.io/berriai/litellm:main-stable`, envFrom Secret `litellm-env`, Liveness `/health/liveliness`, Readiness `/health/readiness`), Service (ClusterIP 4000). Secret NICHT ins Repo: `kubectl create secret generic litellm-env --from-env-file=gateway/.env -n llm` (Befehl im README dokumentieren).
- [ ] **Step 3: Anwenden & verstehen:** `kubectl apply -k k8s/base`, dann gemeinsam durchgehen: Pod vs. Deployment vs. ReplicaSet, Service-Discovery, was `kubectl describe pod` zeigt. Pod killen → Self-Healing beobachten (`kubectl delete pod ... && kubectl get pods -w`).
- [ ] **Step 4: Smoke-Test** über port-forward mit demselben curl wie Task 5 (Ziel `host.docker.internal` funktioniert in k3d: stattdessen api_base in der ConfigMap auf `host.k3d.internal:8000` setzen!).
- [ ] **Step 5: Commit** `feat(k8s): litellm deployment on k3d`

### Task 10 (So 02): ArgoCD — GitOps-Sync  *(Streichkandidat bei Zeitverzug)*

**Files:**
- Create: `k8s/argocd/app.yaml`, `docs/openshift-bruecke.md`

- [ ] **Step 1: ArgoCD installieren:** `kubectl create namespace argocd && kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml`; UI via port-forward 8080, Admin-Passwort aus Secret `argocd-initial-admin-secret`.
- [ ] **Step 2: `app.yaml`:** Application zeigt auf `https://github.com/<user>/llm-inference-lab`, `path: k8s/base`, `syncPolicy.automated {prune: true, selfHeal: true}`, Ziel-Namespace `llm`.
- [ ] **Step 3: GitOps beweisen:** Replicas in `litellm-deployment.yaml` 1→2 ändern, committen, pushen → ArgoCD synct automatisch; `kubectl get pods -n llm` zeigt 2 Pods. Das ist DER GitOps-Moment fürs Vorstellungsgespräch — Screenshot ins Journal.
- [ ] **Step 4: `docs/openshift-bruecke.md`** (DE, halbe Seite): Route↔Ingress, `oc`↔`kubectl`, Project↔Namespace, SCC↔PodSecurity, ImageStream/BuildConfig↔Registry+CI, OpenShift AI/KServe↔„unser vLLM manuell" — je 1 Zeile.
- [ ] **Step 5: Commit** `feat(gitops): argocd application with auto-sync`

### Task 11 (So 02, Abschluss): README-Endausbau

- [ ] **Step 1:** README vervollständigen: Architektur-Diagramm, Quickstart pro Komponente, Links auf alle `docs/*.md`, Screenshot Grafana-Dashboard + ArgoCD-Sync. Aufräum-Pass durchs Repo. Commit + Push. **Ab hier ist das Repo Bewerbungs-Asset.**

### Task 12 (Mo 03): Konzeptpapier (DE)

**Files:**
- Create: `..\Bewerbungsunterlagen\konzeptpapier.md` (→ später PDF; NICHT im Repo)

- [ ] **Step 1: Gliederung:** 1. Ausgangslage FernUni (zentrale KI-Plattform für Lehre) · 2. Referenzarchitektur (= Lab-Architektur, generalisiert auf OpenShift: vLLM/KServe hinter LiteLLM) · 3. Kapazität & Kosten (echte A5000-Zahlen aus `capacity-model.md`, hochgerechnet) · 4. Governance (Keys/Budgets/Quotas pro Fakultät/Kurs, aus `governance.md`) · 5. Betrieb (SLOs, Monitoring, Runbook-Auszug) · 6. Roadmap 90 Tage. 3–4 Seiten.
- [ ] **Step 2: Entwurf schreiben** — jede Behauptung mit einer Zahl oder einem Artefakt aus dem Repo belegen, Repo-URL prominent.
- [ ] **Step 3: Anschreiben-Entwurf** (1 Seite, DE): Kernbotschaft „Ich habe Ihre Plattform im Kleinen gebaut, hier ist der Beweis" + Profil-Mapping. CV-Lücken heute identifizieren, damit Di nur Feinschliff bleibt.

### Task 13 (Di 04): Feinschliff + Submit

- [ ] **Step 1:** Konzeptpapier + Anschreiben Korrektur lesen (frischer Blick), als PDF exportieren, CV aktualisieren.
- [ ] **Step 2:** Bewerbung über das FernUni-Portal (Stellen-ID 2063) einreichen. **Submit-Bestätigung sichern.**
- [ ] **Step 3:** Pod-Kosten-Bilanz ziehen, Pod stoppen/terminieren, Abschluss-Journal.
