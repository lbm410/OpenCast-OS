"""Read SquashFS metadata and copy explicitly selected regular files on macOS.

Unsquashfs runs offline, without filesystem writes, in list/cat mode only.
Vendor modes, links, devices and ownership are never recreated on the host.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import resource
import subprocess
import tempfile

MAX_COPY = 256 * 1024**2
MAX_LIST = 8 * 1024**2
LINE = re.compile(r"^([-dlbcps][rwxstST-]{9})\s+\d+/\d+\s+(\d+(?:,\s*\d+)?)\s+\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}\s+squashfs-root(?:/(.*))?$")


def safe_path(name: str) -> str:
    path = PurePosixPath(name)
    if not name or path.is_absolute() or any(part in {"", ".", ".."} for part in name.split("/")):
        raise ValueError("Unsafe filesystem path")
    if any(ord(char) < 32 or ord(char) > 126 for char in name) or " -> " in name:
        raise ValueError("Unsupported filesystem path")
    return name


def parse_listing(text: str) -> dict[str, dict]:
    records: dict[str, dict] = {}
    for line in text.splitlines():
        match = LINE.fullmatch(line)
        if not match:
            raise ValueError("Unexpected listing format")
        mode, size, name = match.groups()
        if name is None:
            continue
        target = None
        if mode[0] == "l":
            name, target = name.split(" -> ", 1)
        safe_path(name)
        if name in records:
            raise ValueError("Duplicate filesystem path")
        records[name] = {"mode": mode, "size": int(size) if size.isdigit() else None}
        if target is not None:
            records[name]["link_target"] = target
    if len(records) > 50000:
        raise ValueError("Filesystem inventory exceeds bound")
    return records


def limits(max_bytes: int) -> None:
    resource.setrlimit(resource.RLIMIT_CPU, (30, 30))
    resource.setrlimit(resource.RLIMIT_FSIZE, (max_bytes, max_bytes))
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def read_tool(tool: Path, image: Path, options: list[str], max_bytes: int) -> bytes:
    # Parent creates the unnamed output file; child only has an inherited fd.
    # The sandbox denies paths for writing, network and launching other programs.
    executable = str(tool.resolve())
    profile = ('(version 1) (allow default) (deny network*) (deny file-write*) '
               '(deny process-exec) (allow process-exec (literal ' + json.dumps(executable) + '))')
    command = ["/usr/bin/sandbox-exec", "-p", profile, executable,
               "-no-progress", "-processors", "1", "-mem", "64M", "-no-wildcards"]
    env = {"PATH": "/usr/bin:/bin", "LC_ALL": "C", "TZ": "UTC"}
    with tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as errors:
        result = subprocess.run(command + options[:1] + [str(image.resolve())] + options[1:],
                                stdout=output, stderr=errors, timeout=45, env=env,
                                preexec_fn=lambda: limits(max_bytes))
        if result.returncode:
            raise ValueError(f"Unsquashfs failed with exit status {result.returncode}")
        if output.tell() > max_bytes:
            raise ValueError("Unsquashfs output exceeds bound")
        output.seek(0)
        return output.read(max_bytes + 1)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("--tool", required=True, type=Path)
    parser.add_argument("--select", action="append", default=[])
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    if bool(args.select) != bool(args.output_dir):
        parser.error("Selection and output directory must be supplied together")
    records = parse_listing(read_tool(args.tool, args.image, ["-lln"], MAX_LIST).decode("utf-8", "strict"))
    if len(args.select) != len(set(args.select)):
        raise ValueError("Duplicate selection")
    for name in args.select:
        safe_path(name)
        if name not in records or records[name]["mode"][0] != "-":
            raise ValueError("Selection must name a listed regular file")
        if not 0 <= records[name]["size"] <= MAX_COPY:
            raise ValueError("Selected file exceeds bound")
    if args.select:
        args.output_dir.mkdir(mode=0o700, exist_ok=False)
        for name in args.select:
            data = read_tool(args.tool, args.image, ["-cat", name], max(1, records[name]["size"]))
            if len(data) != records[name]["size"]:
                raise ValueError("Copied size differs from inventory")
            destination = args.output_dir.joinpath(*PurePosixPath(name).parts)
            destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            with destination.open("xb") as stream:
                stream.write(data)
            destination.chmod(0o444)
            records[name]["copied_sha256"] = hashlib.sha256(data).hexdigest()
    print(json.dumps({"image": args.image.name, "files": records}, indent=2))


if __name__ == "__main__":
    main()
