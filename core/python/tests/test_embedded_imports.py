"""The embedded iOS runtime ships only the ``math`` and ``_json`` native stdlib extensions
(see scripts/bundle_python.py). Every other stdlib module that is a shared object in the
BeeWare Python-Apple-support 3.13 iOS build is absent inside the app, so any transitive
import of one of them crashes the core at startup — on device only, never on a Mac or Linux.

This test runs the core in a fresh isolated interpreter with those modules blocked, mirroring
the C bridge's ``PyConfig_InitIsolatedConfig`` (no site, no environment), and exercises the
golden request plus one state command. It fails on the desktop the moment someone imports
``dataclasses`` (→ inspect → dis → _opcode), ``datetime``, ``struct``, ``pickle``, ``random`` …
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

# lib-dynload/*.so in Python-3.13-iOS-support.b13 (ios-arm64 slice), minus the two that ship.
STRIPPED_EXTENSIONS = [
    "_asyncio",
    "_bisect",
    "_blake2",
    "_bz2",
    "_codecs_cn",
    "_codecs_hk",
    "_codecs_iso2022",
    "_codecs_jp",
    "_codecs_kr",
    "_codecs_tw",
    "_contextvars",
    "_csv",
    "_ctypes",
    "_datetime",
    "_dbm",
    "_decimal",
    "_elementtree",
    "_hashlib",
    "_heapq",
    "_interpchannels",
    "_interpqueues",
    "_interpreters",
    "_lsprof",
    "_lzma",
    "_md5",
    "_multibytecodec",
    "_opcode",
    "_pickle",
    "_queue",
    "_random",
    "_sha1",
    "_sha2",
    "_sha3",
    "_socket",
    "_sqlite3",
    "_ssl",
    "_statistics",
    "_struct",
    "_uuid",
    "_zoneinfo",
    "array",
    "binascii",
    "cmath",
    "fcntl",
    "mmap",
    "pyexpat",
    "resource",
    "select",
    "termios",
    "unicodedata",
    "zlib",
]

# Pure-Python 3.13 stdlib modules whose *unguarded* imports of the extensions above make them
# unavailable too (verified in Python-3.13-iOS-support.b13/lib/python3.13):
#   opcode.py: `import _opcode`  ->  dis.py  ->  inspect.py  ->  dataclasses.py
#   struct.py: `from _struct import *`; random.py: `import _random`; pickle.py needs struct.
# Older desktop Pythons guard some of these imports, so they are blocked explicitly here.
UNAVAILABLE_PURE_MODULES = ["opcode", "dis", "inspect", "dataclasses", "struct", "random", "pickle"]

PROBE = r"""
import sys, importlib.abc

BLOCKED = set(sys.argv[1].split(","))

class BlockStrippedExtensions(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        if fullname in BLOCKED:
            raise ImportError(f"{fullname} is not bundled in the embedded iOS runtime")
        return None

# Drop anything already imported by startup so the block is honoured.
for name in list(sys.modules):
    if name in BLOCKED:
        del sys.modules[name]
sys.meta_path.insert(0, BlockStrippedExtensions())

sys.path.insert(0, sys.argv[2])
import ai_trainer.service as service  # the bridge's entry module

request = open(sys.argv[3]).read()
response = service.dispatch_json(request)
assert '"result"' in response, response
print("OK")
"""


class EmbeddedImportSafetyTests(unittest.TestCase):
    def test_core_imports_without_stripped_stdlib_extensions(self) -> None:
        fixture = ROOT / "shared/fixtures/v1/qualifying-request.json"
        completed = subprocess.run(
            [
                sys.executable,
                "-I",
                "-S",
                "-c",
                PROBE,
                ",".join(STRIPPED_EXTENSIONS + UNAVAILABLE_PURE_MODULES),
                str(ROOT / "core/python"),
                str(fixture),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(completed.returncode, 0, msg=f"\nSTDOUT:\n{completed.stdout}\nSTDERR:\n{completed.stderr}")
        self.assertIn("OK", completed.stdout)

    def test_bundle_script_still_ships_only_math_and_json(self) -> None:
        source = (ROOT / "scripts/bundle_python.py").read_text()
        self.assertIn('{"math", "_json"}', source.replace("'", '"'))

    def test_stripped_list_is_well_formed(self) -> None:
        self.assertNotIn("math", STRIPPED_EXTENSIONS)
        self.assertNotIn("_json", STRIPPED_EXTENSIONS)
        self.assertEqual(len(STRIPPED_EXTENSIONS), len(set(STRIPPED_EXTENSIONS)))
        json.dumps(STRIPPED_EXTENSIONS)  # sanity: plain strings
