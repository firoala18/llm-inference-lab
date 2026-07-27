# Lernjournal — LLM Inference Lab

Format pro Tag: **Gebaut / Gelernt / Schiefgegangen** (je 1–3 Zeilen).

## Mo 27.07.2026 — Setup

- **Gebaut:** Repo-Grundgerüst, Spec + Plan committed, Repo auf GitHub. Docker Desktop verifiziert, gh installiert und eingeloggt, SSH-Key erzeugt. Erster Chat-Response von Qwen3-8B auf der A5000 (vLLM 0.26.0, via RunPod-Proxy, API-Key-Auth aktiv).
- **Gelernt:** RunPod-Pods sind selbst Container — kein Docker-in-Docker; vLLM läuft nativ auf dem Pod, Docker lerne ich lokal (Gateway/Monitoring via Compose). Der Pod nutzt das vllm/vllm-openai-Image: vLLM startet automatisch als Container-Entrypoint. Qwen3-8B ist ein Thinking-Modell — 90 Reasoning-Tokens für ein „Hallo!". Env-Var-Templating: `sk-$RUNPOD_POD_ID` wurde zum echten Key expandiert.
- **Schiefgegangen:** SSH „Permission denied" — Key war als Fingerprint statt als voller Public Key hinterlegt und fehlte in den Account-Settings; das vllm-openai-Image bringt zudem keinen sshd/Bootstrap mit (Appliance-Image, Entrypoint = API-Server). Der ssh.runpod.io-Basis-Proxy kann außerdem nur interaktive Terminals — kein Exec, kein scp, keine Tunnel.

### Nachtrag (Abend) — Tag-1-Ziel erreicht

- **Gebaut:** Alten Pod ersetzt: `llm-lab-a5000` (A5000, runpod/pytorch-Image, TCP 22 + HTTP 8000/8888, 50-GB-Volume) per RunPod-API provisioniert. Auf dem Pod (manuell, per SSH): venv auf `/workspace` (16 GB, restart-fest), `pip install vllm` (0.26.0), Qwen3-8B (16 GB → HF-Cache auf Volume) via `start_vllm.sh` in tmux gestartet. Beweis: `/v1/models` antwortet durch den RunPod-Proxy mit API-Key-Auth.
- **Gelernt:** (1) Direktes TCP-SSH = Exec + Copy + Tunnel — der Proxy kann nur Terminal. (2) RunPod schreibt Docker-Env nach `/etc/rp_environment`, gesourct nur in interaktiven Shells — Startskripte müssen Env defensiv selbst setzen. (3) vLLM-Speicherbilanz auf 24 GB: 15,27 GiB Gewichte + 1,19 Aktivierung + 0,58 CUDA-Graphs → 5,84 GiB KV-Cache-Pool = das Parallelitätsbudget für morgen. (4) Netzwerk-Volume (MooseFS): langsame Installation/Kalt-Imports, dafür überlebt alles Stop/Start. (5) Appliance-Image (vllm-openai) passt zu K8s mit `kubectl exec`; auf nacktem Pod braucht man Workstation-Image + eigene Prozessverwaltung (tmux).
