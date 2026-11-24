# Rates package format — `bookkeepy-rates-package@1` (spec v1)

This file is the **single source of truth** for the package format. Producers (this repo's
automation) must conform; consumers (the Bookkeepy 1 app) pin the `spec_version` they
support and refuse unknown versions loudly.

## Design rules

- **Immutable.** A published package is never modified. Corrections are new packages with
  `kind = "addendum"` referencing the package they correct.
- **Additive across sources.** Different sources' packages coexist; they never rewrite each
  other's history. The app lets the user choose which source's rate to use per conversion.
- **ISO-linked.** Every currency code must exist in ISO 4217 primary data
  (`data/currencies.toml` in `aAndy03/bookkeepy-1`); unknown codes are rejected by the
  producer. (RULE-DATA-002: referential integrity of primary data by ISO code.)
- **Directional & time-stamped** (fintecheng FX): a rate means "1 unit of `currency` =
  `rate` units of `base_currency`" as of `date`, published by `source` at `fetched_at`.
  The inverse is never assumed.
- **Checksummed.** SHA-256 of the package file is in `manifest.json`; the app verifies
  before importing. Signing (minisign) is layered on later without changing this format.

## manifest.json (repo root, fetched first, small)

```json
{
  "spec_version": "bookkeepy-rates-manifest@1",
  "generated_at": "2026-11-24T06:00:00Z",
  "sources": [
    { "id": "bnr", "name": "Banca Națională a României", "url": "https://www.bnr.ro/23988-cursurile-pietei-valutare-in-format-xml", "base_currency": "RON", "priority": 1 }
  ],
  "packages": [
    {
      "id": "bnr-2026-11-24",
      "source": "bnr",
      "kind": "full | incremental | addendum",
      "date": "2026-11-24",
      "file": "packages/bnr/2026-11-24.json",
      "sha256": "…",
      "size_bytes": 12345,
      "supersedes": null
    }
  ]
}
```

## packages/&lt;source-id&gt;/&lt;date&gt;.json

```json
{
  "spec_version": "bookkeepy-rates-package@1",
  "package_id": "bnr-2026-11-24",
  "source": { "id": "bnr", "name": "…", "url": "…", "fetched_at": "2026-11-24T05:55:00Z" },
  "base_currency": "RON",
  "date": "2026-11-24",
  "kind": "full",
  "rates": [
    { "currency": "EUR", "rate": "4.9750", "multiplier": 1 }
  ],
  "corrections_of": null
}
```

- `rate` is a **string** (decimal, never a JSON float — fintecheng: bare numbers reintroduce
  floating point at the edge).
- `multiplier`: BNR quotes per `multiplier` units (e.g. HUF per 100); stored so consumers
  can compute the per-unit rate exactly with integer minor units.
- `rates` are per `base_currency`. Cross rates between two non-base currencies are derived
  by the app via the base with full precision, rounding once at the boundary (rounding
  account, doc 05 of the main repo).

## Incremental packages

`kind = "incremental"` packages contain only rates that changed/added since the previous
package of the same source (`supersedes` points at it). The app applies packages in
manifest order per source. A `full` package resets the source's series.
