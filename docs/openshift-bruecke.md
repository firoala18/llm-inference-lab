# Die OpenShift-Brücke — was unser k3d-Lab mit OpenShift (AI) zu tun hat

Unser Lab läuft auf k3d (k3s in Docker). OpenShift ist Red Hats
Kubernetes-Distribution — **derselbe Kern, dieselben Objekte, dieselben
YAMLs**, plus Unternehmens-Schicht obendrauf. Diese Seite übersetzt.

## Begriffs-Übersetzung

| Unser Lab (k3d/K8s) | OpenShift | Anmerkung |
|---|---|---|
| Namespace `llm-lab` | **Project** | Project = Namespace + Annotations/Quotas; `oc new-project` |
| `kubectl` | **`oc`** | Superset: `oc` kann alles von kubectl + Login/Projects/Routes |
| Deployment / Service / ConfigMap / Secret / PVC | identisch | unsere Manifeste laufen unverändert |
| Ingress (haben wir via port-forward umgangen) | **Route** | OpenShifts älteres, integriertes Nord-Süd-Routing |
| readiness-/livenessProbe | identisch | Kernkonzept, keine Übersetzung nötig |
| ArgoCD (selbst installiert) | **OpenShift GitOps** | dasselbe ArgoCD, als Operator paketiert und supportet |
| Prometheus + Grafana (selbst verdrahtet) | **eingebaute Monitoring-Stack** | Cluster- und User-Workload-Monitoring ab Werk, gleiche PromQL |
| Docker-Images von ghcr.io | interne **Registry + ImageStreams** | optional; externe Images gehen genauso |
| — | **SecurityContextConstraints (SCC)** | OpenShift-Spezifikum: Container laufen per Default NICHT als root — unser postgres/litellm-Setup müsste ggf. UIDs anpassen. Der klassische Stolperstein bei Migrationen. |
| — | **Operators / OperatorHub** | Betriebswissen als Software (GPU-Operator, GitOps, Monitoring …) |

## Wo unser Stack in OpenShift AI andockt

OpenShift AI (RHOAI) ist Red Hats ML-Plattform auf OpenShift. Die Zuordnung
unserer Lab-Bausteine:

| Unser Lab | OpenShift AI |
|---|---|
| vLLM per tmux/Skript auf dem GPU-Pod | **KServe ServingRuntime mit vLLM-Backend** — dasselbe vLLM, aber als deklarativ verwaltete InferenceService-Ressource mit Autoscaling und Canary-Rollouts |
| unser `gpu_exporter.py` (~40 Zeilen nvidia-smi) | **NVIDIA DCGM-Exporter** via GPU-Operator — gleiche Idee, produktisiert |
| Startreihenfolge-Disziplin, Readiness von Hand | Probes + Operator-Lifecycle — die Plattform erzwingt, was wir manuell gelernt haben |
| LiteLLM-Gateway als Deployment | identisch — plus Route, SCC-konformes Image, HPA |
| ArgoCD-Application auf `k8s/` | OpenShift-GitOps-Application auf dasselbe Repo |

## Der eine Satz fürs Gespräch

> „Alles, was ich im Lab von Hand gebaut habe — Serving, Probes, Monitoring,
> GitOps — existiert in OpenShift als verwaltete, supportete Variante
> desselben Konzepts. Ich habe die Handarbeit gemacht, um zu verstehen,
> was mir die Plattform abnimmt — und was schiefgeht, wenn sie es nicht tut."

Konkrete Migrationsschritte für unser Lab → OpenShift: (1) Manifeste
unverändert anwenden, Namespace→Project; (2) port-forward durch Route
ersetzen; (3) SCC-Verträglichkeit der Images prüfen (non-root); (4) Secret
durch SealedSecret/ExternalSecret ersetzen; (5) vLLM von Pod-Skript auf
KServe-InferenceService heben; (6) ArgoCD-Application in OpenShift GitOps
importieren — Repo und Pfad bleiben gleich.
