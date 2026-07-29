# legacy

Everything that used to live in `s3://wozi.com` and `s3://www.wozi.com` and is no
longer served. Kept because the bucket is no longer the archive — this repo is.

**Nothing in this directory is ever uploaded.** The deploy names the paths it
publishes explicitly rather than excluding the ones it does not, so a file added
here cannot reach the web by accident. See `.github/workflows/deploy.yml`.

## Contents

| Path | What it is | Retired |
| --- | --- | --- |
| `2023-landing/` | The landing page this repo replaces, plus its two assets. Links Twitter and Flickr, and points Threads at `threads.net`. | 2026-07-29 |
| `2014-www/` | The whole of `s3://www.wozi.com`. Unreachable since that bucket was set to redirect every request to the apex, so it had been dead for years. Includes `meta/4k` — 4096 bytes of random binary, a test fixture — and `front_iad*.jpg`, region-test copies of `front.jpg`. | long dead |
| `keybase.html` | Keybase ownership proof for wozi.com, signed 2017. | 2026-07-29 |
| `resume-2014.pdf` | Was served from the `p_d_f/` prefix, so named because a 0-byte object called `pdf` blocked the natural one. | 2026-07-29 |
| `Spacer.gif` | A 1×1 spacer GIF from 2011. Genuinely a spacer GIF. | 2026-07-29 |

## Two things worth knowing before deleting any of this

**The Keybase proof only verifies while it is reachable.** Retiring
`keybase.html` breaks the claim that `cs_marshall` controls wozi.com. That was a
deliberate choice — Keybase has been dormant since the 2020 Zoom acquisition —
but it is a live consequence, not just an archived file. Restoring it means
serving it at `/keybase.html` again, unchanged; the signature covers the content.

**Melissa's contact card is not here.** It was removed from the site on
2026-07-29 and deliberately kept out of this repo entirely, including this
directory. The only copy is `~/work/claude/qr_code_vcf`. Before this migration,
`/cards/index.html` was a byte-identical duplicate of her card rather than an
index of both people, so trimming the path to `/cards/` served her details.
