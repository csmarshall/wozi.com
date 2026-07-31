#!/usr/bin/env osascript -l JavaScript
/*
 * Does the assembly actually fill the window IN WEBKIT?
 *
 * tools/devices.py answers this for Blink and passes 20/20, but Charles's
 * desktop Safari showed the train shrunk to roughly a third of a 2000px window
 * with no outriggers reaching either edge. A Chrome-driven harness cannot see
 * that, which is the same blind spot that cost #31 and #37.
 *
 * So this builds a WKWebView -- the engine Safari and every iOS browser use --
 * at a desktop size and measures what devices.py measures: how much of the long
 * axis the whole assembly spans, and how far its extremes sit from the edges.
 *
 * Usage: osascript -l JavaScript tools/webkit_fit.js [url] [width] [height]
 */

ObjC.import('Cocoa');
ObjC.import('stdlib');   /* for $.exit -- osascript returns 0 no matter what run() returns */
ObjC.import('WebKit');

const MEASURE = `
(() => {
  const svgs = [...document.querySelectorAll('svg')].filter(s => {
    const w = parseFloat(s.getAttribute('width') || '0');
    return w >= 40;
  });
  if (!svgs.length) return JSON.stringify({ rows: [], err: 'no wheels' });
  let lo = Infinity, hi = -Infinity, linkLo = Infinity, linkHi = -Infinity;
  const rows = [];
  svgs.forEach(s => {
    const r = s.getBoundingClientRect();
    lo = Math.min(lo, r.left); hi = Math.max(hi, r.right);
    rows.push({ w: +r.width.toFixed(1), l: +r.left.toFixed(1), r: +r.right.toFixed(1) });
  });
  /* the LINKED wheels are the ones carrying a badge */
  document.querySelectorAll('a[aria-label]').forEach(a => {
    const r = a.getBoundingClientRect();
    if (r.width < 10) return;
    linkLo = Math.min(linkLo, r.left); linkHi = Math.max(linkHi, r.right);
  });
  const stage = document.querySelector('[role="application"]');
  const st = stage ? stage.getBoundingClientRect() : null;
  const cs = stage ? getComputedStyle(stage) : null;
  return JSON.stringify({
    ua: navigator.userAgent,
    vw: window.innerWidth, vh: window.innerHeight,
    vvw: (window.visualViewport && window.visualViewport.width) || null,
    wheels: svgs.length,
    lo: +lo.toFixed(1), hi: +hi.toFixed(1),
    linkLo: isFinite(linkLo) ? +linkLo.toFixed(1) : null,
    linkHi: isFinite(linkHi) ? +linkHi.toFixed(1) : null,
    stage: st ? { l: +st.left.toFixed(1), r: +st.right.toFixed(1),
                  w: +st.width.toFixed(1), h: +st.height.toFixed(1) } : null,
    stageTransform: cs ? cs.transform : null,
    gs: getComputedStyle(document.documentElement).getPropertyValue('--gs'),
    rows: rows
  });
})()
`;

function run(argv) {
  const url = argv[0] || 'http://127.0.0.1:8765/';
  const W = parseInt(argv[1] || '2000', 10);
  const H = parseInt(argv[2] || '1200', 10);
  $.NSApplication.sharedApplication;
  const wv = $.WKWebView.alloc.initWithFrameConfiguration(
    $.NSMakeRect(0, 0, W, H), $.WKWebViewConfiguration.alloc.init);
  const win = $.NSWindow.alloc.initWithContentRectStyleMaskBackingDefer(
    $.NSMakeRect(0, 0, W, H), 0, 2, false);
  win.contentView = wv;
  wv.loadRequest($.NSURLRequest.requestWithURL($.NSURL.URLWithString(url)));

  const pump = (secs) => $.NSRunLoop.currentRunLoop.runUntilDate(
    $.NSDate.dateWithTimeIntervalSinceNow(secs));
  pump(6);

  let raw = null;
  wv.evaluateJavaScriptCompletionHandler(MEASURE, (res, err) => {
    raw = (err && !err.isNil()) ? null : (res && !res.isNil() ? ObjC.unwrap(res) : null);
  });
  for (let i = 0; i < 60 && raw === null; i++) pump(0.25);
  if (raw === null) { console.log('FATAL: WebKit never answered (is anything serving ' + url + '?)'); $.exit(2); }

  const d = JSON.parse(raw);
  if (d.err) { console.log('FATAL: ' + d.err); $.exit(2); }

  const span = d.hi - d.lo;
  const cover = 100 * span / d.vw;
  const linkSpan = (d.linkHi != null) ? d.linkHi - d.linkLo : 0;
  const out = [];
  out.push(d.ua);
  out.push('');
  out.push('window                 : ' + d.vw + ' x ' + d.vh
    + (d.vvw ? '   visualViewport ' + d.vvw : ''));
  out.push('wheels drawn           : ' + d.wheels);
  out.push('stage rect             : ' + (d.stage
    ? d.stage.l + ' -> ' + d.stage.r + '  (' + d.stage.w + ' wide)' : 'not found'));
  out.push('stage transform        : ' + d.stageTransform);
  out.push('--gs                   : ' + (d.gs || '(unset)'));
  out.push('assembly spans         : ' + d.lo + ' -> ' + d.hi
    + '   = ' + span.toFixed(1) + 'px, ' + cover.toFixed(1) + '% of the window');
  out.push('gap to left / right    : ' + d.lo.toFixed(1) + ' / ' + (d.vw - d.hi).toFixed(1));
  out.push('linked wheels span     : ' + linkSpan.toFixed(1) + 'px, '
    + (100 * linkSpan / d.vw).toFixed(1) + '% of the window');
  out.push('');
  /* TWO-SIDED, deliberately (#46). The first version of this file checked only
     `cover >= 98` and PASSED on the very train it was written to catch: the
     outriggers bleed to 127% of the window, so the assembly reaches both edges
     while the linked wheels sit at 29% and the machine reads as a toy in the
     middle of the screen. A bound with no counterpart is how #44 cleared 20
     device profiles, and this harness had the identical flaw within an hour of
     being written to expose it.
     The floor is 0.45, taken from CHROME measurements: 55-64% on every phone,
     tablet and laptop profile and 30-33% on the ultrawides, a 22-point empty
     gap, so 0.45 sits in the middle of it.
     BUT WEBKIT RUNS LOWER, and by a lot: 44.3% at 1280x900 where Chrome reports
     60.7%, and 27.8% at 2000x1200 where Chrome reports 38.5%. So this harness
     currently fails at EVERY desktop width, not only the wide ones. That is not
     a bad threshold -- it is #44 being worse in WebKit than the Chrome numbers
     suggested, which is exactly what Charles saw and what no Blink harness could
     report. Do not loosen the floor to make this green. Re-derive it from WebKit
     numbers once #44 is fixed, and expect it to end up HIGHER, not lower.
     Caveat: per-load variance in one engine is about 3.4 points, so any single
     reading near the boundary is noise. Compare medians, not samples. This file is macOS-only and is NOT in deploy.yml,
     so the floor gates nothing and cannot block a push -- which is why it can
     land before #44 is fixed, whereas devices.py's copy of it must not. */
  const linkShare = linkSpan / d.vw;
  const LINK_FLOOR = 0.45;
  const reaches = cover >= 98;
  const bigEnough = linkShare >= LINK_FLOOR;
  const ok = reaches && bigEnough;
  if (!reaches) out.push('FAIL: the assembly covers only ' + cover.toFixed(1)
    + '% of the long axis, leaving ' + d.lo.toFixed(0) + 'px and '
    + (d.vw - d.hi).toFixed(0) + 'px bare');
  if (!bigEnough) out.push('FAIL: the linked wheels span only '
    + (100 * linkShare).toFixed(1) + '% of the window, under the '
    + (100 * LINK_FLOOR).toFixed(0) + '% floor — the train reads as a toy in the '
    + 'middle of the screen even though the ghosts reach the edges (#44)');
  out.push(ok ? 'RESULT: PASS — reaches both edges AND the train is big enough'
              : 'RESULT: FAIL');
  /* see the note in webkit_band.js: osascript exits 0 regardless of what run()
     returns, so this has to say so itself. */
  console.log(out.join('\n'));
  $.exit(ok ? 0 : 1);
}
