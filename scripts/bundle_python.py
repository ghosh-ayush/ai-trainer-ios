#!/usr/bin/env python3
"""Package the pinned interpreter's library and the pure core, entirely offline."""

import os
import plistlib
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
app = Path(os.environ["TARGET_BUILD_DIR"]) / os.environ["WRAPPER_NAME"]
simulator = os.environ.get("PLATFORM_NAME") == "iphonesimulator"
slice_name = "ios-arm64_x86_64-simulator" if simulator else "ios-arm64"
architectures = os.environ["ARCHS"].split()
arch = architectures[0]
source = ROOT / "apps/ios/Vendor/Python.xcframework" / slice_name
stdlib = source / ("lib-" + arch) / "python3.13"
if not stdlib.is_dir():
    raise SystemExit("Run scripts/setup_python.sh first; missing " + str(stdlib))
# Purge stale modules in the build product only, never source or user data.
for name in ("python", "app"):
    target = app / name
    if target.exists():
        shutil.rmtree(target)
shutil.copytree(
    source.parent / "lib/python3.13",
    app / "python/lib/python3.13",
    ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "test", "tests"),
)
shutil.copytree(stdlib, app / "python/lib/python3.13", dirs_exist_ok=True)
for extra_arch in architectures[1:]:
    for config in (source / ("lib-" + extra_arch) / "python3.13").glob("_sysconfigdata*.py"):
        shutil.copy2(config, app / "python/lib/python3.13")
shutil.copytree(
    ROOT / "core/python/ai_trainer",
    app / "app/ai_trainer",
    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
)
frameworks = app / "Frameworks"
frameworks.mkdir(exist_ok=True)
# The C bridge only imports stdlib/pure Python. Extension modules in CPython's
# library still need iOS framework packaging (PEP 730), including _json and math.
for binary in (app / "python").rglob("*.so"):
    name = binary.name.split(".")[0]
    # The pure core needs only these two native stdlib modules. Exclude optional
    # crypto/compression/FFI/network extensions and their third-party binaries.
    if name not in {"math", "_json"}:
        binary.unlink()
        stale = frameworks / (name + ".framework")
        if stale.exists():
            shutil.rmtree(stale)
        continue
    framework = frameworks / (name + ".framework")
    framework.mkdir(exist_ok=True)
    destination = framework / name
    shutil.move(str(binary), destination)
    if len(architectures) > 1:
        inputs = [str(source / ("lib-" + a) / "python3.13/lib-dynload" / binary.name) for a in architectures]
        subprocess.run(["lipo", "-create", *inputs, "-output", str(destination)], check=True)
    privacy = binary.parent / (name + ".xcprivacy")
    if privacy.exists():
        shutil.copy2(privacy, framework / "PrivacyInfo.xcprivacy")
    info = dict(
        CFBundleExecutable=name,
        CFBundleIdentifier="com.ghoshayush.AITrainer.python." + name.replace("_", "-"),
        CFBundleName=name,
        CFBundlePackageType="FMWK",
        CFBundleShortVersionString="3.13.11",
        CFBundleVersion="13",
        MinimumOSVersion="17.0",
        CFBundleSupportedPlatforms=["iPhoneSimulator" if simulator else "iPhoneOS"],
    )
    (framework / "Info.plist").write_bytes(plistlib.dumps(info))
    marker = binary.with_suffix(".fwork")
    marker.write_text(str(destination.relative_to(app)))
    (framework / (name + ".origin")).write_text(str(marker.relative_to(app)))
    identity = os.environ.get("EXPANDED_CODE_SIGN_IDENTITY") or "-"
    subprocess.run(
        ["codesign", "--force", "--sign", identity, "--timestamp=none", str(framework)],
        check=True,
    )
# Keep upstream license files with the bundled runtime.
print("Bundled local Python core and CPython 3.13.11 for", slice_name, arch)
