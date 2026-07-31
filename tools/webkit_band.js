/* Measure the rim engraving against its band — in WEBKIT.
 *
 *   osascript -l JavaScript tools/webkit_band.js [url]
 *   (default http://127.0.0.1:8765/)
 *
 * Every other harness in this directory drives headless Chrome, which is how
 * #19 shipped: the handle was centred in Blink and Gecko and 19% of a band
 * depth out in WebKit, and nothing here could see it. This one has no Chrome
 * in it. It builds a WKWebView — the same engine Safari and every iOS browser
 * run — loads the page, and reports numbers rather than a screenshot.
 *
 * Needs no Safari settings enabled. `safaridriver` wants "Allow remote
 * automation" and AppleScript `do JavaScript` wants "Allow JavaScript from
 * Apple Events"; both are off by default and both drive the visible browser.
 * WKWebView is just a framework, so this runs offscreen and touches nothing.
 *
 * Method: the band is read out of the live DOM, not recomputed — on a marked
 * wheel the faceR circle IS bandIn (index.html draws it with stroke var(--edge)
 * at 0.4 opacity), and bandOut is that plus MODULE * BAND_DEPTH. For the text,
 * getExtentOfChar returns an AXIS-ALIGNED box, which over-reports a glyph
 * rotated along an arc — so it samples the one glyph nearest the top or bottom
 * of the ring, where the glyph is square to the axis and the box is exact.
 *
 * Reads: off/depth, how far the line box's middle sits from the band's middle
 * as a fraction of band depth. Positive is outward, toward the teeth. Anything
 * past about +/-0.02 is visible on a phone.
 */
ObjC.import('Cocoa');
ObjC.import('stdlib');   /* for $.exit -- osascript returns 0 no matter what run() returns */
ObjC.import('WebKit');

const MEASURE = `
(() => {
  const MODULE = 7, BAND_DEPTH = 1.59;
  const out = [];
  document.querySelectorAll('text').forEach((t) => {
    const tp = t.querySelector('textPath');
    if (!tp) return;
    const href = tp.getAttribute('href') || tp.getAttribute('xlink:href') || '';
    const svg = t.ownerSVGElement;
    if (!svg) return;
    let bandIn = null;
    svg.querySelectorAll('circle').forEach((c) => {
      if ((c.getAttribute('stroke') || '') === 'var(--edge)' &&
          parseFloat(c.getAttribute('stroke-opacity') || '1') < 0.5) {
        bandIn = parseFloat(c.getAttribute('r'));
      }
    });
    if (bandIn === null) return;
    const bandOut = bandIn + MODULE * BAND_DEPTH;
    const ring = document.getElementById(href.replace('#', ''));
    const arc = /A([0-9.]+),([0-9.]+)/.exec(ring ? ring.getAttribute('d') : '');
    const n = t.getNumberOfChars();
    if (!n) return;
    /* the glyph squarest to the axis: its axis-aligned extent is its real
       radial extent, which no other glyph on the arc gives you */
    let best = 0, bestErr = 1e9, top = true;
    for (let i = 0; i < n; i++) {
      const a = Math.abs(((t.getRotationOfChar(i) % 360) + 360) % 360);
      const eTop = Math.min(a, 360 - a), eBot = Math.abs(a - 180);
      const err = Math.min(eTop, eBot);
      if (err < bestErr) { bestErr = err; best = i; top = eTop <= eBot; }
    }
    const ex = t.getExtentOfChar(best);
    /* Radial extent is |y| at the axis, for BOTH rings -- so take it directly
       rather than inferring a direction.
       This used to pick top-vs-bottom from the glyph's ROTATION and then
       measure from its POSITION. Those agree on the handle ring and disagree on
       the stamp ring, which is drawn with the opposite sweep so its text reads
       upright at the bottom: the top flag came out false for a glyph at
       negative y, so lo/hi were returned NEGATIVE and compared against positive
       band radii. That reported off/depth -7.43 and overOut +79.99 for
       lettering sitting correctly inside the band. It went unseen because the
       character layer has been off since 2e5a721, so this harness had only ever
       measured the handle ring.
       NOTE: this whole probe is a template literal, so it must contain no
       backticks -- one in this comment is what broke it first time round. */
    const e0 = Math.abs(ex.y), e1 = Math.abs(ex.y + ex.height);
    const lo = Math.min(e0, e1), hi = Math.max(e0, e1);
    const bandMid = (bandIn + bandOut) / 2, boxMid = (lo + hi) / 2;
    out.push({
      ring: href.replace('#', ''), ch: t.textContent.charAt(best),
      db: t.getAttribute('dominant-baseline') || '(none)',
      F: parseFloat(t.getAttribute('font-size')),
      arcR: arc ? +arc[1] : null, bandIn: bandIn, bandOut: bandOut,
      boxLo: lo, boxHi: hi, boxMid: boxMid, bandMid: bandMid,
      off: (boxMid - bandMid) / (bandOut - bandIn),
      overOut: hi - bandOut, underIn: bandIn - lo
    });
  });
  return JSON.stringify({ ua: navigator.userAgent, rows: out });
})()`;

function run(argv) {
  const url = argv[0] || 'http://127.0.0.1:8765/';
  $.NSApplication.sharedApplication;
  const wv = $.WKWebView.alloc.initWithFrameConfiguration(
    $.NSMakeRect(0, 0, 1600, 1000), $.WKWebViewConfiguration.alloc.init);
  /* WKWebView lays out nothing until it is in a window, even offscreen. */
  const win = $.NSWindow.alloc.initWithContentRectStyleMaskBackingDefer(
    $.NSMakeRect(0, 0, 1600, 1000), 0, 2, false);
  win.contentView = wv;
  wv.loadRequest($.NSURLRequest.requestWithURL($.NSURL.URLWithString(url)));

  const pump = (secs) => $.NSRunLoop.currentRunLoop.runUntilDate(
    $.NSDate.dateWithTimeIntervalSinceNow(secs));
  /* the train deals, mounts and fetches its webfont before any of this means
     anything — measuring early reads a fallback face's metrics */
  pump(6);

  let raw = null;
  wv.evaluateJavaScriptCompletionHandler(MEASURE, (res, err) => {
    raw = (err && !err.isNil()) ? null : (res && !res.isNil() ? ObjC.unwrap(res) : null);
  });
  for (let i = 0; i < 60 && raw === null; i++) pump(0.25);
  if (raw === null) { console.log('FATAL: WebKit never answered (is anything serving ' + url + '?)'); $.exit(2); }

  const d = JSON.parse(raw);
  if (!d.rows.length) { console.log('FATAL: no engraved text found at ' + url); $.exit(2); }

  const pad = (s, w) => (' '.repeat(w) + s).slice(-w);
  const num = (v, w, p) => pad(v.toFixed(p === undefined ? 2 : p), w);
  const lines = [d.ua, ''];
  lines.push(pad('ring', 10) + pad('ch', 3) + pad('baseline', 11) + pad('font', 6)
    + pad('arcR', 8) + pad('bandIn', 8) + pad('bandOut', 9) + pad('boxLo', 8)
    + pad('boxHi', 8) + pad('off/depth', 11) + pad('overOut', 9) + pad('underIn', 9));
  d.rows.forEach((r) => {
    lines.push(pad(r.ring, 10) + pad(r.ch, 3) + pad(r.db, 11) + num(r.F, 6)
      + num(r.arcR, 8) + num(r.bandIn, 8) + num(r.bandOut, 9) + num(r.boxLo, 8)
      + num(r.boxHi, 8) + pad((r.off >= 0 ? '+' : '') + r.off.toFixed(4), 11)
      + pad((r.overOut >= 0 ? '+' : '') + r.overOut.toFixed(2), 9)
      + pad((r.underIn >= 0 ? '+' : '') + r.underIn.toFixed(2), 9));
  });
  const off = d.rows.map((r) => r.off);
  const mean = off.reduce((a, b) => a + b, 0) / off.length;
  lines.push('');
  lines.push('off/depth mean ' + mean.toFixed(4)
    + '   min ' + Math.min.apply(null, off).toFixed(4)
    + '   max ' + Math.max.apply(null, off).toFixed(4));
  lines.push('positive = the lettering rides OUTWARD; overOut > 0 = it has left the band');
  const ok = Math.abs(mean) < 0.02;
  lines.push(ok ? 'RESULT: PASS' : 'RESULT: FAIL — not centred in WebKit');
  /* osascript returns 0 whatever run() returns, so a printed FAIL was invisible
     to any caller -- no shell && chain, no git hook, no scheduled job could gate
     on it. Exit explicitly. */
  console.log(lines.join('\n'));
  $.exit(ok ? 0 : 1);
}
