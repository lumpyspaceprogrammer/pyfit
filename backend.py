#!/usr/bin/env python3
import base64
import hashlib
import hmac
import json
import math
import os
import re
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
GENERATED_DIR = DATA_DIR / "generated"
DB_PATH = DATA_DIR / "pyfit.db"

TOKEN_TTL_DAYS = 30
PBKDF2_ROUNDS = 200_000


@dataclass
class Measurements:
    bust: float
    waist: float
    hip: float
    shoulder: float
    napeToWaist: float
    length: float


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_now_iso() -> str:
    return _utc_now().isoformat()


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _decode_image_data_url(image_data_url: str) -> tuple[str, bytes]:
    if not isinstance(image_data_url, str):
        raise ValueError("imageDataUrl must be a string.")
    match = re.match(r"^data:image/(png|jpeg|jpg|webp);base64,(.+)$", image_data_url, re.IGNORECASE)
    if not match:
        raise ValueError("imageDataUrl must be a valid base64 data URL (png, jpg, jpeg, webp).")
    ext = match.group(1).lower()
    ext = "jpg" if ext == "jpeg" else ext
    try:
        raw = base64.b64decode(match.group(2), validate=True)
    except Exception as exc:
        raise ValueError("imageDataUrl contains invalid base64 data.") from exc
    if len(raw) > 10 * 1024 * 1024:
        raise ValueError("imageDataUrl is too large (max 10MB).")
    return ext, raw


def _write_generated_file(kind: str, ext: str, content: bytes) -> str:
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    allowed_kinds = {"source", "render", "pattern"}
    allowed_exts = {"png", "jpg", "webp", "svg", "pdf"}
    if kind not in allowed_kinds or ext not in allowed_exts:
        raise ValueError("Invalid generated file type.")
    safe_name = f"{kind}-{secrets.token_hex(16)}.{ext}"
    path = (GENERATED_DIR / safe_name).resolve()
    generated_root = GENERATED_DIR.resolve()
    if generated_root not in path.parents:
        raise ValueError("Invalid generated filename.")
    path.write_bytes(content)
    return f"/data/generated/{safe_name}"


def _svg_escape(text: str) -> str:
    return (
        (text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def _layout_pattern_pieces_mm(pattern: dict) -> tuple[list[dict], float, float]:
    pieces = pattern.get("pieces") or []
    placed = []
    cursor_x = 0.0
    max_height = 0.0
    for piece in pieces:
        pts_cm = piece.get("points") or []
        if len(pts_cm) < 2:
            continue
        xs = [float(p[0]) for p in pts_cm]
        ys = [float(p[1]) for p in pts_cm]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        width_mm = max(10.0, (max_x - min_x) * 10.0)
        height_mm = max(10.0, (max_y - min_y) * 10.0)
        shifted = [
            [((float(x) - min_x) * 10.0) + cursor_x + 15.0, ((float(y) - min_y) * 10.0) + 15.0]
            for x, y in pts_cm
        ]
        placed.append(
            {
                "name": piece.get("name") or "Pattern Piece",
                "points_mm": shifted,
                "bbox": [cursor_x + 15.0, 15.0, cursor_x + 15.0 + width_mm, 15.0 + height_mm],
            }
        )
        cursor_x += width_mm + 30.0
        max_height = max(max_height, height_mm)
    total_w = max(40.0, cursor_x + 15.0)
    total_h = max(40.0, max_height + 30.0)
    return placed, total_w, total_h


def generate_mannequin_free_svg(pattern: dict, design_prompt: str) -> bytes:
    pieces, total_w, total_h = _layout_pattern_pieces_mm(pattern)
    width = total_w + 30.0
    height = total_h + 30.0
    rows = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.2f}mm" height="{height:.2f}mm" viewBox="0 0 {width:.2f} {height:.2f}">',
        '<rect x="0" y="0" width="100%" height="100%" fill="#ffffff"/>',
        '<text x="10" y="14" font-family="Arial, sans-serif" font-size="6" fill="#111">Mannequin-free garment layout</text>',
        f'<text x="10" y="22" font-family="Arial, sans-serif" font-size="4" fill="#444">{_svg_escape(design_prompt[:120])}</text>',
    ]
    for piece in pieces:
        pts = " ".join(f"{x+10:.2f},{y+10:.2f}" for x, y in piece["points_mm"])
        rows.append(f'<polygon points="{pts}" fill="none" stroke="#d946ef" stroke-width="0.8"/>')
        label_x = piece["bbox"][0] + 10.0
        label_y = piece["bbox"][1] + 6.0
        rows.append(
            f'<text x="{label_x:.2f}" y="{label_y:.2f}" font-family="Arial, sans-serif" font-size="4" fill="#111">{_svg_escape(piece["name"])}</text>'
        )
    rows.append("</svg>")
    return "\n".join(rows).encode("utf-8")


def _pdf_escape(text: str) -> str:
    return (text or "").replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _mm_to_pt(mm: float) -> float:
    return mm * 72.0 / 25.4


def _build_pdf(pages_commands: list[str], page_w_mm: float = 210.0, page_h_mm: float = 297.0) -> bytes:
    page_w_pt = _mm_to_pt(page_w_mm)
    page_h_pt = _mm_to_pt(page_h_mm)
    object_count = 3 + len(pages_commands) * 2
    objects = [""] * (object_count + 1)

    objects[1] = "<< /Type /Catalog /Pages 2 0 R >>"
    page_ids = []
    for i in range(len(pages_commands)):
        page_ids.append(5 + i * 2)
    kids = " ".join(f"{page_id} 0 R" for page_id in page_ids)
    objects[2] = f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>"
    objects[3] = "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"

    for i, commands in enumerate(pages_commands):
        content_id = 4 + i * 2
        page_id = 5 + i * 2
        stream = commands.encode("utf-8")
        objects[content_id] = f"<< /Length {len(stream)} >>\nstream\n{commands}\nendstream"
        objects[page_id] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {page_w_pt:.3f} {page_h_pt:.3f}] "
            f"/Resources << /Font << /F1 3 0 R >> >> /Contents {content_id} 0 R >>"
        )

    buffer = bytearray()
    buffer.extend(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0] * (object_count + 1)
    for i in range(1, object_count + 1):
        offsets[i] = len(buffer)
        buffer.extend(f"{i} 0 obj\n".encode("utf-8"))
        buffer.extend(objects[i].encode("utf-8"))
        buffer.extend(b"\nendobj\n")

    xref_start = len(buffer)
    buffer.extend(f"xref\n0 {object_count + 1}\n".encode("utf-8"))
    buffer.extend(b"0000000000 65535 f \n")
    for i in range(1, object_count + 1):
        buffer.extend(f"{offsets[i]:010d} 00000 n \n".encode("utf-8"))
    buffer.extend(
        (
            "trailer\n"
            f"<< /Size {object_count + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_start}\n%%EOF\n"
        ).encode("utf-8")
    )
    return bytes(buffer)


def generate_tiled_pattern_pdf(pattern: dict, design_prompt: str, measurements: Measurements) -> bytes:
    pieces, total_w_mm, total_h_mm = _layout_pattern_pieces_mm(pattern)
    printable_w_mm = 190.0
    printable_h_mm = 277.0
    pages_x = max(1, math.ceil(total_w_mm / printable_w_mm))
    pages_y = max(1, math.ceil(total_h_mm / printable_h_mm))
    total_pages = pages_x * pages_y
    page_w_mm = 210.0
    page_h_mm = 297.0
    margin_x_mm = 10.0
    margin_y_mm = 10.0
    pages = []

    for py in range(pages_y):
        for px in range(pages_x):
            commands = []
            commands.append("0 0 0 RG 0.6 w")
            commands.append(
                f"{_mm_to_pt(margin_x_mm):.3f} {_mm_to_pt(margin_y_mm):.3f} "
                f"{_mm_to_pt(printable_w_mm):.3f} {_mm_to_pt(printable_h_mm):.3f} re S"
            )
            commands.append("0.88 0.88 0.88 RG 0.2 w")
            for gx in range(0, int(printable_w_mm) + 1, 10):
                x_pt = _mm_to_pt(margin_x_mm + gx)
                commands.append(
                    f"{x_pt:.3f} {_mm_to_pt(margin_y_mm):.3f} m {x_pt:.3f} {_mm_to_pt(margin_y_mm + printable_h_mm):.3f} l S"
                )
            for gy in range(0, int(printable_h_mm) + 1, 10):
                y_pt = _mm_to_pt(margin_y_mm + gy)
                commands.append(
                    f"{_mm_to_pt(margin_x_mm):.3f} {y_pt:.3f} m {_mm_to_pt(margin_x_mm + printable_w_mm):.3f} {y_pt:.3f} l S"
                )

            tile_label = (
                f"Page {py * pages_x + px + 1}/{total_pages}  Tile {chr(65 + py)}{px + 1}  "
                f"Prompt: {design_prompt[:40]}"
            )
            commands.append("BT /F1 9 Tf 0 0 0 rg")
            commands.append(f"{_mm_to_pt(12):.3f} {_mm_to_pt(287):.3f} Td ({_pdf_escape(tile_label)}) Tj ET")

            measure_line = (
                f"B:{measurements.bust:.1f} W:{measurements.waist:.1f} H:{measurements.hip:.1f} "
                f"Sh:{measurements.shoulder:.1f} N-W:{measurements.napeToWaist:.1f} L:{measurements.length:.1f} cm"
            )
            commands.append("BT /F1 8 Tf 0 0 0 rg")
            commands.append(f"{_mm_to_pt(12):.3f} {_mm_to_pt(281):.3f} Td ({_pdf_escape(measure_line)}) Tj ET")
            commands.append("1 0.27 0.94 RG 0.9 w")

            tile_x0 = px * printable_w_mm
            tile_x1 = tile_x0 + printable_w_mm
            tile_y0 = py * printable_h_mm
            tile_y1 = tile_y0 + printable_h_mm

            for piece in pieces:
                bx0, by0, bx1, by1 = piece["bbox"]
                if bx1 < tile_x0 or bx0 > tile_x1 or by1 < tile_y0 or by0 > tile_y1:
                    continue
                pts = piece["points_mm"]
                if len(pts) < 2:
                    continue
                transformed = []
                for x_mm, y_mm in pts:
                    local_x = x_mm - tile_x0 + margin_x_mm
                    local_y = y_mm - tile_y0 + margin_y_mm
                    pdf_x = _mm_to_pt(local_x)
                    pdf_y = _mm_to_pt(page_h_mm - local_y)
                    transformed.append((pdf_x, pdf_y))
                commands.append(f"{transformed[0][0]:.3f} {transformed[0][1]:.3f} m")
                for x_pt, y_pt in transformed[1:]:
                    commands.append(f"{x_pt:.3f} {y_pt:.3f} l")
                commands.append("h S")
            pages.append("\n".join(commands))

    return _build_pdf(pages)


def _password_hash(password: str, salt_b64: str) -> str:
    salt = base64.b64decode(salt_b64.encode("utf-8"))
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ROUNDS)
    return base64.b64encode(digest).decode("utf-8")


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


def db_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    with db_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                password_salt TEXT NOT NULL,
                credits INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS auth_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                token_hash TEXT UNIQUE NOT NULL,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                design_prompt TEXT NOT NULL,
                measurements_json TEXT NOT NULL,
                pattern_json TEXT NOT NULL,
                instructions_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS pipeline_assets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                design_prompt TEXT NOT NULL,
                source_image_path TEXT NOT NULL,
                render_svg_path TEXT NOT NULL,
                pdf_path TEXT NOT NULL,
                measurements_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS payment_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                tier_name TEXT NOT NULL,
                credits INTEGER NOT NULL,
                amount_cents INTEGER NOT NULL,
                currency TEXT NOT NULL DEFAULT 'usd',
                status TEXT NOT NULL,
                stripe_session_id TEXT UNIQUE,
                checkout_url TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );
            """
        )


def issue_token(conn: sqlite3.Connection, user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    token_hash = _sha256(token)
    expires_at = (_utc_now() + timedelta(days=TOKEN_TTL_DAYS)).isoformat()
    conn.execute(
        """
        INSERT INTO auth_tokens (user_id, token_hash, expires_at, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (user_id, token_hash, expires_at, _utc_now_iso()),
    )
    conn.commit()
    return token


def parse_bearer_token(headers) -> str | None:
    auth = headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    return auth[7:].strip()


def get_user_from_token(conn: sqlite3.Connection, token: str | None):
    if not token:
        return None
    token_hash = _sha256(token)
    row = conn.execute(
        """
        SELECT u.id, u.email, u.credits, t.expires_at
        FROM auth_tokens t
        JOIN users u ON u.id = t.user_id
        WHERE t.token_hash = ?
        """,
        (token_hash,),
    ).fetchone()
    if not row:
        return None
    try:
        expires = datetime.fromisoformat(row["expires_at"])
        if expires <= _utc_now():
            return None
    except ValueError:
        return None
    return {"id": row["id"], "email": row["email"], "credits": row["credits"]}


def create_stripe_checkout_session(
    *,
    user_id: int,
    tier_name: str,
    credits: int,
    amount_cents: int,
    success_url: str,
    cancel_url: str,
) -> dict:
    secret_key = os.environ.get("STRIPE_SECRET_KEY")
    if not secret_key:
        raise RuntimeError("Stripe is not configured. Set STRIPE_SECRET_KEY.")

    payload = {
        "mode": "payment",
        "success_url": success_url,
        "cancel_url": cancel_url,
        "client_reference_id": str(user_id),
        "metadata[user_id]": str(user_id),
        "metadata[tier_name]": tier_name,
        "metadata[credits]": str(credits),
        "line_items[0][price_data][currency]": "usd",
        "line_items[0][price_data][product_data][name]": f"{tier_name} ({credits} credits)",
        "line_items[0][price_data][unit_amount]": str(amount_cents),
        "line_items[0][quantity]": "1",
    }

    request = Request(
        "https://api.stripe.com/v1/checkout/sessions",
        data=urlencode(payload).encode("utf-8"),
        method="POST",
        headers={"Authorization": "Bearer " + secret_key},
    )
    with urlopen(request, timeout=20) as response:
        raw = json.loads(response.read().decode("utf-8"))
    return {"id": raw["id"], "url": raw["url"]}


def fetch_stripe_checkout_session(session_id: str) -> dict:
    secret_key = os.environ.get("STRIPE_SECRET_KEY")
    if not secret_key:
        raise RuntimeError("Stripe is not configured. Set STRIPE_SECRET_KEY.")
    request = Request(
        f"https://api.stripe.com/v1/checkout/sessions/{session_id}",
        method="GET",
        headers={"Authorization": "Bearer " + secret_key},
    )
    with urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


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
        try:
            return json.loads(data.decode("utf-8"))
        except json.JSONDecodeError:
            return {}

    def _require_auth_user(self, conn: sqlite3.Connection):
        token = parse_bearer_token(self.headers)
        user = get_user_from_token(conn, token)
        if not user:
            self._send_json({"error": "Unauthorized"}, status=HTTPStatus.UNAUTHORIZED)
            return None
        return user

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/api/health":
            self._send_json({"status": "ok"})
            return

        if parsed.path == "/api/auth/me":
            with db_conn() as conn:
                user = self._require_auth_user(conn)
                if not user:
                    return
                self._send_json({"user": user})
            return

        if parsed.path == "/api/patterns":
            with db_conn() as conn:
                user = self._require_auth_user(conn)
                if not user:
                    return
                rows = conn.execute(
                    """
                    SELECT id, design_prompt, measurements_json, pattern_json, instructions_json, created_at
                    FROM patterns
                    WHERE user_id = ?
                    ORDER BY id DESC
                    LIMIT 50
                    """,
                    (user["id"],),
                ).fetchall()
                patterns = []
                for row in rows:
                    patterns.append(
                        {
                            "id": row["id"],
                            "designPrompt": row["design_prompt"],
                            "measurements": json.loads(row["measurements_json"]),
                            "pattern": json.loads(row["pattern_json"]),
                            "instructions": json.loads(row["instructions_json"]),
                            "createdAt": row["created_at"],
                        }
                    )
                self._send_json({"patterns": patterns})
            return

        return super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        payload = self._read_json()

        if parsed.path == "/api/auth/signup":
            email = (payload.get("email") or "").strip().lower()
            password = payload.get("password") or ""
            if not email or len(password) < 8:
                self._send_json(
                    {"error": "Email is required and password must be at least 8 chars."},
                    status=HTTPStatus.BAD_REQUEST,
                )
                return
            salt = base64.b64encode(os.urandom(16)).decode("utf-8")
            password_hash = _password_hash(password, salt)
            with db_conn() as conn:
                try:
                    conn.execute(
                        """
                        INSERT INTO users (email, password_hash, password_salt, created_at)
                        VALUES (?, ?, ?, ?)
                        """,
                        (email, password_hash, salt, _utc_now_iso()),
                    )
                    conn.commit()
                except sqlite3.IntegrityError:
                    self._send_json(
                        {"error": "An account with this email already exists."},
                        status=HTTPStatus.CONFLICT,
                    )
                    return
                user = conn.execute(
                    "SELECT id, email, credits FROM users WHERE email = ?", (email,)
                ).fetchone()
                token = issue_token(conn, int(user["id"]))
                self._send_json(
                    {"token": token, "user": {"id": user["id"], "email": user["email"], "credits": user["credits"]}}
                )
            return

        if parsed.path == "/api/auth/login":
            email = (payload.get("email") or "").strip().lower()
            password = payload.get("password") or ""
            with db_conn() as conn:
                user = conn.execute(
                    "SELECT id, email, password_hash, password_salt, credits FROM users WHERE email = ?",
                    (email,),
                ).fetchone()
                if not user:
                    self._send_json({"error": "Invalid email or password."}, status=HTTPStatus.UNAUTHORIZED)
                    return
                candidate = _password_hash(password, user["password_salt"])
                if not hmac.compare_digest(candidate, user["password_hash"]):
                    self._send_json({"error": "Invalid email or password."}, status=HTTPStatus.UNAUTHORIZED)
                    return
                token = issue_token(conn, int(user["id"]))
                self._send_json(
                    {"token": token, "user": {"id": user["id"], "email": user["email"], "credits": user["credits"]}}
                )
            return

        if parsed.path == "/api/auth/logout":
            token = parse_bearer_token(self.headers)
            if not token:
                self._send_json({"ok": True})
                return
            with db_conn() as conn:
                conn.execute("DELETE FROM auth_tokens WHERE token_hash = ?", (_sha256(token),))
                conn.commit()
            self._send_json({"ok": True})
            return

        if parsed.path == "/api/mesh/refine":
            mesh_params = payload.get("meshParams") or {}
            refinement_text = payload.get("refinementText") or ""
            updated = refine_mesh(mesh_params, refinement_text)
            self._send_json({"meshParams": updated})
            return

        if parsed.path == "/api/pattern/generate":
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

            result = generate_pattern(measurements, payload.get("designPrompt", ""))
            with db_conn() as conn:
                user = get_user_from_token(conn, parse_bearer_token(self.headers))
                user_id = user["id"] if user else None
                remaining_credits = None
                consume_credit = bool(payload.get("consumeCredit"))
                if user_id and consume_credit:
                    current_credits = int(user["credits"])
                    if current_credits <= 0:
                        self._send_json({"error": "No credits remaining."}, status=HTTPStatus.PAYMENT_REQUIRED)
                        return
                    conn.execute("UPDATE users SET credits = credits - 1 WHERE id = ?", (user_id,))
                    conn.commit()
                    remaining_credits = current_credits - 1
                conn.execute(
                    """
                    INSERT INTO patterns (user_id, design_prompt, measurements_json, pattern_json, instructions_json, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user_id,
                        result["designPrompt"],
                        json.dumps(result["measurements"]),
                        json.dumps(result["pattern"]),
                        json.dumps(result["instructions"]),
                        _utc_now_iso(),
                    ),
                )
                conn.commit()
            if remaining_credits is not None:
                result["remainingCredits"] = remaining_credits
            self._send_json(result)
            return

        if parsed.path == "/api/pipeline/run":
            image_data_url = payload.get("imageDataUrl")
            design_prompt = (payload.get("designPrompt") or "").strip()
            if not image_data_url:
                self._send_json({"error": "imageDataUrl is required."}, status=HTTPStatus.BAD_REQUEST)
                return
            if not design_prompt:
                self._send_json({"error": "designPrompt is required."}, status=HTTPStatus.BAD_REQUEST)
                return
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
                self._send_json({"error": "Invalid measurements payload."}, status=HTTPStatus.BAD_REQUEST)
                return

            try:
                image_ext, image_bytes = _decode_image_data_url(image_data_url)
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
                return

            result = generate_pattern(measurements, design_prompt)
            source_image_url = _write_generated_file("source", image_ext, image_bytes)
            render_svg = generate_mannequin_free_svg(result["pattern"], design_prompt)
            render_svg_url = _write_generated_file("render", "svg", render_svg)
            tiled_pdf = generate_tiled_pattern_pdf(result["pattern"], design_prompt, measurements)
            pdf_url = _write_generated_file("pattern", "pdf", tiled_pdf)

            with db_conn() as conn:
                user = get_user_from_token(conn, parse_bearer_token(self.headers))
                user_id = user["id"] if user else None
                conn.execute(
                    """
                    INSERT INTO pipeline_assets (
                        user_id, design_prompt, source_image_path, render_svg_path, pdf_path, measurements_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user_id,
                        design_prompt,
                        source_image_url,
                        render_svg_url,
                        pdf_url,
                        json.dumps(result["measurements"]),
                        _utc_now_iso(),
                    ),
                )
                conn.commit()

            self._send_json(
                {
                    "designPrompt": result["designPrompt"],
                    "measurements": result["measurements"],
                    "pattern": result["pattern"],
                    "instructions": result["instructions"],
                    "sourceImageUrl": source_image_url,
                    "mannequinFreeRenderUrl": render_svg_url,
                    "patternPdfUrl": pdf_url,
                }
            )
            return

        if parsed.path == "/api/payments/checkout":
            with db_conn() as conn:
                user = self._require_auth_user(conn)
                if not user:
                    return

                tier_name = (payload.get("tierName") or "").strip()
                credits = int(payload.get("credits") or 0)
                amount_cents = int(payload.get("amountCents") or 0)
                origin = (payload.get("origin") or "http://localhost:8000").strip()
                if not tier_name or credits <= 0 or amount_cents <= 0:
                    self._send_json({"error": "Invalid checkout payload."}, status=HTTPStatus.BAD_REQUEST)
                    return

                success_url = f"{origin}?checkout=success&session_id={{CHECKOUT_SESSION_ID}}"
                cancel_url = f"{origin}?checkout=canceled"
                try:
                    stripe_session = create_stripe_checkout_session(
                        user_id=user["id"],
                        tier_name=tier_name,
                        credits=credits,
                        amount_cents=amount_cents,
                        success_url=success_url,
                        cancel_url=cancel_url,
                    )
                except Exception as exc:
                    self._send_json(
                        {"error": f"Checkout unavailable: {exc}"},
                        status=HTTPStatus.SERVICE_UNAVAILABLE,
                    )
                    return

                now = _utc_now_iso()
                conn.execute(
                    """
                    INSERT INTO payment_sessions (
                        user_id, tier_name, credits, amount_cents, currency, status, stripe_session_id, checkout_url, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, 'usd', 'pending', ?, ?, ?, ?)
                    """,
                    (
                        user["id"],
                        tier_name,
                        credits,
                        amount_cents,
                        stripe_session["id"],
                        stripe_session["url"],
                        now,
                        now,
                    ),
                )
                conn.commit()
                self._send_json({"checkoutUrl": stripe_session["url"], "sessionId": stripe_session["id"]})
            return

        if parsed.path == "/api/payments/confirm":
            session_id = (payload.get("sessionId") or "").strip()
            if not session_id:
                self._send_json({"error": "sessionId is required."}, status=HTTPStatus.BAD_REQUEST)
                return
            with db_conn() as conn:
                user = self._require_auth_user(conn)
                if not user:
                    return
                row = conn.execute(
                    """
                    SELECT id, user_id, credits, status
                    FROM payment_sessions
                    WHERE stripe_session_id = ?
                    """,
                    (session_id,),
                ).fetchone()
                if not row or row["user_id"] != user["id"]:
                    self._send_json({"error": "Payment session not found."}, status=HTTPStatus.NOT_FOUND)
                    return
                if row["status"] == "paid":
                    credits = conn.execute("SELECT credits FROM users WHERE id = ?", (user["id"],)).fetchone()["credits"]
                    self._send_json({"status": "paid", "credits": credits})
                    return

                try:
                    stripe_session = fetch_stripe_checkout_session(session_id)
                except Exception as exc:
                    self._send_json(
                        {"error": f"Unable to verify session: {exc}"},
                        status=HTTPStatus.SERVICE_UNAVAILABLE,
                    )
                    return

                payment_status = stripe_session.get("payment_status")
                if payment_status == "paid":
                    now = _utc_now_iso()
                    conn.execute(
                        "UPDATE payment_sessions SET status = 'paid', updated_at = ? WHERE id = ?",
                        (now, row["id"]),
                    )
                    conn.execute(
                        "UPDATE users SET credits = credits + ? WHERE id = ?",
                        (row["credits"], user["id"]),
                    )
                    conn.commit()
                    credits = conn.execute("SELECT credits FROM users WHERE id = ?", (user["id"],)).fetchone()["credits"]
                    self._send_json({"status": "paid", "credits": credits})
                    return

                self._send_json({"status": "pending"})
            return

        self._send_json({"error": "Route not found."}, status=HTTPStatus.NOT_FOUND)


def run() -> None:
    init_db()
    host, port = "0.0.0.0", 8000
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Serving PRINT YOUR FIT at http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run()
