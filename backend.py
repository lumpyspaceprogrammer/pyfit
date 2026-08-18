#!/usr/bin/env python3
import json
from dataclasses import dataclass
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parent


@dataclass
class Measurements:
    bust: float
    waist: float
    hip: float
    shoulder: float
    napeToWaist: float
    length: float


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def refine_mesh(mesh_params: dict, refinement_text: str) -> dict:
    flare = float(mesh_params.get("flare", 0.35))
    waist_radius = float(mesh_params.get("waistRadius", 0.65))
    top_height = float(mesh_params.get("topHeight", 1.8))
    text = (refinement_text or "").lower()

    if "flare" in text or "wider" in text or "volume" in text:
        flare += 0.12
    if "slim" in text or "tighter" in text or "fitted" in text:
        waist_radius -= 0.05
    if "long" in text or "length" in text:
        top_height += 0.1
    if "short" in text:
        top_height -= 0.1

    return {
        "flare": round(_clamp(flare, 0.15, 1.8), 3),
        "waistRadius": round(_clamp(waist_radius, 0.35, 1.2), 3),
        "topHeight": round(_clamp(top_height, 1.0, 3.0), 3),
    }


def generate_pattern(measurements: Measurements, design_prompt: str) -> dict:
    bust_q = measurements.bust / 4.0
    waist_q = measurements.waist / 4.0
    hip_q = measurements.hip / 4.0
    armhole_depth = measurements.bust / 6.0 + 7.0
    neckline_width = measurements.shoulder / 5.0
    bodice_height = measurements.napeToWaist
    skirt_length = max(20.0, measurements.length - bodice_height)

    front_bodice = [
        [0.0, 0.0],
        [bust_q + 2.0, 0.0],
        [bust_q + 1.5, armhole_depth],
        [waist_q + 1.0, bodice_height],
        [0.0, bodice_height],
    ]
    back_bodice = [
        [0.0, 0.0],
        [bust_q + 1.0, 0.0],
        [bust_q + 0.8, armhole_depth - 1.0],
        [waist_q + 0.5, bodice_height],
        [0.0, bodice_height],
    ]
    skirt_panel = [
        [0.0, 0.0],
        [waist_q + 1.5, 0.0],
        [hip_q + 3.0, skirt_length],
        [0.0, skirt_length],
    ]

    instructions = [
        "Print at 100% scale with no page scaling.",
        "Verify the 50mm test square on the first page before cutting.",
        "Cut one front bodice on fold, two back bodice pieces, and two skirt panels.",
        "Join bodice shoulder and side seams, then attach skirt to waist seam.",
        "Seam allowance is included at 1.5cm on all outer edges.",
    ]

    return {
        "designPrompt": design_prompt or "",
        "measurements": measurements.__dict__,
        "pattern": {
            "units": "cm",
            "necklineWidth": round(neckline_width, 2),
            "armholeDepth": round(armhole_depth, 2),
            "pieces": [
                {"name": "Front Bodice", "points": front_bodice},
                {"name": "Back Bodice", "points": back_bodice},
                {"name": "Skirt Panel", "points": skirt_panel},
            ],
        },
        "instructions": instructions,
    }


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def _send_json(self, payload: dict, status: int = HTTPStatus.OK) -> None:
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _read_json(self) -> dict:
        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length <= 0:
            return {}
        data = self.rfile.read(content_length)
        return json.loads(data.decode("utf-8"))

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/health":
            self._send_json({"status": "ok"})
            return
        return super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/mesh/refine":
            payload = self._read_json()
            mesh_params = payload.get("meshParams") or {}
            refinement_text = payload.get("refinementText") or ""
            updated = refine_mesh(mesh_params, refinement_text)
            self._send_json({"meshParams": updated})
            return

        if parsed.path == "/api/pattern/generate":
            payload = self._read_json()
            try:
                m = payload.get("measurements") or {}
                measurements = Measurements(
                    bust=float(m["bust"]),
                    waist=float(m["waist"]),
                    hip=float(m["hip"]),
                    shoulder=float(m["shoulder"]),
                    napeToWaist=float(m["napeToWaist"]),
                    length=float(m["length"]),
                )
            except (KeyError, TypeError, ValueError):
                self._send_json(
                    {"error": "Invalid measurements payload."},
                    status=HTTPStatus.BAD_REQUEST,
                )
                return
            response = generate_pattern(measurements, payload.get("designPrompt", ""))
            self._send_json(response)
            return

        self._send_json({"error": "Route not found."}, status=HTTPStatus.NOT_FOUND)


def run() -> None:
    host, port = "0.0.0.0", 8000
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Serving PRINT YOUR FIT at http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run()
