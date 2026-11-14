"""Synthetic tests for the bounded ELF dependency mapper. No firmware is used or executed."""

import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from tools import elf_dependency_graph as edg

LOADER = "/lib/ld-linux.so.3"


def make_elf(*, needed=(), soname=None, interpreter=None, rpath=None, runpath=None, bits=32,
             endian="<", machine=40, file_type=3, flags=0x05000000, extra_sonames=()):
    """Build a minimal ELF file: one PT_LOAD, PT_DYNAMIC, a string table, optional PT_INTERP."""
    ehsize, phsize, width = (52, 32, 8) if bits == 32 else (64, 56, 16)
    strings = bytearray(b"\0")

    def add(text):
        offset = len(strings)
        strings.extend((text if isinstance(text, bytes) else text.encode()) + b"\0")
        return offset

    entries = [(1, add(name)) for name in needed]
    for name in ([soname] if soname is not None else []) + list(extra_sonames):
        entries.append((14, add(name)))
    if rpath is not None:
        entries.append((15, add(rpath)))
    if runpath is not None:
        entries.append((29, add(runpath)))
    phnum = 3 if interpreter is not None else 2
    dynamic_offset = ehsize + phnum * phsize
    dynamic_size = (len(entries) + 3) * width
    strings_offset = dynamic_offset + dynamic_size
    if isinstance(interpreter, str):
        interpreter = interpreter.encode()
    interp = (interpreter + b"\0") if interpreter is not None else b""
    interp_offset = strings_offset + len(strings)
    total = interp_offset + len(interp)
    base = 0x10000
    dynamic = [(5, base + strings_offset), (10, len(strings))] + entries + [(0, 0)]
    data = bytearray(total)
    data[:16] = b"\x7fELF" + bytes((1 if bits == 32 else 2, 1 if endian == "<" else 2, 1, 0)) \
        + bytes(8)
    struct.pack_into(endian + ("HHIIIIIHHHHHH" if bits == 32 else "HHIQQQIHHHHHH"), data, 16,
                     file_type, machine, 1, 0, ehsize, 0, flags, ehsize, phsize, phnum, 0, 0, 0)
    segments = [(1, 0, base, total, 5), (2, dynamic_offset, base + dynamic_offset, dynamic_size, 6)]
    if interpreter is not None:
        segments.append((3, interp_offset, base + interp_offset, len(interp), 4))
    for position, (kind, offset, address, size, permissions) in enumerate(segments):
        values = ((kind, offset, address, address, size, size, permissions, 4) if bits == 32 else
                  (kind, permissions, offset, address, address, size, size, 4))
        struct.pack_into(endian + ("8I" if bits == 32 else "II6Q"), data,
                         ehsize + position * phsize, *values)
    for position, pair in enumerate(dynamic):
        struct.pack_into(endian + ("iI" if bits == 32 else "qQ"), data,
                         dynamic_offset + position * width, *pair)
    data[strings_offset:strings_offset + len(strings)] = strings
    data[interp_offset:total] = interp
    return bytes(data)


def listing(files):
    """Serialise a package listing in the lab inventory format."""
    out = {}
    for path, value in files.items():
        if isinstance(value, str):
            out[path] = {"mode": "lrwxrwxrwx", "size": len(value), "link_target": value}
        elif value is None:
            out[path] = {"mode": "drwxr-xr-x", "size": 0}
        else:
            out[path] = {"mode": "-rwxr-xr-x", "size": value}
    return json.dumps({"image": "synthetic.pak", "files": out})


class Workspace(unittest.TestCase):
    def setUp(self):
        self._directory = tempfile.TemporaryDirectory()
        self.addCleanup(self._directory.cleanup)
        self.root = Path(self._directory.name)

    def write(self, name, data=None, **options):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(make_elf(**options) if data is None else data)
        return str(path)

    def inventory(self, name, files):
        path = self.root / f"{name}-inventory.json"
        path.write_text(files if isinstance(files, str) else listing(files))
        return (name, str(path))

    def spec(self, identity, name, **options):
        return f"{identity}={self.write(name, **options)}"

    @staticmethod
    def node(report, identifier):
        return next(entry for entry in report["files"] if entry["id"] == identifier)

    @staticmethod
    def edge(report, identifier, name):
        entry = Workspace.node(report, identifier)
        return next(dep for dep in entry["dependencies"] if dep["name"] == name)


class ResolutionTests(Workspace):
    def test_simple_chain_reports_metadata_and_dependents(self):
        report = edg.build_report([
            self.spec("p:bin/app", "app", needed=["libb.so.1", "liba.so.1"],
                      interpreter=LOADER, file_type=2, rpath="/opt/lib", runpath="$ORIGIN/x"),
            self.spec("p:lib/libb.so.1.0", "libb.so.1.0", soname="libb.so.1",
                      needed=["liba.so.1"]),
            self.spec("p:lib/liba.so.1.0", "liba.so.1.0", soname="liba.so.1"),
        ])
        self.assertEqual(report["status"], "ok")
        app = self.node(report, "p:bin/app")
        self.assertEqual(app["needed"], ["libb.so.1", "liba.so.1"])  # declared order kept
        self.assertEqual([dep["index"] for dep in app["dependencies"]], [0, 1])
        self.assertEqual((app["bits"], app["byte_order"], app["machine"], app["elf_type_name"]),
                         (32, "little", "ARM", "ET_EXEC"))
        self.assertEqual((app["interpreter"], app["rpath"], app["runpath"], app["soname"]),
                         (LOADER, ["/opt/lib"], ["$ORIGIN/x"], None))
        self.assertEqual(app["arm_eabi_version"], 5)
        self.assertEqual(len(app["sha256"]), 64)
        self.assertEqual(app["summary"]["local_soname"], 2)
        self.assertEqual(app["interpreter_dependency"]["category"], edg.UNRESOLVED)
        self.assertEqual(self.node(report, "p:lib/liba.so.1.0")["verified_dependents"],
                         ["p:bin/app", "p:lib/libb.so.1.0"])
        self.assertEqual(report["graph"]["cycles"], [])
        self.assertEqual(report["summary"]["needed_edges_by_category"][edg.LOCAL_SONAME], 3)
        self.assertEqual(report["summary"]["files_with_rpath_or_runpath"], 1)
        self.assertEqual(len(report["graph"]["verified_edges"]), 3)
        self.assertEqual({e["listed_alternatives"] for e in report["graph"]["verified_edges"]}, {0})

    def test_cycle_and_self_dependency_are_reported(self):
        report = edg.build_report([
            self.spec("p:liba.so", "liba.so", soname="liba.so", needed=["libb.so"]),
            self.spec("p:libb.so", "libb.so", soname="libb.so", needed=["liba.so"]),
            self.spec("p:libself.so", "libself.so", soname="libself.so", needed=["libself.so"]),
            self.spec("p:libleaf.so", "libleaf.so", soname="libleaf.so"),
        ])
        cycles = report["graph"]["cycles"]
        self.assertEqual([(cycle["kind"], cycle["members"]) for cycle in cycles],
                         [("cycle", ["p:liba.so", "p:libb.so"]),
                          ("self_dependency", ["p:libself.so"])])
        self.assertEqual([(e["from"], e["to"]) for e in cycles[0]["edges"]],
                         [("p:liba.so", "p:libb.so"), ("p:libb.so", "p:liba.so")])
        self.assertTrue(self.edge(report, "p:libself.so", "libself.so")["candidates"][0]["self"])
        self.assertEqual(report["summary"]["cycles"], 2)

    def test_longer_cycle_is_one_component(self):
        names = ["a", "b", "c", "d"]
        specs = [self.spec(f"p:lib{n}.so", f"lib{n}.so", soname=f"lib{n}.so",
                           needed=[f"lib{names[(i + 1) % 4]}.so"]) for i, n in enumerate(names)]
        specs.append(self.spec("p:app", "app", needed=["liba.so"]))
        cycles = edg.build_report(specs)["graph"]["cycles"]
        self.assertEqual(len(cycles), 1)
        self.assertEqual(cycles[0]["members"], [f"p:lib{n}.so" for n in names])

    def test_missing_provider_is_unresolved_and_creates_no_edge(self):
        report = edg.build_report([
            self.spec("p:app", "app", needed=["libmissing.so.1"]),
            self.spec("p:other", "other", needed=["libmissing.so.1", "libgone.so"]),
        ])
        edge = self.edge(report, "p:app", "libmissing.so.1")
        self.assertEqual((edge["category"], edge["candidates"]), (edg.UNRESOLVED, []))
        self.assertEqual(report["graph"]["verified_edges"], [])
        self.assertEqual(report["status"], "ok")  # a missing provider is a finding, not an error
        self.assertEqual(
            [(item["name"], item["consumers"])
             for item in report["missing_evidence"]["unresolved"]],
            [("libgone.so", ["p:other"]), ("libmissing.so.1", ["p:app", "p:other"])])
        self.assertEqual(report["summary"]["distinct_names_by_category"][edg.UNRESOLVED], 2)
        self.assertEqual(report["summary"]["needed_edges_by_category"][edg.UNRESOLVED], 3)
        self.assertEqual(report["missing_evidence"]["listed_only"], [])

    def test_missing_provider_is_not_satisfied_by_a_similar_name(self):
        report = edg.build_report([
            self.spec("p:app", "app", needed=["libx.so.1"]),
            self.spec("p:libx.so.2", "libx.so.2", soname="libx.so.2"),
            self.spec("p:libx.so", "libx.so"),
            self.spec("p:LIBX.SO.1", "upper", soname="LIBX.SO.1"),
        ])
        self.assertEqual(self.edge(report, "p:app", "libx.so.1")["category"], edg.UNRESOLVED)

    def test_two_files_with_the_same_soname_are_ambiguous_and_never_chosen(self):
        report = edg.build_report([
            self.spec("p:app", "app", needed=["libdup.so.1"]),
            self.spec("p:x/libdup.so.1.0", "x/libdup", soname="libdup.so.1"),
            self.spec("q:y/libdup.so.1.5", "y/libdup", soname="libdup.so.1",
                      needed=["libother.so"]),
        ])
        edge = self.edge(report, "p:app", "libdup.so.1")
        self.assertEqual(edge["category"], edg.AMBIGUOUS)
        self.assertEqual([c["id"] for c in edge["candidates"]],
                         ["p:x/libdup.so.1.0", "q:y/libdup.so.1.5"])
        self.assertEqual({c["rule"] for c in edge["candidates"]}, {"soname"})
        self.assertEqual(report["graph"]["verified_edges"], [])  # no provider is picked
        for identifier in ("p:x/libdup.so.1.0", "q:y/libdup.so.1.5"):
            provider = self.node(report, identifier)
            self.assertEqual(provider["verified_dependents"], [])
            self.assertEqual(provider["ambiguous_dependent_count"], 1)
        ambiguous = report["missing_evidence"]["ambiguous"]
        self.assertEqual(len(ambiguous), 1)
        self.assertEqual(ambiguous[0]["candidates"], ["p:x/libdup.so.1.0", "q:y/libdup.so.1.5"])
        self.assertFalse(ambiguous[0]["identical_content"])
        self.assertEqual(report["summary"]["needed_edges_by_category"][edg.AMBIGUOUS], 1)
        self.assertEqual(report["summary"]["needed_edges_by_category"][edg.LOCAL_SONAME], 0)

    def test_soname_and_basename_candidates_together_are_ambiguous(self):
        report = edg.build_report([
            self.spec("p:app", "app", needed=["libmix.so"]),
            self.spec("p:a/libmix.so.1", "a/libmix", soname="libmix.so"),
            self.spec("p:b/libmix.so", "b/libmix", soname="libelse.so"),
        ])
        edge = self.edge(report, "p:app", "libmix.so")
        self.assertEqual(edge["category"], edg.AMBIGUOUS)
        self.assertEqual({c["id"]: c["rule"] for c in edge["candidates"]},
                         {"p:a/libmix.so.1": "soname", "p:b/libmix.so": "basename"})

    def test_ambiguity_never_closes_a_cycle(self):
        report = edg.build_report([
            self.spec("p:liba.so", "liba", soname="liba.so", needed=["libb.so"]),
            self.spec("p:x/libb.so", "x/libb", soname="libb.so", needed=["liba.so"]),
            self.spec("p:y/libb.so", "y/libb", soname="libb.so", needed=["liba.so"]),
        ])
        self.assertEqual(report["graph"]["cycles"], [])
        self.assertEqual(self.edge(report, "p:liba.so", "libb.so")["category"], edg.AMBIGUOUS)

    def test_rule_labels_distinguish_soname_from_basename(self):
        report = edg.build_report([
            self.spec("p:app", "app",
                      needed=["libson.so.1", "libbase.so", "libother.so", "libboth.so"]),
            self.spec("p:lib/libson.so.1.2.3", "libson", soname="libson.so.1"),
            self.spec("p:lib/libbase.so", "libbase"),                       # no DT_SONAME
            self.spec("p:lib/libother.so", "libother", soname="libreal.so.9"),  # other DT_SONAME
            self.spec("p:lib/libboth.so", "libboth", soname="libboth.so"),
        ])
        expected = {"libson.so.1": (edg.LOCAL_SONAME, "soname", True, False),
                    "libbase.so": (edg.LOCAL_BASENAME, "basename", False, True),
                    "libother.so": (edg.LOCAL_BASENAME, "basename", False, True),
                    "libboth.so": (edg.LOCAL_SONAME, "soname", True, True)}
        for name, (category, rule, soname_matches, basename_matches) in expected.items():
            with self.subTest(name=name):
                self.assertEqual(self.edge(report, "p:app", name)["category"], category)
                candidate = report["names"][name]["local_candidates"][0]
                self.assertEqual((candidate["rule"], candidate["soname_matches"],
                                  candidate["basename_matches"]),
                                 (rule, soname_matches, basename_matches))
        self.assertEqual(self.node(report, "p:app")["summary"][edg.LOCAL_BASENAME], 2)
        self.assertEqual({edge["rule"] for edge in report["graph"]["verified_edges"]},
                         {"soname", "basename"})

    def test_in_image_basename_is_used_instead_of_the_local_file_name(self):
        report = edg.build_report([
            self.spec("p:app", "app", needed=["libreal.so", "renamed.bin"]),
            self.spec("p:lib/libreal.so", "renamed.bin"),
        ])
        self.assertEqual(self.edge(report, "p:app", "libreal.so")["category"], edg.LOCAL_BASENAME)
        self.assertEqual(self.edge(report, "p:app", "renamed.bin")["category"], edg.UNRESOLVED)

    def test_plain_local_path_uses_its_own_file_name(self):
        app = self.write("app", needed=["libplain.so"])
        lib = self.write("libplain.so")
        report = edg.build_report([app, lib])
        entry = self.node(report, f"local:{os.path.normpath(app)}")
        self.assertEqual((entry["package"], entry["in_image_path"], entry["path"]),
                         (None, None, app))
        self.assertEqual(entry["dependencies"][0]["category"], edg.LOCAL_BASENAME)
        self.assertEqual(entry["identity_check"], {"status": "no_identity"})

    def test_interpreter_is_resolved_by_final_path_component(self):
        loader = self.spec("root:lib/ld-2.12.so", "ld", soname="ld-linux.so.3")
        specs = [
            self.spec("p:bin/app", "app", interpreter=LOADER, file_type=2),
            self.spec("p:bin/app2", "app2", interpreter="/lib/ld-missing.so.1", file_type=2),
            loader,
        ]
        inventory = self.inventory("root", {
            "lib/ld-linux.so.3": "ld-2.12.so",
            "lib/ld-2.12.so": os.path.getsize(loader.split("=", 1)[1]),
            "opt/lib/ld-missing.so.1": 50})
        report = edg.build_report(specs, [inventory])
        edge = self.node(report, "p:bin/app")["interpreter_dependency"]
        self.assertEqual((edge["kind"], edge["declared"], edge["name"], edge["path_form"]),
                         ("interpreter", LOADER, "ld-linux.so.3", True))
        self.assertEqual(edge["category"], edg.LOCAL_SONAME)
        self.assertEqual(edge["candidates"][0]["id"], "root:lib/ld-2.12.so")
        self.assertEqual(report["names"]["ld-linux.so.3"]["local_candidates"][0]["listings"],
                         ["root:lib/ld-linux.so.3"])
        other = self.node(report, "p:bin/app2")["interpreter_dependency"]
        self.assertEqual(other["category"], edg.LISTED_ONLY)
        self.assertFalse(report["names"]["ld-missing.so.1"]["listed"][0]["matches_declared_path"])
        self.assertEqual(report["summary"]["interpreter_edges_by_category"][edg.LOCAL_SONAME], 1)
        self.assertEqual(report["summary"]["interpreter_edges_by_category"][edg.LISTED_ONLY], 1)
        self.assertEqual(report["summary"]["needed_edges"], 0)
        self.assertEqual(self.node(report, "p:bin/app")["dependencies"], [])

    def test_path_form_needed_matches_on_final_component_and_keeps_declaration(self):
        report = edg.build_report([
            self.spec("p:app", "app", needed=["/opt/lib/libabs.so"]),
            self.spec("p:lib/libabs.so", "libabs", soname="libabs.so"),
        ])
        edge = self.node(report, "p:app")["dependencies"][0]
        self.assertEqual((edge["declared"], edge["name"], edge["path_form"], edge["category"]),
                         ("/opt/lib/libabs.so", "libabs.so", True, edg.LOCAL_SONAME))


class InventoryTests(Workspace):
    def test_listed_only_candidates_follow_a_symlink_chain(self):
        inventory = self.inventory("lib", {
            "libchain.so": "libchain.so.1", "libchain.so.1": "sub/../libchain.so.1.2",
            "libchain.so.1.2": 4321, "libdirect.so": 77, "dir": None})
        other = self.inventory("alt", {"usr/lib/libdirect.so": 78})
        report = edg.build_report(
            [self.spec("p:app", "app", needed=["libchain.so", "libdirect.so", "libnone.so"])],
            [inventory, other])
        chain = report["names"]["libchain.so"]
        self.assertEqual(chain["category"], edg.LISTED_ONLY)
        self.assertEqual(chain["local_candidates"], [])
        self.assertEqual(chain["listed"], [{
            "package": "lib", "path": "libchain.so", "type": "symlink",
            "link_target": "libchain.so.1", "status": "file", "hops": 2,
            "resolved_path": "libchain.so.1.2", "size": 4321}])
        direct = report["names"]["libdirect.so"]
        self.assertEqual(direct["listed_packages"], ["alt", "lib"])
        self.assertEqual([(r["package"], r["path"], r["hops"]) for r in direct["listed"]],
                         [("alt", "usr/lib/libdirect.so", 0), ("lib", "libdirect.so", 0)])
        self.assertEqual(report["names"]["libnone.so"]["category"], edg.UNRESOLVED)
        missing = report["missing_evidence"]
        self.assertEqual([(item["name"], item["packages"]) for item in missing["listed_only"]],
                         [("libchain.so", ["lib"]), ("libdirect.so", ["alt", "lib"])])
        self.assertEqual([item["name"] for item in missing["unresolved"]], ["libnone.so"])
        self.assertEqual(self.edge(report, "p:app", "libchain.so")["candidates"], [])
        self.assertEqual(report["graph"]["verified_edges"], [])

    def test_symlink_loop_and_hop_bound_do_not_resolve(self):
        files = {"libloop.so": "libloop.so.1", "libloop.so.1": "libloop.so",
                 "libself.so": "libself.so"}
        for hop in range(12):
            files[f"deep/l{hop}"] = f"l{hop + 1}"
        files["deep/l12"] = 10
        files["libdeep.so"] = "deep/l0"
        files["libshort.so"] = "deep/l5"  # eight hops: exactly at the bound
        report = edg.build_report(
            [self.spec("p:app", "app",
                       needed=["libloop.so", "libself.so", "libdeep.so", "libshort.so"])],
            [self.inventory("lib", files)])
        statuses = {name: [r["status"] for r in report["names"][name]["listed_broken"]]
                    for name in ("libloop.so", "libself.so", "libdeep.so")}
        self.assertEqual(statuses, {"libloop.so": ["loop"], "libself.so": ["loop"],
                                    "libdeep.so": ["hop_limit"]})
        for name in statuses:
            self.assertEqual(report["names"][name]["category"], edg.UNRESOLVED)
            self.assertEqual(report["names"][name]["listed"], [])
        self.assertEqual(report["names"]["libdeep.so"]["listed_broken"][0]["hops"],
                         edg.MAX_SYMLINK_HOPS)
        short = report["names"]["libshort.so"]
        self.assertEqual((short["category"], short["listed"][0]["hops"]), (edg.LISTED_ONLY, 8))
        unresolved = {item["name"]: item for item in report["missing_evidence"]["unresolved"]}
        self.assertEqual(unresolved["libloop.so"]["listed_broken"][0]["status"], "loop")

    def test_lowered_hop_bound_is_enforced(self):
        inventory = self.inventory("lib", {"liba.so": "liba.so.1", "liba.so.1": "liba.so.1.0",
                                           "liba.so.1.0": 5})
        spec = self.spec("p:app", "app", needed=["liba.so"])
        with mock.patch.object(edg, "MAX_SYMLINK_HOPS", 1):
            report = edg.build_report([spec], [inventory])
        self.assertEqual(report["names"]["liba.so"]["category"], edg.UNRESOLVED)
        self.assertEqual(report["names"]["liba.so"]["listed_broken"][0]["status"], "hop_limit")
        self.assertEqual(report["limits"]["max_symlink_hops"], 1)

    def test_unresolvable_link_targets_are_not_candidates(self):
        inventory = self.inventory("lib", {
            "libabs.so": "/mnt/other/libabs.so.1", "libdangling.so": "nowhere.so",
            "libout.so": "../../libout.so.1", "libdir.so": "dir", "dir": None})
        names = ["libabs.so", "libdangling.so", "libout.so", "libdir.so"]
        report = edg.build_report([self.spec("p:app", "app", needed=names)], [inventory])
        found = {name: report["names"][name]["listed_broken"][0]["status"] for name in names}
        self.assertEqual(found, {"libabs.so": "absolute_target", "libdangling.so": "dangling",
                                 "libout.so": "outside_image", "libdir.so": "not_regular"})
        self.assertEqual(report["names"]["libabs.so"]["listed_broken"][0]["target"],
                         "/mnt/other/libabs.so.1")
        self.assertEqual(report["summary"]["distinct_names_by_category"][edg.UNRESOLVED], 4)

    def test_listed_link_reaches_a_local_input_by_identity(self):
        inventory = self.inventory("lgx", {"libgl.so": "libgl.so.1.4", "libgl.so.1.4": None})
        # The listing says libgl.so.1.4 is a directory: the link must not count.
        report = edg.build_report(
            [self.spec("p:app", "app", needed=["libgl.so"]),
             self.spec("lgx:libgl.so.1.4", "gl", soname="libgl.so.1")], [inventory])
        self.assertEqual(report["names"]["libgl.so"]["category"], edg.UNRESOLVED)
        self.assertEqual(self.node(report, "lgx:libgl.so.1.4")["identity_check"]["status"],
                         "listed_not_regular")
        lib = self.spec("lgy:libgl.so.1.4", "gl2", soname="libgl.so.1")
        size = os.path.getsize(lib.split("=", 1)[1])
        good = self.inventory("lgy", {"libgl.so": "libgl.so.1.4", "libgl.so.1.4": size,
                                      "extra/libgl.so": 9})
        report = edg.build_report([self.spec("p:app", "app", needed=["libgl.so"]), lib], [good])
        name = report["names"]["libgl.so"]
        self.assertEqual(name["category"], edg.LOCAL_LISTED_LINK)
        self.assertEqual(name["local_candidates"], [{
            "id": "lgy:libgl.so.1.4", "rule": "listed_link", "soname_matches": False,
            "basename_matches": False, "identity_check": "listed_size_match",
            "listings": ["lgy:libgl.so"]}])
        self.assertEqual([r["path"] for r in name["listed"]], ["extra/libgl.so"])
        self.assertEqual(self.node(report, "lgy:libgl.so.1.4")["identity_check"],
                         {"status": "listed_size_match", "listed_size": size})
        self.assertEqual(self.edge(report, "p:app", "libgl.so")["listed_alternatives"], 1)
        self.assertEqual(report["graph"]["verified_edges"][0]["listed_alternatives"], 1)
        self.assertEqual(report["summary"]["verified_local_edges_with_listed_alternatives"], 1)
        alternatives = report["missing_evidence"]["local_with_uninspected_alternatives"]
        self.assertEqual([(item["name"], item["provider"], item["rule"]) for item in alternatives],
                         [("libgl.so", "lgy:libgl.so.1.4", "listed_link")])

    def test_identity_is_checked_against_listing_size(self):
        lib = self.spec("pk:lib/libsz.so", "libsz", soname="libsz.so")
        report = edg.build_report(
            [lib, self.spec("pk:lib/absent.so", "absent"), self.spec("zz:x.so", "x")],
            [self.inventory("pk", {"lib/libsz.so": 1})])
        self.assertEqual(self.node(report, "pk:lib/libsz.so")["identity_check"],
                         {"status": "listed_size_mismatch", "listed_size": 1})
        self.assertEqual(self.node(report, "pk:lib/absent.so")["identity_check"],
                         {"status": "not_listed"})
        self.assertEqual(self.node(report, "zz:x.so")["identity_check"],
                         {"status": "no_inventory"})

    def test_malformed_inventory_entries_are_ignored_and_counted(self):
        document = json.dumps({"files": {
            "ok/libfine.so": {"mode": "-rw-r--r--", "size": 3},
            "/abs/libbad.so": {"mode": "-rw-r--r--", "size": 3},
            "a/../libbad.so": {"mode": "-rw-r--r--", "size": 3},
            "nomode/libbad.so": {"size": 3}, "list/libbad.so": [1, 2],
            "link/libbad.so": {"mode": "lrwxrwxrwx"},
            "dev/libbad.so": {"mode": "crw-r--r--", "size": "1, 3"}}})
        report = edg.build_report(
            [self.spec("p:app", "app", needed=["libbad.so", "libfine.so"])],
            [self.inventory("pk", document)])
        self.assertEqual(report["names"]["libbad.so"]["category"], edg.UNRESOLVED)
        self.assertEqual(report["names"]["libfine.so"]["category"], edg.LISTED_ONLY)
        record = report["inventories"][0]
        self.assertEqual((record["package"], record["ignored_entries"], record["image"]),
                         ("pk", 5, None))
        self.assertEqual(record["entry_counts"], {"file": 1, "other": 1})

    def test_invalid_inventories_are_refused(self):
        spec = self.spec("p:app", "app")
        cases = {"not-json": "{", "no-files": json.dumps({"image": "x"}),
                 "files-list": json.dumps({"files": []}), "array": "[]",
                 "deep": "[" * 100000}
        for name, text in cases.items():
            with self.subTest(name=name), self.assertRaises(edg.UsageError):
                edg.build_report([spec], [self.inventory(name, text)])
        binary = self.root / "binary.json"
        binary.write_bytes(b"\xff\xfe{}")
        with self.assertRaises(edg.UsageError):
            edg.build_report([spec], [("pk", str(binary))])
        with self.assertRaises(edg.UsageError):
            edg.build_report([spec], [("pk", str(self.root / "absent.json"))])
        good = self.inventory("pk", {"a": 1})
        link = self.root / "link.json"
        link.symlink_to(good[1])
        with self.assertRaises(edg.UsageError):
            edg.build_report([spec], [("pk", str(link))])
        with self.assertRaises(edg.UsageError):
            edg.build_report([spec], [("pk", str(self.root))])
        with self.assertRaises(edg.UsageError):
            edg.build_report([spec], [good, good])
        for package in ("", "local", "bad/name", "x" * 33):
            with self.subTest(package=package), self.assertRaises(edg.UsageError):
                edg.build_report([spec], [(package, good[1])])


class CompatibilityTests(Workspace):
    def test_class_byte_order_and_machine_mismatches_are_flagged(self):
        report = edg.build_report([
            self.spec("p:app", "app",
                      needed=["lib64.so", "libbe.so", "libmips.so", "libok.so", "libexe.so",
                              "libeabi.so"]),
            self.spec("p:lib64.so", "lib64", soname="lib64.so", bits=64, machine=183),
            self.spec("p:libbe.so", "libbe", soname="libbe.so", endian=">"),
            self.spec("p:libmips.so", "libmips", soname="libmips.so", machine=8),
            self.spec("p:libok.so", "libok", soname="libok.so"),
            self.spec("p:libexe.so", "libexe", soname="libexe.so", file_type=2),
            self.spec("p:libeabi.so", "libeabi", soname="libeabi.so", flags=0x04000000),
        ])
        found = {name: self.edge(report, "p:app", name)["candidates"][0]["mismatches"]
                 for name in ("lib64.so", "libbe.so", "libmips.so", "libok.so", "libexe.so",
                              "libeabi.so")}
        self.assertEqual(found, {
            "lib64.so": ["class", "machine"], "libbe.so": ["byte_order"],
            "libmips.so": ["machine"], "libok.so": [],
            "libexe.so": ["provider_not_shared_object"], "libeabi.so": ["arm_eabi_version"]})
        checks = self.edge(report, "p:app", "libok.so")["candidates"][0]["checks"]
        self.assertEqual(checks, {"class": "match", "byte_order": "match", "machine": "match",
                                  "arm_eabi_version": "match",
                                  "float_calling_convention": "not_compared",
                                  "provider_elf_type": "ET_DYN"})
        self.assertEqual(
            self.edge(report, "p:app", "libmips.so")["candidates"][0]["checks"]["arm_eabi_version"],
            "not_applicable")
        # A mismatch is a flag on a name-level candidate, not a change of category.
        self.assertEqual(self.edge(report, "p:app", "lib64.so")["category"], edg.LOCAL_SONAME)
        self.assertEqual([(f["name"], f["provider"]) for f in report["compatibility_flags"]],
                         [("lib64.so", "p:lib64.so"), ("libbe.so", "p:libbe.so"),
                          ("libeabi.so", "p:libeabi.so"), ("libexe.so", "p:libexe.so"),
                          ("libmips.so", "p:libmips.so")])
        self.assertEqual(report["summary"]["compatibility_flag_records"], 5)
        self.assertEqual(self.node(report, "p:app")["summary"]["edges_with_mismatch_flags"], 5)

    @staticmethod
    def label(stream, size):
        """Identify a synthetic fixture from the open stream: its DT_SONAME, or 'app'."""
        sonames = edg.elf_inventory.inspect_stream(stream, size)["soname"]
        return sonames[0] if sonames else "app"

    def test_float_calling_convention_annotation_is_compared_when_present(self):
        conventions = {"app": "base", "libvfp.so": "vfp", "libbase.so": "base",
                       "libboth.so": "compatible-with-both"}

        def annotator(stream, size):
            name = self.label(stream, size)
            if name == "libbroken.so":
                raise RuntimeError("annotator failure")
            if name == "libodd.so":
                return {"status": "ok", "summary": {"float_calling_convention": ["x"]}}
            if name == "libnone.so":
                return "unexpected"
            if name == "libsurrogate.so":
                return {"status": "ok", "summary": {
                    "float_calling_convention": "vfp\ud800",
                    "cpu_arch": {"value": 10, "source": "\udcff", "meaning": "Arm v7"}}}
            return {"status": "ok", "summary": {
                "float_calling_convention": conventions[name],
                "fp_arch": {"value": 3, "source": "explicit", "meaning": "FP v3", "tag": 10},
                "cpu_arch": {"value": 10, "source": "explicit", "meaning": "Arm v7"}}}

        names = ["libvfp.so", "libbase.so", "libboth.so", "libbroken.so", "libodd.so",
                 "libnone.so", "libsurrogate.so"]
        specs = [self.spec("p:app", "app", needed=names)]
        specs += [self.spec(f"p:{name}", name, soname=name) for name in names]
        report = edg.build_report(specs, annotator=annotator)
        found = {name: self.edge(report, "p:app", name)["candidates"][0] for name in names}
        self.assertEqual({n: c["checks"]["float_calling_convention"] for n, c in found.items()},
                         {"libvfp.so": "different", "libbase.so": "same",
                          "libboth.so": "not_compared", "libbroken.so": "not_compared",
                          "libodd.so": "not_compared", "libnone.so": "not_compared",
                          "libsurrogate.so": "not_compared"})
        self.assertEqual(found["libvfp.so"]["mismatches"], ["float_calling_convention"])
        self.assertEqual(found["libbase.so"]["mismatches"], [])
        annotation = self.node(report, "p:app")["abi_annotation"]
        self.assertEqual(annotation["float_calling_convention"], "base")
        self.assertEqual(annotation["fp_arch"],
                         {"value": 3, "source": "explicit", "meaning": "FP v3"})
        self.assertIn("annotation", annotation["kind"])
        broken = self.node(report, "p:libbroken.so")["abi_annotation"]
        self.assertEqual((broken["status"], broken["reason"]), ("unavailable", "RuntimeError"))
        self.assertEqual(self.node(report, "p:libnone.so")["abi_annotation"]["status"],
                         "unavailable")
        self.assertIsNone(self.node(report, "p:libodd.so")["abi_annotation"]
                          ["float_calling_convention"])
        # Un-encodable annotator text is dropped, never copied into the report.
        odd = self.node(report, "p:libsurrogate.so")["abi_annotation"]
        self.assertEqual((odd["float_calling_convention"], odd["cpu_arch"]["source"]),
                         (None, None))
        edg.render(report).encode("utf-8")
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["summary"]["abi_annotation"], "requested")

    def test_annotation_without_a_summary_is_tolerated(self):
        report = edg.build_report([self.spec("p:libb.so", "libb.so", soname="libb.so")],
                                  annotator=lambda stream, size: {"status": "unsupported"})
        other = self.node(report, "p:libb.so")["abi_annotation"]
        self.assertEqual((other["status"], other["float_calling_convention"]),
                         ("unsupported", None))

    def test_default_annotator_never_fails_the_report(self):
        annotator = edg.load_default_annotator()
        report = edg.build_report([self.spec("p:liba.so", "liba.so", soname="liba.so")],
                                  annotator=annotator)
        self.assertEqual(report["status"], "ok")
        annotation = self.node(report, "p:liba.so")["abi_annotation"]
        if annotator is None:
            self.assertIsNone(annotation)
        else:
            self.assertIsInstance(annotation["status"], str)
        self.assertIsNone(edg.build_report(
            [self.spec("p:libb.so", "libb.so")])["files"][0]["abi_annotation"])


class MalformedInputTests(Workspace):
    def test_bad_inputs_become_error_entries_without_edges(self):
        good = make_elf(needed=["libdep.so"], soname="libgood.so")
        unterminated = bytearray(make_elf(needed=["libdep.so"]))
        struct.pack_into("<iI", unterminated, 52 + 2 * 32 + 3 * 8, 1, 1)  # overwrite DT_NULL
        bad_offset = bytearray(make_elf(needed=["libdep.so"]))
        struct.pack_into("<iI", bad_offset, 52 + 2 * 32 + 2 * 8, 1, 999999)
        specs = [
            f"p:lib/libgood.so={self.write('good', good)}",
            f"p:lib/libdep.so={self.write('truncated', good[:40])}",
            f"p:text={self.write('text', b'not an ELF file at all' * 4)}",
            f"p:empty={self.write('empty', b'')}",
            f"p:unterminated={self.write('unterminated', bytes(unterminated))}",
            f"p:badoffset={self.write('badoffset', bytes(bad_offset))}",
            f"p:absent={self.root / 'absent'}",
        ]
        report = edg.build_report(specs)
        self.assertEqual(report["status"], "partial")
        errors = {entry["id"]: entry for entry in report["files"] if entry["status"] == "error"}
        self.assertEqual(sorted(errors), ["p:absent", "p:badoffset", "p:empty",
                                          "p:lib/libdep.so", "p:text", "p:unterminated"])
        for entry in errors.values():
            self.assertNotIn("dependencies", entry)
            self.assertNotIn("needed", entry)
            self.assertTrue(entry["error"])
        self.assertIn("ENOENT", errors["p:absent"]["error"])
        self.assertNotIn(str(self.root), errors["p:absent"]["error"])
        # The surviving file is still analysed; the failed file is not a provider.
        edge = self.edge(report, "p:lib/libgood.so", "libdep.so")
        self.assertEqual((edge["category"], edge["candidates"]), (edg.UNRESOLVED, []))
        self.assertEqual(report["names"]["libdep.so"]["uninspected_inputs"], ["p:lib/libdep.so"])
        self.assertEqual(report["missing_evidence"]["unresolved"][0]["uninspected_inputs"],
                         ["p:lib/libdep.so"])
        self.assertEqual(report["summary"]["file_errors"], 6)
        self.assertEqual(report["summary"]["files_inspected"], 1)
        self.assertEqual(report["summary"]["needed_edges"], 1)

    def test_symlinks_directories_and_fifos_are_refused(self):
        target = self.write("libreal.so", soname="libreal.so")
        link = self.root / "liblink.so"
        link.symlink_to(target)
        (self.root / "dir").mkdir()
        fifo = self.root / "fifo"
        os.mkfifo(fifo)
        report = edg.build_report([f"p:liblink.so={link}", f"p:dir={self.root / 'dir'}",
                                   f"p:fifo={fifo}", f"p:libreal.so={target}"])
        errors = {entry["id"]: entry["error"] for entry in report["files"]
                  if entry["status"] == "error"}
        self.assertEqual(errors, {"p:liblink.so": "Symbolic links are refused",
                                  "p:dir": "Only regular files are supported",
                                  "p:fifo": "Only regular files are supported"})
        self.assertEqual(report["summary"]["files_inspected"], 1)

    def test_invalid_declared_names_reject_the_file(self):
        cases = {
            "empty-needed": dict(needed=[""]),
            "control-needed": dict(needed=["lib\x01bad.so"]),
            "long-needed": dict(needed=["l" * 256]),
            "trailing-slash": dict(needed=["/opt/lib/"]),
            "two-sonames": dict(soname="liba.so", extra_sonames=["libb.so"]),
            "long-soname": dict(soname="s" * 256),
            "control-rpath": dict(rpath="/a\n/b"),
        }
        specs = [self.spec(f"p:{name}", name, **options) for name, options in cases.items()]
        specs.append(self.spec("p:ok", "ok", needed=["l" * 255], soname="s" * 255))
        report = edg.build_report(specs)
        errors = sorted(entry["id"] for entry in report["files"] if entry["status"] == "error")
        self.assertEqual(errors, sorted(f"p:{name}" for name in cases))
        self.assertEqual(sorted(report["names"]), ["l" * 255])


class BoundTests(Workspace):
    def test_maximum_number_of_inputs(self):
        specs = [self.spec(f"p:lib{i}.so", f"lib{i}.so") for i in range(4)]
        with mock.patch.object(edg, "MAX_INPUTS", 3):
            with self.assertRaises(edg.UsageError):
                edg.build_report(specs)
            self.assertEqual(edg.build_report(specs[:3])["summary"]["files_inspected"], 3)
            with self.assertRaises(edg.UsageError):  # repeats count against the bound
                edg.build_report([specs[0]] * 4)
        with self.assertRaises(edg.UsageError):
            edg.build_report([])

    def test_per_file_size_limit_of_the_shared_reader(self):
        spec = self.spec("p:liba.so", "liba.so", soname="liba.so")
        with mock.patch.object(edg.elf_inventory, "MAX_FILE", 64):
            report = edg.build_report([spec])
        self.assertEqual(report["status"], "partial")
        self.assertIn("size", report["files"][0]["error"])
        self.assertEqual(report["limits"]["max_file_bytes"], 64)

    def test_cumulative_input_byte_limit(self):
        first = self.spec("p:a", "a", soname="liba.so")
        size = os.path.getsize(first.split("=", 1)[1])
        second = self.spec("p:b", "b", soname="libb.so")
        with mock.patch.object(edg, "MAX_TOTAL_INPUT_BYTES", size + 1):
            report = edg.build_report([second, first])
        self.assertEqual([(e["id"], e["status"]) for e in report["files"]],
                         [("p:a", "ok"), ("p:b", "error")])
        self.assertEqual(report["files"][1]["error"], "cumulative input byte limit exceeded")
        self.assertEqual(report["summary"]["input_bytes"], size)

    def test_needed_entries_per_file_limit(self):
        over = self.spec("p:over", "over", needed=["liba.so", "libb.so", "libc.so"])
        at = self.spec("p:at", "at", needed=["liba.so", "libb.so"])
        with mock.patch.object(edg, "MAX_NEEDED_PER_FILE", 2):
            report = edg.build_report([over, at])
        self.assertEqual(self.node(report, "p:over")["status"], "error")
        self.assertIn("DT_NEEDED", self.node(report, "p:over")["error"])
        self.assertEqual(self.node(report, "p:at")["summary"]["needed"], 2)
        self.assertEqual(sorted(report["names"]), ["liba.so", "libb.so"])  # nothing truncated in

    def test_total_edge_limit_counts_interpreters(self):
        specs = [self.spec("p:a", "a", needed=["libx.so", "liby.so"]),
                 self.spec("p:b", "b", needed=["libx.so"], interpreter=LOADER),
                 self.spec("p:c", "c", needed=["libz.so"])]
        with mock.patch.object(edg, "MAX_TOTAL_EDGES", 3):
            report = edg.build_report(specs)
        self.assertEqual([(e["id"], e["status"]) for e in report["files"]],
                         [("p:a", "ok"), ("p:b", "error"), ("p:c", "ok")])
        self.assertEqual(self.node(report, "p:b")["error"],
                         "total dependency edge limit exceeded")
        self.assertEqual(report["summary"]["needed_edges"], 3)
        self.assertEqual(report["status"], "partial")

    def test_inventory_size_entry_and_count_limits(self):
        spec = self.spec("p:app", "app")
        inventory = self.inventory("pk", {"a": 1, "b": 2, "c": 3})
        with mock.patch.object(edg, "MAX_INVENTORY_ENTRIES", 2), \
                self.assertRaises(edg.UsageError):
            edg.build_report([spec], [inventory])
        with mock.patch.object(edg, "MAX_INVENTORY_BYTES", 16), self.assertRaises(edg.UsageError):
            edg.build_report([spec], [inventory])
        many = [self.inventory(f"pk{i}", {"a": 1}) for i in range(3)]
        with mock.patch.object(edg, "MAX_INVENTORIES", 2):
            with self.assertRaises(edg.UsageError):
                edg.build_report([spec], many)
            self.assertEqual(edg.build_report([spec], many[:2])["summary"]["inventories"], 2)

    def test_path_length_limit_applies_to_identities_and_listings(self):
        path = self.write("x")
        with self.assertRaises(edg.UsageError):
            edg.build_report([f"p:{'d/' * 600}x={path}"])
        with self.assertRaises(edg.UsageError):
            edg.build_report(["x" * 5000])
        with mock.patch.object(edg, "MAX_PATH_BYTES", 12):
            report = edg.build_report(
                [self.spec("p:app", "app", needed=["liblong.so"])],
                [self.inventory("pk", {"a/very/long/path/liblong.so": 1,
                                       "liblong.so": "a/very/long/target"})])
        self.assertEqual(report["inventories"][0]["ignored_entries"], 2)
        self.assertEqual(report["names"]["liblong.so"]["category"], edg.UNRESOLVED)

    def test_candidate_and_listing_lists_are_truncated_with_true_counts(self):
        specs = [self.spec("p:app", "app", needed=["libmany.so", "liblisted.so"])]
        specs += [self.spec(f"p:d{i}/libmany.so", f"d{i}/libmany.so", soname="libmany.so",
                            needed=[f"libdep{i}.so"]) for i in range(5)]
        inventory = self.inventory("pk", {f"d{i}/liblisted.so": i for i in range(6)})
        with mock.patch.object(edg, "MAX_CANDIDATES_PER_NAME", 3), \
                mock.patch.object(edg, "MAX_LISTINGS_PER_NAME", 4):
            report = edg.build_report(specs, [inventory])
        many = report["names"]["libmany.so"]
        self.assertEqual((many["category"], many["local_candidate_count"],
                          len(many["local_candidates"]), many["local_candidates_truncated"]),
                         (edg.AMBIGUOUS, 5, 3, True))
        self.assertEqual(len(self.edge(report, "p:app", "libmany.so")["candidates"]), 3)
        listed = report["names"]["liblisted.so"]
        self.assertEqual((listed["listed_count"], len(listed["listed"]),
                          listed["listed_truncated"]), (6, 4, True))
        item = report["missing_evidence"]["ambiguous"][0]
        self.assertEqual((item["candidate_count"], len(item["candidates"])), (5, 3))

    def test_file_list_limits(self):
        path = self.write("liba.so", soname="liba.so")
        big = self.root / "big.list"
        big.write_text("# comment\n" * 20)
        with mock.patch.object(edg, "MAX_FILE_LIST_BYTES", 64), self.assertRaises(edg.UsageError):
            edg.read_file_list(big)
        entries = self.root / "many.list"
        entries.write_text("".join(f"p:lib{i}.so={path}\n" for i in range(4)))
        with mock.patch.object(edg, "MAX_INPUTS", 3), self.assertRaises(edg.UsageError):
            edg.read_file_list(entries)
        binary = self.root / "binary.list"
        binary.write_bytes(b"\xff\xff\n")
        with self.assertRaises(edg.UsageError):
            edg.read_file_list(binary)
        link = self.root / "link.list"
        link.symlink_to(entries)
        with self.assertRaises(edg.UsageError):
            edg.read_file_list(link)
        with self.assertRaises(edg.UsageError):
            edg.read_file_list(self.root)
        entries.write_text(f"# header\n\n  \np:liba.so={path}\r\n{path}\n")
        self.assertEqual(edg.read_file_list(entries), [f"p:liba.so={path}", path])


class SpecificationTests(Workspace):
    def test_specification_grammar(self):
        spec = edg.parse_spec("lgli:lib/liba.so=some/dir/x=y.bin")
        self.assertEqual((spec["id"], spec["package"], spec["in_image_path"], spec["path"],
                          spec["match_basename"]),
                         ("lgli:lib/liba.so", "lgli", "lib/liba.so", "some/dir/x=y.bin",
                          "liba.so"))
        plain = edg.parse_spec("./odd=name/libz.so")
        self.assertEqual((plain["id"], plain["package"], plain["match_basename"]),
                         ("local:odd=name/libz.so", None, "libz.so"))
        self.assertEqual(edg.parse_spec("/abs/a=b")["id"], "local:/abs/a=b")
        self.assertEqual(edg.parse_spec("rel/../libq.so")["id"], "local:libq.so")
        for bad in ("", "noidentity=path", "pkg:=path", "pkg:/abs=path", "pkg:a/../b=path",
                    "pkg:a//b=path", "bad pkg:a=path", "local:a=path", "pkg:a=", "a\nb",
                    "pkg:./a=path", "x" * 33 + ":a=path"):
            with self.subTest(spec=bad), self.assertRaises(edg.UsageError):
                edg.parse_spec(bad)

    def test_duplicate_inputs_are_collapsed_and_reported(self):
        path = self.write("liba.so", soname="liba.so")
        copy = self.write("copy/liba.so", soname="liba.so")
        other = self.write("libother.so", soname="libother.so")
        app = self.spec("p:app", "app", needed=["liba.so", "libother.so"])
        report = edg.build_report([
            app, f"p:liba.so={path}", f"p:liba.so={self.root}/./liba.so", f"p:liba.so={path}",
            f"q:lib/liba.so={copy}", path,
            f"p:libother.so={other}", f"p:libother.so={copy}"])
        self.assertEqual(report["duplicates"]["repeated_inputs"],
                         [{"id": "p:liba.so", "times": 3}])
        self.assertEqual(report["duplicates"]["conflicting_identities"],
                         [{"id": "p:libother.so", "paths": sorted([copy, other])}])
        digest = self.node(report, "p:liba.so")["sha256"]
        self.assertEqual(report["duplicates"]["identical_content"],
                         [{"sha256": digest, "inputs": sorted(
                             [f"local:{path}", "p:liba.so", "q:lib/liba.so"])}])
        conflict = self.node(report, "p:libother.so")
        self.assertEqual(conflict["status"], "error")
        self.assertIn("more than one local path", conflict["error"])
        self.assertEqual(report["status"], "partial")
        self.assertEqual((report["summary"]["inputs_given"], report["summary"]["inputs_unique"]),
                         (8, 5))
        # Identical content under several inputs is still an ambiguous location, flagged as such.
        name = report["names"]["liba.so"]
        self.assertEqual((name["category"], name["candidates_identical_content"],
                          name["local_candidate_count"]), (edg.AMBIGUOUS, True, 3))
        self.assertTrue(report["missing_evidence"]["ambiguous"][0]["identical_content"])
        self.assertEqual(self.edge(report, "p:app", "libother.so")["category"], edg.UNRESOLVED)

    def test_output_is_deterministic_and_independent_of_input_order(self):
        specs = [
            self.spec("p:app", "app", needed=["libb.so", "liba.so", "libnone.so", "liblisted.so"],
                      interpreter=LOADER),
            self.spec("p:libb.so", "libb.so", soname="libb.so", needed=["liba.so"]),
            self.spec("p:liba.so", "liba.so", soname="liba.so", needed=["libb.so"]),
            self.spec("p:broken", "broken", data=b"\x7fELF" + bytes(8)),
        ]
        inventories = [self.inventory("pk", {"liblisted.so": "liblisted.so.1",
                                             "liblisted.so.1": 9}),
                       self.inventory("root", {"lib/ld-linux.so.3": 5})]
        first = edg.render(edg.build_report(specs, inventories))
        second = edg.render(edg.build_report(specs, inventories))
        shuffled = edg.render(edg.build_report(specs[::-1], inventories[::-1]))
        self.assertEqual(first.encode(), second.encode())
        self.assertEqual(first.encode(), shuffled.encode())
        document = json.loads(first)
        self.assertEqual([entry["id"] for entry in document["files"]],
                         sorted(entry["id"] for entry in document["files"]))
        self.assertEqual(document["tool"], "tools.elf_dependency_graph")
        text = " ".join(document["caveats"])
        for phrase in ("not proof of link or runtime compatibility", "LD_LIBRARY_PATH", "dlopen",
                       "inter-process", "symbol-version", "never picks a provider",
                       "listed_alternatives"):
            self.assertIn(phrase, text)

    def test_report_states_limits_in_effect(self):
        report = edg.build_report([self.spec("p:app", "app")])
        self.assertEqual(report["limits"], {
            "max_inputs": 512, "max_file_bytes": 1024**3, "max_total_input_bytes": 4 * 1024**3,
            "max_file_lists": 4, "max_file_list_bytes": 1024**2, "max_spec_bytes": 4096,
            "max_needed_per_file": 256, "max_total_edges": 16384, "max_name_bytes": 255,
            "max_path_bytes": 1024, "max_inventories": 16, "max_inventory_bytes": 16 * 1024**2,
            "max_inventory_entries": 65536, "max_symlink_hops": 8,
            "max_candidates_per_name": 16, "max_listings_per_name": 32,
            "read_passes_per_file": {"without_annotation": 2, "with_annotation": 3},
            "byte_budget_charge": edg.BYTE_BUDGET_RULE,
            "listed_link_identity_states": ["listed_size_match"]})
        self.assertIn("charged once", report["limits"]["byte_budget_charge"])
        self.assertIn("kept when the input is then rejected",
                      report["limits"]["byte_budget_charge"])
        text = " ".join(report["caveats"])
        for phrase in ("charged once, before any content is read", "three when ABI annotation",
                       "not once per pass", "listed_size_match"):
            self.assertIn(phrase, text)


class ByteBudgetRegressionTests(Workspace):
    """Review defect 1: the cumulative budget must bound every file that is opened."""

    @staticmethod
    def counting_parser(calls):
        original = edg.elf_inventory.inspect_stream

        def parser(stream, size):
            calls.append(size)
            return original(stream, size)
        return parser

    def test_rejected_input_still_consumes_the_byte_budget(self):
        first = self.write("a", needed=[""])          # parses and hashes, then is rejected
        second = self.write("b", soname="libb.so")    # valid
        sizes = (os.path.getsize(first), os.path.getsize(second))
        calls = []
        with mock.patch.object(edg, "MAX_TOTAL_INPUT_BYTES", max(sizes) + 1), \
                mock.patch.object(edg.elf_inventory, "inspect_stream",
                                  self.counting_parser(calls)):
            report = edg.build_report([f"p:a={first}", f"p:b={second}"])
        self.assertEqual([(e["id"], e["status"]) for e in report["files"]],
                         [("p:a", "error"), ("p:b", "error")])
        self.assertIn("declared needed name", report["files"][0]["error"])
        self.assertEqual(report["files"][1]["error"], "cumulative input byte limit exceeded")
        self.assertEqual(calls, [sizes[0]])  # the second file was never read
        self.assertEqual(report["summary"]["input_bytes"], 0)
        self.assertEqual(report["summary"]["input_bytes_charged"], sizes[0])
        self.assertEqual(report["status"], "partial")

    def test_every_kind_of_rejected_input_is_charged(self):
        cases = {"a-text": b"not an ELF file" * 8, "b-truncated": make_elf(soname="x.so")[:60],
                 "c-two-sonames": make_elf(soname="a.so", extra_sonames=["b.so"]),
                 "d-good": make_elf(soname="libgood.so")}
        specs = [f"p:{name}={self.write(name, data)}" for name, data in cases.items()]
        total = sum(len(data) for data in cases.values())
        report = edg.build_report(specs)
        self.assertEqual([e["status"] for e in report["files"]], ["error"] * 3 + ["ok"])
        self.assertEqual(report["summary"]["input_bytes_charged"], total)
        self.assertEqual(report["summary"]["input_bytes"], len(cases["d-good"]))
        with mock.patch.object(edg, "MAX_TOTAL_INPUT_BYTES", total - 1):
            limited = edg.build_report(specs)
        self.assertEqual([e["status"] for e in limited["files"]], ["error"] * 4)
        self.assertEqual(limited["files"][3]["error"], "cumulative input byte limit exceeded")
        self.assertEqual(limited["summary"]["input_bytes_charged"],
                         total - len(cases["d-good"]))

    def test_budget_is_enforced_on_the_opened_descriptor_not_on_a_pre_check(self):
        # Replacement race: the path looked small when it was first examined, but the file
        # that is opened is larger. Only the opened descriptor's size may be trusted.
        small = self.write("small", b"tiny")
        big = self.write("big.so", soname="libbig.so", needed=["libx.so"] * 40)
        size = os.path.getsize(big)
        stale = os.lstat(small)
        self.assertLess(stale.st_size, size)
        calls = []
        with mock.patch.object(edg.os, "lstat", lambda path: stale), \
                mock.patch.object(edg.elf_inventory, "inspect_stream",
                                  self.counting_parser(calls)):
            with mock.patch.object(edg, "MAX_TOTAL_INPUT_BYTES", size - 1):
                refused = edg.build_report([f"p:big.so={big}"])
            with mock.patch.object(edg, "MAX_TOTAL_INPUT_BYTES", size):
                accepted = edg.build_report([f"p:big.so={big}"])
            with mock.patch.object(edg.elf_inventory, "MAX_FILE", size - 1):
                oversized = edg.build_report([f"p:big.so={big}"])
        self.assertEqual(refused["files"][0]["error"], "cumulative input byte limit exceeded")
        self.assertEqual(refused["summary"]["input_bytes_charged"], 0)
        self.assertEqual(accepted["files"][0]["status"], "ok")
        self.assertEqual((accepted["files"][0]["bytes"],
                          accepted["summary"]["input_bytes_charged"]), (size, size))
        self.assertEqual(oversized["files"][0]["error"],
                         "ELF file size is outside the allowed range")
        self.assertEqual(oversized["summary"]["input_bytes_charged"], 0)
        self.assertEqual(calls, [size])  # only the accepted run read any content

    def test_file_that_grows_while_open_is_rejected_and_stays_charged(self):
        path = self.write("libgrow.so", soname="libgrow.so")
        size = os.path.getsize(path)

        def growing_annotator(stream, size):
            with open(path, "ab") as handle:
                handle.write(b"x")
            return {"status": "ok"}

        report = edg.build_report([f"p:libgrow.so={path}"], annotator=growing_annotator)
        self.assertEqual((report["files"][0]["status"], report["files"][0]["error"]),
                         ("error", "ELF changed during inspection"))
        self.assertEqual(report["summary"]["input_bytes_charged"], size)
        self.assertEqual(report["names"], {})

    def test_annotation_uses_the_open_stream_and_the_budget_counts_each_file_once(self):
        specs = [self.spec("p:app", "app", needed=["liba.so"]),
                 self.spec("p:liba.so", "liba.so", soname="liba.so")]
        paths = [spec.split("=", 1)[1] for spec in specs]
        seen, opened = [], []
        real_open = os.open

        def counting_open(path, *arguments, **options):
            opened.append(os.fspath(path))
            return real_open(path, *arguments, **options)

        def annotator(stream, size):
            stream.seek(0)
            seen.append((size, hashlib.sha256(stream.read()).hexdigest()))
            return {"status": "ok", "summary": {"float_calling_convention": "base"}}

        total = sum(os.path.getsize(path) for path in paths)
        with mock.patch.object(edg.os, "open", counting_open), \
                mock.patch.object(edg, "MAX_TOTAL_INPUT_BYTES", total):
            report = edg.build_report(specs, annotator=annotator)
        self.assertEqual(report["status"], "ok")
        self.assertEqual(sorted(opened), sorted(paths))  # one open per input, none for annotation
        self.assertEqual(seen, [(entry["bytes"], entry["sha256"]) for entry in report["files"]])
        self.assertEqual((report["summary"]["input_bytes"],
                          report["summary"]["input_bytes_charged"]), (total, total))
        self.assertEqual(self.edge(report, "p:app", "liba.so")["candidates"][0]["checks"]
                         ["float_calling_convention"], "same")

    def test_default_annotator_reads_the_stream_interface(self):
        annotator = edg.load_default_annotator()
        if annotator is None:
            self.skipTest("tools.arm_attributes cannot be imported right now")
        self.assertEqual(annotator.__name__, "inspect_stream")

    @unittest.skipUnless(os.path.isdir("/dev/fd"), "needs /dev/fd to count descriptors")
    def test_no_descriptor_is_left_open_on_any_rejection_path(self):
        target = self.write("libreal.so", soname="libreal.so")
        link = self.root / "liblink.so"
        link.symlink_to(target)
        specs = [f"p:a={self.write('a', needed=[''])}", f"p:b={self.write('b', b'junk' * 9)}",
                 f"p:c={self.root}", f"p:d={link}", f"p:e={self.root / 'absent'}",
                 f"p:f={self.write('f', soname='libf.so')}", f"p:g={target}"]
        before = len(os.listdir("/dev/fd"))
        with mock.patch.object(edg, "MAX_TOTAL_INPUT_BYTES",
                               os.path.getsize(specs[0].split("=", 1)[1]) + 40):
            report = edg.build_report(specs)
        with mock.patch.object(edg.os, "lstat", lambda path: os.stat(target)):
            raced = edg.build_report([f"p:c={self.root}", f"p:d={link}"])
        self.assertEqual(len(os.listdir("/dev/fd")), before)
        self.assertEqual([e["status"] for e in report["files"]], ["error"] * 7)
        # With the advisory check defeated, the opened descriptor still refuses both.
        self.assertEqual([e["status"] for e in raced["files"]], ["error", "error"])
        self.assertEqual(raced["files"][0]["error"], "Only regular files are supported")
        self.assertEqual(raced["summary"]["input_bytes_charged"], 0)


class EncodingRegressionTests(Workspace):
    """Review defect 2: text that cannot be encoded must be refused without a traceback."""

    SURROGATE_FILES = {
        "key": '{"files":{"\\ud800":{"mode":"-rw-r--r--","size":1}}}',
        "nested-key": '{"files":{"lib/\\udfff.so":{"mode":"-rw-r--r--","size":1}}}',
        "link-target": '{"files":{"liba.so":{"mode":"lrwxrwxrwx","size":1,'
                       '"link_target":"lib\\ud83d.so"}}}',
        "image": '{"image":"\\udc80.pak","files":{}}',
        "mode": '{"files":{"liba.so":{"mode":"-\\ud800","size":1}}}',
        "unused-field": '{"files":{"liba.so":{"mode":"-rw-r--r--","size":1,"note":"\\ud800"}}}',
    }

    def test_isolated_surrogate_anywhere_in_an_inventory_is_refused(self):
        spec = self.spec("p:app", "app", needed=["liba.so"])
        for name, text in self.SURROGATE_FILES.items():
            path = self.root / f"{name}.json"
            path.write_text(text, encoding="utf-8")
            with self.subTest(case=name):
                with self.assertRaises(edg.UsageError) as raised:
                    edg.load_inventory("p", path)
                self.assertNotIsInstance(raised.exception, UnicodeError)
                self.assertIn("not valid Unicode", str(raised.exception))
                self.assertLess(len(str(raised.exception)), 200)
                with self.assertRaises(edg.UsageError):
                    edg.build_report([spec], [("p", str(path))])
        # A properly paired escape is ordinary text and is accepted.
        paired = self.root / "paired.json"
        paired.write_text('{"files":{"lib\\ud83d\\ude00.so":{"mode":"-rw-r--r--","size":1}}}',
                          encoding="utf-8")
        self.assertEqual(edg.load_inventory("p", paired)["entry_counts"], {"file": 1})

    def test_unencodable_text_is_refused_on_every_request_path(self):
        path = self.write("liba.so", soname="liba.so")
        inventory = self.inventory("p", {"liba.so": 1})[1]
        for spec in ("lib\ud800.so", "./lib\udcff.so", f"p:lib\udc80.so={path}",
                     f"p:liba.so={path}\udcff", "p\ud800:liba.so=x"):
            with self.subTest(spec=ascii(spec)):
                with self.assertRaises(edg.UsageError) as raised:
                    edg.parse_spec(spec)
                self.assertNotIsInstance(raised.exception, UnicodeError)
                with self.assertRaises(edg.UsageError):
                    edg.build_report([spec])
        for package, location in (("p", inventory + "\udcff"), ("p", "\ud800.json"),
                                  ("p\ud800", inventory), ("\udcff", inventory)):
            with self.subTest(package=ascii(package), location=ascii(location)[-12:]):
                with self.assertRaises(edg.UsageError) as raised:
                    edg.build_report([path], [(package, location)])
                self.assertNotIsInstance(raised.exception, UnicodeError)
        for location in ("list\ud800.txt", "list\udcff.txt", "list\0.txt"):
            with self.subTest(file_list=ascii(location)):
                with self.assertRaises(edg.UsageError) as raised:
                    edg.read_file_list(location)
                self.assertNotIsInstance(raised.exception, UnicodeError)
        encoded = self.root / "encoded.list"
        encoded.write_bytes(b"p:lib\xed\xa0\x80.so=" + path.encode() + b"\n")
        with self.assertRaises(edg.UsageError):  # a UTF-8 encoded surrogate is not valid UTF-8
            edg.read_file_list(encoded)
        escaped = self.root / "escaped.list"
        escaped.write_text(f"p:lib\\ud800.so={path}\n")  # six ordinary characters, no surrogate
        self.assertEqual(edg.build_report(edg.read_file_list(escaped))["status"], "ok")

    def test_cli_reports_unencodable_input_as_a_json_error_without_traceback(self):
        path = self.write("liba.so", soname="liba.so")
        inventory = self.inventory("p", {"liba.so": 1})[1]
        surrogate = self.root / "surrogate.json"
        surrogate.write_text(self.SURROGATE_FILES["key"], encoding="utf-8")
        output = self.root / "never.json"
        cases = {
            "spec": [f"p:lib\udcff.so={path}"],
            "plain-path": ["lib\udc80.so"],
            "inventory-content": [path, "--inventory", f"p={surrogate}"],
            "inventory-path": [path, "--inventory", f"p={inventory}\udcff"],
            "inventory-package": [path, "--inventory", f"p\udcff={inventory}"],
            "file-list-path": ["--file-list", f"{self.root}/list\udcff.txt"],
        }
        for name, arguments in cases.items():
            with self.subTest(case=name):
                stream = io.StringIO()
                with contextlib.redirect_stdout(stream):
                    status = edg.main(arguments + ["--no-abi-annotation", "--output", str(output)])
                self.assertEqual(status, 2)
                lines = stream.getvalue().splitlines()
                self.assertEqual(len(lines), 1)
                self.assertEqual(json.loads(lines[0])["status"], "error")
                lines[0].encode("ascii")
                self.assertFalse(output.exists())

    def test_cli_process_gets_raw_undecodable_arguments_and_a_surrogate_inventory(self):
        path = self.write("liba.so", soname="liba.so")
        surrogate = self.root / "surrogate.json"
        surrogate.write_text(self.SURROGATE_FILES["key"], encoding="utf-8")
        script = Path(__file__).resolve().parents[1] / "tools" / "elf_dependency_graph.py"
        base = [sys.executable, "-I", "-B", str(script)]
        cases = {
            "spec-bytes": [b"p:lib\xff.so=" + path.encode()],
            "path-bytes": [b"./lib\xfe\xff.so"],
            "inventory-content": [path, "--inventory", f"p={surrogate}"],
            "inventory-path-bytes": [path, "--inventory",
                                     b"p=" + str(surrogate).encode() + b"\xff"],
        }
        for name, arguments in cases.items():
            with self.subTest(case=name):
                result = subprocess.run(base + arguments, capture_output=True, cwd=self.root,
                                        timeout=60)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertNotIn(b"Traceback", result.stderr)
                self.assertEqual(result.stderr, b"")
                lines = result.stdout.decode("ascii").splitlines()
                self.assertEqual(len(lines), 1)
                self.assertEqual(json.loads(lines[0])["status"], "error")

    def test_undecodable_elf_names_cannot_put_unencodable_text_in_a_report(self):
        raw = [b"lib\xed\xa0\x80bad.so", b"lib\xffx.so"]  # encoded surrogate, stray byte
        report = edg.build_report([
            self.spec("p:app", "app", needed=raw, interpreter=b"/lib/ld\xff.so"),
            self.spec("p:lib", "lib", soname=b"lib\xed\xb0\x80.so", rpath=b"/a\xc0/b")])
        self.assertEqual(report["status"], "ok")
        text = edg.render(report)
        text.encode("utf-8")  # the shared reader replaces invalid bytes; nothing un-encodable
        names = self.node(report, "p:app")["needed"]
        self.assertTrue(all("�" in name for name in names))
        self.assertFalse(any(0xD800 <= ord(char) <= 0xDFFF for char in text))

    def test_unencodable_name_from_the_reader_is_a_per_file_error(self):
        # Defence in depth: should the shared reader ever return such text, the file is
        # rejected and the report still renders.
        original = edg.elf_inventory.inspect_stream
        for field, value in (("needed", ["lib\ud800.so"]), ("soname", ["lib\udcff.so"]),
                             ("interpreter", "/lib/ld\ud800.so"), ("rpath", ["/a\udc80"]),
                             ("runpath", ["/b\ud800"])):
            def injected(stream, size, field=field, value=value):
                return {**original(stream, size), field: value}

            with self.subTest(field=field), \
                    mock.patch.object(edg.elf_inventory, "inspect_stream", injected):
                report = edg.build_report([self.spec("p:liba.so", "liba.so", soname="liba.so")])
                self.assertEqual(report["files"][0]["status"], "error")
                self.assertIn("not valid", report["files"][0]["error"])
                edg.render(report).encode("utf-8")

    def test_last_resort_guard_never_writes_an_unencodable_report(self):
        path = self.write("liba.so", soname="liba.so")
        output = self.root / "report.json"
        poisoned = edg.build_report([path])
        poisoned["files"][0]["path"] = "lib\ud800.so"
        for extra in ([], ["--output", str(output)]):
            stream = io.StringIO()
            with mock.patch.object(edg, "build_report", lambda *a, **k: poisoned), \
                    contextlib.redirect_stdout(stream):
                status = edg.main([path, "--no-abi-annotation"] + extra)
            self.assertEqual(status, 2)
            self.assertEqual(json.loads(stream.getvalue())["status"], "error")
            self.assertFalse(output.exists())


class IdentityRegressionTests(Workspace):
    """Review defect 3: a contradicted in-image identity must not establish an alias provider."""

    def test_contradicted_identity_does_not_establish_a_listed_link(self):
        provider = self.spec("p:actual.so.1", "provider", soname="other.so")
        size = os.path.getsize(provider.split("=", 1)[1])
        self.assertGreater(size, 1)
        report = edg.build_report(
            [self.spec("q:app", "app", needed=["libalias.so"]), provider],
            [self.inventory("p", {"libalias.so": "actual.so.1", "actual.so.1": 1})])
        node = self.node(report, "p:actual.so.1")
        self.assertEqual(node["identity_check"],
                         {"status": "listed_size_mismatch", "listed_size": 1})
        name = report["names"]["libalias.so"]
        self.assertEqual((name["category"], name["local_candidates"]), (edg.LISTED_ONLY, []))
        self.assertEqual(name["listed"][0]["local_input_not_linked"],
                         {"id": "p:actual.so.1", "identity_check": "listed_size_mismatch"})
        self.assertEqual(report["graph"]["verified_edges"], [])
        edge = self.edge(report, "q:app", "libalias.so")
        self.assertEqual((edge["category"], edge["candidates"]), (edg.LISTED_ONLY, []))
        self.assertEqual((node["verified_dependents"], node["ambiguous_dependent_count"]), ([], 0))
        self.assertEqual(report["missing_evidence"]["contradicted_identities"], [{
            "id": "p:actual.so.1", "input_status": "ok",
            "identity_check": {"status": "listed_size_mismatch", "listed_size": 1},
            "blocked_listed_links": [{"name": "libalias.so", "listing": "p:libalias.so"}]}])
        listed = report["missing_evidence"]["listed_only"][0]
        self.assertEqual(listed["listed"][0]["local_input_not_linked"]["id"], "p:actual.so.1")
        self.assertEqual(report["summary"]["inputs_with_contradicted_identity"], 1)
        self.assertEqual(report["summary"]["needed_edges_by_category"][edg.LOCAL_LISTED_LINK], 0)
        self.assertEqual(report["status"], "ok")  # a contradiction is evidence, not a file error
        # The same layout with the true size is a listed-link match: only the size differs.
        confirmed = edg.build_report(
            [self.spec("q:app", "app", needed=["libalias.so"]), provider],
            [self.inventory("p2", {"x": 1}),
             (self.inventory("p", {"libalias.so": "actual.so.1", "actual.so.1": size}))])
        self.assertEqual(confirmed["names"]["libalias.so"]["category"], edg.LOCAL_LISTED_LINK)
        self.assertEqual(confirmed["missing_evidence"]["contradicted_identities"], [])

    def test_soname_and_basename_matches_survive_a_contradicted_identity(self):
        report = edg.build_report(
            [self.spec("q:app", "app", needed=["libson.so", "libbase.so", "libalias.so"]),
             self.spec("p:lib/libbase.so", "provider", soname="libson.so")],
            [self.inventory("p", {"lib/libbase.so": 1, "lib/libson.so": "libbase.so",
                                  "lib/libalias.so": "libbase.so"})])
        expected = {"libson.so": (edg.LOCAL_SONAME, "soname"),
                    "libbase.so": (edg.LOCAL_BASENAME, "basename")}
        for name, (category, rule) in expected.items():
            with self.subTest(name=name):
                entry = report["names"][name]
                self.assertEqual(entry["category"], category)
                candidate = entry["local_candidates"][0]
                self.assertEqual((candidate["id"], candidate["rule"], candidate["identity_check"],
                                  candidate["listings"]),
                                 ("p:lib/libbase.so", rule, "listed_size_mismatch", []))
                # The listing is not taken as confirmation; it stays an uninspected alternative.
                self.assertEqual(entry["listed"][0]["local_input_not_linked"]["id"],
                                 "p:lib/libbase.so")
                self.assertEqual(self.edge(report, "q:app", name)["listed_alternatives"], 1)
        self.assertEqual(report["names"]["libalias.so"]["category"], edg.LISTED_ONLY)
        self.assertEqual(sorted((e["name"], e["rule"]) for e in report["graph"]["verified_edges"]),
                         [("libbase.so", "basename"), ("libson.so", "soname")])
        blocked = report["missing_evidence"]["contradicted_identities"][0]["blocked_listed_links"]
        self.assertEqual([item["name"] for item in blocked],
                         ["libalias.so", "libbase.so", "libson.so"])

    def test_listed_link_allow_list_is_only_a_confirmed_size_match(self):
        self.assertEqual(edg.LISTED_LINK_IDENTITY_STATES, ("listed_size_match",))
        provider = self.spec("p:actual.so.1", "provider", soname="other.so")
        size = os.path.getsize(provider.split("=", 1)[1])
        app = self.spec("q:app", "app", needed=["libalias.so"])
        link = {"mode": "lrwxrwxrwx", "size": 11, "link_target": "actual.so.1"}
        listings = {
            "listed_size_match": {"libalias.so": link,
                                  "actual.so.1": {"mode": "-rw-r--r--", "size": size}},
            "listed_size_mismatch": {"libalias.so": link,
                                     "actual.so.1": {"mode": "-rw-r--r--", "size": size + 1}},
            "listed": {"libalias.so": link, "actual.so.1": {"mode": "-rw-r--r--"}},
            "listed_not_regular": {"libalias.so": link,
                                   "actual.so.1": {"mode": "drwxr-xr-x", "size": size}},
            "not_listed": {"libalias.so": dict(link, link_target="elsewhere.so.1"),
                           "elsewhere.so.1": {"mode": "-rw-r--r--", "size": size}},
        }
        for state, files in listings.items():
            with self.subTest(state=state):
                inventory = self.inventory(f"inv-{state}", json.dumps({"files": files}))[1]
                report = edg.build_report([app, provider], [("p", inventory)])
                self.assertEqual(self.node(report, "p:actual.so.1")["identity_check"]["status"],
                                 state)
                linked = report["names"]["libalias.so"]["category"] == edg.LOCAL_LISTED_LINK
                self.assertEqual(linked, state == "listed_size_match")
                self.assertEqual(bool(report["graph"]["verified_edges"]), linked)
                contradicted = [item["id"] for item in
                                report["missing_evidence"]["contradicted_identities"]]
                self.assertEqual(contradicted, ["p:actual.so.1"] if state in (
                    "listed_size_mismatch", "listed_not_regular", "not_listed") else [])
        # Without a listing for the package there is nothing to follow.
        report = edg.build_report([app, provider], [self.inventory("other", {"libalias.so": 3})])
        self.assertEqual(self.node(report, "p:actual.so.1")["identity_check"],
                         {"status": "no_inventory"})
        self.assertEqual(report["names"]["libalias.so"]["category"], edg.LISTED_ONLY)
        self.assertEqual(report["graph"]["verified_edges"], [])

    def test_contradicted_identity_of_a_failed_input_is_reported(self):
        report = edg.build_report(
            [self.spec("q:app", "app", needed=["libalias.so"]),
             f"p:actual.so.1={self.write('junk', b'junk' * 10)}"],
            [self.inventory("p", {"libalias.so": "other.so.1", "other.so.1": 9})])
        self.assertEqual(report["missing_evidence"]["contradicted_identities"], [{
            "id": "p:actual.so.1", "input_status": "error",
            "identity_check": {"status": "not_listed"}, "blocked_listed_links": []}])


class CommandLineTests(Workspace):
    def run_main(self, *arguments):
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            status = edg.main([str(argument) for argument in arguments])
        return status, stream.getvalue()

    def test_cli_exit_codes_file_list_inventory_and_output(self):
        app = self.spec("p:app", "app", needed=["liba.so", "liblisted.so"])
        lib = self.spec("p:liba.so", "liba.so", soname="liba.so")
        entries = self.root / "inputs.list"
        entries.write_text(f"# inputs\n{lib}\n")
        inventory = self.inventory("pk", {"liblisted.so": 3})
        output = self.root / "report.json"
        arguments = (app, "--file-list", entries, "--inventory", f"pk={inventory[1]}",
                     "--no-abi-annotation")
        status, text = self.run_main(*arguments)
        self.assertEqual(status, 0)
        report = json.loads(text)
        self.assertEqual(report["summary"]["needed_edges_by_category"],
                         {edg.LOCAL_SONAME: 1, edg.LOCAL_BASENAME: 0, edg.LOCAL_LISTED_LINK: 0,
                          edg.AMBIGUOUS: 0, edg.LISTED_ONLY: 1, edg.UNRESOLVED: 0})
        self.assertEqual(report["summary"]["abi_annotation"], "not_requested")
        status, brief = self.run_main(*arguments, "--output", output)
        self.assertEqual(status, 0)
        self.assertEqual(json.loads(brief)["status"], "ok")
        self.assertEqual(output.read_text(), text)
        status, refusal = self.run_main(*arguments, "--output", output)
        self.assertEqual(status, 2)
        self.assertEqual(json.loads(refusal)["status"], "error")
        self.assertEqual(output.read_text(), text)  # the existing file is untouched
        dangling = self.root / "dangling.json"
        dangling.symlink_to(self.root / "nowhere.json")
        self.assertEqual(self.run_main(*arguments, "--output", dangling)[0], 2)
        self.assertFalse((self.root / "nowhere.json").exists())

    def test_cli_reports_file_errors_and_usage_errors_with_nonzero_exit(self):
        lib = self.spec("p:liba.so", "liba.so", soname="liba.so")
        junk = self.write("junk", b"junk" * 16)
        status, text = self.run_main(lib, junk, "--no-abi-annotation")
        self.assertEqual(status, 2)
        report = json.loads(text)
        self.assertEqual(report["status"], "partial")
        self.assertEqual(report["summary"]["files_inspected"], 1)
        for arguments in ((), ("bad:=x",), (lib, "--inventory", "nopath"),
                          (lib, "--inventory", f"pk={self.root / 'absent.json'}"),
                          (lib, "--file-list", self.root / "absent.list")):
            with self.subTest(arguments=arguments):
                status, text = self.run_main(*arguments)
                self.assertEqual(status, 2)
                self.assertEqual(json.loads(text)["status"], "error")
        lists = []
        for index in range(edg.MAX_FILE_LISTS + 1):
            path = self.root / f"l{index}.list"
            path.write_text(lib + "\n")
            lists += ["--file-list", path]
        self.assertEqual(self.run_main(*lists)[0], 2)
        with mock.patch.object(edg, "MAX_INVENTORIES", 1):
            inventory = self.inventory("pk", {"a": 1})[1]
            status, _ = self.run_main(lib, "--inventory", f"a={inventory}",
                                      "--inventory", f"b={inventory}")
            self.assertEqual(status, 2)

    def test_cli_default_annotation_never_changes_exit_status(self):
        status, text = self.run_main(self.spec("p:liba.so", "liba.so", soname="liba.so"))
        self.assertEqual(status, 0)
        self.assertIn(json.loads(text)["summary"]["abi_annotation"], ("requested", "unavailable"))

    def test_help_states_what_a_match_does_not_prove(self):
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream), self.assertRaises(SystemExit) as raised:
            edg.main(["--help"])
        self.assertEqual(raised.exception.code, 0)
        text = stream.getvalue()
        for phrase in ("NOT proof of link or runtime compatibility", "LD_LIBRARY_PATH", "dlopen",
                       "inter-process", "never picks one", "never runs ldd",
                       "contradicted identity never establishes a provider",
                       "charged once", "also when the input is then rejected",
                       "not valid Unicode"):
            self.assertIn(phrase, text)

    def test_module_runs_in_isolated_mode_and_as_a_package_module(self):
        app = self.spec("p:app", "app", needed=["liba.so"], interpreter=LOADER)
        lib = self.spec("p:liba.so", "liba.so", soname="liba.so")
        repository = Path(__file__).resolve().parents[1]
        script = repository / "tools" / "elf_dependency_graph.py"
        isolated = subprocess.run([sys.executable, "-I", "-B", str(script), app, lib],
                                  capture_output=True, text=True, cwd=self.root, timeout=60)
        self.assertEqual(isolated.returncode, 0, isolated.stderr)
        report = json.loads(isolated.stdout)
        self.assertEqual(report["summary"]["needed_edges_by_category"][edg.LOCAL_SONAME], 1)
        self.assertEqual(report["summary"]["interpreter_edges_by_category"][edg.UNRESOLVED], 1)
        packaged = subprocess.run(
            [sys.executable, "-B", "-m", "tools.elf_dependency_graph", app, lib,
             "--no-abi-annotation"],
            capture_output=True, text=True, cwd=repository, timeout=60)
        self.assertEqual(packaged.returncode, 0, packaged.stderr)
        again = subprocess.run(
            [sys.executable, "-I", "-B", str(script), app, lib, "--no-abi-annotation"],
            capture_output=True, text=True, cwd=self.root, timeout=60)
        self.assertEqual(packaged.stdout.encode(), again.stdout.encode())


if __name__ == "__main__":
    unittest.main()
