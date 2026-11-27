# bookkeepy-1-rates — the Bookkeepy 1 rates mirror

This repository is the **only** FX-rates source a Bookkeepy 1 app ever talks to. The app
never connects to rate providers directly (ADR-0011/ADR-0012 in
[aAndy03/bookkeepy-1](https://github.com/aAndy03/bookkeepy-1)).

Automation (GitHub Actions, added in a later milestone) pulls reference rates from public
sources — first source: **BNR** ( Banca Națională a României, XML:
https://www.bnr.ro/23988-cursurile-pietei-valutare-in-format-xml , feed
`nbrfxrates.xml`) — normalizes them into immutable packages, and publishes them here.

## What gets published

- `manifest.json` at the repo root — the small entry point every app fetches first.
- `packages/<source-id>/<date>.json` — one immutable package per source per publication
  date (full or incremental; see `docs/package-format.md`).
- Every package file carries a SHA-256 in the manifest. Sources **add** packages; they
  never rewrite or delete published history (corrections = new addendum package).

## Consumption contract (for the app)

1. Fetch `manifest.json` (small). Compare with locally installed packages.
2. Download missing/incremental packages, verify SHA-256 against the manifest.
3. Store packages read-only in the app data dir, import rows into the local `fx_rates`
  table with `origin = "live"`.
4. The app works fully offline with whatever is downloaded; "Download rates" re-syncs.

## Format spec

The single source of truth for the package format is [docs/package-format.md](docs/package-format.md)
(currently `bookkeepy-rates-package@1`). The app pins a `spec_version` it understands.

## License

MIT (see [LICENSE](LICENSE)) for this repo's tooling and package arrangement. The rates data
itself is published by Banca Națională a României (https://www.bnr.ro) and remains theirs;
facts/data are not copyrightable, and BNR's terms of use apply to the data.

## Automation & trust

- `.github/workflows/update-rates.yml` fetches the sources (BNR first) on a schedule and
  on manual dispatch, builds `bookkeepy-rates-package@1` packages, sha256-checksums them
  and **ed25519-signs** them (ADR-0023 in the main repo). The private key is the repo
  secret `RATES_SIGNING_KEY`; the public key is committed at `keys/rates-ed25519.pub.pem`
  and the app pins it (refuses unsigned/badly-signed packages, `BK-RATES-0002`).
- Packages are immutable; corrections are `kind = "addendum"` packages (spec:
  `docs/package-format.md`).
- The app never talks to live sources — it downloads only from this repo.
