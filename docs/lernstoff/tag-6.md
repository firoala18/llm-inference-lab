# Lernstoff Tag 6 — Monitoring: Das System meldet sich selbst (Sa 01.08.2026)

Die Antwort auf die wichtigste Frage von Tag 5 („Womit bemerkt man den
lautlosen Prozess-Tod?"): heute gebaut, live bewiesen — der erste Alarm
dieser Woche kam vom System, nicht von uns.

---

## 1. Die Architektur (in einem Satz pro Baustein)

| Baustein | Rolle | Merksatz |
|---|---|---|
| **Prometheus** | Sammler + Regelwerk | Holt alle 15s `/metrics` von jedem Ziel (Pull), speichert Historie, wertet Alerts aus |
| **Grafana** | Anzeige | Malt nur — Alarm-Logik gehört in Prometheus (versionierbare YAML), nicht ins Dashboard |
| **gpu_exporter.py** | Lückenfüller | vLLM instrumentiert sich selbst; nur die GPU-Hardware braucht einen eigenen Exporter (~40 Zeilen stdlib; Produktion: DCGM) |
| **Provisionierung** | Dashboards als Code | Datasource + Dashboard als Dateien im Git — jeder `git clone` bekommt dasselbe Monitoring, nichts ist zusammengeklickt |

## 2. Pull vs. Push — der Kern des Tages

**„Pull macht Abwesenheit messbar."** Beim Push-Modell ist Stille mehrdeutig
(tot? Netz? nichts los?). Beim Pull-Modell stellt Prometheus die Frage selbst —
bleibt die Antwort aus, ist das ein aktiv festgestellter Fehler. Die
`up`-Metrik erzeugt **Prometheus**, nicht das Ziel: Ein toter Dienst kann sie
weder fälschen noch vergessen. Damit ist Fehler Nr. 5 von Tag 5 (lautloser
SIGHUP-Tod) strukturell erledigt: maximal 2 Minuten unbemerkt.

## 3. Alert-Design: warum `for: 2m`

Ohne `for:` alarmiert EIN fehlgeschlagener Scrape (Netz-Hickser, Neustart).
Wer nachts dreimal grundlos geweckt wird, stellt die Alarme stumm — und
verpasst dann den echten Ausfall. **Alert-Müdigkeit ist gefährlicher als
2 Minuten Verzögerung.** `for:` tauscht Erkennungsgeschwindigkeit gegen
Signalqualität. (Gleiche Denkfigur wie Healthcheck vs. plain `depends_on`:
Robustheit entsteht durch bewusstes Warten.)

## 4. PromQL-Grundmuster (reicht fürs Gespräch)

```promql
rate(vllm:generation_tokens_total[1m])          # Zähler → Rate: tok/s
histogram_quantile(0.99,
  sum by (le, model_name)
  (rate(vllm:time_to_first_token_seconds_bucket[5m])))   # P99 der letzten 5 Min
```

- Counter zählen nur hoch → immer durch `rate()` in „pro Sekunde" übersetzen.
- Histogramme liegen als `_bucket`-Zähler vor; `histogram_quantile` baut
  daraus Perzentile. `le` = Bucket-Grenze („less or equal").
- Das 5-Min-Fenster glättet UND verzögert: Ein Burst wirkt ~5 Min nach —
  deshalb löst sich der Alert nach Lastende erst verspätet auf.

## 5. Der Härtetest — Überlast anatomisch (c=32 gegen ko-residentes 8B)

Gemessen: **Ø 14 aktiv, Peak 18** (Rechenweg: 334 tok/s ÷ 23,4 tok/s je
Request), **20 wartend, KV-Cache 100 %**, TTFT P99 **18,1 s**, TPOT P99 **73 ms**.

1. **Überlast trifft die Wartenden, nicht die Laufenden.** vLLM schützt
   aktive Requests (TPOT gesund) und parkt den Rest in der Queue (TTFT
   explodiert, denn TTFT enthält die Wartezeit). → TTFT = Frühwarn-SLI,
   TPOT = Gesundheits-SLI.
2. **Preis der Ko-Residenz end-to-end:** Solo 772 tok/s (P99 3,6 s) →
   ko-resident 334 tok/s (P99 18,1 s) bei identischer Last.
3. **Kosten sind blind für Qualität:** Der überlastete Lauf lieferte exakt
   den Capacity-Model-Preis ($0,42/M) — bei fünffach gerissenem SLO. Erst
   Kosten-Panel + SLO-Panel zusammen beschreiben den Zustand.
4. Antwort auf die 96-%-Frage von Tag 5: 96 % VRAM sagt NICHTS über
   Kapazität — die steckt im KV-Pool-Rest. Ko-resident: ~14 parallele
   Chat-Requests statt ~32 solo.

## 6. Die drei Fehler des Tages (und ihre Regeln)

| Fehler | Regel |
|---|---|
| LiteLLM-Target `401 Unauthorized` | LiteLLM schützt `/metrics` mit API-Auth, vLLM nur `/v1/*` — Prometheus bekommt den Token per `credentials_file` aus gitignorierter Datei, nie in die committete YAML |
| Zwei Panels „No data" | vLLMs V1-Engine hat Metriken umbenannt (`kv_cache_usage_perc`, `inter_token_latency_seconds`) — **Dashboards gegen die echte `/metrics`-Ausgabe verifizieren, nicht gegen Doku/Gedächtnis** |
| Struktur/Secret-Trennung, 3. Wiederholung | config.yaml↔.env, prometheus.yml↔pod-targets.json (File SD), authorization↔credentials_file — ein Muster, drei Ebenen |

Dazu Wiederholung: Geänderter *Inhalt* gemounteter Dateien → `restart` reicht;
geänderte Service-Definition (env/Ports/Mounts) → `--force-recreate`.

## 7. Übungsfragen

1. **„Wie erkennen Sie einen abgestürzten Modell-Server?"** → Pull-Monitoring:
   Prometheus scrapt alle 15s; bleibt der Scrape aus, fällt `up` auf 0 und
   nach 2 Min Entprellung feuert ServiceDown. Ein toter Prozess kann `up`
   nicht fälschen — die Metrik entsteht beim Sammler.
2. **„Ihr P99-TTFT-Alarm feuert. Erste Handgriffe?"** → Grafana: `waiting` > 0
   und KV-Cache voll? Dann Sättigung → Verursacher-Tenant identifizieren,
   Rate-Limit senken (Gateway, ohne Neustart). `waiting` = 0? Dann Regression
   suchen. (docs/runbook.md)
3. **„Warum P99 statt Mittelwert im SLO?"** → Der Mittelwert versteckt die
   Opfer: Er kann gesund aussehen, während jeder hundertste Nutzer unbrauchbar
   bedient wird. SLOs definieren das schlechteste akzeptierte Erlebnis.
4. **„Ihr Dashboard zeigt 96 % GPU-Speicher. Ist das ein Problem?"** → Nein —
   statische Reservierung durch vLLM beim Start, unabhängig von Last
   (Auslastung 0 % daneben beweist es). Kapazität misst der KV-Cache-Füllstand
   und die Warteschlange, nicht die VRAM-Prozente.
5. **„Was kostet ein Token bei Ihnen?"** → Falsch gestellte Frage: Kosten pro
   Token sind eine Auslastungseigenschaft. Sequenziell c=1: ~$8,50/M.
   Gesättigt: $0,42/M — bei gerissenem SLO. Der ehrliche Preis ist der am
   SLO-konformen Betriebspunkt (c=8): $0,41/M.
