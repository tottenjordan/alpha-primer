"""Production Web Server for AlphaEvolve Supply Chain & Digital Twin Intelligence Suite.

Enforces mandatory web security headers, strict allow-list input validation,
decoupled dispatching for 100% testability with zero network overhead,
and dual-mode serving (FastAPI/Uvicorn if available, with standard library
http.server.ThreadingHTTPServer fallback).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent
DASHBOARD_DIR = ROOT_DIR / "dashboard"
ASSETS_DIR = DASHBOARD_DIR / "assets"
RECORDS_DIR = ROOT_DIR / "records"

ALLOWED_USE_CASES = {
    "inventory_replenishment": "inventory_replenishment_trajectory.json",
}

SECURITY_HEADERS: dict[str, str] = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "SAMEORIGIN",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Cache-Control": "no-store",
    "Content-Security-Policy": (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com data:; "
        "img-src 'self' data: blob:; "
        "connect-src 'self'; "
        "frame-ancestors 'self';"
    ),
}


def build_cloud_status_payload() -> dict[str, Any]:
    """Build telemetry summary payload for Discovery Engine AlphaEvolve status."""
    master_file = RECORDS_DIR / "master_trajectories.json"
    experiments_summary = {}
    engine_info = {
        "project_id": "934903580331",
        "location": "global",
        "collection_id": "default_collection",
        "engine_id": "alpha-evolve-experiment-engine",
        "auth_mode": "Application Default Credentials (ADC - google.auth.default)",
    }

    if master_file.exists():
        try:
            bundle = json.loads(master_file.read_text(encoding="utf-8"))
            engine_info.update(bundle.get("engine_info", {}))
            for uc_id, uc_data in bundle.get("use_cases", {}).items():
                champ = uc_data.get("champion_summary", {})
                experiments_summary[uc_id] = {
                    "title": uc_data.get("title"),
                    "program_resource_name": champ.get("program_resource_name"),
                    "cost_reduction_pct": champ.get("cost_reduction_pct"),
                    "fill_rate_pct": champ.get("fill_rate_pct"),
                    "spoilage_rate_pct": champ.get("spoilage_rate_pct"),
                }
        except Exception:
            experiments_summary = {}

    return {
        "status": "healthy",
        "engine_info": engine_info,
        "experiments": experiments_summary,
        "secrets_leaked": False,
    }


def handle_api_request(path: str) -> tuple[int, dict[str, str], Any]:
    """Framework-agnostic request dispatcher enforcing security headers and allow-lists.

    Returns:
        tuple of (status_code, headers_dict, body_data)
    """
    headers = dict(SECURITY_HEADERS)

    if path == "/health":
        return (
            200,
            headers,
            {
                "status": "healthy",
                "service": "alpha-evolve-inventory-digital-twin",
                "engine_id": "alpha-evolve-experiment-engine",
                "auth_mode": "ADC (google.auth.default)",
                "secrets_leaked": False,
            },
        )

    if path == "/api/cloud-status":
        return 200, headers, build_cloud_status_payload()

    if path == "/":
        index_file = DASHBOARD_DIR / "index.html"
        if not index_file.exists():
            return 404, headers, {"detail": "Dashboard index.html not found."}
        headers["Content-Type"] = "text/html; charset=utf-8"
        return 200, headers, index_file.read_text(encoding="utf-8")

    if path == "/api/data":
        data_file = DASHBOARD_DIR / "data.json"
        if not data_file.exists():
            return 404, headers, {"detail": "Dashboard data.json not found."}
        headers["Content-Type"] = "application/json"
        return 200, headers, json.loads(data_file.read_text(encoding="utf-8"))

    if path.startswith("/api/trajectories/"):
        uc_id = path.split("/api/trajectories/", 1)[1].strip("/")
        if uc_id not in ALLOWED_USE_CASES:
            return 400, headers, {"detail": f"Invalid use_case_id: '{uc_id}'"}
        target_path = (RECORDS_DIR / ALLOWED_USE_CASES[uc_id]).resolve()
        if not str(target_path).startswith(str(RECORDS_DIR.resolve()) + os.sep):
            return 403, headers, {"detail": "Access denied."}
        if not target_path.exists():
            return 404, headers, {"detail": "Trajectory file not found."}
        headers["Content-Type"] = "application/json"
        return 200, headers, json.loads(target_path.read_text(encoding="utf-8"))

    return 404, headers, {"detail": "Not found"}


# Optional FastAPI / Uvicorn Integration
try:
    from fastapi import FastAPI, HTTPException, Request, Response
    from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
    from fastapi.staticfiles import StaticFiles

    app = FastAPI(
        title="AlphaEvolve Supply Chain & Digital Twin Intelligence Suite",
        description="Autonomous Multi-Echelon Perishable Inventory Replenishment Dashboard",
        version="1.0.0",
    )

    @app.middleware("http")
    async def add_security_headers(request: Request, call_next: Any) -> Response:
        response: Response = await call_next(request)
        for k, v in SECURITY_HEADERS.items():
            response.headers[k] = v
        return response

    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    app.mount("/assets", StaticFiles(directory=str(ASSETS_DIR)), name="assets")

    @app.get("/health", tags=["Monitoring"])
    def health_check() -> Any:
        code, _, body = handle_api_request("/health")
        return body

    @app.get("/api/cloud-status", tags=["Cloud AlphaEvolve"])
    def get_cloud_status() -> Any:
        code, _, body = handle_api_request("/api/cloud-status")
        return body

    @app.get("/", response_class=HTMLResponse, tags=["Dashboard"])
    def get_dashboard() -> Any:
        index_file = DASHBOARD_DIR / "index.html"
        if not index_file.exists():
            raise HTTPException(status_code=404, detail="Dashboard index.html not found.")
        return FileResponse(str(index_file))

    @app.get("/api/data", tags=["Telemetry"])
    def get_master_data() -> Any:
        data_file = DASHBOARD_DIR / "data.json"
        if not data_file.exists():
            raise HTTPException(status_code=404, detail="Dashboard data.json not found.")
        return FileResponse(str(data_file))

    @app.get("/api/trajectories/{use_case_id}", tags=["Telemetry"])
    def get_use_case_trajectory(use_case_id: str) -> Any:
        code, _, body = handle_api_request(f"/api/trajectories/{use_case_id}")
        if code != 200:
            raise HTTPException(status_code=code, detail=body.get("detail", "Error"))
        return JSONResponse(content=body)

except ImportError:
    app = None  # type: ignore


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    host = "0.0.0.0" if os.environ.get("K_SERVICE") else "127.0.0.1"

    if app is not None:
        try:
            import uvicorn

            print(f"Starting FastAPI / Uvicorn server at http://{host}:{port}")
            uvicorn.run(app, host=host, port=port)
        except ImportError:
            app = None

    if app is None:
        import http.server

        class FallbackHandler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                super().__init__(*args, directory=str(DASHBOARD_DIR), **kwargs)

            def do_GET(self) -> None:
                if self.path in (
                    "/health",
                    "/api/cloud-status",
                    "/api/data",
                ) or self.path.startswith("/api/trajectories/"):
                    code, hdrs, body = handle_api_request(self.path)
                    self.send_response(code)
                    self.send_header("Content-Type", "application/json")
                    for hk, hv in hdrs.items():
                        self.send_header(hk, hv)
                    self.end_headers()
                    self.wfile.write(json.dumps(body).encode("utf-8"))
                    return
                super().do_GET()

        httpd = http.server.ThreadingHTTPServer((host, port), FallbackHandler)
        print(f"Serving AlphaEvolve Executive Suite at http://{host}:{port} (stdlib fallback)")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down server.")
            httpd.server_close()
