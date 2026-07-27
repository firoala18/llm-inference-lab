# Lernjournal — LLM Inference Lab

Format pro Tag: **Gebaut / Gelernt / Schiefgegangen** (je 1–3 Zeilen).

## Mo 27.07.2026 — Setup

- **Gebaut:** Repo-Grundgerüst, Spec + Plan committed, Repo auf GitHub. Docker Desktop verifiziert, gh installiert und eingeloggt, SSH-Key erzeugt. Erster Chat-Response von Qwen3-8B auf der A5000 (vLLM 0.26.0, via RunPod-Proxy, API-Key-Auth aktiv).
- **Gelernt:** RunPod-Pods sind selbst Container — kein Docker-in-Docker; vLLM läuft nativ auf dem Pod, Docker lerne ich lokal (Gateway/Monitoring via Compose). Der Pod nutzt das vllm/vllm-openai-Image: vLLM startet automatisch als Container-Entrypoint. Qwen3-8B ist ein Thinking-Modell — 90 Reasoning-Tokens für ein „Hallo!". Env-Var-Templating: `sk-$RUNPOD_POD_ID` wurde zum echten Key expandiert.
- **Schiefgegangen:** SSH „Permission denied" — Key war als Fingerprint statt als voller Public Key hinterlegt und fehlte in den Account-Settings; das vllm-openai-Image bringt zudem evtl. keinen sshd mit. Diagnose läuft; Fallback: Pod auf RunPod-PyTorch-Template umstellen (Volume + HF-Cache bleiben erhalten).
