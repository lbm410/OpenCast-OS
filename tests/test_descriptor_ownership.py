"""Descriptors remain owned until fdopen succeeds, including real directory input."""
from contextlib import contextmanager
import errno
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import (arm_disassembly, knowledge, lz4p_inspect, lzhs_inspect,
                   netcast_package, netcast_source, udap, udap_session)
from tests.test_lz4p_inspect import container, uimage


class DescriptorOwnershipTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        # Component-walking readers intentionally reject macOS's /var symlink.
        self.root = Path(temporary.name).resolve()
        self.directory = self.root / "directory"
        self.directory.mkdir()
        self.regular = self.root / "regular"
        self.regular.write_bytes(b"bounded fixture")

    @contextmanager
    def closed_descriptors(self):
        original_open = os.open
        opened = []

        def tracked(*args, **kwargs):
            descriptor = original_open(*args, **kwargs)
            opened.append(descriptor)
            return descriptor

        try:
            with patch.object(os, "open", side_effect=tracked):
                yield
        finally:
            leaked = []
            for descriptor in set(opened):
                try:
                    os.fstat(descriptor)
                except OSError as error:
                    self.assertEqual(error.errno, errno.EBADF)
                else:
                    leaked.append(descriptor)
                    os.close(descriptor)  # Keep a failed regression from leaking in the test process.
            self.assertTrue(opened, "The tested path must actually open descriptors")
            self.assertEqual(leaked, [], "All opened descriptors must be closed on this failure path")

    def test_real_directory_inputs_close_leaf_and_parent_descriptors(self):
        cases = (
            lambda: netcast_package._read_local(self.directory),
            lambda: arm_disassembly._open_regular(self.directory, 1024),
            lambda: lzhs_inspect.read_bounded(self.directory, 1024),
            lambda: lz4p_inspect.decode_file(self.directory, self.root / "unused-output"),
        )
        for number, invoke in enumerate(cases):
            with self.subTest(reader=number), self.closed_descriptors():
                with self.assertRaises((OSError, netcast_package.PackageError)):
                    invoke()
        self.assertFalse((self.root / "unused-output").exists())

    def test_source_asset_replaced_by_directory_is_closed(self):
        with patch.object(netcast_source, "ROOT", self.root), patch.object(
                netcast_source, "ASSETS", {"/": ("directory", "text/html")}), self.closed_descriptors():
            with self.assertRaises(IsADirectoryError):
                netcast_source.build_source("probe")

    def test_knowledge_file_to_directory_race_closes_opened_leaf(self):
        bundle = self.root / "bundle"
        bundle.mkdir()
        (bundle / "raced.md").mkdir()
        original_stat = os.stat
        prior_regular_metadata = self.regular.stat()

        def replaced_after_stat(path, *args, **kwargs):
            if path == "raced.md":
                return prior_regular_metadata
            return original_stat(path, *args, **kwargs)

        with patch.object(os, "stat", side_effect=replaced_after_stat), self.closed_descriptors():
            result = knowledge.load_bundle(bundle)
        self.assertEqual(len(result.issues), 1)
        self.assertEqual(result.issues[0]["severity"], "error")

    def test_validation_failure_after_successful_wrapper_also_closes(self):
        cases = (
            lambda: arm_disassembly._open_regular(self.regular, 1),
            lambda: lzhs_inspect.read_bounded(self.regular, 1),
            lambda: lz4p_inspect.decode_file(self.regular, self.root / "unused-output"),
        )
        for number, invoke in enumerate(cases):
            with self.subTest(reader=number), self.closed_descriptors():
                with self.assertRaises(ValueError):
                    invoke()
        with patch.object(netcast_package, "MAX_ZIP", 1), self.closed_descriptors():
            with self.assertRaises(netcast_package.PackageError):
                netcast_package._read_local(self.regular)

    def test_reader_wrapper_allocation_failure_closes_raw_descriptor(self):
        cases = (
            lambda: netcast_package._read_local(self.regular),
            lambda: arm_disassembly._open_regular(self.regular, 1024),
            lambda: lzhs_inspect.read_bounded(self.regular, 1024),
            lambda: lz4p_inspect.decode_file(self.regular, self.root / "unused-output"),
        )
        for number, invoke in enumerate(cases):
            with self.subTest(reader=number), self.closed_descriptors(), patch.object(
                    os, "fdopen", side_effect=MemoryError("synthetic wrapper allocation failure")):
                with self.assertRaises(MemoryError):
                    invoke()
        with patch.object(netcast_source, "ROOT", self.root), patch.object(
                netcast_source, "ASSETS", {"/": ("regular", "text/html")}), self.closed_descriptors(), patch.object(
                    os, "fdopen", side_effect=MemoryError("synthetic wrapper allocation failure")):
            with self.assertRaises(MemoryError):
                netcast_source.build_source("probe")

    def test_knowledge_wrapper_failure_closes_leaf_and_traversal_descriptors(self):
        bundle = self.root / "bundle"
        bundle.mkdir()
        (bundle / "index.md").write_text("# Fixture\n")
        with self.closed_descriptors(), patch.object(os, "fdopen", side_effect=MemoryError("synthetic")):
            with self.assertRaises(MemoryError):
                knowledge.load_bundle(bundle)

    def test_exclusive_writer_wrapper_failure_closes_descriptors_without_replacing_files(self):
        encoded = self.root / "synthetic-lz4p"
        encoded.write_bytes(container(uimage(), 128))
        original_fdopen = os.fdopen

        def fail_write_wrapper(descriptor, mode, *args, **kwargs):
            if mode == "wb":
                raise MemoryError("synthetic write wrapper failure")
            return original_fdopen(descriptor, mode, *args, **kwargs)

        for name, invoke in (
                ("lzhs-output", lambda target: lzhs_inspect.write_exclusive(target, b"fixture")),
                ("lz4p-output", lambda target: lz4p_inspect.decode_file(encoded, target))):
            target = self.root / name
            with self.subTest(writer=name), self.closed_descriptors(), patch.object(os, "fdopen", side_effect=fail_write_wrapper):
                with self.assertRaises(MemoryError):
                    invoke(target)
            # Preserve the existing non-atomic exclusive-writer policy: no publication
            # redesign here; a failed newly-created artifact remains empty and closed.
            self.assertEqual(target.read_bytes(), b"")
            target.write_bytes(b"owner content")
            with self.closed_descriptors():
                with self.assertRaises(FileExistsError):
                    invoke(target)
            self.assertEqual(target.read_bytes(), b"owner content")

    def test_inventory_wrapper_failure_closes_leaf_and_removes_pending_output(self):
        inventory = udap.Inventory(0, (), False)
        for error in (OSError(errno.ENOMEM, "synthetic wrapper error"), MemoryError("synthetic")):
            with self.subTest(error=type(error).__name__), self.closed_descriptors(), patch.object(os, "fdopen", side_effect=error):
                with self.assertRaises(udap.UDAPError if isinstance(error, OSError) else MemoryError):
                    udap_session.save_inventory(inventory, project_root=self.root)
            self.assertEqual(list((self.root / "artifacts/diagnostics").iterdir()), [])


if __name__ == "__main__":
    unittest.main()
