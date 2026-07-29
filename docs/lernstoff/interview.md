# Interview-Simulation — Fragen & Musterantworten (zum Auswendiglernen)

Stand: Mi 29.07. — wird nach jeder Simulationsrunde erweitert.
Antworten bewusst kurz: **Kernsatz zuerst, dann 2–3 Stützpunkte.**

## Antwort-Techniken (wichtiger als jede Einzelantwort)

1. **Flughöhe:** Erst fragen: Wer hört zu? Dekan = kein Fachwort. Techniker = präzise Begriffe.
2. **Szenario-Schema:** Diagnose → Sofortmaßnahme → nachhaltige Lösung. NIE mit Gegenfrage antworten.
3. **Halb-recht-Struktur:** „Da ist etwas dran — präzise gilt: …" (würdigen, dann schärfen).
4. **Modelle verteidigen:** Schwachstellen selbst benennen + zeigen, wie man sie durch Daten ersetzt.
5. **Grenzen zugeben:** Ehrliche „Das kann mein Aufbau nicht"-Antworten sind Stärke-Signale.

---

## F1: „Erklären Sie dem Dekan: Was ist vLLM, warum nicht einfach ChatGPT?"

> vLLM ist die Software, mit der wir Sprachmodelle auf eigenen Servern für viele
> Nutzer gleichzeitig betreiben. Alle Daten — Forschung, Lehre, Studierendendaten —
> bleiben DSGVO-konform im Haus. Und weil wir die Last der ganzen Uni bündeln,
> kostet es einen Bruchteil einzelner Cloud-Abos.

*Merke: Drei Sätze, null Fachwörter, DSGVO muss fallen.*

## F2: „Was ist der KV-Cache und warum limitiert er die Nutzerzahl?"

> Der KV-Cache speichert die Attention-Zwischenwerte aller bisherigen Tokens
> eines Requests im GPU-Speicher — ohne ihn müsste jedes neue Token alles neu
> berechnen. Die Kette: 24 GB VRAM − 16 GB Modellgewichte − Overhead ≈ 6 GB
> KV-Cache-Pool. Jeder aktive Request belegt davon proportional zu seiner
> Kontextlänge — **der Pool ist das Parallelitätsbudget.**

*Merke die Dreiteilung: Speicher(größe) limitiert Parallelität ·
Speicherbandbreite limitiert Geschwindigkeit · Rechenleistung ist beim
Decoding fast nie der Engpass.*

## F3: „P99-TTFT springt auf 4 s, ITL bleibt 22 ms — was ist los, was tun Sie?"

> **Diagnose:** Klassische Überlast-Signatur — Requests stauen sich VOR dem
> ersten Token in der Scheduling-Queue; wer drin ist, wird flüssig bedient.
> **Sofort:** Grafana prüfen (laufende vs. wartende Requests, welche Keys
> erzeugen die Last) → Rate-Limits der größten Verbraucher senken, unkritische
> Anfragen aufs kleinere Modell routen — beides live im Gateway, kein Deployment.
> **Nachhaltig:** Zweite Replika hinter dem Gateway; Alert bei P99 > 1,5 s;
> Runbook dokumentieren.

## F4: „125–200 Studierende pro GPU — verteidigen Sie die Zahl."

> Gemessen: Ein Request belegt bei c=16 ca. 7,2 s (TTFT 1,1 s + 256 Tokens ×
> 24 ms). Angenommen: ein Request pro Studierendem alle 90 s → 8 % Duty Cycle →
> 12,5 Studierende pro Slot → ×16 Slots ≈ 200 (konservativ bei c=8: ~125).
> **Angreifbarste Annahme: die 90 Sekunden** — sie ist explizit ausgewiesen und
> der einzige freie Parameter. Halbiert man sie, halbiert sich die Kapazität.
> Im Pilotbetrieb ersetze ich sie durch echte Nutzungsdaten — das Modell bleibt,
> nur die Konstante wechselt.

## F5: „Bei c=32 liefert die GPU doppelt so viel — warum fahren Sie c=8?"

> Weil wir ein **SLO** versprechen: P99-TTFT unter 2 s. Bei c=32 sind es 3,6 s —
> das Versprechen wäre gebrochen; Durchsatz nützt dem Betreiber, Latenz dem
> Nutzer. Und die c=32-Ökonomie nutzen wir trotzdem: nachts und für Batch-Jobs
> (Korrekturhilfen, Zusammenfassungen) über eine separate Queue. Interaktiv bei
> 8, Batch bei 32 — beide Welten bedient.

## F6: „GPU zeigt 60 % — ‚da ist noch Luft, machen wir die Requests schneller'?"

> Halb richtig: Luft ist da — aber für **mehr parallele Requests**, nicht für
> schnellere einzelne. Decoding ist speicherbandbreiten-limitiert: Die ~20 ms
> pro Token sind die Zeit, die die Gewichte durch den Speicherbus fließen.
> `nvidia-smi util` misst nur „irgendein Kernel aktiv", nicht „Rechenwerke
> ausgelastet". Mehr Durchsatz: ja. Weniger Latenz pro Request: nein.

## F7: „Informatik verbraucht alles, Jura wartet — was tun Sie?"

> **Technisch:** Pro Fakultät ein virtueller API-Key im Gateway mit eigenem
> Budget und Rate-Limit — niemand kann fremde Kontingente verbrauchen.
> **Organisatorisch:** Die Kontingente beschließt ein abgestimmtes Verfahren mit
> den Fakultäten, nicht die IT allein; die IT liefert Transparenz per
> Verbrauchs-Dashboard. **Technik erzwingt die Regeln, Gremien beschließen sie.**

## F8: „Was kann Ihr Lab NICHT, was unsere Produktion können muss?"

> Vier Dinge: (1) Keine Hochverfügbarkeit — eine Instanz, Neustart = Downtime.
> (2) Kein automatisches Skalieren — dafür gibt es Kubernetes/OpenShift.
> (3) Keine Anbindung an die Uni-Identität — API-Keys ersetzen kein SSO/LDAP.
> (4) Ein-Personen-Betrieb — Monitoring ja, aber keine Alarmkette. Das Lab
> zeigt die Konzepte im Kleinen; produktionsreif macht sie Ihre Plattformtechnik.

---

## Auswertung Runde 1 (Mi 29.07.)

| Frage | Punkte | Lücke |
|---|---|---|
| F1 Dekan-Pitch | 7/10 | Fachjargon vor Laien; DSGVO fehlte |
| F2 KV-Cache | 6/10 | **Speicher mit Leistung verwechselt** |
| F3 Überlast-Szenario | 5/10 | Mit Gegenfrage geantwortet statt Maßnahmen |
| F4 Capacity verteidigen | 7/10 | Rechnung perfekt; Kritiker-Teil ignoriert |
| F5 c=8 vs c=32 | 6,5/10 | Wort „SLO" fehlte; Batch-Queue-Zug fehlte |
| F6 60 % Auslastung | 4/10 | Richtiges Nein, falsche Begründung („Puffer") |

**Top-3-Baustellen zum Wiederholen:** (1) Speicher vs. Bandbreite vs.
Rechenleistung — die Dreiteilung aus F2/F6. (2) Szenario-Schema Diagnose →
Sofort → nachhaltig. (3) Publikums-Flughöhe: Dekan-Antworten ohne Fachwörter.
