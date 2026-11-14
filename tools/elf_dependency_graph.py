"""Map declared ELF shared-library dependencies among explicit local files, offline.

The tool reads ELF metadata (``DT_NEEDED``, ``DT_SONAME``, ``DT_RPATH``, ``DT_RUNPATH``,
``PT_INTERP``) from an explicit set of local regular files and, optionally, name-level listings of
firmware packages. It reports which declared names have a candidate provider among the inspected
files, which are only listed in a package, and which have no candidate at all.

It is a static host reader. Inputs are opened read-only and are never loaded, linked, emulated or
run; ``ldd`` is never invoked. It does not walk directories: every inspected file is named by the
caller.

A candidate match is NOT proof of link or runtime compatibility. The tool does not reproduce the
dynamic loader: it applies no library search path or search order, no ``LD_LIBRARY_PATH``, no
``DT_RPATH``/``DT_RUNPATH`` expansion, no symbol or symbol-version resolution, no ``dlopen``
dependencies, no preloading and no secure-execution rules.

Declared ``DT_NEEDED`` edges are only one layer of what a process depends on. Libraries and
plugins opened at run time, and services reached through inter-process communication, are outside
this graph, so no output of this tool is a complete dependency list. Several candidates for one
name are reported as ambiguity; the tool never picks one of them.
"""

from __future__ import annotations

import argparse
import errno
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import posixpath
import re
import stat
import struct
import sys

try:
    from tools import elf_inventory
except ModuleNotFoundError:  # isolated mode (-I) or direct script execution
    _spec = importlib.util.spec_from_file_location(
        "elf_inventory", Path(__file__).resolve().with_name("elf_inventory.py"))
    elf_inventory = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(elf_inventory)

TOOL = "tools.elf_dependency_graph"
SCHEMA = 1

# Every limit is read at call time, so a caller or a test may lower it.
MAX_INPUTS = 512
MAX_TOTAL_INPUT_BYTES = 4 * 1024**3
MAX_FILE_LISTS = 4
MAX_FILE_LIST_BYTES = 1024**2
MAX_SPEC_BYTES = 4096
MAX_NEEDED_PER_FILE = 256
MAX_TOTAL_EDGES = 16384
MAX_NAME_BYTES = 255
MAX_PATH_BYTES = 1024
MAX_INVENTORIES = 16
MAX_INVENTORY_BYTES = 16 * 1024**2
MAX_INVENTORY_ENTRIES = 65536
MAX_SYMLINK_HOPS = 8
MAX_CANDIDATES_PER_NAME = 16
MAX_LISTINGS_PER_NAME = 32

LOCAL_SONAME = "local_soname"
LOCAL_BASENAME = "local_basename"
LOCAL_LISTED_LINK = "local_listed_link"
AMBIGUOUS = "ambiguous"
LISTED_ONLY = "listed_only"
UNRESOLVED = "unresolved"
CATEGORIES = (LOCAL_SONAME, LOCAL_BASENAME, LOCAL_LISTED_LINK, AMBIGUOUS, LISTED_ONLY, UNRESOLVED)
VERIFIED = (LOCAL_SONAME, LOCAL_BASENAME, LOCAL_LISTED_LINK)
RULES = {"soname": LOCAL_SONAME, "basename": LOCAL_BASENAME, "listed_link": LOCAL_LISTED_LINK}
RULE_ORDER = ("soname", "basename", "listed_link")
# Identity-check states. Only the allow-list lets a listing establish a provider.
LISTED_LINK_IDENTITY_STATES = ("listed_size_match",)
CONTRADICTED_IDENTITY_STATES = ("listed_size_mismatch", "not_listed", "listed_not_regular")
# Read passes over one open descriptor: ELF metadata, SHA-256, optional attribute annotation.
READ_PASSES = {"without_annotation": 2, "with_annotation": 3}
BYTE_BUDGET_RULE = ("each opened input is charged once, at the size reported by fstat on the "
                    "opened descriptor, before any content is read; the charge is kept when the "
                    "input is then rejected")

ELF_TYPES = {0: "ET_NONE", 1: "ET_REL", 2: "ET_EXEC", 3: "ET_DYN", 4: "ET_CORE"}
ET_DYN = 3
EM_ARM = 40
RESERVED_PACKAGE = "local"
PACKAGE_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,31}\Z")

CAVEATS = [
    "A candidate provider is a name-level match, not proof of link or runtime compatibility.",
    "No dynamic-loader behaviour is reproduced: no library search path or search order, no "
    "LD_LIBRARY_PATH, no DT_RPATH/DT_RUNPATH or $ORIGIN expansion, no ld.so cache, no preloading "
    "and no secure-execution rules. DT_RPATH and DT_RUNPATH are reported verbatim only.",
    "No symbol, symbol-version, relocation or TLS requirement is resolved. A provider with the "
    "right name can still lack a required symbol or version.",
    "Only DT_NEEDED and PT_INTERP declarations are mapped, and they are one layer only. "
    "Libraries and plugins opened at run time with dlopen, configuration-selected modules, and "
    "services reached through inter-process communication (sockets, message buses, shared "
    "memory, device nodes) are outside this graph. No output here is a complete dependency list.",
    "More than one inspected candidate for a name is reported as 'ambiguous'. The tool never "
    "picks a provider among several candidates, and an ambiguous name contributes no edge to "
    "the verified graph, the cycle report or the dependent counts.",
    "Rule strength differs: 'soname' means the provider's DT_SONAME equals the declared name; "
    "'basename' means only its file name does; 'listed_link' means a supplied package listing "
    "names a symbolic link that textually resolves to the provider's declared in-image path.",
    "'Verified' edges mean only that exactly one inspected file matched the declared name. "
    "It does not mean the loader would select that file: when the same name is also listed "
    "elsewhere and that listed file was not inspected, the edge carries listed_alternatives > 0 "
    "and the name appears under missing_evidence.local_with_uninspected_alternatives.",
    "A 'listed_only' candidate is a file name in a supplied package listing. The file was not "
    "inspected: it may not be an ELF file, and its architecture and ABI are unknown.",
    "Package listings are followed textually inside one listing. Absolute link targets, links "
    "through a directory that is itself a link, and links into another package are not resolved.",
    "The class, byte-order, machine and EABI-version checks compare ELF header fields only. The "
    "float-calling-convention check is an annotation derived from build attributes when "
    "available; 'not_compared' means no conclusion, not agreement.",
    "Firmware metadata is untrusted input. In-image identities are supplied by the caller and "
    "are checked only against a listing's entry type and size when a listing is supplied.",
    "The 'listed_link' rule applies only to an input whose identity check is "
    "'listed_size_match'. An identity that the listing contradicts ('listed_size_mismatch', "
    "'not_listed', 'listed_not_regular') or cannot confirm never establishes a provider through "
    "a listing; such inputs are reported under missing_evidence.contradicted_identities. "
    "DT_SONAME and file-name matches do not depend on the listing and stay classified on their "
    "own, with the candidate's identity check shown beside them.",
    "Byte budget: each input is opened once without following a final symbolic link, and the "
    "size reported by fstat on that descriptor is checked against the per-file limit and the "
    "remaining cumulative budget, then charged once, before any content is read. A rejected "
    "input keeps its charge. The file is then read from that one descriptor in at most two "
    "passes (ELF metadata, SHA-256), or three when ABI annotation is requested (the attribute "
    "reader parses the same open stream; the path is not looked up again). Every read is "
    "confined to the charged size; the budget counts the size once, not once per pass.",
]


class UsageError(ValueError):
    """The request itself is invalid or exceeds a bound; no partial report is produced."""


def _error_text(error: BaseException) -> str:
    """Describe a failure without echoing host paths that the caller did not supply."""
    if isinstance(error, OSError):
        code = errno.errorcode.get(error.errno, "OSError") if error.errno else "OSError"
        return f"{code}: {error.strerror or 'operating system error'}"
    text = str(error) or type(error).__name__
    return text.encode("utf-8", "replace").decode("utf-8")


def _has_control(text: str) -> bool:
    return any(ord(char) < 32 or ord(char) == 127 for char in text)


def _encodable(text: str) -> bool:
    """True if the text is valid Unicode: it has no isolated surrogate code point."""
    try:
        text.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True


def _byte_length(text: str) -> int:
    """UTF-8 length that never raises; un-encodable text is rejected separately."""
    return len(text.encode("utf-8", "surrogatepass"))


def _clean_relative(path) -> bool:
    """Accept only a normalised relative POSIX path with no empty, '.' or '..' component."""
    return (isinstance(path, str) and bool(path) and _encodable(path)
            and _byte_length(path) <= MAX_PATH_BYTES and not _has_control(path)
            and all(part not in ("", ".", "..") for part in path.split("/")))


def _valid_package(name: str) -> bool:
    return bool(PACKAGE_PATTERN.match(name)) and name != RESERVED_PACKAGE


def parse_spec(text: str) -> dict:
    """Parse one input: ``LOCAL_PATH`` or ``PACKAGE:IN_IMAGE_PATH=LOCAL_PATH``.

    A specification that starts with ``/``, ``./`` or ``../`` is always a plain local path. Any
    other specification that contains ``=`` must be the identity form.
    """
    if not isinstance(text, str) or not text or _has_control(text):
        raise UsageError("input specification is empty or contains control characters")
    if not _encodable(text):
        raise UsageError("input specification is not valid UTF-8 text")
    if _byte_length(text) > MAX_SPEC_BYTES:
        raise UsageError(f"input specification exceeds {MAX_SPEC_BYTES} bytes")
    if text.startswith(("/", "./", "../")) or "=" not in text:
        local = os.path.normpath(text)
        return {"id": f"{RESERVED_PACKAGE}:{local}", "package": None, "in_image_path": None,
                "path": text, "normalized_path": local, "match_basename": os.path.basename(local)}
    identity, local = text.split("=", 1)
    package, separator, in_image = identity.partition(":")
    if not separator or not _valid_package(package):
        raise UsageError("identity must be PACKAGE:IN_IMAGE_PATH=LOCAL_PATH with a package name "
                         "of letters, digits, '_', '.' or '-' (at most 32; 'local' is reserved); "
                         "prefix a plain local path that contains '=' with './'")
    if not _clean_relative(in_image):
        raise UsageError("in-image path must be a relative path without empty, '.' or '..' "
                         f"components and at most {MAX_PATH_BYTES} bytes")
    if not local:
        raise UsageError("identity form lacks a local path")
    return {"id": f"{package}:{in_image}", "package": package, "in_image_path": in_image,
            "path": local, "normalized_path": os.path.normpath(local),
            "match_basename": posixpath.basename(in_image)}


def _read_bounded(path, limit: int, label: str) -> bytes:
    """Read one small regular file completely, refusing final-component symbolic links."""
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NONBLOCK | getattr(os, "O_NOFOLLOW", 0))
    except OSError as error:
        raise UsageError(f"cannot open {label}: {_error_text(error)}") from None
    except ValueError:  # embedded NUL or text that cannot be encoded as a file name
        raise UsageError(f"cannot open {label}: the path is not a valid file name") from None
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise UsageError(f"{label} is not a regular file")
        chunks, remaining = [], limit + 1
        while remaining > 0:
            chunk = os.read(descriptor, min(remaining, 1024**2))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        data = b"".join(chunks)
    except OSError as error:
        raise UsageError(f"cannot read {label}: {_error_text(error)}") from None
    finally:
        os.close(descriptor)
    if len(data) > limit:
        raise UsageError(f"{label} exceeds {limit} bytes")
    return data


def read_file_list(path) -> list:
    """Return the input specifications of a list file: one per line, '#' comments allowed."""
    data = _read_bounded(path, MAX_FILE_LIST_BYTES, "file list")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise UsageError("file list is not valid UTF-8") from None
    specs = []
    for line in text.split("\n"):
        line = line.rstrip("\r")
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        specs.append(line)
        if len(specs) > MAX_INPUTS:
            raise UsageError(f"more than {MAX_INPUTS} inputs")
    return specs


def load_inventory(package: str, path) -> dict:
    """Load a package listing: {"image": ..., "files": {path: {"mode", "size", "link_target"}}}."""
    if not isinstance(package, str) or not _valid_package(package):
        raise UsageError("inventory package name is invalid")
    location = os.fspath(path)
    if not isinstance(location, str) or not _encodable(location):
        raise UsageError(f"inventory '{package}' path is not valid UTF-8 text")
    data = _read_bounded(location, MAX_INVENTORY_BYTES, f"inventory '{package}'")
    try:
        document = json.loads(data.decode("utf-8"))
        # JSON escapes can spell an isolated surrogate, which no file name, report or
        # comparison can represent. Such a listing is refused as a whole.
        json.dumps(document, ensure_ascii=False).encode("utf-8")
    except UnicodeEncodeError:
        raise UsageError(f"inventory '{package}' contains text that is not valid Unicode "
                         "(isolated surrogate)") from None
    except (ValueError, RecursionError):
        raise UsageError(f"inventory '{package}' is not valid UTF-8 JSON") from None
    files = document.get("files") if isinstance(document, dict) else None
    if not isinstance(files, dict):
        raise UsageError(f"inventory '{package}' lacks a 'files' object")
    if len(files) > MAX_INVENTORY_ENTRIES:
        raise UsageError(f"inventory '{package}' has more than {MAX_INVENTORY_ENTRIES} entries")
    entries, by_basename, ignored, counts = {}, {}, 0, {}
    for key in sorted(files):
        value = files[key]
        mode = value.get("mode") if isinstance(value, dict) else None
        if not _clean_relative(key) or not isinstance(mode, str) or not mode:
            ignored += 1
            continue
        kind = {"-": "file", "l": "symlink", "d": "directory"}.get(mode[0], "other")
        entry = {"type": kind}
        size = value.get("size")
        if isinstance(size, int) and not isinstance(size, bool) and size >= 0:
            entry["size"] = size
        if kind == "symlink":
            target = value.get("link_target")
            if (not isinstance(target, str) or not target or _has_control(target)
                    or _byte_length(target) > MAX_PATH_BYTES):
                ignored += 1
                continue
            entry["link_target"] = target
        entries[key] = entry
        counts[kind] = counts.get(kind, 0) + 1
        if kind in ("file", "symlink"):
            by_basename.setdefault(posixpath.basename(key), []).append(key)
    image = document.get("image")
    if not isinstance(image, str) or _has_control(image) or _byte_length(image) > MAX_NAME_BYTES:
        image = None
    return {"package": package, "path": location, "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(), "image": image,
            "entries": entries, "by_basename": by_basename, "ignored_entries": ignored,
            "entry_counts": counts}


def resolve_listing(entries: dict, path: str) -> dict:
    """Follow symbolic links textually inside one listing, with a hop bound and loop detection."""
    current, seen, hops = path, {path}, 0
    while True:
        entry = entries.get(current)
        if entry is None:
            return {"status": "dangling", "hops": hops, "stopped_at": current}
        if entry["type"] == "file":
            result = {"status": "file", "hops": hops, "resolved_path": current}
            if "size" in entry:
                result["size"] = entry["size"]
            return result
        if entry["type"] != "symlink":
            return {"status": "not_regular", "hops": hops, "stopped_at": current}
        target = entry["link_target"]
        if target.startswith("/"):
            return {"status": "absolute_target", "hops": hops, "stopped_at": current,
                    "target": target}
        if hops >= MAX_SYMLINK_HOPS:
            return {"status": "hop_limit", "hops": hops, "stopped_at": current}
        following = posixpath.normpath(posixpath.join(posixpath.dirname(current), target))
        if following in (".", "..") or following.startswith("../"):
            return {"status": "outside_image", "hops": hops, "stopped_at": current,
                    "target": target}
        if following in seen:
            return {"status": "loop", "hops": hops, "stopped_at": current}
        seen.add(following)
        current, hops = following, hops + 1


def collect_inputs(spec_texts) -> tuple:
    """Parse, sort and de-duplicate input specifications deterministically."""
    spec_texts = list(spec_texts)
    if len(spec_texts) > MAX_INPUTS:
        raise UsageError(f"more than {MAX_INPUTS} inputs")
    if not spec_texts:
        raise UsageError("no input files were given")
    grouped = {}
    for spec in (parse_spec(text) for text in spec_texts):
        grouped.setdefault(spec["id"], []).append(spec)
    unique, repeated, conflicting = [], [], []
    for identifier in sorted(grouped):
        group = sorted(grouped[identifier], key=lambda spec: spec["normalized_path"])
        paths = sorted({spec["normalized_path"] for spec in group})
        spec = dict(group[0])
        if len(paths) > 1:
            spec["conflict"] = True
            conflicting.append({"id": identifier, "paths": paths})
        elif len(group) > 1:
            repeated.append({"id": identifier, "times": len(group)})
        unique.append(spec)
    return unique, repeated, conflicting


def _validate_names(raw: dict) -> dict:
    """Check declared names against the bounds and split path-form names from match names."""
    needed = raw["needed"]
    if len(needed) > MAX_NEEDED_PER_FILE:
        raise ValueError(f"more than {MAX_NEEDED_PER_FILE} DT_NEEDED entries")
    sonames = raw["soname"]
    if len(sonames) > 1:
        raise ValueError("more than one DT_SONAME entry")
    for soname in sonames:
        if (not soname or not _encodable(soname) or _has_control(soname)
                or _byte_length(soname) > MAX_NAME_BYTES):
            raise ValueError("DT_SONAME is empty, has control characters, is not valid Unicode "
                             f"or exceeds {MAX_NAME_BYTES} bytes")
    declared = [("needed", name) for name in needed]
    if raw["interpreter"] is not None:
        declared.append(("interpreter", raw["interpreter"]))
    edges = []
    for kind, text in declared:
        name = posixpath.basename(text) if "/" in text else text
        if (not name or not _encodable(text) or _has_control(text)
                or _byte_length(name) > MAX_NAME_BYTES or _byte_length(text) > MAX_PATH_BYTES):
            raise ValueError(f"declared {kind} name is empty, has control characters, is not "
                             f"valid Unicode or exceeds {MAX_NAME_BYTES} bytes (path form: "
                             f"{MAX_PATH_BYTES})")
        edges.append({"kind": kind, "declared": text, "name": name, "path_form": "/" in text})
    for label in ("rpath", "runpath"):
        if any(_has_control(value) or not _encodable(value) for value in raw[label]):
            raise ValueError(f"DT_{label.upper()} contains control characters or is not valid "
                             "Unicode")
    return {"soname": sonames[0] if sonames else None, "edges": edges}


def _scalar(value, limit: int = 200):
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, str) and not _has_control(value) and _encodable(value):
        return value[:limit]
    return None


def _annotation(annotator, stream, size: int) -> dict:
    """Adapt an optional ABI annotation; any failure or surprise becomes 'unavailable'.

    The annotator parses the stream that is already open, so no path is looked up again.
    """
    base = {"source": "tools.arm_attributes", "kind": "annotation, not used for matching"}
    try:
        result = annotator(stream, size)
        if not isinstance(result, dict):
            raise TypeError("annotator returned an unexpected value")
        status = _scalar(result.get("status"))
        if not isinstance(status, str):
            raise ValueError("annotator returned no status")
        summary = result.get("summary")
        if not isinstance(summary, dict):
            return {**base, "status": status, "float_calling_convention": None,
                    "cpu_arch": None, "fp_arch": None}
        fields = {}
        for key in ("cpu_arch", "fp_arch"):
            field = summary.get(key)
            fields[key] = ({name: _scalar(field.get(name)) for name in ("value", "source",
                                                                         "meaning")}
                           if isinstance(field, dict) else None)
        convention = _scalar(summary.get("float_calling_convention"))
        return {**base, "status": status,
                "float_calling_convention": convention if isinstance(convention, str) else None,
                **fields}
    except Exception as error:  # the annotation is optional and must never fail the report
        return {**base, "status": "unavailable", "reason": type(error).__name__,
                "float_calling_convention": None, "cpu_arch": None, "fp_arch": None}


def load_default_annotator():
    """Return ``tools.arm_attributes.inspect_stream`` if that module can be imported, else None."""
    try:
        from tools import arm_attributes
        return arm_attributes.inspect_stream
    except Exception:
        pass
    try:
        spec = importlib.util.spec_from_file_location(
            "arm_attributes", Path(__file__).resolve().with_name("arm_attributes.py"))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.inspect_stream
    except Exception:
        return None


def _open_input(path: str, state: dict):
    """Open one input and charge its size to the byte budget before any content is read.

    The size is the one fstat reports for the descriptor that will be read, so a path that is
    replaced after an earlier check cannot be read beyond what was checked and charged. The
    descriptor is closed on every failure before its ownership passes to the stream.
    """
    descriptor = os.open(path, os.O_RDONLY | os.O_NONBLOCK | getattr(os, "O_NOFOLLOW", 0))
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode):
            raise ValueError("Only regular files are supported")
        if info.st_size > elf_inventory.MAX_FILE:
            raise ValueError("ELF file size is outside the allowed range")
        if info.st_size > MAX_TOTAL_INPUT_BYTES - state["charged"]:
            raise ValueError("cumulative input byte limit exceeded")
        stream = os.fdopen(descriptor, "rb")
    except BaseException:
        os.close(descriptor)
        raise
    state["charged"] += info.st_size
    return stream, info


def _inspect(spec: dict, state: dict, annotator) -> dict:
    """Inspect one input. Any failure becomes an error entry that declares no dependency."""
    entry = {"id": spec["id"], "package": spec["package"], "in_image_path": spec["in_image_path"],
             "path": spec["path"], "match_basename": spec["match_basename"]}
    try:
        if spec.get("conflict"):
            raise ValueError("the same identity was given for more than one local path")
        # Advisory only: it gives a clear refusal and avoids opening special files. The
        # descriptor opened below is what is enforced, checked and charged.
        kind = os.lstat(spec["path"]).st_mode
        if stat.S_ISLNK(kind):
            raise ValueError("Symbolic links are refused")
        if not stat.S_ISREG(kind):
            raise ValueError("Only regular files are supported")
        stream, before = _open_input(spec["path"], state)
        with stream:
            size = before.st_size
            raw = elf_inventory.inspect_stream(stream, size)
            stream.seek(0)
            digest, consumed = hashlib.sha256(), 0
            while consumed <= size:
                chunk = stream.read(min(1024**2, size + 1 - consumed))
                if not chunk:
                    break
                consumed += len(chunk)
                digest.update(chunk)
            names = _validate_names(raw)
            if len(names["edges"]) > MAX_TOTAL_EDGES - state["edges"]:
                raise ValueError("total dependency edge limit exceeded")
            annotation = _annotation(annotator, stream, size) if annotator else None
            after = os.fstat(stream.fileno())
            if (consumed != size or after.st_size != size
                    or after.st_mtime_ns != before.st_mtime_ns):
                raise ValueError("ELF changed during inspection")
    except (OSError, ValueError, struct.error) as error:
        return {**entry, "status": "error", "error": _error_text(error)}
    state["bytes"] += size
    state["edges"] += len(names["edges"])
    entry.update(
        status="ok", bytes=size, sha256=digest.hexdigest(), bits=raw["bits"],
        byte_order=raw["byte_order"], machine=raw["machine"], machine_id=raw["machine_id"],
        elf_type=raw["elf_type"], elf_type_name=ELF_TYPES.get(raw["elf_type"], "other"),
        soname=names["soname"], interpreter=raw["interpreter"], needed=list(raw["needed"]),
        rpath=list(raw["rpath"]), runpath=list(raw["runpath"]),
        arm_eabi_version=raw.get("arm_eabi_version"),
        arm_float_abi_flags=raw.get("arm_float_abi_flags"))
    entry["abi_annotation"] = annotation
    entry["_edges"] = names["edges"]
    return entry


def _identity_check(node: dict, inventories: dict) -> dict:
    """Compare a caller-supplied in-image identity with the listing of that package."""
    if node["package"] is None:
        return {"status": "no_identity"}
    inventory = inventories.get(node["package"])
    if inventory is None:
        return {"status": "no_inventory"}
    listed = inventory["entries"].get(node["in_image_path"])
    if listed is None:
        return {"status": "not_listed"}
    if listed["type"] != "file":
        return {"status": "listed_not_regular", "listed_type": listed["type"]}
    if node["status"] != "ok" or "size" not in listed:
        return {"status": "listed"}
    return {"status": "listed_size_match" if listed["size"] == node["bytes"]
            else "listed_size_mismatch", "listed_size": listed["size"]}


def _listings(name: str, inventories: dict, declared_paths: set) -> list:
    """Every listing entry whose file name equals ``name``, each resolved inside its listing."""
    found = []
    for package in sorted(inventories):
        inventory = inventories[package]
        for path in inventory["by_basename"].get(name, ()):
            entry = inventory["entries"][path]
            record = {"package": package, "path": path, "type": entry["type"]}
            if entry["type"] == "symlink":
                record["link_target"] = entry["link_target"]
            record.update(resolve_listing(inventory["entries"], path))
            if declared_paths:
                record["matches_declared_path"] = ("/" + path) in declared_paths
            found.append(record)
    return found


def _resolve_name(name: str, usage: dict, index: dict, inventories: dict) -> dict:
    """Classify one declared name. The result does not depend on which file declares it."""
    rules = {}
    for node in index["soname"].get(name, ()):
        rules[node["id"]] = "soname"
    for node in index["basename"].get(name, ()):
        rules.setdefault(node["id"], "basename")
    confirmations, listed, broken = {}, [], []
    for record in _listings(name, inventories, usage["declared_paths"]):
        if record["status"] != "file":
            broken.append(record)
            continue
        target = (record["package"], record["resolved_path"])
        local = index["identity"].get(target)
        if local is None:
            # The listed file was not inspected. If an input claims this identity but the
            # listing does not confirm it, say so; that input is not linked to this name.
            claimed = index["unlinked"].get(target)
            if claimed is not None:
                record["local_input_not_linked"] = {
                    "id": claimed["id"], "identity_check": claimed["identity_check"]["status"]}
                index["blocked"].setdefault(claimed["id"], []).append(
                    {"name": name, "listing": f"{record['package']}:{record['path']}"})
            listed.append(record)
            continue
        rules.setdefault(local["id"], "listed_link")
        confirmations.setdefault(local["id"], []).append(f"{record['package']}:{record['path']}")
    candidates = []
    for identifier in sorted(rules):
        node = index["id"][identifier]
        candidates.append({"id": identifier, "rule": rules[identifier],
                           "soname_matches": node["soname"] == name,
                           "basename_matches": node["match_basename"] == name,
                           "identity_check": node["identity_check"]["status"],
                           "listings": sorted(confirmations.get(identifier, []))})
    if len(candidates) == 1:
        category = RULES[candidates[0]["rule"]]
    elif candidates:
        category = AMBIGUOUS
    elif listed:
        category = LISTED_ONLY
    else:
        category = UNRESOLVED
    result = {
        "category": category,
        "kinds": sorted(usage["kinds"]),
        "declared_forms": sorted(usage["declared"]),
        "consumers": sorted(usage["consumers"]),
        "local_candidates": candidates[:MAX_CANDIDATES_PER_NAME],
        "local_candidate_count": len(candidates),
        "local_candidates_truncated": len(candidates) > MAX_CANDIDATES_PER_NAME,
        "listed": listed[:MAX_LISTINGS_PER_NAME],
        "listed_count": len(listed),
        "listed_truncated": len(listed) > MAX_LISTINGS_PER_NAME,
        "listed_packages": sorted({record["package"] for record in listed}),
        "listed_broken": broken[:MAX_LISTINGS_PER_NAME],
        "listed_broken_count": len(broken),
        "uninspected_inputs": sorted(node["id"] for node in index["failed"].get(name, ())),
    }
    if category == AMBIGUOUS:
        result["candidates_identical_content"] = len(
            {index["id"][candidate["id"]]["sha256"] for candidate in candidates}) == 1
    return result


def _convention(node: dict):
    annotation = node.get("abi_annotation")
    return annotation.get("float_calling_convention") if isinstance(annotation, dict) else None


def _compare(consumer: dict, provider: dict) -> dict:
    """Header-level compatibility flags of one candidate against one consumer."""
    def same(key):
        return "match" if consumer[key] == provider[key] else "mismatch"

    checks = {"class": same("bits"), "byte_order": same("byte_order"),
              "machine": same("machine_id")}
    if consumer["machine_id"] == EM_ARM and provider["machine_id"] == EM_ARM:
        checks["arm_eabi_version"] = same("arm_eabi_version")
    else:
        checks["arm_eabi_version"] = "not_applicable"
    ours, theirs = _convention(consumer), _convention(provider)
    if ours in ("base", "vfp") and theirs in ("base", "vfp"):
        checks["float_calling_convention"] = "same" if ours == theirs else "different"
    else:
        checks["float_calling_convention"] = "not_compared"
    checks["provider_elf_type"] = provider["elf_type_name"]
    mismatches = sorted(key for key, value in checks.items() if value == "mismatch")
    if checks["float_calling_convention"] == "different":
        mismatches.append("float_calling_convention")
    if provider["elf_type"] != ET_DYN:
        mismatches.append("provider_not_shared_object")
    return {"checks": checks, "mismatches": mismatches}


def _components(nodes: list, adjacency: dict) -> list:
    """Strongly connected components (iterative Tarjan), each returned as a sorted list."""
    order, low, on_stack, stack, components = {}, {}, set(), [], []
    for root in nodes:
        if root in order:
            continue
        order[root] = low[root] = len(order)
        stack.append(root)
        on_stack.add(root)
        work = [(root, iter(adjacency.get(root, ())))]
        while work:
            node, successors = work[-1]
            descended = False
            for following in successors:
                if following not in order:
                    order[following] = low[following] = len(order)
                    stack.append(following)
                    on_stack.add(following)
                    work.append((following, iter(adjacency.get(following, ()))))
                    descended = True
                    break
                if following in on_stack:
                    low[node] = min(low[node], order[following])
            if descended:
                continue
            work.pop()
            if work:
                parent = work[-1][0]
                low[parent] = min(low[parent], low[node])
            if low[node] == order[node]:
                component = []
                while True:
                    member = stack.pop()
                    on_stack.discard(member)
                    component.append(member)
                    if member == node:
                        break
                components.append(sorted(component))
    return sorted(components)


def _limits() -> dict:
    return {
        "max_inputs": MAX_INPUTS, "max_file_bytes": elf_inventory.MAX_FILE,
        "max_total_input_bytes": MAX_TOTAL_INPUT_BYTES, "max_file_lists": MAX_FILE_LISTS,
        "max_file_list_bytes": MAX_FILE_LIST_BYTES, "max_spec_bytes": MAX_SPEC_BYTES,
        "max_needed_per_file": MAX_NEEDED_PER_FILE, "max_total_edges": MAX_TOTAL_EDGES,
        "max_name_bytes": MAX_NAME_BYTES, "max_path_bytes": MAX_PATH_BYTES,
        "max_inventories": MAX_INVENTORIES, "max_inventory_bytes": MAX_INVENTORY_BYTES,
        "max_inventory_entries": MAX_INVENTORY_ENTRIES, "max_symlink_hops": MAX_SYMLINK_HOPS,
        "max_candidates_per_name": MAX_CANDIDATES_PER_NAME,
        "max_listings_per_name": MAX_LISTINGS_PER_NAME,
        "read_passes_per_file": dict(READ_PASSES), "byte_budget_charge": BYTE_BUDGET_RULE,
        "listed_link_identity_states": list(LISTED_LINK_IDENTITY_STATES),
    }


def _brief(record: dict) -> dict:
    keys = ("package", "path", "type", "resolved_path", "size", "hops", "matches_declared_path",
            "local_input_not_linked")
    return {key: record[key] for key in keys if key in record}


def build_report(inputs, inventories=(), annotator=None) -> dict:
    """Build the dependency report.

    ``inputs`` are input specifications (see ``parse_spec``); ``inventories`` are
    ``(package, path)`` pairs; ``annotator`` is an optional callable ``(stream, size)`` with the
    interface of ``tools.arm_attributes.inspect_stream``; it is given the stream that is already
    open. Raises ``UsageError`` for an invalid request.
    """
    inputs, inventories = list(inputs), list(inventories)
    if len(inventories) > MAX_INVENTORIES:
        raise UsageError(f"more than {MAX_INVENTORIES} inventories")
    specs, repeated, conflicting = collect_inputs(inputs)
    loaded = {}
    for package, path in inventories:
        if package in loaded:
            raise UsageError(f"inventory package '{package}' was given more than once")
        loaded[package] = load_inventory(package, path)

    state = {"bytes": 0, "charged": 0, "edges": 0}
    nodes = [_inspect(spec, state, annotator) for spec in specs]
    for node in nodes:
        node["identity_check"] = _identity_check(node, loaded)
    good = [node for node in nodes if node["status"] == "ok"]
    index = {"id": {node["id"]: node for node in good}, "soname": {}, "basename": {},
             "identity": {}, "unlinked": {}, "blocked": {}, "failed": {}}
    for node in good:
        if node["soname"] is not None:
            index["soname"].setdefault(node["soname"], []).append(node)
        index["basename"].setdefault(node["match_basename"], []).append(node)
        if node["package"] is not None:
            # Explicit allow-list: only a confirmed identity may be reached through a listing.
            confirmed = node["identity_check"]["status"] in LISTED_LINK_IDENTITY_STATES
            index["identity" if confirmed else "unlinked"][
                (node["package"], node["in_image_path"])] = node
    for node in nodes:
        if node["status"] != "ok":
            index["failed"].setdefault(node["match_basename"], []).append(node)

    usage = {}
    for node in good:
        for edge in node["_edges"]:
            record = usage.setdefault(edge["name"], {"kinds": set(), "declared": set(),
                                                     "consumers": set(), "declared_paths": set()})
            record["kinds"].add(edge["kind"])
            record["declared"].add(edge["declared"])
            record["consumers"].add(node["id"])
            if edge["path_form"]:
                record["declared_paths"].add(edge["declared"])
    names = {name: _resolve_name(name, usage[name], index, loaded) for name in sorted(usage)}

    verified_edges, flagged, adjacency = [], [], {}
    dependents = {node["id"]: set() for node in good}
    ambiguous_dependents = {node["id"]: set() for node in good}
    edge_counts = {kind: dict.fromkeys(CATEGORIES, 0) for kind in ("needed", "interpreter")}
    for node in good:
        counts = dict.fromkeys(CATEGORIES, 0)
        dependencies, interpreter, with_mismatch = [], None, 0
        for position, edge in enumerate(node.pop("_edges")):
            resolution = names[edge["name"]]
            category = resolution["category"]
            edge_counts[edge["kind"]][category] += 1
            candidates = []
            for candidate in resolution["local_candidates"]:
                provider = index["id"][candidate["id"]]
                comparison = _compare(node, provider)
                candidates.append({"id": candidate["id"], "rule": candidate["rule"],
                                   "self": candidate["id"] == node["id"], **comparison})
                if comparison["mismatches"]:
                    flagged.append({"consumer": node["id"], "name": edge["name"],
                                    "kind": edge["kind"], "provider": candidate["id"],
                                    "mismatches": comparison["mismatches"]})
                if category == AMBIGUOUS:
                    ambiguous_dependents[candidate["id"]].add(node["id"])
            with_mismatch += any(candidate["mismatches"] for candidate in candidates)
            record = {"kind": edge["kind"], "declared": edge["declared"], "name": edge["name"],
                      "path_form": edge["path_form"], "category": category,
                      "candidates": candidates,
                      "listed_alternatives": resolution["listed_count"] if candidates else 0}
            if category in VERIFIED:
                provider = candidates[0]["id"]
                verified_edges.append({"from": node["id"], "to": provider, "name": edge["name"],
                                       "kind": edge["kind"], "rule": candidates[0]["rule"],
                                       "listed_alternatives": resolution["listed_count"]})
                adjacency.setdefault(node["id"], set()).add(provider)
                dependents[provider].add(node["id"])
            if edge["kind"] == "interpreter":
                interpreter = record
            else:
                record["index"] = position
                counts[category] += 1
                dependencies.append(record)
        node["dependencies"] = dependencies
        node["interpreter_dependency"] = interpreter
        node["summary"] = {"needed": len(dependencies), **counts,
                           "interpreter": interpreter["category"] if interpreter else None,
                           "edges_with_mismatch_flags": with_mismatch}
    for node in good:
        node["verified_dependents"] = sorted(dependents[node["id"]])
        node["verified_dependent_count"] = len(dependents[node["id"]])
        node["ambiguous_dependent_count"] = len(ambiguous_dependents[node["id"]])

    ordered = {key: sorted(value) for key, value in adjacency.items()}
    cycles = []
    for component in _components(sorted(index["id"]), ordered):
        members = set(component)
        self_loop = len(component) == 1 and component[0] in adjacency.get(component[0], ())
        if len(component) == 1 and not self_loop:
            continue
        inside = sorted({(edge["from"], edge["to"], edge["name"], edge["kind"])
                         for edge in verified_edges
                         if edge["from"] in members and edge["to"] in members})
        cycles.append({"kind": "self_dependency" if self_loop else "cycle",
                       "members": component,
                       "edges": [{"from": a, "to": b, "name": name, "kind": kind}
                                 for a, b, name, kind in inside]})

    by_hash = {}
    for node in good:
        by_hash.setdefault(node["sha256"], []).append(node["id"])
    identical = [{"sha256": digest, "inputs": sorted(members)}
                 for digest, members in sorted(by_hash.items()) if len(members) > 1]

    missing = {"unresolved": [], "listed_only": [], "ambiguous": [],
               "local_with_uninspected_alternatives": [], "contradicted_identities": []}
    for node in nodes:
        if node["identity_check"]["status"] in CONTRADICTED_IDENTITY_STATES:
            missing["contradicted_identities"].append({
                "id": node["id"], "input_status": node["status"],
                "identity_check": node["identity_check"],
                "blocked_listed_links": sorted(
                    index["blocked"].get(node["id"], []),
                    key=lambda item: (item["name"], item["listing"]))})
    name_counts = dict.fromkeys(CATEGORIES, 0)
    for name, resolution in names.items():
        category = resolution["category"]
        name_counts[category] += 1
        common = {"name": name, "kinds": resolution["kinds"],
                  "consumers": resolution["consumers"]}
        if category == UNRESOLVED:
            missing["unresolved"].append({
                **common, "declared_forms": resolution["declared_forms"],
                "listed_broken": resolution["listed_broken"],
                "uninspected_inputs": resolution["uninspected_inputs"]})
        elif category == LISTED_ONLY:
            missing["listed_only"].append({
                **common, "packages": resolution["listed_packages"],
                "listed": [_brief(record) for record in resolution["listed"]],
                "listed_count": resolution["listed_count"],
                "listed_truncated": resolution["listed_truncated"]})
        elif category == AMBIGUOUS:
            missing["ambiguous"].append({
                **common,
                "candidates": [candidate["id"] for candidate in resolution["local_candidates"]],
                "candidate_count": resolution["local_candidate_count"],
                "identical_content": resolution["candidates_identical_content"]})
        elif resolution["listed"]:
            missing["local_with_uninspected_alternatives"].append({
                **common, "provider": resolution["local_candidates"][0]["id"],
                "rule": resolution["local_candidates"][0]["rule"],
                "packages": resolution["listed_packages"],
                "listed": [_brief(record) for record in resolution["listed"]],
                "listed_count": resolution["listed_count"]})

    errors = [node for node in nodes if node["status"] != "ok"]
    for node in nodes:
        del node["match_basename"]
    summary = {
        "inputs_given": len(inputs),
        "inputs_unique": len(nodes), "files_inspected": len(good), "file_errors": len(errors),
        "input_bytes": state["bytes"], "input_bytes_charged": state["charged"],
        "inputs_with_contradicted_identity": len(missing["contradicted_identities"]),
        "inventories": len(loaded),
        "needed_edges": sum(edge_counts["needed"].values()),
        "needed_edges_by_category": edge_counts["needed"],
        "interpreter_edges": sum(edge_counts["interpreter"].values()),
        "interpreter_edges_by_category": edge_counts["interpreter"],
        "distinct_names": len(names), "distinct_names_by_category": name_counts,
        "verified_local_edges": len(verified_edges),
        "verified_local_edges_with_listed_alternatives": sum(
            1 for edge in verified_edges if edge["listed_alternatives"]),
        "cycles": len(cycles),
        "compatibility_flag_records": len(flagged),
        "identical_content_groups": len(identical),
        "files_with_rpath_or_runpath": sum(1 for node in good if node["rpath"] or node["runpath"]),
        "abi_annotation": "requested" if annotator else "not_requested",
    }
    return {
        "tool": TOOL, "schema": SCHEMA, "status": "partial" if errors else "ok",
        "caveats": CAVEATS, "limits": _limits(),
        "inventories": [{key: inventory[key] for key in
                         ("package", "path", "bytes", "sha256", "image", "ignored_entries",
                          "entry_counts")} for _, inventory in sorted(loaded.items())],
        "files": nodes, "names": names, "missing_evidence": missing,
        "graph": {"verified_edges": sorted(verified_edges, key=lambda edge: (
                      edge["from"], edge["to"], edge["name"], edge["kind"])),
                  "cycles": cycles},
        "compatibility_flags": sorted(flagged, key=lambda item: (
            item["consumer"], item["name"], item["kind"], item["provider"])),
        "duplicates": {"repeated_inputs": repeated, "conflicting_identities": conflicting,
                       "identical_content": identical},
        "summary": summary,
    }


def render(report: dict) -> str:
    """Serialise deterministically: sorted keys, fixed indentation, no timestamps."""
    return json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


EPILOG = """\
inputs:
  Each INPUT (and each line of a --file-list) is either LOCAL_PATH or
  PACKAGE:IN_IMAGE_PATH=LOCAL_PATH. The second form records where the file lives inside a
  firmware package, so that it can be matched against a listing of that package. An INPUT that
  starts with '/', './' or '../' is always a plain local path. Directories are never walked.

inventories:
  --inventory PACKAGE=FILE supplies a JSON listing {"files": {"<in-image path>": {"mode": ...,
  "size": ..., "link_target": ...}}}. A listing only tells the tool that a name exists inside a
  package; the listed file is not inspected.

categories (one per declared name):
  local_soname       exactly one inspected file whose DT_SONAME equals the name
  local_basename     exactly one inspected file whose file name (not DT_SONAME) equals the name
  local_listed_link  exactly one inspected file reached through a listed symbolic link; only
                     for an input whose in-image identity the listing confirms (entry type
                     and byte size). A contradicted identity never establishes a provider.
  ambiguous          more than one inspected candidate
  listed_only        no inspected candidate; the name is listed in a supplied package listing
  unresolved         no inspected or listed candidate

A candidate match is NOT proof of link or runtime compatibility: the tool applies no search
path or search order, no LD_LIBRARY_PATH, no RPATH/RUNPATH expansion, no symbol or
symbol-version resolution, no dlopen dependencies, no preloading and no secure-execution rules.
It never executes, loads or emulates an input and never runs ldd.

Declared DT_NEEDED edges are one layer only. Run-time dlopen libraries, plugins and
inter-process services are outside the graph: no output is a complete dependency list.
Several candidates for one name are reported as ambiguity; the tool never picks one.

byte budget: each input is opened once and the size of the opened file is charged once,
before any content is read, also when the input is then rejected. The file is read from that
one descriptor in at most two passes, or three with ABI annotation.

Text that is not valid Unicode (in an input, a path or a listing) is refused as an error.

exit status: 0 complete report; 2 invalid request, a bound exceeded, or any per-file error.
"""


def _split_inventory(text: str) -> tuple:
    package, separator, path = text.partition("=")
    if not separator or not path or not _valid_package(package):
        raise UsageError("--inventory expects PACKAGE=FILE")
    return package, path


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__.split("\n\n")[0], epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("inputs", nargs="*", metavar="INPUT",
                        help="LOCAL_PATH or PACKAGE:IN_IMAGE_PATH=LOCAL_PATH")
    parser.add_argument("--file-list", action="append", default=[], metavar="FILE",
                        help="text file with one INPUT per line ('#' starts a comment line)")
    parser.add_argument("--inventory", action="append", default=[], metavar="PACKAGE=FILE",
                        help="name-level listing of one firmware package (repeatable)")
    parser.add_argument("--no-abi-annotation", action="store_true",
                        help="do not annotate ARM files with tools.arm_attributes")
    parser.add_argument("--output", type=Path, metavar="FILE",
                        help="write the JSON report to a new file; an existing file is refused")
    args = parser.parse_args(argv)
    try:
        if len(args.file_list) > MAX_FILE_LISTS:
            raise UsageError(f"more than {MAX_FILE_LISTS} file lists")
        if len(args.inventory) > MAX_INVENTORIES:
            raise UsageError(f"more than {MAX_INVENTORIES} inventories")
        inputs = list(args.inputs)
        if len(inputs) > MAX_INPUTS:
            raise UsageError(f"more than {MAX_INPUTS} inputs")
        for path in args.file_list:
            inputs.extend(read_file_list(path))
            if len(inputs) > MAX_INPUTS:
                raise UsageError(f"more than {MAX_INPUTS} inputs")
        inventories = [_split_inventory(text) for text in args.inventory]
        annotator = None if args.no_abi_annotation else load_default_annotator()
        report = build_report(inputs, inventories, annotator)
        if not args.no_abi_annotation and annotator is None:
            report["summary"]["abi_annotation"] = "unavailable"
    except UsageError as error:
        print(json.dumps({"status": "error", "error": str(error)}))
        return 2
    try:
        data = render(report).encode("utf-8")
    except UnicodeEncodeError:  # last resort: inputs are validated before they reach the report
        print(json.dumps({"status": "error",
                          "error": "report contains text that is not valid Unicode"}))
        return 2
    if args.output:
        try:
            with open(args.output, "xb") as handle:
                handle.write(data)
        except OSError as error:
            print(json.dumps({"status": "error",
                              "error": f"cannot create output: {_error_text(error)}"}))
            return 2
        print(json.dumps({"status": report["status"], "output": str(args.output),
                          "summary": report["summary"]}, sort_keys=True))
    else:
        binary = getattr(sys.stdout, "buffer", None)
        if binary is None:
            sys.stdout.write(data.decode("utf-8"))
        else:  # fixed UTF-8 bytes, independent of the locale's output encoding
            sys.stdout.flush()
            binary.write(data)
            binary.flush()
    return 0 if report["status"] == "ok" else 2


if __name__ == "__main__":
    sys.exit(main())
