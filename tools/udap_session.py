"""Reviewed-entry UDAP inventory session; no app launch, keys or SmartText sends.

`preview` is offline. `inventory` requires explicit confirmed IPv4 configuration
and a typed, interactive effect confirmation before opening a callback listener.
The listener starts before showKey/hello, discards callback field text, and stops
in finally. Device use still needs integration review and owner coordination.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import datetime as dt
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import math
import os
from pathlib import Path
import secrets
import re
import socket
from socketserver import TCPServer
import sys
import threading
import time
from typing import Callable

from tools import udap

MAX_HEADERS = 4096
MAX_CALLBACK_CONNECTIONS = 64


def _seconds(value, minimum, maximum):
    if type(value) not in (int, float) or not math.isfinite(value) or not minimum <= value <= maximum:
        raise udap.UDAPError("invalid_session_deadline")
    return float(value)


class CallbackState:
    """Sanitized receiver metadata only; never stores XML, PINs or field text."""

    def __init__(self):
        self.lock = threading.Lock()
        self.connections = 0
        self.events = 0
        self.invalid = 0
        self.remote_closed = False
        self.expired = False
        self.keyboard_visible = False
        self.keyboard_mode = None
        self.editing_observed = False
        self.generation = 0
        self.observed_at = None

    def invalidate(self):
        with self.lock:
            self.invalid += 1
            self.keyboard_visible = False
            self.keyboard_mode = None
            self.editing_observed = False
            self.generation += 1
            self.observed_at = None

    def observe(self, event: udap.CallbackEvent, received_at: float):
        with self.lock:
            self.events += 1
            self.generation += 1
            self.observed_at = received_at
            if event.name == "byebye":
                self.remote_closed = True
                self.keyboard_visible = False
                self.keyboard_mode = None
                self.editing_observed = False
            elif event.name == "KeyboardVisible":
                self.keyboard_visible = bool(event.visible)
                self.keyboard_mode = event.mode
                self.editing_observed = False
            elif event.name == "TextEdited":
                self.editing_observed = (self.keyboard_visible and self.keyboard_mode == "default" and event.state == "Editing")
                if not self.editing_observed:
                    self.keyboard_visible = False
                    self.keyboard_mode = None
            # text_present is unnecessary for inventory and is not retained.

    def summary(self):
        with self.lock:
            return {"connections": self.connections, "events": self.events, "invalid": self.invalid,
                    "remote_closed": self.remote_closed, "expired": self.expired,
                    "keyboard_visible": self.keyboard_visible, "keyboard_mode": self.keyboard_mode,
                    "editing_observed": self.editing_observed, "generation": self.generation}


class _HeaderBudget:
    def __init__(self, stream, remaining):
        self.stream, self.remaining = stream, remaining

    def readline(self, size=-1):
        data = self.stream.readline(min(size if size >= 0 else self.remaining + 1, self.remaining + 1))
        self.remaining -= len(data)
        if self.remaining < 0:
            raise ValueError("header budget")
        return data


class CallbackReceiver:
    """One confirmed peer, finite lifetime, finite connections and hard request timer."""

    def __init__(self, config: udap.PeerConfig, port=0, *, lifetime=90.0, request_seconds=2.0):
        if not isinstance(config, udap.PeerConfig):
            raise udap.UDAPError("invalid_peer_config")
        udap._integer(port, 0, 65535)
        self.config, self.requested_port = config, port
        self.lifetime = _seconds(lifetime, 0.1, 300)
        self.request_seconds = _seconds(request_seconds, 0.05, 3)
        self.state = CallbackState()
        self.server = self.thread = self.timer = None
        self._lifecycle = threading.Lock()
        self._stopped = threading.Event()
        self._started = self._stopping = False

    @property
    def port(self):
        if self.server is None:
            raise udap.UDAPError("callback_receiver_not_started")
        return self.server.server_address[1]

    def ready(self):
        with self._lifecycle:
            return self._started and not self._stopping and self.thread is not None and self.thread.is_alive()

    def start(self):
        owner = self
        with self._lifecycle:
            if self._started or self._stopping:
                raise udap.UDAPError("callback_receiver_already_used")

            class Handler(BaseHTTPRequestHandler):
                protocol_version = "HTTP/1.0"
                server_version = "UDAPCallback/0.1"
                sys_version = ""

                def setup(self):
                    super().setup()
                    self.connection.settimeout(owner.request_seconds)
                    self.deadline = threading.Timer(owner.request_seconds, self.expire_connection)
                    self.deadline.daemon = True
                    self.deadline.start()

                def expire_connection(self):
                    owner.state.invalidate()
                    try:
                        self.connection.shutdown(socket.SHUT_RDWR)
                    except OSError:
                        pass
                    self.connection.close()

                def finish(self):
                    self.deadline.cancel()
                    try:
                        super().finish()
                    except OSError:
                        pass

                def parse_request(self):
                    if len(self.raw_requestline) > 512:
                        owner.state.invalidate()
                        return False
                    original = self.rfile
                    self.rfile = _HeaderBudget(original, MAX_HEADERS - len(self.raw_requestline))
                    try:
                        return super().parse_request()
                    except (ValueError, OSError):
                        owner.state.invalidate()
                        return False
                    finally:
                        self.rfile = original

                def handle_expect_100(self):
                    self.reply(400)
                    return False

                def reply(self, status):
                    self.send_response(status)
                    self.send_header("Content-Length", "0")
                    self.send_header("Connection", "close")
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    self.wfile.flush()
                    self.close_connection = True

                def send_error(self, code, message=None, explain=None):
                    owner.state.invalidate()
                    self.reply(code)  # Never echo the URL, method, headers or exception.

                def do_POST(self):
                    if self.path not in (udap.PAIRING_PATH, udap.EVENT_PATH):
                        owner.state.invalidate()
                        self.reply(404)
                        return
                    lengths = self.headers.get_all("Content-Length", [])
                    hosts = self.headers.get_all("Host", [])
                    expected_host = "%s:%s" % self.server.server_address
                    types = self.headers.get_all("Content-Type", [])
                    media_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
                    if (len(types) != 1 or len(lengths) != 1 or not re.fullmatch(r"[0-9]{1,5}", lengths[0])
                            or hosts != [expected_host] or self.headers.get("Transfer-Encoding")
                            or self.headers.get("Content-Encoding") or self.headers.get("Expect")
                            or media_type not in ("text/xml", "application/xml")):
                        owner.state.invalidate(); self.reply(400); return
                    length = int(lengths[0])
                    if not 0 < length <= udap.MAX_CALLBACK:
                        owner.state.invalidate(); self.reply(413); return
                    try:
                        data = self.rfile.read(length)
                        if len(data) != length:
                            raise udap.UDAPError("truncated_callback")
                        event = udap.parse_callback(self.path, data)
                        data = b""  # Do not retain the full text field in receiver state.
                        owner.state.observe(event, time.monotonic())
                    except (udap.UDAPError, OSError):
                        owner.state.invalidate(); self.reply(400); return
                    self.reply(200)

                def do_GET(self):
                    owner.state.invalidate()
                    self.reply(405)

                def log_message(self, *args):
                    pass

            class Server(HTTPServer):
                def server_bind(self):
                    TCPServer.server_bind(self)
                    self.server_name, self.server_port = self.server_address

                def verify_request(self, request, address):
                    if address[0] != owner.config.peer:
                        return False
                    with owner.state.lock:
                        owner.state.connections += 1
                        exhausted = owner.state.connections > MAX_CALLBACK_CONNECTIONS
                        if exhausted:
                            owner.state.expired = True
                    if exhausted:
                        threading.Thread(target=owner.stop, daemon=True).start()
                        return False
                    return True

                def handle_error(self, request, address):
                    owner.state.invalidate()  # No default traceback with peer or request data.

            try:
                self.server = Server((self.config.controller, self.requested_port), Handler)
                self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
                self.thread.start()
                self._started = True
                self.timer = threading.Timer(self.lifetime, self.expire)
                self.timer.daemon = True
                self.timer.start()
            except BaseException as error:
                if self.timer is not None:
                    self.timer.cancel()
                if self.server is not None:
                    if self.thread is not None and self.thread.is_alive():
                        self.server.shutdown()
                        self.thread.join(timeout=self.request_seconds + 1)
                    self.server.server_close()
                self._stopping = True
                self._stopped.set()
                if isinstance(error, (OSError, RuntimeError)):
                    raise udap.UDAPError("callback_start_failed") from None
                raise
        return self

    def expire(self):
        with self.state.lock:
            self.state.expired = True
        self.state.invalidate()
        self.stop()

    def stop(self):
        with self._lifecycle:
            if not self._started:
                return
            follower = self._stopping
            self._stopping = True
            server, thread, timer = self.server, self.thread, self.timer
        if follower:
            if not self._stopped.wait(self.request_seconds + 1):
                raise udap.UDAPError("callback_shutdown_incomplete")
            return
        if timer is not None:
            timer.cancel()
        try:
            server.shutdown()
        finally:
            try:
                server.server_close()
                if thread is not threading.current_thread():
                    thread.join(timeout=self.request_seconds + 1)
            finally:
                self._stopped.set()

    def __enter__(self):
        return self.start()

    def __exit__(self, *args):
        self.stop()


class GuardedTransport:
    """Check asynchronous receiver state before every outgoing request."""

    def __init__(self, transport: udap.Transport, receiver: CallbackReceiver):
        self.transport, self.receiver, self.config = transport, receiver, transport.config
        self.disconnect_acknowledged = False

    def exchange(self, request):
        operation = udap._validate_wire(request)
        state = self.receiver.state.summary()
        if state["remote_closed"]:
            raise udap.UDAPError("remote_session_ended")
        if operation != "byebye" and (state["expired"] or not self.receiver.ready()):
            raise udap.UDAPError("callback_receiver_not_ready")
        response = self.transport.exchange(request)
        if operation == "byebye":
            self.disconnect_acknowledged = True
        return response


@dataclass(frozen=True)
class SessionResult:
    inventory: udap.Inventory | None = field(repr=False)
    paired: bool
    disconnect_acknowledged: bool
    callback_summary: dict
    error: str | None

    def summary(self):
        return {"paired": self.paired, "apps_received": len(self.inventory.apps) if self.inventory else 0,
                "apps_reported": self.inventory.total if self.inventory else None,
                "partial_inventory": self.inventory.partial if self.inventory else None,
                "disconnect_acknowledged": self.disconnect_acknowledged,
                "callbacks": self.callback_summary, "error": self.error,
                "physical_tv_confirmed": False, "smarttext_transmission": False}


def run_inventory(config: udap.PeerConfig, *, approve_effects: Callable[[], bool],
                  pin_reader=udap.read_pairing_pin, callback_port=0, lifetime=90.0) -> SessionResult:
    """No automatic retry; caller must supply the already-informed owner decision."""
    if approve_effects() is not True:
        raise udap.UDAPError("session_effects_not_confirmed")
    receiver = CallbackReceiver(config, callback_port, lifetime=lifetime)
    session = None
    inventory = None
    paired = disconnected = False
    error = None
    try:
        receiver.start()
        transport = GuardedTransport(udap.Transport(config), receiver)
        session = udap.Session(transport, receiver.port, callback_ready=receiver.ready)
        session.request_pairing_code(owner_approved=True)
        session.pair_interactive(pin_reader=pin_reader)
        paired = True
        inventory = session.inventory()
    except udap.UDAPError as exc:
        error = exc.code
    except (KeyboardInterrupt, EOFError):
        error = "session_interrupted"
    finally:
        try:
            if session is not None:
                try:
                    session.close()
                    disconnected = transport.disconnect_acknowledged
                except udap.UDAPError as exc:
                    if exc.code != "remote_session_ended" and error is None:
                        error = "disconnect_failed"
                except (KeyboardInterrupt, EOFError):
                    error = "session_interrupted_during_disconnect"
        finally:
            receiver.stop()
    summary = receiver.state.summary()
    summary["listener_stopped"] = not receiver.ready()
    return SessionResult(inventory, paired, disconnected, summary, error)


def save_inventory(inventory: udap.Inventory, *, project_root: Path | None = None,
                   stamp: dt.datetime | None = None) -> str:
    """Exclusive private report beneath artifacts/diagnostics; no arbitrary output path."""
    if not isinstance(inventory, udap.Inventory) or len(inventory.apps) > 16 or type(inventory.partial) is not bool:
        raise udap.UDAPError("invalid_inventory_report")
    udap._integer(inventory.total, 0, 2048)
    apps = []
    for app in inventory.apps:
        if not re.fullmatch(r"[0-9A-Fa-f]{1,32}", app.auid):
            raise udap.UDAPError("invalid_inventory_report")
        udap._text(app.name, 256)
        udap._integer(app.category, 2, 3)
        apps.append({"auid": app.auid, "name": app.name, "category": app.category})
    stamp = stamp or dt.datetime.now(dt.timezone.utc)
    filename = stamp.strftime("udap-inventory-%Y%m%dT%H%M%S-%fZ.json")
    payload = (json.dumps({"captured_at": stamp.isoformat(), "total": inventory.total,
                          "partial": inventory.partial, "apps": apps}, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    root = project_root if project_root is not None else Path(__file__).resolve().parents[1]
    descriptors = []
    temporary = None
    directory = None
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    try:
        parent = os.open(root, flags)
        descriptors.append(parent)
        for component in ("artifacts", "diagnostics"):
            try:
                os.mkdir(component, mode=0o700, dir_fd=parent)
            except FileExistsError:
                pass
            parent = os.open(component, flags, dir_fd=parent)
            descriptors.append(parent)
        directory = parent
        candidate = ".pending-udap-" + secrets.token_hex(12)
        descriptor = os.open(candidate, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory)
        temporary = candidate
        with os.fdopen(descriptor, "wb") as stream:
            os.fchmod(stream.fileno(), 0o600)
            stream.write(payload)
        os.link(temporary, filename, src_dir_fd=directory, dst_dir_fd=directory, follow_symlinks=False)
        return "artifacts/diagnostics/" + filename
    except (OSError, UnicodeError):
        raise udap.UDAPError("inventory_report_not_saved") from None
    finally:
        if temporary is not None and directory is not None:
            try:
                os.unlink(temporary, dir_fd=directory)
            except OSError:
                pass
        for descriptor in reversed(descriptors):
            os.close(descriptor)


class _PrivateParser(argparse.ArgumentParser):
    def error(self, message):
        self.exit(2, "Invalid arguments. Use --help. PINs and text values are never accepted as arguments.\n")


def main(argv=None):
    parser = _PrivateParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True, parser_class=_PrivateParser)
    commands.add_parser("preview", help="Offline plan; no sockets or credentials")
    live = commands.add_parser("inventory", help="Interactive, explicitly confirmed pairing and bounded inventory")
    live.add_argument("--confirmed-target", required=True)
    live.add_argument("--port", type=int, required=True, help="UDAP port from the verified descriptor")
    live.add_argument("--bind", required=True, help="Current controller IPv4 on the confirmed private subnet")
    live.add_argument("--network", required=True, help="Exact local RFC1918 subnet, /24 or narrower")
    live.add_argument("--callback-port", type=int, default=0, help="0 chooses an available local callback port")
    live.add_argument("--timeout", type=float, default=3.0)
    live.add_argument("--session-seconds", type=float, default=90.0, help="Callback lifetime; terminal input may still wait after listener expiry")
    live.add_argument("--save-inventory", action="store_true", help="Save app identities to a private ignored JSON report; never log them")
    args = parser.parse_args(argv)
    if args.command == "preview":
        print(json.dumps({"mode": "offline", "network_requests": 0,
                          "steps": ["confirm pairing-overlay effects", "start restricted callbacks", "showKey once", "hidden PIN and hello once", "one count and first app page", "byebye and listener cleanup"],
                          "smarttext_transmission": False}, indent=2))
        return 0
    try:
        config = udap.PeerConfig(args.confirmed_target, args.port, args.bind, args.network, True, args.timeout)
        udap._integer(args.callback_port, 0, 65535)
        _seconds(args.session_seconds, 5, 300)
        if not sys.stdin.isatty():
            raise udap.UDAPError("interactive_terminal_required")
        def approve():
            print("This will show a pairing code on the confirmed TV, pair once, read one bounded app inventory, then disconnect.")
            print("A callback listener will accept only that TV and close at session end. No app, input, key or text command will be sent.")
            print("Confirmed target: %s:%d; callback interface: %s." % (config.peer, config.port, config.controller))
            return input("Type PAIR to accept these temporary effects: ").strip() == "PAIR"
        result = run_inventory(config, approve_effects=approve, callback_port=args.callback_port, lifetime=args.session_seconds)
        summary = result.summary()
        if args.save_inventory and result.inventory is not None:
            summary["inventory_report"] = save_inventory(result.inventory)
        print(json.dumps(summary, indent=2))
        return 0 if result.error is None else 2
    except (udap.UDAPError, KeyboardInterrupt, EOFError) as exc:
        print(json.dumps({"error": exc.code if isinstance(exc, udap.UDAPError) else "session_interrupted"}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
