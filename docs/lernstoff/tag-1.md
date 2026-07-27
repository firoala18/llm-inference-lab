# Lernstoff Tag 1 — Model-Serving-Grundlagen (Mo 27.07.2026)

Zum Auswendiglernen fürs Bewerbungsgespräch. Alles hier hast du heute selbst
gebaut oder erlebt — antworte im Gespräch immer mit Bezug aufs eigene Projekt.

---

## 1. vLLM — das Herzstück

**Was:** Eine Open-Source-Inference-Engine zum Servieren von LLMs auf GPUs.
Der De-facto-Standard für Self-Hosted-LLM-Serving (steht wörtlich in der
FernUni-Ausschreibung).

**Wofür:** Ein Modell einmal in den GPU-Speicher laden und dann viele
gleichzeitige Nutzer-Requests effizient bedienen — statt für jeden Nutzer
eine eigene Modellkopie zu brauchen.

**Warum vLLM und nicht einfach PyTorch/Transformers?** Zwei Kernideen:

| Technik | Was sie tut | Warum das zählt |
|---|---|---|
| **PagedAttention** | Verwaltet den KV-Cache in kleinen Blöcken („Seiten"), wie ein Betriebssystem den RAM | Kaum Speicherverschnitt → mehr parallele Requests pro GPU |
| **Continuous Batching** | Neue Requests steigen sofort in den laufenden Batch ein, fertige steigen aus | GPU wartet nie auf den langsamsten Request → hoher Durchsatz |

**Alternativen, die man nennen können sollte:** HF Text Generation Inference
(TGI), TensorRT-LLM (NVIDIA), Ollama/llama.cpp (Einzelnutzer/CPU). In der
Ausschreibung: KServe & OpenShift AI = Plattformen, die vLLM auf Kubernetes
betreiben — nicht Konkurrenz, sondern die Schicht darüber.

**OpenAI-kompatible API:** vLLM spricht dieselbe HTTP-API wie OpenAI
(`/v1/chat/completions`, `/v1/models`). Warum wichtig: Das gesamte
Tool-Ökosystem (SDKs, LiteLLM, Chatbots) funktioniert dann ohne Änderung —
man tauscht nur die URL. Die Uni kann so ChatGPT-artige Dienste auf eigener
Hardware anbieten (Datenschutz!).

## 2. Unser Modell: Qwen3-8B

- Offenes Modell von Alibaba, **8 Mrd. Parameter** → in BF16 (2 Byte/Parameter)
  ≈ **16 GB Gewichte**. Merkregel: `Parameter × 2 Byte = VRAM für Gewichte`.
- **Nicht gated** (kein Lizenzantrag nötig — anders als Meta Llama). Deshalb
  lief unser Download anonym; die `HF_TOKEN`-Warnung war harmlos.
- **Thinking-Modell:** Denkt vor der Antwort in `<think>…</think>` — auf
  „Sag Hallo" kamen 90 Reasoning-Tokens + 1 Wort. Konsequenz: Kosten/Latenz
  steigen; pro Request abschaltbar. Für Benchmarks kontrollieren wir die
  Output-Länge deshalb explizit.
- Bezogen vom **Hugging Face Hub** (das „GitHub für Modelle"), gecacht in
  `HF_HOME=/workspace/.huggingface` auf dem Volume → nur 1× laden.

## 3. Die Server-Flags (unser `start_vllm.sh`) — jede einzeln erklärbar

```
vllm serve Qwen/Qwen3-8B --host 0.0.0.0 --port 8000 --api-key …
  --dtype auto --gpu-memory-utilization 0.95 --max-model-len 8128
```

- **`--host 0.0.0.0`** = auf allen Netzwerk-Interfaces lauschen. Mit
  `127.0.0.1` wäre der Server nur innerhalb des Containers erreichbar —
  der RunPod-Proxy käme nicht ran.
- **`--api-key`** = Backend-Schutz. Der Port hängt öffentlich im Internet
  (Proxy-URL ist erratbar); ohne Key könnte jeder unsere GPU mitbenutzen
  und Prompts mitlesen. **Schichtenmodell:** API-Key sichert das Backend;
  Governance pro Nutzer (Budgets, Quotas) macht später das Gateway (LiteLLM).
- **`--max-model-len 8128`** = maximaler Kontext **pro Request** (Prompt +
  Antwort, in Tokens). Jeder Token im Kontext belegt KV-Cache — ein größeres
  Limit erlaubt längere Dokumente, lässt aber weniger parallele Requests zu.
  Klassischer Kapazitäts-Trade-off.
- **`--gpu-memory-utilization 0.95`** = vLLM reserviert vorab 95 % des VRAM.
  Unsere echte Bilanz auf der A5000 (24 GB), aus dem Startup-Log:

  | Posten | GiB |
  |---|---|
  | Modellgewichte | 15,27 |
  | Aktivierungen (Peak) | 1,19 |
  | CUDA-Graphs | 0,58 |
  | **→ KV-Cache-Pool** | **5,84** |

- **KV-Cache** = zwischengespeicherte Attention-Keys/-Values aller bisherigen
  Tokens eines Requests. Wächst linear mit der Kontextlänge. **Der KV-Cache-
  Pool ist das Parallelitätsbudget der GPU:** Ist er voll, müssen neue
  Requests warten (Queueing) → Latenz steigt. Daraus entsteht das Capacity
  Model.
- **CUDA-Graphs vs. `--enforce-eager`:** CUDA-Graphs zeichnen die
  GPU-Befehlsfolge einmal auf und spielen sie dann ohne CPU-Overhead ab →
  schneller. `--enforce-eager` schaltet das ab (einfacher zu debuggen,
  weniger Startzeit, aber langsamer). Der alte Pod hatte es an — wir messen
  den Unterschied im Benchmark.

## 4. Infrastruktur (RunPod) — was ich heute debuggt habe

- **Ein RunPod-Pod IST ein Docker-Container** (kein Docker-in-Docker möglich).
  Deshalb: vLLM nativ auf dem Pod; Docker/Compose lerne ich lokal.
- **Appliance- vs. Workstation-Image:** `vllm/vllm-openai` = Appliance, der
  einzige Prozess ist der API-Server — kein SSH-Daemon, kein Bootstrap.
  Perfekt für Kubernetes (dort liefert die Plattform `exec`/Logs/Restart) —
  unbrauchbar auf einem nackten Pod. `runpod/pytorch` = Workstation: Start-
  Skript schreibt `PUBLIC_KEY` → `authorized_keys`, startet sshd + Jupyter.
  **Diese Unterscheidung ist ein Kernargument, warum man LLM-Serving auf
  K8s/OpenShift betreibt.**
- **Container-Disk vs. Volume:** Container-Disk ist ephemär (stirbt bei
  Stop/Neustart), Volume (`/workspace`) persistiert bis Terminate. Deshalb
  liegen venv **und** Modell-Cache auf dem Volume → Pod stoppen kostet nichts
  außer Neustart-Zeit. Stop = GPU-Abrechnung endet, Volume bleibt;
  Terminate = alles weg.
- **Netzwerk-Dateisystem:** `/workspace` ist MooseFS im Rechenzentrum —
  darum dauerten pip-Install und Kalt-Imports lang (Tausende kleine Dateien
  übers Netz). Trade-off: Langsamer I/O, dafür überlebt alles.
- **SSH, zwei Wege:** Basis-Proxy (`ssh.runpod.io`) = nur interaktives
  Terminal. Direktes TCP-SSH (exponierter Port 22) = **Exec + Copy + Tunnel**
  (Befehle skripten, `scp`, `ssh -L`-Portweiterleitung). Merke die Dreierliste.
- **Env-Variablen:** RunPod schreibt sie nach `/etc/rp_environment`, gesourct
  nur von interaktiven Shells. Skripte/nicht-interaktives SSH sehen sie NICHT
  → Startskripte setzen kritische Variablen defensiv selbst.
- **tmux:** Terminal-Sessions, die den SSH-Disconnect überleben. Ohne tmux
  stirbt der Server beim Schließen des Laptops. (`Strg+B, D` = raus,
  `tmux attach -t vllm` = rein.)

## 5. Übungsfragen (laut beantworten, dann Musterantwort prüfen)

1. **„Warum vLLM und nicht einfach ein Python-Skript mit Transformers?"**
   → Continuous Batching + PagedAttention: viele parallele Nutzer pro GPU
   statt sequenzieller Abarbeitung; dazu OpenAI-API, Metriken, Produktionsreife.
2. **„Was limitiert die Zahl gleichzeitiger Nutzer auf einer GPU?"**
   → Der KV-Cache-Pool (VRAM minus Gewichte/Overhead). Bei uns 5,84 GiB.
   Jeder Request belegt KV-Cache proportional zu seiner Kontextlänge.
3. **„Was bewirkt `max_model_len` und wie würden Sie es wählen?"**
   → Max. Tokens pro Request; nach Use-Case: Chat kurz (4k reicht oft),
   Dokumentanalyse lang. Größer = weniger Parallelität pro GPU.
4. **„Wie sichern Sie einen öffentlich erreichbaren Inferenz-Endpoint?"**
   → Schichten: API-Key am Backend, Gateway davor für Nutzer-Governance
   (Keys, Budgets, Rate-Limits), plus Monitoring.
5. **„Warum betreibt man so etwas auf Kubernetes/OpenShift?"**
   → Appliance-Images brauchen eine Plattform, die Prozessverwaltung,
   Self-Healing, Logs, Skalierung liefert; auf nackten VMs baut man das
   (wie ich mit tmux/Skripten) von Hand nach.
6. **„8B-Modell — wie viel VRAM und warum?"**
   → ~16 GB in BF16 (2 Byte/Parameter) nur für Gewichte, plus KV-Cache und
   Overhead → 24-GB-GPU ist die Untergrenze; Quantisierung (AWQ/GPTQ) senkt es.
