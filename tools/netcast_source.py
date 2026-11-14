"""Build a reproducible source ZIP for LG App Test, not an installable TV package."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import zipfile

from tools.probe_server import ASSETS, ROOT, SHELL_ASSETS, SHELL_ROOT

MAX_ASSET = 1024 * 1024


def build_source(kind: str) -> tuple[bytes, dict]:
    if kind == "probe":
        root, routes = ROOT, ASSETS
    elif kind == "shell":
        root, routes = SHELL_ROOT, SHELL_ASSETS
    else:
        raise ValueError("Choose probe or shell")
    filenames = sorted({filename for filename, _ in routes.values()})
    entries = []
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED) as archive:
        for filename in filenames:
            # Files come from the fixed project allowlist, never a directory walk.
            descriptor = os.open(root / filename, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            try:
                stream = os.fdopen(descriptor, "rb")
            except BaseException:
                os.close(descriptor)
                raise
            with stream:
                info = os.fstat(stream.fileno())
                if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= MAX_ASSET:
                    raise ValueError("Source asset must be a bounded regular file")
                data = stream.read(MAX_ASSET + 1)
                if len(data) != info.st_size or len(data) > MAX_ASSET:
                    raise ValueError("Source asset changed or exceeded its limit")
            member = zipfile.ZipInfo(filename, date_time=(1980, 1, 1, 0, 0, 0))
            member.create_system = 3
            member.external_attr = (stat.S_IFREG | 0o644) << 16
            archive.writestr(member, data)
            entries.append({"path": filename, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    data = buffer.getvalue()
    return data, {"kind": kind, "entry_path": "index.html", "installable": False,
                  "purpose": "Source input for LG App Test; backend/entitlement availability unverified",
                  "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(), "files": entries}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=("probe", "shell"))
    parser.add_argument("--output", type=Path, required=True, help="New ZIP in an existing local directory")
    args = parser.parse_args(argv)
    try:
        data, report = build_source(args.kind)
        with args.output.open("xb") as stream:
            stream.write(data)
        print(json.dumps(report, indent=2))
        return 0
    except (OSError, ValueError) as error:
        parser.exit(1, f"Source bundle error: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
