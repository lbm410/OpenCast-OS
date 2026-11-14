"""Bounded UDAP discovery and descriptor reads from a confirmed target.

No pairing, key commands, link traversal, port scans or subnet sweeps.
"""

from __future__ import annotations

import argparse
import datetime as dt
import http.client
import ipaddress
import json
import signal
import socket
import sys
import threading
import time
from contextlib import contextmanager
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

PRIVATE = tuple(ipaddress.ip_network(n) for n in
                ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"))
TARGETS = ("udap:rootservice", "urn:schemas-upnp-org:device:MediaRenderer:1")
MAX_BODY = 128 * 1024


@contextmanager
def total_timeout(seconds: float):
    """Wall-clock deadline on macOS/Linux, including slow headers and bodies.

    Main thread only; never replaces an importing application's active timer.
    """
    if (not hasattr(signal, "setitimer") or
            threading.current_thread() is not threading.main_thread()):
        raise RuntimeError("The total timeout requires macOS/Linux and the main thread")
    if seconds <= 0 or signal.getitimer(signal.ITIMER_REAL) != (0.0, 0.0):
        raise ValueError("Invalid deadline or an existing timer is active")
    previous = signal.getsignal(signal.SIGALRM)

    def expired(signum, frame):
        raise TimeoutError("The descriptor read exceeded its total deadline")

    signal.signal(signal.SIGALRM, expired)
    try:
        signal.setitimer(signal.ITIMER_REAL, seconds)
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def local_network(value: str) -> ipaddress.IPv4Network:
    network = ipaddress.IPv4Network(value, strict=True)
    if network.prefixlen < 24 or not any(network.subnet_of(n) for n in PRIVATE):
        raise ValueError("Provide the local RFC1918 subnet, /24 or narrower; public networks are rejected")
    return network


def local_host(value: str, network: ipaddress.IPv4Network) -> str:
    address = ipaddress.IPv4Address(value)
    if address not in network or address in (network.network_address, network.broadcast_address):
        raise ValueError("The IP must be a host within the specified local subnet")
    return str(address)


def search_packet(target: str) -> bytes:
    if target not in TARGETS:
        raise ValueError("Unsupported search target")
    return ("M-SEARCH * HTTP/1.1\r\nHOST: 239.255.255.250:1900\r\n"
            'MAN: "ssdp:discover"\r\nMX: 3\r\nST: ' + target +
            "\r\nUSER-AGENT: UDAP/2.0 OpenCast/0.1\r\n\r\n").encode("ascii")


def parse_ssdp(data: bytes) -> dict[str, str]:
    if len(data) > 8192:
        raise ValueError("SSDP response exceeds the size limit")
    lines = data.decode("ascii", "strict").split("\r\n")
    if lines[0] != "HTTP/1.1 200 OK":
        raise ValueError("Not an SSDP 200 response")
    result: dict[str, str] = {}
    for line in lines[1:]:
        if not line:
            break
        key, separator, value = line.partition(":")
        key = key.strip().lower()
        if not separator or not key or key in result:
            raise ValueError("Invalid or duplicate header")
        if any(ord(c) < 32 for c in value):
            raise ValueError("Control character in header")
        result[key] = value.strip()
    return {k: v for k, v in result.items() if k in ("location", "server", "st")}


def validate_location(url: str, target: str, network: ipaddress.IPv4Network) -> str:
    local_host(target, network)
    if any(ord(c) <= 32 for c in url):
        raise ValueError("URL contains whitespace or control characters")
    parsed = urllib.parse.urlsplit(url)
    if (parsed.scheme != "http" or parsed.hostname != target or parsed.username is not None
            or parsed.password is not None or parsed.fragment):
        raise ValueError("LOCATION must use HTTP to the confirmed literal IP, without credentials")
    if parsed.port is not None and not 1 <= parsed.port <= 65535:
        raise ValueError("Invalid port")
    return url


def discover(interface_ip: str, network: ipaddress.IPv4Network) -> dict:
    local_host(interface_ip, network)
    responses: list[dict] = []
    sent = 0
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind((interface_ip, 0))
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton(interface_ip))
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1)
        for st in TARGETS:
            sock.sendto(search_packet(st), ("239.255.255.250", 1900))
            sent += 1
            deadline = time.monotonic() + 4
            # At most 64 datagrams per query, even on a noisy LAN.
            for _ in range(64):
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                sock.settimeout(remaining)
                try:
                    data, peer = sock.recvfrom(8193)
                except socket.timeout:
                    break
                try:
                    local_host(peer[0], network)
                    record = {"ip": peer[0], **parse_ssdp(data)}
                    if record not in responses:
                        responses.append(record)
                except (ValueError, UnicodeError):
                    continue
    return {"status": "responses" if responses else "inconclusive_no_response",
            "sent_datagrams": sent, "responses": responses,
            "note": "Unauthenticated responses do not prove identity. No descriptors have been fetched."}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Redirect rejected: requests must remain on the confirmed target")


def parse_description(data: bytes) -> dict:
    if len(data) > MAX_BODY:
        raise ValueError("Descriptor exceeds the size limit")
    # UTF-8 only: reject null bytes/UTF-16, DTDs and entity declarations.
    decoded = data.decode("utf-8-sig", "strict")
    if "\x00" in decoded or "<!DOCTYPE" in decoded.upper() or "<!ENTITY" in decoded.upper():
        raise ValueError("Null bytes, DTDs and entity declarations are not allowed")
    root = ET.fromstring(decoded)
    allowed = {"friendlyName", "manufacturer", "modelName", "modelNumber",
               "deviceType", "serviceType", "serviceId", "SCPDURL", "controlURL",
               "eventSubURL", "serviceName"}
    fields: dict[str, list] = {}
    for count, element in enumerate(root.iter()):
        if count >= 2048:
            raise ValueError("Too many XML elements")
        tag = element.tag.rsplit("}", 1)[-1]
        if tag in allowed and element.text and element.text.strip():
            fields.setdefault(tag, []).append(element.text.strip()[:512])
    services = []
    for element in root.iter():
        if element.tag.rsplit("}", 1)[-1] != "service" or "name" not in element.attrib:
            continue
        api_groups = []
        for api in element.iter():
            if api.tag.rsplit("}", 1)[-1] == "api":
                names = [(child.text or "").strip()[:128] for child in api
                         if child.tag.rsplit("}", 1)[-1] == "name"]
                api_groups.append({"type": api.get("type", "")[:64], "names": names})
        services.append({"name": element.get("name", "")[:64], "apis": api_groups})
    if services:
        fields["udapServices"] = services
    return fields


def describe(url: str, target: str, network: ipaddress.IPv4Network,
             timeout: float = 8) -> dict:
    validate_location(url, target, network)
    with total_timeout(timeout):
        return _read_description(url, target)


def _read_description(url: str, target: str) -> dict:
    # Do not use environment proxies for private LAN traffic.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    request = urllib.request.Request(url, headers={"User-Agent": "UDAP/2.0 OpenCast/0.1",
                                                  "Connection": "close"}, method="GET")
    with opener.open(request, timeout=3) as response:
        data = bytearray()
        while True:
            chunk = response.read1(min(8192, MAX_BODY + 1 - len(data)))
            if not chunk:
                break
            data.extend(chunk)
            if len(data) > MAX_BODY:
                raise ValueError("Descriptor exceeds the size limit")
        return {"status": "description_received", "http_status": response.status,
                "target": target, "fields": parse_description(bytes(data)),
                "note": "Unauthenticated device-reported data; service URLs are not followed."}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    scan = sub.add_parser("discover", help="Two multicast queries, TTL=1; no address sweep")
    scan.add_argument("--interface-ip", required=True)
    scan.add_argument("--network", required=True)
    desc = sub.add_parser("describe", help="One GET to the advertised descriptor of the confirmed device")
    desc.add_argument("--confirmed-target", required=True)
    desc.add_argument("--location", required=True, help="LOCATION observed in SSDP")
    desc.add_argument("--network", required=True)
    args = parser.parse_args()
    try:
        network = local_network(args.network)
        result = (discover(args.interface_ip, network) if args.command == "discover" else
                  describe(args.location, args.confirmed_target, network))
        code = 0
    except (OSError, ValueError, RuntimeError, ET.ParseError,
            urllib.error.URLError, http.client.HTTPException) as error:
        result = {"status": "blocked_or_error", "error_type": type(error).__name__,
                  "error": str(error), "note": "This does not establish that the TV or service is absent"}
        code = 2
    result["observed_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return code


if __name__ == "__main__":
    sys.exit(main())
