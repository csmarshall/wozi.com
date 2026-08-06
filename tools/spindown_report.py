#!/usr/bin/env python3
"""Turn tools/spindown_capture.py's per-candidate JSON+PNGs into one comparison
(GitHub #106, CL#127): an overlaid speed-vs-time plot and a filmstrip contact
sheet, one row per candidate, so the shape of each spin-down/spin-up can be
read at a glance and the FEEL judged from moving pictures rather than a table.

Usage:
    tools/spindown_report.py <outdir> <candidate-name> [<candidate-name> ...]

Reads <outdir>/<name>.json + <outdir>/<name>_frames/*.png for each candidate
(written by spindown_capture.py) and writes:
    <outdir>/spindown_plot.png       -- x(t) for every candidate, one axes
    <outdir>/spindown_filmstrip.png  -- one row of frames per candidate
"""
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image, ImageDraw, ImageFont

BUCKET_MS = 50          # velocity bucket width for finite-differencing
PRETAP_CAL_S = 1.0      # window before the tap used to calibrate "200x"
POSTTAP_CAL_S = 1.5     # window at the END of the capture used to calibrate "1x"

COLORS = {"lag": "#9AA6AD", "octave": "#3B7DE8", "coulomb": "#E8483A"}
LABELS = {
    "lag": "A — as shipped (fixed 900ms lag, the control)",
    "octave": "B — proportional/logarithmic tau (ms per octave)",
    "coulomb": "C — Coulomb-ish constant deceleration",
}


def bucket_velocity(samples):
    """[[t_ms, angle], ...] -> [[t_ms_center, deg_per_s], ...], bucketed."""
    if not samples:
        return []
    out = []
    i = 0
    n = len(samples)
    t_end = samples[-1][0]
    b0 = 0.0
    while b0 < t_end:
        b1 = b0 + BUCKET_MS
        # First and last sample within [b0, b1)
        lo = None
        hi = None
        while i < n and samples[i][0] < b1:
            if samples[i][0] >= b0:
                if lo is None:
                    lo = samples[i]
                hi = samples[i]
            i += 1
        if lo is not None and hi is not None and hi[0] > lo[0]:
            v = (hi[1] - lo[1]) / ((hi[0] - lo[0]) / 1000.0)
            out.append([(lo[0] + hi[0]) / 2, v])
        b0 = b1
        i = max(0, i - 1)  # allow overlap at bucket boundary
    return out


def angle_at(samples, t):
    """Linear interpolation directly against the raw (unbucketed) trace."""
    for i in range(len(samples) - 1):
        t0, a0 = samples[i]
        t1, a1 = samples[i + 1]
        if t0 <= t <= t1:
            if t1 == t0:
                return a0
            return a0 + (t - t0) / (t1 - t0) * (a1 - a0)
    return None


def calibrate(samples, tap_at_ms, total_ms):
    """A SINGLE finite difference across each whole calibration window, not an
    average of small buckets. Averaging ~20-30 independent 50ms-bucket
    estimates turned out to be biased ~20% high against a direct measurement
    on this same data — each small bucket's finite difference inherits the
    30fps write cadence's quantization, and those errors did not cancel over
    so few buckets. One long difference divides that noise out by using the
    full window's clean displacement instead of re-noising and re-averaging
    it. """
    a0 = angle_at(samples, tap_at_ms - PRETAP_CAL_S * 1000)
    a1 = angle_at(samples, tap_at_ms - 100)
    ref200 = abs(a1 - a0) / (PRETAP_CAL_S - 0.1) if a0 is not None and a1 is not None else None
    b0 = angle_at(samples, total_ms - POSTTAP_CAL_S * 1000)
    b1 = angle_at(samples, total_ms - 50)
    ref1 = abs(b1 - b0) / (POSTTAP_CAL_S - 0.05) if b0 is not None and b1 is not None else None
    return ref200, ref1


def to_x_units(vel, ref200, ref1):
    if not ref200 or not ref1 or ref200 == ref1:
        return [[t, None] for t, v in vel]
    return [[t, 1 + (abs(v) - ref1) / (ref200 - ref1) * (200 - 1)] for t, v in vel]


def smooth(xs, window=3):
    """Centred moving average over `window` buckets — light denoising for the
    PLOTTED curve only; calibrate() never sees this, it works off the raw
    trace directly (see its own docstring for why that matters)."""
    out = []
    n = len(xs)
    half = window // 2
    for i in range(n):
        lo, hi = max(0, i - half), min(n, i + half + 1)
        vals = [xs[j][1] for j in range(lo, hi) if xs[j][1] is not None]
        out.append([xs[i][0], sum(vals) / len(vals) if vals else None])
    return out


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    outdir, names = sys.argv[1], sys.argv[2:]

    fig, ax = plt.subplots(1, 2, figsize=(13, 5.2))
    curves = {}
    loaded = {}
    own_calib = {}

    for name in names:
        with open(os.path.join(outdir, name + ".json")) as f:
            d = json.load(f)
        loaded[name] = d
        own_calib[name] = calibrate(d["samples"], d["tap_at_ms"], d["samples"][-1][0])
        print(f"{name}: own ref200={own_calib[name][0]:.2f} deg/s, "
              f"own ref1={own_calib[name][1]:.2f} deg/s")

    # ONE CANONICAL CALIBRATION, applied to every candidate, not one per curve.
    # The 200x/1x reference is a property of the SAME wheel in the SAME seeded
    # deal (?seed=8231, same viewport) across every run, so it should be
    # identical candidate to candidate — and self-calibrating each curve off
    # its OWN pre/post windows silently absorbs that candidate's own
    # convergence error into what gets treated as "1.0". Candidate B (the
    # logarithmic-tau one) is the case that actually bit this: at
    # SPINDOWN_MS_PER_OCTAVE=300, tau for the full 200x<->1x span is ~2.3s, and
    # neither this script's PRETAP_S=6s spin-up window nor its POSTTAP_S=9s
    # spin-down window is long enough for a ~5-tau settle — so B's own tail
    # was still measurably decaying, and self-calibrating against it read
    # "1x" as ~125 deg/s instead of the ~20 deg/s every other candidate agrees
    # on. Candidate C (Coulomb) reaches its target EXACTLY, in finite time,
    # well inside both windows, which is what makes it the one to calibrate
    # from — falling back to A (the fixed-tau control, which converges in
    # ~5*900ms = 4.5s, also comfortably inside both windows) if C's capture
    # is not present. */
    canon_name = "coulomb" if "coulomb" in own_calib else (
        "lag" if "lag" in own_calib else names[0])
    ref200, ref1 = own_calib[canon_name]
    print(f"canonical calibration taken from '{canon_name}': "
          f"ref200={ref200:.2f} deg/s, ref1={ref1:.2f} deg/s "
          f"(ratio {ref200/ref1:.1f}x, expect ~199x)")

    for name in names:
        d = loaded[name]
        vel = bucket_velocity(d["samples"])
        xs = smooth(to_x_units(vel, ref200, ref1))
        t = [(p[0] - d["tap_at_ms"]) / 1000 for p in xs]
        x = [p[1] for p in xs]
        curves[name] = (t, x, ref200, ref1)
        color = COLORS.get(name, None)
        label = LABELS.get(name, name)
        ax[0].plot(t, x, label=label, color=color, linewidth=1.6)
        ax[1].plot(t, x, label=label, color=color, linewidth=1.6)

    ax[0].set_title("linear — what the eye actually sees")
    ax[0].set_xlabel("seconds since the reset tap")
    ax[0].set_ylabel("speed (× multiplier, self-calibrated)")
    ax[0].axhline(1, color="#888", linewidth=0.6, linestyle=":")
    ax[0].axvline(0, color="#888", linewidth=0.6)
    ax[0].set_xlim(-0.5, 6)
    ax[0].legend(fontsize=8, loc="upper right")
    ax[0].grid(alpha=0.25)

    ax[1].set_title("log — the multiplicative shape")
    ax[1].set_xlabel("seconds since the reset tap")
    ax[1].set_yscale("log")
    ax[1].axhline(1, color="#888", linewidth=0.6, linestyle=":")
    ax[1].axvline(0, color="#888", linewidth=0.6)
    ax[1].set_xlim(-0.5, 8)
    ax[1].grid(alpha=0.25, which="both")

    fig.suptitle("GitHub #106 / CL#127 — spin-down from 200x, three candidates "
                  "(sampled from the real page, not simulated)")
    fig.tight_layout()
    plot_path = os.path.join(outdir, "spindown_plot.png")
    fig.savefig(plot_path, dpi=150)
    print("wrote", plot_path)

    # ---- filmstrip -----------------------------------------------------
    thumb_w = 260
    pad = 6
    label_h = 26
    rows = []
    max_cols = 0
    for name in names:
        with open(os.path.join(outdir, name + ".json")) as f:
            d = json.load(f)
        frames = d["frames"]
        max_cols = max(max_cols, len(frames))
        rows.append((name, frames))

    thumb_h = None
    thumbs_by_row = []
    for name, frames in rows:
        thumbs = []
        for fr in frames:
            im = Image.open(os.path.join(outdir, fr["file"])).convert("RGB")
            ratio = thumb_w / im.width
            th = int(im.height * ratio)
            thumb_h = th
            im = im.resize((thumb_w, th))
            thumbs.append((fr["offset_s"], im))
        thumbs_by_row.append((name, thumbs))

    sheet_w = pad + max_cols * (thumb_w + pad)
    sheet_h = pad + len(rows) * (thumb_h + label_h + pad)
    sheet = Image.new("RGB", (sheet_w, sheet_h), "white")
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 14)
        font_small = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 11)
    except Exception:
        font = font_small = ImageFont.load_default()

    y = pad
    for name, thumbs in thumbs_by_row:
        draw.text((pad, y), LABELS.get(name, name), fill="black", font=font)
        y += label_h
        x = pad
        for off, im in thumbs:
            sheet.paste(im, (x, y))
            tag = f"t={off:+.2f}s" + ("  (pre-tap)" if off < 0 else "  (tap)" if off == 0 else "")
            draw.text((x + 4, y + thumb_h - 16), tag, fill="yellow", font=font_small)
            x += thumb_w + pad
        y += thumb_h + pad

    strip_path = os.path.join(outdir, "spindown_filmstrip.png")
    sheet.save(strip_path)
    print("wrote", strip_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
