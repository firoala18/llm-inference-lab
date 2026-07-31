#!/usr/bin/env python3
"""Minimal GPU exporter: nvidia-smi -> Prometheus text format on :8888.

vLLM exports engine metrics (tokens, latency, KV cache) but not the GPU
hardware itself. This fills the gap with zero dependencies (stdlib only) —
in production you would run NVIDIA's DCGM exporter instead; this is the
same idea small enough to read in one sitting.

Run on the pod (own tmux session):  python3 /workspace/gpu_exporter.py
Scraped by Prometheus via the RunPod proxy on port 8888.
"""
import http.server
import subprocess

QUERY = "utilization.gpu,memory.used,memory.total,power.draw,temperature.gpu"


def collect() -> str:
    out = subprocess.check_output(
        ["nvidia-smi", f"--query-gpu={QUERY}", "--format=csv,noheader,nounits"],
        text=True, timeout=5,
    )
    lines = [
        "# HELP gpu_utilization_percent SM utilization as reported by nvidia-smi",
        "# TYPE gpu_utilization_percent gauge",
    ]
    for idx, row in enumerate(out.strip().splitlines()):
        util, mem_used, mem_total, power, temp = (v.strip() for v in row.split(","))
        label = f'{{gpu="{idx}"}}'
        lines += [
            f"gpu_utilization_percent{label} {util}",
            f"gpu_memory_used_mib{label} {mem_used}",
            f"gpu_memory_total_mib{label} {mem_total}",
            f"gpu_power_draw_watts{label} {power}",
            f"gpu_temperature_celsius{label} {temp}",
        ]
    return "\n".join(lines) + "\n"


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/metrics":
            self.send_response(404)
            self.end_headers()
            return
        try:
            body = collect().encode()
        except Exception as exc:  # nvidia-smi missing/hung -> visible 500, not silence
            self.send_response(500)
            self.end_headers()
            self.wfile.write(str(exc).encode())
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; version=0.0.4")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # keep the tmux pane quiet
        pass


if __name__ == "__main__":
    print("gpu_exporter listening on :8888/metrics")
    http.server.HTTPServer(("0.0.0.0", 8888), Handler).serve_forever()
