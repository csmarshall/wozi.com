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
  if (raw === null) return 'FATAL: WebKit never answered (is anything serving ' + url + '?)';

  const d = JSON.parse(raw);
  if (d.err) return 'FATAL: ' + d.err;

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
  /* devices.py wants the assembly at both edges; the same bar applies here. */
  const ok = cover >= 98;
  out.push(ok ? 'RESULT: PASS — the assembly reaches both edges'
    : 'RESULT: FAIL — the assembly covers only ' + cover.toFixed(1)
      + '% of the long axis, leaving ' + d.lo.toFixed(0) + 'px and '
      + (d.vw - d.hi).toFixed(0) + 'px bare');
  return out.join('\n');
}
