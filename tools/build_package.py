#!/usr/bin/env python3
"""Build bookkeepy-rates-package@1 packages from BNR feeds.

Modes:
  daily:   build_package.py daily <latest-url> <outdir>
           -> packages/bnr/<date>.json (kind=full, one day)
  archive: build_package.py archive <year> <yearly-url-template> <outdir>
           -> packages/bnr/archive-<year>.json (kind=archive, all days of the year)

Both update manifest.json + SHA256SUMS and ed25519-sign packages that lack a .sig
when RATES_SIGNING_KEY is set. Rates stay strings (no float money math).
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
SOURCE = {
    "id": "bnr",
    "name": "Banca Națională a României",
    "url": "https://www.bnr.ro/23988-cursurile-pietei-valutare-in-format-xml",
}


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "bookkeepy-1-rates/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def parse_rates(xml_bytes: bytes):
    """Return (publishing_date, [ {date, currency, rate, multiplier}, ... ])."""
    root = ET.fromstring(xml_bytes)
    ns = {"b": "https://www.bnr.ro/xsd"}
    header = root.find("b:Header", ns) or root.find("Header")
    pub_date = None
    if header is not None:
        pd = header.find("b:PublishingDate", ns) or header.find("PublishingDate")
        pub_date = pd.text if pd is not None else None
    body = root.find("b:Body", ns) or root.find("Body")
    out = []
    for cube in body.iter():
        tag = cube.tag.split("}")[-1]
        if tag != "Cube" or cube.get("date") is None:
            continue
        date = cube.get("date")
        for rate in cube:
            rtag = rate.tag.split("}")[-1]
            if rtag == "Rate":
                out.append({
                    "date": date,
                    "currency": rate.get("currency"),
                    "rate": rate.text.strip(),
                    "multiplier": rate.get("multiplier", "1"),
                })
            elif rtag == "Cube":  # legacy nesting <Cube currency= rate=>
                out.append({
                    "date": date,
                    "currency": rate.get("currency"),
                    "rate": rate.get("rate"),
                    "multiplier": rate.get("multiplier", "1"),
                })
    return pub_date, out


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def sign(path: str) -> None:
    key = os.environ.get("RATES_SIGNING_KEY")
    if not key:
        return
    sig = path + ".sig"
    if os.path.exists(sig):
        return
    with open("/tmp/rates_key.pem", "w") as f:
        f.write(key)
    subprocess.run(
        ["openssl", "pkeyutl", "-sign", "-inkey", "/tmp/rates_key.pem", "-rawin", "-in", path, "-out", sig],
        check=True,
    )
    os.remove("/tmp/rates_key.pem")
    print(f"signed {os.path.basename(path)}")


def update_manifest(outdir: str, entry: dict) -> None:
    man_path = os.path.join(outdir, "manifest.json")
    man = {"spec_version": SPEC_MAN,
           "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "sources": [dict(SOURCE, base_currency="RON", priority=1)],
           "packages": []}
    if os.path.exists(man_path):
        with open(man_path, encoding="utf-8") as f:
            man = json.load(f)
    pkgs = [p for p in man.get("packages", []) if p["id"] != entry["id"]]
    pkgs.append(entry)
    pkgs.sort(key=lambda p: (p["source"], p["date"]))
    man["packages"] = pkgs
    with open(man_path, "w", encoding="utf-8") as f:
        json.dump(man, f, indent=2, ensure_ascii=False)
        f.write("\n")


def update_sums(outdir: str, relpath: str, digest: str) -> None:
    sums = os.path.join(outdir, "SHA256SUMS")
    lines = []
    if os.path.exists(sums):
        with open(sums, encoding="utf-8") as f:
            lines = [l for l in f.read().splitlines() if l.strip() and not l.endswith(" " + relpath)]
    lines.append(f"{digest}  {relpath}")
    with open(sums, "w", encoding="utf-8") as f:
        f.write("\n".join(sorted(lines)) + "\n")


def write_package(outdir: str, pkg: dict, relpath: str) -> None:
    path = os.path.join(outdir, relpath)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path):
        print(f"{relpath} exists; packages are immutable — skip")
        return
    with open(path, "w", encoding="utf-8") as f:
        json.dump(pkg, f, indent=2, ensure_ascii=False)
        f.write("\n")
    sign(path)
    digest = sha256_file(path)
    update_sums(outdir, relpath, digest)
    update_manifest(outdir, {
        "id": pkg["package_id"], "source": SOURCE["id"], "kind": pkg["kind"],
        "date": pkg["date"], "file": relpath, "sha256": digest,
        "size_bytes": os.path.getsize(path), "supersedes": None,
    })
    print(f"wrote {relpath} ({os.path.getsize(path)} bytes)")


def main() -> int:
    mode = sys.argv[1]
    outdir = sys.argv[-1]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if mode == "daily":
        url = sys.argv[2]
        pub_date, rates = parse_rates(fetch(url))
        day_rates = [r for r in rates if r["date"] == pub_date] or rates
        date = pub_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        pkg = {
            "spec_version": SPEC_PKG, "package_id": f"bnr-{date}",
            "source": dict(SOURCE, fetched_at=now),
            "base_currency": "RON", "date": date, "kind": "full",
            "rates": [{"currency": r["currency"], "rate": r["rate"], "multiplier": r["multiplier"]} for r in day_rates],
            "corrections_of": None,
        }
        write_package(outdir, pkg, f"packages/bnr/{date}.json")
        return 0
    if mode == "archive":
        year = sys.argv[2]
        url = sys.argv[3].replace("{year}", year)
        _pub, rates = parse_rates(fetch(url))
        pkg = {
            "spec_version": SPEC_PKG, "package_id": f"bnr-archive-{year}",
            "source": dict(SOURCE, fetched_at=now),
            "base_currency": "RON", "date": year, "kind": "archive",
            "rates": rates,  # each entry carries its own "date"
            "corrections_of": None,
        }
        write_package(outdir, pkg, f"packages/bnr/archive-{year}.json")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
