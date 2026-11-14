"""Synthetic partition-map boundary tests, without vendor data."""

import struct
import unittest

from tools.partition_inventory import ENTRY, FILE_SIZE, HEADER, PartitionError, inventory


def fixture(entries=None, device_size=4096):
    if entries is None:
        entries = [(b"rootfs", 0, 1024, b"root.squashfs", 0, 0, 1, 1, 2)]
    data = bytearray(FILE_SIZE)
    HEADER.pack_into(data, 0, 0x20120716, 0, 0, len(entries), b"mtk3598-emmc", device_size, 0, 0, 0, 0, 1)
    for index, entry in enumerate(entries):
        ENTRY.pack_into(data, HEADER.size + index * ENTRY.size, *entry)
    return data


class PartitionTests(unittest.TestCase):
    def test_fixed_wire_sizes_and_duplicate_names(self):
        self.assertEqual((HEADER.size, ENTRY.size, FILE_SIZE), (80, 96, 12368))
        data = fixture([(b"rootfs", 0, 1024, b"root.squashfs", 0, 0, 1, 1, 2),
                        (b"rootfs", 1024, 1024, b"root.squashfs", 0, 0, 0, 1, 0)])
        report = inventory(data)
        self.assertEqual(report["repeated_names"][0]["indices"], [0, 1])
        self.assertEqual(report["unused_zero_slots"], 126)
        self.assertEqual(report["partitions"][0]["flag_labels"], ["MASTER"])

    def test_bounds_magic_count_and_unused_slots(self):
        data = fixture()
        for bad in [data[:-1], data + b"x"]:
            with self.assertRaises(PartitionError):
                inventory(bad)
        for offset, value in [(0, 0), (12, 0), (12, 129), (13, 1), (HEADER.size + ENTRY.size, 1)]:
            bad = fixture()
            bad[offset] = value
            with self.assertRaises(PartitionError):
                inventory(bad)

    def test_overlapping_and_overflowing_extents_rejected(self):
        rows = [(b"one", 0, 2048, b"", 0, 0, 1, 1, 2),
                (b"two", 1024, 1024, b"", 0, 0, 0, 1, 0)]
        with self.assertRaises(PartitionError):
            inventory(fixture(rows))
        with self.assertRaises(PartitionError):
            inventory(fixture([(b"overflow", (1 << 64) - 2, 4, b"", 0, 0, 1, 1, 0)]))

    def test_outside_device_extent_is_reported_not_hidden(self):
        report = inventory(fixture([(b"reserved", 4096, 1024, b"", 0, 0, 0, 0, 1)]))
        self.assertEqual(report["outside_device_bound_indices"], [0])
        self.assertEqual(report["maximum_described_end"], 5120)
        self.assertEqual(report["unassigned_gaps"][0]["size"], 4096)

    def test_invalid_fields_rejected(self):
        for change in [(0, b"x" * 32), (2, 0), (4, 1025), (6, 2), (7, 2)]:
            row = [b"rootfs", 0, 1024, b"root.squashfs", 0, 0, 1, 1, 2]
            row[change[0]] = change[1]
            with self.assertRaises(PartitionError):
                inventory(fixture([tuple(row)]))
        bad = fixture()
        bad[HEADER.size + 90] = 1
        with self.assertRaises(PartitionError):
            inventory(bad)


if __name__ == "__main__":
    unittest.main()
