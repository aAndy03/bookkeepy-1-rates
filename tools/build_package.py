#!/usr/bin/env python3
"""Build a bookkeepy-rates-package@1 package from a source feed (BNR first).

Usage: build_package.py <source-id> <url> <outdir>
Writes packages/<source>/<date>.json, updates manifest.json + SHA256SUMS,
signs each package with ed25519 (openssl, key from RATES_SIGNING_KEY env).
Pure stdlib; rates are kept as strings (no float money math, INV-MONEY-001 spirit).
"""
import hashlib
import json
import os
import subprocess
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

SPEC_PKG = "bookkeepy-rates-package@1"
SPEC_MAN = "bookkeepy-rates-manifest@1"


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "bookkeepy-1-rates/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def parse_bnr(xml_bytes: bytes, date_hint: str):
    root = ET.fromstring(xml_bytes)
    body = root.find("Body")
    cube = body.find("Cube")  # carries date
    date = cube.get("date") or date_hint
    rates = []
    for c in cube.findall("Cube"):
        rates.append(
            {"currency": c.get("currency"), "rate": c.get("rate"), "multiplier": c.get("multiplier", "1")}
        )
    return date, rates


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def sign(path: str, key_pem: str) -> str:
    with open("/tmp/rates_key.pem", "w") as f:
        f.write(key_pem)
    sig = path + ".sig"
    subprocess.run(
        ["openssl", "pkeyutl", "-sign", "-inkey", "/tmp/rates_key.pem", "-rawin", "-in", path, "-out", sig],
        check=True,
    )
    os.remove("/tmp/rates_key.pem")
    return sig


def main() -> int:
    source_id, url, outdir = sys.argv[1], sys.argv[2], sys.argv[3]
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    xml = fetch(url)
    date, rates = parse_bnr(xml, today)
    pkg_id = f"{source_id}-{date}"
    pkg = {
        "spec_version": SPEC_PKG,
        "package_id": pkg_id,
        "source": {
            "id": source_id,
            "name": "Banca Națională a României" if source_id == "bnr" else source_id,
            "url": url,
            "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
        "base_currency": "RON",
        "date": date,
        "kind": "full",
        "rates": rates,
        "corrections_of": None,
    }
    src_dir = os.path.join(outdir, "packages", source_id)
    os.makedirs(src_dir, exist_ok=True)
    pkg_file = os.path.join(src_dir, f"{date}.json")
    if os.path.exists(pkg_file):
        print(f"package for {date} already exists; packages are immutable — nothing to do")
        return 0
    with open(pkg_file, "w", encoding="utf-8") as f:
        json.dump(pkg, f, indent=2, ensure_ascii=False)
        f.write("\n")
    digest = sha256_file(pkg_file)
    size = os.path.getsize(pkg_file)
    key = os.environ.get("RATES_SIGNING_KEY")
    if key:
        sign(pkg_file, key)
        print(f"signed {pkg_file}")
    # manifest
    man_path = os.path.join(outdir, "manifest.json")
    man = {"spec_version": SPEC_MAN, "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "sources": [{"id": source_id, "name": pkg["source"]["name"], "url": url, "base_currency": "RON", "priority": 1}],
           "packages": []}
    if os.path.exists(man_path):
        with open(man_path, encoding="utf-8") as f:
            man = json.load(f)
    man["packages"] = [p for p in man.get("packages", []) if not (p["source"] == source_id and p["date"] == date)]
    man["packages"].append({"id": pkg_id, "source": source_id, "kind": "full", "date": date,
                             "file": f"packages/{source_id}/{date}.json", "sha256": digest, "size_bytes": size,
                             "supersedes": None})
    man["packages"].sort(key=lambda p: p["date"])
    with open(man_path, "w", encoding="utf-8") as f:
        json.dump(man, f, indent=2, ensure_ascii=False)
        f.write("\n")
    # SHA256SUMS
    sums = os.path.join(outdir, "SHA256SUMS")
    lines = []
    if os.path.exists(sums):
        with open(sums, encoding="utf-8") as f:
            lines = [l for l in f.read().splitlines() if l.strip()]
    lines = [l for l in lines if not l.endswith(f"packages/{source_id}/{date}.json")]
    lines.append(f"{digest}  packages/{source_id}/{date}.json")
    with open(sums, "w", encoding="utf-8") as f:
        f.write("\n".join(sorted(lines)) + "\n")
    print(f"wrote {pkg_file} ({size} bytes, sha256 {digest[:12]}…) + manifest entry")
    return 0


if __name__ == "__main__":
    sys.exit(main())
