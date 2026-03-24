"""
AvaPilot REST API — serves registry data for the gateway-ui.
Run: avapilot api [--port 8080]
"""
from __future__ import annotations

import json
from http.server import HTTPServer, SimpleHTTPRequestHandler
from avapilot.registry import ServiceRegistry


class AvaPilotAPIHandler(SimpleHTTPRequestHandler):
    registry = None

    def do_GET(self):
        if self.path == "/api/services":
            self._json_response(self._get_services())
        elif self.path == "/api/stats":
            self._json_response(self._get_stats())
        elif self.path.startswith("/api/service/"):
            name = self.path[len("/api/service/"):].replace("%20", " ")
            self._json_response(self._get_service(name))
        else:
            self.send_error(404)

    def _get_services(self):
        services = self.registry.list_services()
        return [{
            "name": s.name,
            "category": s.category,
            "description": s.description,
            "read_tools": s.total_read_tools,
            "write_tools": s.total_write_tools,
            "total_tools": s.total_read_tools + s.total_write_tools,
        } for s in services]

    def _get_stats(self):
        services = self.registry.list_services()
        total_read = sum(s.total_read_tools for s in services)
        total_write = sum(s.total_write_tools for s in services)
        return {
            "services": len(services),
            "read_tools": total_read,
            "write_tools": total_write,
            "total_tools": total_read + total_write,
            "built_in_tools": 45,
        }

    def _get_service(self, name):
        s = self.registry.get_service(name)
        if not s:
            return {"error": f"Service '{name}' not found"}
        return {
            "name": s.name,
            "category": s.category,
            "description": s.description,
            "website": s.website,
            "contracts": [{
                "address": c.address,
                "label": c.label,
                "type": c.contract_type,
                "read_functions": len(c.read_functions),
                "write_functions": len(c.write_functions),
            } for c in s.contracts],
        }

    def _json_response(self, data):
        body = json.dumps(data).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass  # quiet


def run_api(port=8080, registry_path=None):
    AvaPilotAPIHandler.registry = ServiceRegistry(registry_path)
    server = HTTPServer(("0.0.0.0", port), AvaPilotAPIHandler)
    import sys
    print(f"🔺 AvaPilot API running on http://localhost:{port}", file=sys.stderr)
    print(f"   /api/services  — list all services", file=sys.stderr)
    print(f"   /api/stats     — platform stats", file=sys.stderr)
    print(f"   /api/service/Name — service details", file=sys.stderr)
    server.serve_forever()
