# Roadmap / future todos (approved 2026-11-27)

Governing decision record: **ADR-0027** in `aAndy03/bookkeepy-1` (`docs/adr/ADR-0027-rates-mirror-data-only-engine-crate.md`).

This repo stays **data-only** (manifest + immutable packages + sha256 + ed25519 + producer
tooling). The approved long-term items:

1. **Consumption engine lives in the main app repo**, as a Rust crate under
   `crates/` in `aAndy03/bookkeepy-1` (publishable to crates.io). Third parties use it via
   `cargo add` or by copying the crate folder. Do NOT vendor engine code into this repo —
   one home for parse/verify logic, no stale copies, no license friction.
2. **File-count scaling via archive rollups**: a periodic job publishes new yearly
   `kind: "archive"` packages / addenda. Existing packages are never rewritten —
   `manifest.json` remains the small index consumers fetch. Daily `kind: "full"` packages
   continue for the current period as today.
3. **Optional**: the engine crate may define a single-file bundle format (one packed
   artifact + index) for consumers who want to ship exactly one file.
4. **License**: this repo is MIT (tooling + arrangement); the rates data is BNR's.

See `docs/package-format.md` for the package/manifest spec (`bookkeepy-rates-package@1`).
