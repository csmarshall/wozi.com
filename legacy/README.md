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
| `resume-2014.pdf` | Was served from the `p_d_f/` prefix, so named because a 0-byte object called `pdf` blocked the natural one. | 2026-07-29 |
| `Spacer.gif` | A 1×1 spacer GIF from 2011. Genuinely a spacer GIF. | 2026-07-29 |

## Recovering something from here

The archive in git is the durable copy, but the bucket can also give a file back.
Versioning was enabled on `s3://wozi.com` and `s3://www.wozi.com` **before**
anything was deleted, so every object retired on 2026-07-29 still exists as a
`null` version with a delete marker on top. Deleting the marker restores the
object; `aws s3api list-object-versions` shows both.

Restoring a file to the live site is a separate step from restoring the object —
it also has to be added to the include list in the deploy workflow, or the next
deploy will not carry it.

**`keybase.html` is not here.** It was going to be retired, then kept: it is a
signed ownership proof and the claim only verifies while the file is reachable.
It lives at the repo root and is published.

## One thing worth knowing

**Melissa's contact card is not here.** It was removed from the site on
2026-07-29 and deliberately kept out of this repo entirely, including this
directory. The only copy is `~/work/claude/qr_code_vcf`. Before this migration,
`/cards/index.html` was a byte-identical duplicate of her card rather than an
index of both people, so trimming the path to `/cards/` served her details.
