# Runbook — LLM Inference Lab

Was tun, wenn ein Alert feuert. Jeder Abschnitt gehört zu einer Regel in
[alerts.yml](../monitoring/prometheus/alerts.yml) (die Alerts verlinken
hierher). Format je Vorfall: **Bedeutung → Diagnose → Gegenmaßnahme →
Verifikation.** Ein Runbook ist für den 3-Uhr-nachts-Fall geschrieben:
Befehle zum Kopieren, keine Prosa zum Interpretieren.

---

## ServiceDown

**Bedeutung:** Ein Scrape-Ziel antwortet seit 2 Minuten nicht. Entweder ist
der Prozess tot (Tag-5-Klassiker: SIGHUP außerhalb von tmux), er bootet noch
(Modell lädt — aus Client-Sicht identisch mit tot), oder der Weg dorthin ist
kaputt (Proxy/Netz).

**Diagnose** (auf dem Pod, per SSH — Port vorher frisch abfragen, nie cachen):

```bash
tmux ls                                  # leben die Sessions vllm-small / vllm / gpuexp?
tmux capture-pane -pt =vllm | tail -30   # =name → exaktes Match (Präfix-Falle!)
curl -s localhost:8000/v1/models -H "Authorization: Bearer $VLLM_API_KEY"  # 8B direkt
curl -s localhost:8002/v1/models -H "Authorization: Bearer $VLLM_API_KEY"  # Fallback
curl -s localhost:8888/metrics | head -3 # GPU-Exporter
nvidia-smi                               # OOM-Verdacht: Speicherstand + laufende Prozesse
```

Typische Log-Signaturen: `torch.OutOfMemoryError` (Speicher-Eskalationsleiter
in [governance.md](governance.md) §4), `Address already in use`
(`ss -tlnp`, Port-Kollision), leere tmux-Session (Prozess starb → Log oben
im Scrollback).

**Gegenmaßnahme** — Neustart streng in dieser Reihenfolge (klein → groß,
seriell; Begründung in governance.md §4):

```bash
tmux new -s vllm-small   # bash /workspace/start_vllm_small.sh → "startup complete" abwarten
tmux new -s vllm         # bash /workspace/start_vllm.sh       → "startup complete" abwarten
tmux new -s gpuexp       # python3 /workspace/gpu_exporter.py
```

**Verifikation:** http://localhost:9090/targets → Ziel wieder `up`; ein
Testrequest durchs Gateway (Antwort-`model`-Feld beachten: kam sie vom
Primärmodell oder noch vom Fallback?). Alert löst sich nach dem nächsten
erfolgreichen Scrape auf.

**Merke:** Während des Neustarts fängt die Fallback-Kette den Traffic ab
(429/Fallback statt Totalausfall) — deshalb existiert sie.

---

## TTFT-SLO (TTFTP99AboveSLO)

**Bedeutung:** P99 der Time-to-First-Token liegt seit 5 Minuten über 2,5 s.
Die Concurrency ist über den Knick — neue Requests stauen sich in der
Warteschlange. Das System ist nicht tot, es ist **satt**.

**Diagnose** — zuerst Überlast von Regression unterscheiden (Grafana reicht):

| Befund | Lesart |
|---|---|
| `waiting` > 0, KV-Cache ~100 % | Echte Sättigung — zu viel Last für das Parallelitätsbudget |
| `waiting` = 0, TTFT trotzdem hoch | Keine Überlast → Regression suchen (Modellwechsel? Config? Nachbar auf der GPU?) |
| Nur ein Tenant erzeugt die Last | Governance-Fall: `curl -s http://localhost:4000/key/info …` → Spend/Traffic je Key prüfen |

Belegter Referenzfall (siehe [slo.md](slo.md)): c=32 auf ko-residentem 8B →
Ø 14 aktiv, 20 wartend, KV 100 %, P99 18,1 s — TPOT blieb 73 ms (Läufer
gesund, Wartende leiden).

**Gegenmaßnahmen, nach Eskalationsstufe:**

1. **Sofort (Minuten):** Last drosseln an der Governance-Schicht — rpm/tpm
   des Verursacher-Keys senken (`/key/update`). Die Warteschlange leert sich
   von selbst; nichts muss neu gestartet werden.
2. **Kurzfristig (Stunden):** Parallelitätsbudget zurückholen — Fallback auf
   eigene Instanz/GPU verschieben (gibt dem Primärmodell ~4× KV-Pool, siehe
   governance.md §4) oder Kontextlänge des Angebots senken.
3. **Mittelfristig (Tage):** Kapazität erhöhen — zweite Replika hinter dem
   Gateway (LiteLLM verteilt), oder Quantisierung (AWQ: ~3× KV-Pool auf
   derselben Karte, nur nach Eval-Gate — lernstoff/tag-5.md §6).

**Verifikation:** TTFT-P99-Kurve fällt unter 2,5 s, `waiting` → 0, Alert
wechselt auf resolved. Das 5-Minuten-Ratenfenster braucht ein paar Minuten,
bis der Burst herausgespült ist — ein noch feuernder Alert direkt nach der
Maßnahme ist kein Fehlschlag.

---

## Grundregeln für jeden Vorfall

1. **Erst schauen, dann anfassen** — jede Maßnahme folgt aus einem Befund,
   nicht aus einem Reflex. (Tag 5: acht Fehler, acht verschiedene Ursachen.)
2. **Ein startender Dienst ist aus Client-Sicht tot** — nach jedem Neustart
   „startup complete" abwarten, bevor irgendetwas verifiziert wird.
3. **Ports niemals aus dem Gedächtnis** — TCP-Mappings wechseln pro
   Container-Start; Proxy-URLs sind stabil.
4. **Nach dem Vorfall: Journal.** Was war die Ursache, woran hätte man sie
   schneller erkannt, welche Regel folgt daraus.
