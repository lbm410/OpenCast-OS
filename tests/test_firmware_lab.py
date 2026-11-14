"""Synthetic tests for the optional offline firmware workflow; no vendor data."""

import hashlib
import io
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from tools import firmware_lab as lab
from tools.firmware_lab_squashfs import parse_listing, safe_path

try:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding, rsa
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
except ImportError:
    HAS_CRYPTOGRAPHY = False
else:
    HAS_CRYPTOGRAPHY = True


class BoundaryTests(unittest.TestCase):
    def test_bounded_reads(self):
        for offset, size in [(-1, 1), (0, -1), (3, 2)]:
            with self.assertRaises(lab.LabError):
                lab.read_at(io.BytesIO(b"1234"), offset, size, 4)
        with self.assertRaises(lab.LabError):
            lab.read_at(io.BytesIO(b"1"), 0, 4, 4)

    def test_metadata_controls_rejected(self):
        with self.assertRaises(lab.LabError):
            lab.field_text(b"name\n")
        self.assertEqual(lab.field_text(b"model\0binary\xff"), "model")

    def test_path_traversal_and_ambiguity_rejected(self):
        for name in ["", "/etc/init", "../etc", "a/../b", "a//b", "a/./b", "a\nb", "x -> y"]:
            with self.assertRaises(ValueError):
                safe_path(name)
        self.assertEqual(safe_path("etc/init.d/rcS"), "etc/init.d/rcS")

    def test_listing_preserves_symlinks_as_metadata(self):
        text = ("drwxr-xr-x 0/0 30 2018-01-11 03:08 squashfs-root\n"
                "-rwxr-xr-x 0/0 12 2018-01-11 03:08 squashfs-root/etc/init\n"
                "lrwxrwxrwx 0/0 4 2018-01-11 03:08 squashfs-root/outside -> /outside\n")
        result = parse_listing(text)
        self.assertEqual(result["etc/init"]["size"], 12)
        self.assertEqual(result["outside"]["link_target"], "/outside")
        with self.assertRaises(ValueError):
            parse_listing(text + text)
        with self.assertRaises(ValueError):
            parse_listing(text.replace("etc/init", "../init"))


@unittest.skipUnless(HAS_CRYPTOGRAPHY, "Optional firmware cryptography dependency not installed")
class ContainerTests(unittest.TestCase):
    key = b"\x00" * 16  # Synthetic all-zero test key; never a vendor key.

    def encrypt(self, plain):
        blocks = len(plain) // 16 * 16
        encoder = Cipher(algorithms.AES(self.key), modes.ECB()).encryptor()
        return encoder.update(plain[:blocks]) + encoder.finalize() + plain[blocks:]

    def fixture(self, name=b"root", segment_index=0, segment_size=32, declared_size=160):
        header = bytearray(lab.HEADER_SIZE)
        struct.pack_into("<4sII4s4s32s", header, 0, b"epak", declared_size, 1, b"EPK2", b"\1\0\0\0", b"TEST")
        lab.LOCATION.pack_into(header, 52, 1620, 160, name, 1, 4096)
        pak = lab.PAK_HEADER.pack(name, 32, b"TEST", 1, 0, 0, 1, segment_size, segment_index, b"MPAK", b"\0" * 24, 0)
        image = b"\0" * lab.FIRST_PACKAGE_OFFSET + b"\0" * 128 + self.encrypt(pak) + self.encrypt(b"\0" * 32)
        return bytes(header), image

    def test_valid_table_accounts_for_entire_image(self):
        header, image = self.fixture()
        packages = lab.parse_packages(io.BytesIO(image), header, self.key, len(image))
        self.assertEqual(packages[0]["size"], 32)
        self.assertEqual(packages[0]["segments"][0]["data_offset"], 2004)

    def test_bad_segment_and_paths_rejected(self):
        for kwargs in [{"name": b"../a"}, {"segment_index": 1}, {"segment_size": 4097}, {"declared_size": 161}]:
            header, image = self.fixture(**kwargs)
            with self.assertRaises(lab.LabError):
                lab.parse_packages(io.BytesIO(image), header, self.key, len(image))
        header, image = self.fixture()
        with self.assertRaises(lab.LabError):
            lab.parse_packages(io.BytesIO(image + b"x"), header, self.key, len(image) + 1)

    def test_exact_signature_rejects_mutation_and_wrong_key(self):
        private = rsa.generate_private_key(public_exponent=65537, key_size=1024)
        wrong = rsa.generate_private_key(public_exponent=65537, key_size=1024)
        data = b"synthetic image"
        signature = private.sign(hashlib.sha1(data).digest(), padding.PKCS1v15(), hashes.SHA1())
        self.assertTrue(lab.verify_signature(private.public_key(), signature, data))
        self.assertFalse(lab.verify_signature(private.public_key(), signature, data + b"x"))
        self.assertFalse(lab.verify_signature(wrong.public_key(), signature, data))

    def test_existing_output_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(FileExistsError):
                lab.extract_selected(io.BytesIO(), {"packages": [], "signature": {"header_verified": True}},
                                     self.key, None, [], Path(directory))

    def audit_fixture(self):
        private = rsa.generate_private_key(public_exponent=65537, key_size=1024)
        image = bytearray()
        segments = []
        for index in range(2):
            data = bytes([index + 1]) * 160
            signature = private.sign(hashlib.sha1(data).digest(), padding.PKCS1v15(), hashes.SHA1())
            offset = len(image)
            image.extend(signature + data)
            segments.append({"index": index, "signature_offset": offset,
                             "signed_offset": offset + 128, "signed_size": len(data)})
        return bytes(image), {"input_size": len(image), "signature": {"header_verified": True},
                              "packages": [{"name": "test", "segments": segments}]}, private.public_key()

    def test_full_audit_verifies_every_span_and_preserves_input(self):
        image, manifest, public = self.audit_fixture()
        stream = io.BytesIO(image)
        result = lab.audit_signatures(stream, manifest, public)
        self.assertEqual(result["verified_segments"], 2)
        self.assertTrue(result["negative_control"]["rejected"])
        self.assertEqual(stream.getvalue(), image)
        corrupted = bytearray(image)
        corrupted[-1] ^= 1
        with self.assertRaises(lab.LabError):
            lab.audit_signatures(io.BytesIO(corrupted), manifest, public)

    def test_audit_rejects_vacuous_and_unauthenticated_manifests(self):
        image, manifest, public = self.audit_fixture()
        manifest["signature"]["header_verified"] = False
        with self.assertRaises(lab.LabError):
            lab.audit_signatures(io.BytesIO(image), manifest, public)
        manifest["signature"]["header_verified"] = True
        manifest["packages"] = []
        with self.assertRaises(lab.LabError):
            lab.audit_signatures(io.BytesIO(image), manifest, public)

    def test_audit_negative_control_detects_permissive_verifier(self):
        image, manifest, public = self.audit_fixture()
        with patch.object(lab, "verify_signature", return_value=True):
            with self.assertRaisesRegex(lab.LabError, "negative control"):
                lab.audit_signatures(io.BytesIO(image), manifest, public)


if __name__ == "__main__":
    unittest.main()
