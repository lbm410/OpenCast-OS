"""Bounded UDAP foundation; CLI is offline-only and never accepts a pairing PIN."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import getpass
import http.client
import ipaddress
import json
import math
import re
import sys
import threading
import time
from typing import Callable
from urllib.parse import parse_qsl, urlencode, urlsplit
import warnings
import xml.etree.ElementTree as ET

from tools.discovery import PRIVATE, total_timeout

MAX_BODY = 64 * 1024
MAX_CALLBACK = 8192
MAX_TEXT = 2048
MAX_REQUESTS = 32
USER_AGENT = "Python/3 UDAP/2.0 OpenCast/0.1"
PAIRING_PATH = "/udap/api/pairing"
EVENT_PATH = "/udap/api/event"


class UDAPError(Exception):
    """Only fixed diagnostic codes and numeric HTTP status; no remote content."""

    def __init__(self, code: str, status: int | None = None):
        self.code, self.status = code, status
        super().__init__(code if status is None else "%s (HTTP %d)" % (code, status))


def _integer(value, minimum, maximum):
    if type(value) is not int or not minimum <= value <= maximum:
        raise UDAPError("invalid_integer")
    return value


def _text(value, maximum=MAX_TEXT):
    if not isinstance(value, str):
        raise UDAPError("invalid_text")
    try:
        encoded = value.encode("utf-8", "strict")
    except UnicodeError:
        raise UDAPError("invalid_text_encoding") from None
    if len(encoded) > maximum or any(ord(c) < 32 or 0xD800 <= ord(c) <= 0xDFFF or ord(c) in (0xFFFE, 0xFFFF) for c in value):
        raise UDAPError("invalid_text")
    return value


@dataclass(frozen=True, repr=False)
class PeerConfig:
    peer: str
    port: int
    controller: str
    network: str
    confirmed: bool
    timeout: float = 3.0
    lab_loopback: bool = False

    def __post_init__(self):
        if not all(isinstance(value, str) for value in (self.peer, self.controller, self.network)):
            raise UDAPError("literal_ipv4_required")
        try:
            peer = ipaddress.IPv4Address(self.peer)
            controller = ipaddress.IPv4Address(self.controller)
            network = ipaddress.IPv4Network(self.network, strict=True)
        except (ValueError, TypeError):
            raise UDAPError("literal_ipv4_required") from None
        _integer(self.port, 1, 65535)
        if self.confirmed is not True or type(self.lab_loopback) is not bool:
            raise UDAPError("confirmed_peer_required")
        if type(self.timeout) not in (int, float) or not math.isfinite(self.timeout) or not 0.05 <= self.timeout <= 10:
            raise UDAPError("invalid_timeout")
        if self.lab_loopback:
            if str(peer) != "127.0.0.1" or str(controller) != "127.0.0.1" or str(network) != "127.0.0.0/30":
                raise UDAPError("invalid_loopback_fixture")
        else:
            if network.prefixlen < 24 or not any(network.subnet_of(block) for block in PRIVATE):
                raise UDAPError("private_local_subnet_required")
            if peer == controller:
                raise UDAPError("distinct_peer_required")
            for address in (peer, controller):
                if address not in network or address in (network.network_address, network.broadcast_address):
                    raise UDAPError("peer_outside_confirmed_subnet")

    @classmethod
    def loopback_fixture(cls, port: int, timeout=1.0):
        return cls("127.0.0.1", port, "127.0.0.1", "127.0.0.0/30", True, timeout, True)

    def __repr__(self):
        return "<PeerConfig confirmed IPv4; addresses omitted>"


@dataclass(frozen=True)
class WireRequest:
    method: str
    path: str
    body: bytes = field(default=b"", repr=False)


@dataclass(frozen=True)
class WireResponse:
    status: int
    body: bytes = field(repr=False)


def _xml(kind: str, name: str, fields: tuple[tuple[str, str], ...] = ()) -> bytes:
    root = ET.Element("envelope")
    api = ET.SubElement(root, "api", {"type": kind})
    ET.SubElement(api, "name").text = name
    for key, value in fields:
        ET.SubElement(api, key).text = _text(value)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def show_key_request() -> WireRequest:
    return WireRequest("POST", PAIRING_PATH, _xml("pairing", "showKey"))


def hello_request(pin: str, callback_port: int) -> WireRequest:
    if not isinstance(pin, str) or not re.fullmatch(r"[0-9]{6}", pin):
        raise UDAPError("invalid_pairing_code")
    _integer(callback_port, 1, 65535)
    return WireRequest("POST", PAIRING_PATH, _xml("pairing", "hello", (("value", pin), ("port", str(callback_port)))))


def byebye_request(callback_port: int) -> WireRequest:
    _integer(callback_port, 1, 65535)
    return WireRequest("POST", PAIRING_PATH, _xml("pairing", "byebye", (("port", str(callback_port)),)))


def inventory_request(category: int = 1, number: int | None = None) -> WireRequest:
    _integer(category, 1, 3)
    pairs = [("target", "appnum_get" if number is None else "applist_get"), ("type", str(category))]
    if number is not None:
        _integer(number, 1, 16)
        pairs.extend((("index", "1"), ("number", str(number))))
    return WireRequest("GET", "/udap/api/data?" + urlencode(pairs))


def _parse_xml(data: bytes, limit=MAX_BODY) -> ET.Element:
    if not isinstance(data, bytes) or not data or len(data) > limit:
        raise UDAPError("xml_size_limit")
    try:
        decoded = data.decode("utf-8-sig", "strict")
        if "\x00" in decoded or "<!DOCTYPE" in decoded.upper() or "<!ENTITY" in decoded.upper():
            raise UDAPError("xml_declaration_rejected")
        root = ET.fromstring(decoded)
    except (UnicodeError, ET.ParseError):
        raise UDAPError("invalid_xml") from None
    pending, visited = [(root, 0)], 0
    while pending:
        node, depth = pending.pop()
        visited += 1
        if depth > 5 or visited > 256:
            raise UDAPError("xml_structure_limit")
        pending.extend((child, depth + 1) for child in node)
    if root.tag != "envelope" or root.attrib or (root.text or "").strip() or len(root) != 1:
        raise UDAPError("unexpected_xml_envelope")
    return root


def _leaves(node: ET.Element, expected: set[str]) -> dict[str, str]:
    if (node.text or "").strip():
        raise UDAPError("unexpected_xml_text")
    result = {}
    for child in node:
        if child.tag not in expected or child.tag in result or child.attrib or len(child) or (child.tail or "").strip():
            raise UDAPError("unexpected_xml_fields")
        result[child.tag] = _text(child.text or "")
    if set(result) != expected:
        raise UDAPError("missing_xml_fields")
    return result


def _api(data: bytes, kind: str, expected: set[str]) -> dict[str, str]:
    root = _parse_xml(data, MAX_CALLBACK)
    api = root[0]
    if api.tag != "api" or api.attrib != {"type": kind} or (api.tail or "").strip():
        raise UDAPError("unexpected_api")
    return _leaves(api, expected)


def _validate_wire(request: WireRequest):
    if (not isinstance(request, WireRequest) or not isinstance(request.body, bytes)
            or not isinstance(request.method, str) or not isinstance(request.path, str)
            or len(request.body) > MAX_CALLBACK or len(request.path) > 512
            or any(ord(c) < 32 or ord(c) == 127 for c in request.path)):
        raise UDAPError("invalid_request")
    if request.method == "POST" and request.path == EVENT_PATH:
        raise UDAPError("smarttext_transport_not_integrated")
    if request.method == "POST" and request.path == PAIRING_PATH:
        root = _parse_xml(request.body, MAX_CALLBACK)
        name = root[0].findtext("name")
        expected = {"name"} if name == "showKey" else {"name", "port"} if name == "byebye" else {"name", "value", "port"} if name == "hello" else set()
        fields = _api(request.body, "pairing", expected)
        if not expected:
            raise UDAPError("unsupported_pairing_operation")
        if "port" in fields:
            if not re.fullmatch(r"[0-9]{1,5}", fields["port"]):
                raise UDAPError("invalid_callback_port")
            _integer(int(fields["port"]), 1, 65535)
        if name == "hello" and not re.fullmatch(r"[0-9]{6}", fields["value"]):
            raise UDAPError("invalid_pairing_code")
        return name
    if request.method == "GET" and request.body == b"":
        try:
            parsed = urlsplit(request.path)
            pairs = parse_qsl(parsed.query, strict_parsing=True, max_num_fields=4)
        except ValueError:
            raise UDAPError("unsupported_query") from None
        if parsed.scheme or parsed.netloc or parsed.fragment or parsed.path != "/udap/api/data":
            raise UDAPError("unsupported_query")
        fields = dict(pairs)
        if len(fields) != len(pairs) or fields.get("type") not in ("1", "2", "3"):
            raise UDAPError("unsupported_query")
        if fields.get("target") == "appnum_get" and set(fields) == {"target", "type"}:
            return "query"
        if fields.get("target") == "applist_get" and set(fields) == {"target", "type", "index", "number"} and fields["index"] == "1" and fields["number"] in tuple(str(n) for n in range(1, 17)):
            return "query"
    raise UDAPError("unsupported_request")


class Transport:
    """Direct source-bound HTTP; no URL input, proxies, redirects or retries."""

    def __init__(self, config: PeerConfig):
        if not isinstance(config, PeerConfig):
            raise UDAPError("invalid_peer_config")
        self.config, self.requests = config, 0

    def exchange(self, request: WireRequest) -> WireResponse:
        operation = _validate_wire(request)
        # Keep the final request slot for one explicit session-disconnect attempt.
        budget = MAX_REQUESTS if operation == "byebye" else MAX_REQUESTS - 1
        if self.requests >= budget:
            raise UDAPError("request_budget_exhausted")
        self.requests += 1
        connection = http.client.HTTPConnection(self.config.peer, self.config.port,
            timeout=self.config.timeout, source_address=(self.config.controller, 0))
        connection.set_debuglevel(0)
        try:
            with total_timeout(self.config.timeout):
                connection.request(request.method, request.path, body=request.body or None,
                    headers={"User-Agent": USER_AGENT, "Content-Type": "text/xml; charset=utf-8",
                             "Connection": "close", "Cache-Control": "no-cache"})
                response = connection.getresponse()
                headers = response.getheaders()
                if sum(len(k) + len(v) for k, v in headers) > 8192:
                    raise UDAPError("response_header_limit")
                lengths = [v for k, v in headers if k.lower() == "content-length"]
                if len(lengths) > 1 or response.getheader("Transfer-Encoding"):
                    raise UDAPError("ambiguous_response_framing")
                if response.getheader("Content-Encoding", "identity").lower() != "identity":
                    raise UDAPError("encoded_response_rejected")
                length = None
                if lengths:
                    if not re.fullmatch(r"[0-9]{1,7}", lengths[0]):
                        raise UDAPError("invalid_response_length")
                    length = int(lengths[0])
                    if length > MAX_BODY:
                        raise UDAPError("response_body_limit")
                if response.status != 200:
                    raise UDAPError("http_rejected", response.status)
                body = response.read(MAX_BODY + 1)
                if len(body) > MAX_BODY or (length is not None and len(body) != length):
                    raise UDAPError("response_body_limit_or_truncation")
                if request.method == "POST" and body:
                    raise UDAPError("unexpected_acknowledgement_body")
                if request.method == "GET":
                    content_type = response.getheader("Content-Type", "").split(";", 1)[0].strip().lower()
                    if content_type not in ("text/xml", "application/xml"):
                        raise UDAPError("unexpected_response_type")
                return WireResponse(response.status, body)
        except UDAPError:
            raise
        except (OSError, ValueError, RuntimeError, http.client.HTTPException):
            raise UDAPError("transport_failed") from None
        finally:
            connection.close()


def _dataset(data: bytes, maximum: int) -> list[ET.Element]:
    root = _parse_xml(data)
    listing = root[0]
    if listing.tag != "dataList" or listing.attrib != {"name": "App List"} or (listing.text or "").strip() or (listing.tail or "").strip() or len(listing) > maximum:
        raise UDAPError("unexpected_app_dataset")
    for row in listing:
        if row.tag != "data" or row.attrib or (row.tail or "").strip():
            raise UDAPError("unexpected_app_record")
    return list(listing)


def parse_app_count(data: bytes, category=1) -> int:
    _integer(category, 1, 3)
    rows = _dataset(data, 1)
    if len(rows) != 1:
        raise UDAPError("missing_app_count")
    values = _leaves(rows[0], {"type", "number"})
    if values["type"] != str(category) or not re.fullmatch(r"[0-9]{1,4}", values["number"]):
        raise UDAPError("invalid_app_count")
    return _integer(int(values["number"]), 0, 2048)


@dataclass(frozen=True)
class App:
    auid: str = field(repr=False)
    name: str = field(repr=False)
    category: int


def parse_app_list(data: bytes, requested: int) -> tuple[App, ...]:
    _integer(requested, 1, 16)
    result, seen = [], set()
    for row in _dataset(data, requested):
        fields = _leaves(row, {"auid", "name", "type", "cpid", "adult", "icon_name"})
        if not re.fullmatch(r"[0-9a-fA-F]{1,32}", fields["auid"]) or fields["auid"].lower() in seen:
            raise UDAPError("invalid_or_duplicate_app_id")
        if fields["type"] not in ("2", "3") or fields["adult"] not in ("true", "false"):
            raise UDAPError("invalid_app_metadata")
        _text(fields["name"], 256)
        _text(fields["cpid"], 256)
        _text(fields["icon_name"], 512)
        seen.add(fields["auid"].lower())
        result.append(App(fields["auid"], fields["name"], int(fields["type"])))
    return tuple(result)


def read_pairing_pin() -> str:
    """Fail closed when hidden input is unavailable; never fall back to echo."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", getpass.GetPassWarning)
            return getpass.getpass("TV pairing code (hidden): ")
    except (getpass.GetPassWarning, EOFError, OSError):
        raise UDAPError("hidden_pairing_input_unavailable") from None


@dataclass(frozen=True)
class CallbackEvent:
    name: str
    visible: bool | None = None
    mode: str | None = None
    state: str | None = None
    text_present: bool | None = None


def parse_callback(path: str, data: bytes) -> CallbackEvent:
    root = _parse_xml(data, MAX_CALLBACK)
    name = root[0].findtext("name")
    if path == EVENT_PATH and name == "KeyboardVisible":
        values = _api(data, "event", {"name", "value", "mode"})
        if values["value"] not in ("true", "false") or values["mode"] not in ("default", "password"):
            raise UDAPError("invalid_keyboard_event")
        return CallbackEvent(name, values["value"] == "true", values["mode"])
    if path == EVENT_PATH and name == "TextEdited":
        values = _api(data, "event", {"name", "state", "value"})
        if values["state"] not in ("EditStart", "Editing", "EditEnd"):
            raise UDAPError("invalid_edit_state")
        # The complete field text is deliberately absent from returned/stored data.
        return CallbackEvent(name, state=values["state"], text_present=bool(values["value"]))
    if path == PAIRING_PATH and name == "byebye":
        values = _api(data, "pairing", {"name", "port"})
        if not re.fullmatch(r"[0-9]{1,5}", values["port"]):
            raise UDAPError("invalid_callback_port")
        _integer(int(values["port"]), 1, 65535)
        return CallbackEvent(name)
    raise UDAPError("unsupported_callback")


@dataclass(frozen=True)
class Inventory:
    total: int
    apps: tuple[App, ...] = field(repr=False)
    partial: bool


@dataclass(frozen=True)
class SmartTextPlan:
    """One consumed confirmation; requests are inspectable but not transport-enabled."""

    requests: tuple[WireRequest, ...] = field(repr=False)
    transmission_enabled: bool = False


class Session:
    def __init__(self, transport: Transport, callback_port: int, *, callback_ready: Callable[[], bool], clock=time.monotonic):
        _integer(callback_port, 1, 65535)
        if not callable(callback_ready):
            raise UDAPError("callback_readiness_required")
        self.transport, self.callback_port = transport, callback_port
        self.callback_ready, self.clock = callback_ready, clock
        self.state = "new"
        self._hello_attempted = False
        self._events = 0
        self._keyboard_at = None
        self._editing = None
        self._confirmed_at = None
        self._lock = threading.RLock()

    def __repr__(self):
        return "<UDAP Session state=%s; credentials and field text not retained>" % self.state

    def _revoke_text(self):
        self._keyboard_at = self._editing = self._confirmed_at = None

    def _ready(self):
        if self.callback_ready() is not True:
            self._revoke_text()
            raise UDAPError("callback_receiver_not_ready")

    def request_pairing_code(self, *, owner_approved: bool):
        with self._lock:
            if owner_approved is not True or self.state != "new":
                raise UDAPError("pairing_overlay_not_authorized")
            self._ready()
            self.state = "code_requested"
            try:
                self.transport.exchange(show_key_request())
            except UDAPError:
                self.state = "failed"
                raise

    def pair_interactive(self, *, pin_reader: Callable[[], str] = read_pairing_pin):
        with self._lock:
            if self.state != "code_requested":
                raise UDAPError("pairing_state_invalid")
            self._ready()
            pin = request = None
            try:
                pin = pin_reader()
                request = hello_request(pin, self.callback_port)
                self._hello_attempted = True
                self.transport.exchange(request)
                self.state = "paired"
            except (UDAPError, KeyboardInterrupt):
                self.state = "failed"
                raise
            finally:
                pin = request = None

    def _paired(self):
        if self.state != "paired":
            raise UDAPError("paired_session_required")
        self._ready()

    def inventory(self, category=1) -> Inventory:
        with self._lock:
            self._paired()
            try:
                count = parse_app_count(self.transport.exchange(inventory_request(category)).body, category)
                if count == 0:
                    return Inventory(0, (), False)
                number = min(count, 16)
                self._paired()
                apps = parse_app_list(self.transport.exchange(inventory_request(category, number)).body, number)
                if category != 1 and any(app.category != category for app in apps):
                    raise UDAPError("app_category_filter_mismatch")
                return Inventory(count, apps, len(apps) < count)
            except UDAPError:
                self.state = "failed"
                self._revoke_text()
                raise

    def receive_callback(self, peer: str, path: str, data: bytes) -> CallbackEvent:
        with self._lock:
            if peer != self.transport.config.peer:
                raise UDAPError("unexpected_callback_peer")
            self._paired()
            self._events += 1
            if self._events > 64:
                self._revoke_text()
                raise UDAPError("callback_budget_exhausted")
            try:
                event = parse_callback(path, data)
            except UDAPError:
                self._revoke_text()
                raise
            if event.name == "byebye":
                self.state = "closed"
                self._revoke_text()
            elif event.name == "KeyboardVisible":
                self._revoke_text()
                if event.visible and event.mode == "default":
                    self._keyboard_at = self.clock()
            elif event.name == "TextEdited":
                if self._keyboard_at is None or event.state != "Editing":
                    self._revoke_text()
                    event = CallbackEvent("TextEdited", state=event.state)
                else:
                    self._editing = event.text_present
                    self._confirmed_at = None
            return event

    def confirm_browser_address_field(self, *, owner_confirmed: bool):
        with self._lock:
            self._paired()
            if owner_confirmed is not True or self._keyboard_at is None or self._editing is None or not 0 <= self.clock() - self._keyboard_at <= 30:
                self._revoke_text()
                raise UDAPError("normal_browser_address_field_not_confirmed")
            self._confirmed_at = self.clock()

    def prepare_local_url(self, url: str) -> SmartTextPlan:
        with self._lock:
            self._paired()
            if self._keyboard_at is None or self._confirmed_at is None or self._editing is None or not 0 <= self.clock() - self._keyboard_at <= 30 or not 0 <= self.clock() - self._confirmed_at <= 15:
                self._revoke_text()
                raise UDAPError("smarttext_confirmation_missing_or_expired")
            editing = self._editing
            self._revoke_text()  # A confirmation is consumed even if validation fails.
            _text(url, 512)
            try:
                parsed = urlsplit(url)
                valid = (parsed.scheme == "http" and parsed.hostname == self.transport.config.controller
                         and parsed.port is not None and 1 <= parsed.port <= 65535
                         and parsed.username is None and parsed.password is None
                         and not parsed.query and not parsed.fragment and not any(c.isspace() for c in url))
            except ValueError:
                valid = False
            if not valid:
                raise UDAPError("confirmed_controller_url_required")
            states = ([] if editing else [("EditStart", "")]) + [("Editing", url), ("EditEnd", url)]
            requests = tuple(WireRequest("POST", EVENT_PATH, _xml("event", "TextEdited", (("state", state), ("value", value)))) for state, value in states)
            return SmartTextPlan(requests)

    def close(self):
        with self._lock:
            if self.state == "closed":
                return
            should_disconnect = self._hello_attempted
            self.state = "closed"
            self._revoke_text()
            if should_disconnect:
                self.transport.exchange(byebye_request(self.callback_port))


class _PrivateArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        self.exit(2, "Invalid arguments. Use --help; pairing codes are never accepted as arguments.\n")


def main(argv=None) -> int:
    parser = _PrivateArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", choices=("pairing", "inventory", "smarttext"), default="inventory")
    args = parser.parse_args(argv)
    previews = {
        "pairing": {"steps": ["confirm callback receiver and visible overlay", "showKey once", "hidden local PIN input", "hello once", "byebye once on explicit close"], "live_cli_available": False},
        "inventory": {"steps": ["require paired session", "appnum_get type=1", "applist_get type=1 index=1 number<=16"], "pagination": False},
        "smarttext": {"steps": ["observe normal KeyboardVisible", "observe Editing without retaining field text", "owner confirms browser address field", "prepare one local URL plan"], "transmission_enabled": False},
    }
    print(json.dumps({"mode": "offline_only", "network_requests": 0, "plan": previews[args.dry_run]}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
