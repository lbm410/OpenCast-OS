"""Serve explicitly allowed probe/shell assets to one confirmed LAN peer."""

from __future__ import annotations

import argparse
import datetime as dt
from http.server import BaseHTTPRequestHandler, HTTPServer
import ipaddress
import json
import os
import re
from pathlib import Path
from socketserver import TCPServer
import sys
import tempfile
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1] / "prototypes/netcast-web"
ASSETS = {"/": ("index.html", "text/html"), "/index.html": ("index.html", "text/html"),
          "/style.css": ("style.css", "text/css"),
          "/navigation.js": ("navigation.js", "application/javascript"),
          "/probe.js": ("probe.js", "application/javascript")}
SHELL_ROOT = ROOT.parent / "opencast-shell"
SHELL_ASSETS = {"/shell/": ("index.html", "text/html"),
                "/shell/index.html": ("index.html", "text/html"),
                "/shell/style.css": ("style.css", "text/css"),
                "/shell/navigation.js": ("navigation.js", "application/javascript"),
                "/shell/capabilities.js": ("capabilities.js", "application/javascript"),
                "/shell/shell.js": ("shell.js", "application/javascript"),
                "/shell/assets/landscape-v2.jpg": ("assets/landscape-v2.jpg", "image/jpeg")}
NUMBER_FIELDS = ("viewportWidth", "viewportHeight", "loadMs", "keyEvents", "lastKey",
                 "interactions", "maxHandlerMs")
FEATURE_FIELDS = ("canvas2d", "requestAnimationFrame", "json", "xhr", "netCastBack", "netCastExit")
MAX_REPORT_BYTES = 8192
EVENT_TYPES = ("keydown", "keyup", "keypress", "click", "focus")
V2_FEATURES = (*FEATURE_FIELDS, "webkitRequestAnimationFrame", "mozRequestAnimationFrame", "captureEvents")
V2_FIELDS = {"probeVersion", "eventCounts", "events", "droppedEvents", "activeElement"}


def bounded_integer(value, maximum=10**9):
    return type(value) is int and 0 <= value <= maximum


def element_label(value):
    return isinstance(value, str) and re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,23}", value) is not None


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON field")
        result[key] = value
    return result


def validate_report(data: bytes) -> dict:
    if len(data) > MAX_REPORT_BYTES:
        raise ValueError("Report exceeds byte limit")
    try:
        report = json.loads(data, object_pairs_hook=unique_object)
    except RecursionError as error:
        raise ValueError("Report nesting exceeds parser limit") from error
    legacy_fields = {"userAgent", "features", *NUMBER_FIELDS}
    if not isinstance(report, dict) or set(report) not in (legacy_fields, legacy_fields | V2_FIELDS):
        raise ValueError("Unexpected report fields")
    version_two = "probeVersion" in report
    if (not isinstance(report["userAgent"], str) or len(report["userAgent"]) > 1024
            or any(ord(c) < 32 or 0xD800 <= ord(c) <= 0xDFFF for c in report["userAgent"])):
        raise ValueError("Invalid user agent")
    for name in NUMBER_FIELDS:
        if not bounded_integer(report[name]):
            raise ValueError("Invalid numeric field: " + name)
    features = report["features"]
    if (not isinstance(features, dict) or set(features) != set(V2_FEATURES if version_two else FEATURE_FIELDS)
            or any(type(value) is not bool for value in features.values())):
        raise ValueError("Invalid capability fields")
    if version_two:
        if report["probeVersion"] != "input-001-v2":
            raise ValueError("Unknown probe version")
        counts = report["eventCounts"]
        if (not isinstance(counts, dict) or set(counts) != set(EVENT_TYPES)
                or not all(bounded_integer(value) for value in counts.values())):
            raise ValueError("Invalid event counters")
        if report["keyEvents"] != counts["keydown"]:
            raise ValueError("Inconsistent keydown count")
        if not bounded_integer(report["droppedEvents"]) or not element_label(report["activeElement"]):
            raise ValueError("Invalid event summary")
        events = report["events"]
        if not isinstance(events, list) or len(events) > 16:
            raise ValueError("Invalid event buffer")
        for event in events:
            if (not isinstance(event, dict)
                    or set(event) != {"type", "key", "target", "active", "phase", "elapsedMs"}
                    or event["type"] not in EVENT_TYPES
                    or not bounded_integer(event["key"], 65535)
                    or not element_label(event["target"]) or not element_label(event["active"])
                    or event["phase"] not in ("capture", "bubble")
                    or not bounded_integer(event["elapsedMs"])):
                raise ValueError("Invalid recorded event")
    return report


def make_server(bind: str, port: int, allowed: str, output: Path,
                include_shell: bool = False) -> HTTPServer:
    bind_ip, peer_ip = ipaddress.IPv4Address(bind), ipaddress.IPv4Address(allowed)
    if bind_ip.is_loopback:
        if not peer_ip.is_loopback:
            raise ValueError("Loopback server requires a loopback peer")
    else:
        from tools.discovery import PRIVATE
        if not any(bind_ip in n and peer_ip in n for n in PRIVATE):
            raise ValueError("Use a private LAN address and a confirmed private peer")
    # Snapshot an explicit asset allowlist. No directory browsing or arbitrary paths.
    assets = {path: ((ROOT / filename).read_bytes(), mime) for path, (filename, mime) in ASSETS.items()}
    if include_shell:
        assets.update({path: ((SHELL_ROOT / filename).read_bytes(), mime)
                       for path, (filename, mime) in SHELL_ASSETS.items()})
    if any(len(data) > 1024 * 1024 for data, _ in assets.values()):
        raise ValueError("Static asset exceeds 1 MiB limit")
    output.mkdir(parents=True, exist_ok=True)

    class Handler(BaseHTTPRequestHandler):
        server_version = "OpenCastProbe/0.1"
        sys_version = ""

        def setup(self):
            super().setup()
            self.connection.settimeout(3)

        def reply(self, status, body=b"", mime="text/plain"):
            self.send_response(status)
            self.send_header("Content-Type", mime if mime.startswith("image/") else mime + "; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            item = assets.get(urlsplit(self.path).path)
            if not item:
                self.reply(404, b"Not found")
                return
            self.reply(200, item[0], item[1])

        def do_POST(self):
            if self.path != "/report":
                self.reply(404)
                return
            origin = self.headers.get("Origin")
            expected = "http://%s:%s" % self.server.server_address
            if origin and origin != expected:
                self.reply(403)
                return
            if self.headers.get("Transfer-Encoding") or len(self.headers.get_all("Content-Length", [])) != 1:
                self.reply(400)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= MAX_REPORT_BYTES:
                    raise ValueError("Invalid length")
                report = validate_report(self.rfile.read(length))
            except (ValueError, UnicodeError, TimeoutError):
                self.reply(400)
                return
            if self.server.reports_saved >= 32:
                self.reply(429)
                return
            stamp = dt.datetime.now(dt.timezone.utc)
            report["received_at"] = stamp.isoformat()
            report["physical_tv_confirmed"] = False
            target = output / (stamp.strftime("probe-%Y%m%dT%H%M%S-%fZ") + ".json")
            temporary = None
            try:
                payload = (json.dumps(report, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
                with tempfile.NamedTemporaryFile(dir=output, prefix=".pending-", delete=False) as stream:
                    temporary = Path(stream.name)
                    stream.write(payload)
                # Publish a complete file without overwriting a colliding report.
                os.link(temporary, target)
            except (OSError, UnicodeError):
                self.reply(500, b"Local report could not be stored")
                return
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)
            self.server.reports_saved += 1
            self.reply(201, b"Saved locally")

        def log_message(self, fmt, *args):
            # No raw URLs, request bodies, user agents or network identifiers in logs.
            pass

    class Server(HTTPServer):
        reports_saved = 0

        def server_bind(self):
            # HTTPServer normally performs reverse DNS here. The private probe
            # must start without depending on the router's DNS behavior.
            TCPServer.server_bind(self)
            self.server_name, self.server_port = self.server_address

        def verify_request(self, request, address):
            return address[0] == allowed

    return Server((bind, port), Handler)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bind", default="127.0.0.1")
    parser.add_argument("--allow", default="127.0.0.1", help="Only this peer may connect")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--output", type=Path, default=Path("artifacts/probe"))
    parser.add_argument("--include-shell", action="store_true",
                        help="Also expose the fixed launcher allowlist at /shell/; no native TV actions")
    args = parser.parse_args()
    try:
        with make_server(args.bind, args.port, args.allow, args.output, args.include_shell) as server:
            print("Probe: http://%s:%s/ | allowed peer: %s | Ctrl-C to stop" %
                  (*server.server_address, args.allow), flush=True)
            if args.include_shell:
                print("Launcher preview: /shell/ | native TV actions remain unavailable", flush=True)
            server.serve_forever()
    except KeyboardInterrupt:
        return 0
    except (OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
