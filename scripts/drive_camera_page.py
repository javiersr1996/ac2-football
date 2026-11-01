"""Drive the built camera page from the browser console and check it against the storyboard.

    uv run --with playwright playwright install chromium        # once
    uv run --with playwright python scripts/drive_camera_page.py [path-or-url] [--shots DIR]
        [--only one-screen]                                     # just the no-scroll rows

The default target is ``reports/camera/what_the_camera_saw.html``; after publishing, the same
driver runs against the Pages URL. The expected values are read from ``reports/camera/camera.json``
and ``reports/reliability.csv``, never typed and never read from the page's source. One line per
check; exit 0 if every check passes and 1 otherwise. Screenshots go to ``build/camera/`` (ignored)
or ``--shots``.

The page is one screen at every size: a header, the stage, the control bar and a panel of tabs
whose body alone scrolls. The layout rows run at seven viewports (``VIEWPORTS``): the page never
scrolls, each tab opens by mouse, tap and keyboard and shows inside the panel uncut, the text is
large enough and dark enough, nothing written overlaps, and the players stay at least the floors
below.

The browser runs on the machine's GPU (ANGLE on D3D11 on Windows). If WebGL is not live the driver
fails loudly before anything else; if the renderer is a software one (SwiftShader), every row that
times something fails as "software renderer: timing not measurable" rather than passing on a clock
that measures the CPU. The natural run is timed by the page's own clock (``camera.clock()``: the
animation frames it drew), not by a sampler in the driver, so a loaded machine slows it without
failing it. Headless Chromium cannot hide a tab, so the hidden-tab rule is not exercised.

Copied, with a declaration, from the author's basketball entry
(github.com/javiersr1996/nobody-helps-the-helper, ``scripts/drive_wind_page.py``, MIT): ``INIT_JS``
(adapted), ``SCAN_JS``, ``PROJ_JS``, ``Report`` and ``R.check``, ``guarded``, the WebGL and
software-renderer guard, the reduced-motion route and the layout rows.
"""

# The in-page JavaScript and the check sentences are long lines, as in the basketball driver.
# ruff: noqa: E501

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
import time
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import numpy as np
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
DEFAULT_PAGE = REPORTS / "camera" / "what_the_camera_saw.html"
CHROMIUM_ARGS = ["--use-angle=d3d11", "--enable-gpu", "--ignore-gpu-blocklist"]
SOFTWARE = "software renderer: timing not measurable"
# The storyboard's numbers the checks are written from (tasks/camera_page.md): the body and the
# markers drawn (2.3), the timing (2.6), the start-up and frame-time targets, the legibility and
# layout floors (2.4, 6), the pitch and its apron (2.1).
BODY_H, DISC_R, ME_RING = 1.8, 1.1, 1.45
RATE, HOLD_S, FLIGHT_S, FADE_S = 1.0, 0.6, 1.5, 0.4
FIRST_FRAME_S, PLAYING_S, FRAME_MEDIAN_MS = 1.0, 1.5, 17.0
# The hold is a setTimeout and one animation frame after it, so it may run late by a frame and the
# timer's slack: 0.15 s, as the storyboard's table allowed. The flight and the fade are timed to the
# frame by the page's clock (each with the longest step between two of its frames).
HOLD_SLACK_S = 0.15
# The seven viewports of the one-screen layout (width, height; the last four are touch screens).
VIEWPORTS = [(1440, 900), (1280, 720), (1024, 768), (844, 390), (390, 844), (360, 780), (320, 568)]
TOUCH = {(844, 390), (390, 844), (360, 780), (320, 568)}
# Legibility floors, measured on this layout and set a little under what it gave (1440: 23.9 px,
# 41.6 % sky, an 18.6 px disc; 390: 9.5 px, 40.3 %, 7.5 px; 320: 7.7 px, 12.3 %, 3.6 px), so a
# regression of the fit fails: the median drawn height of the defenders in broadcast (px), the
# share of the stage that is bare sky in broadcast, and a defender's disc in plan (px across).
# The stage is no longer the whole window, so 1440's floor is under the scrolling page's 30 px:
# the camera's window on the grass is wide and shallow, the width sets the scale and the spare
# height above it is sky. Lowering FIT_REACH from 20 to 8 changes none of it (only the keeper is
# ever left out of the fit); letting the tilt trade field of view for height leans the bodies.
# A portrait screen opens in plan, where its floor is the disc.
LEGIBLE_PX = {
    (1440, 900): 22.0,
    (1280, 720): 20.0,
    (1024, 768): 16.0,
    (844, 390): 12.0,
    (390, 844): 9.0,
    (360, 780): 8.0,
    (320, 568): 7.0,
}
EMPTY_MAX = {
    (1440, 900): 0.45,
    (1280, 720): 0.35,
    (1024, 768): 0.48,
    (844, 390): 0.18,
    (390, 844): 0.45,
    (360, 780): 0.42,
    (320, 568): 0.18,
}
DISC_MIN_PX = {
    (1440, 900): 17.0,
    (1280, 720): 12.5,
    (1024, 768): 13.0,
    (844, 390): 5.5,
    (390, 844): 7.0,
    (360, 780): 6.0,
    (320, 568): 3.2,
}
# The tabs whose body must fit at 1440 x 900 without scrolling inside the panel.
FIT_TABS = ("story", "metrics", "matches")
TABS = ("story", "metrics", "matches", "camera", "limits")
SKY = "#DFE3DA"
BODY_MIN_PX, LABEL_MIN_PX, TARGET_PX, CONTRAST_MIN = 16, 12, 44, 4.5
HALF_L, HALF_W, APRON = 52.5, 34.0, 6.0
VERMILION, INK, GREY = "#D55E00", "#222222", "#777777"
THESIS_SAYS = "a different sample, not an error"
TIMED = {"on": True}

# In-page helpers, installed before the page's own script runs: `__vis(el)` (really visible),
# `__ui()` (buttons and the caption), a 10 ms sampler that logs every change of (view, phase, i,
# tab) with its time, the time of the first draw on the stage's canvas, the time of the first
# `playing`, and the animation frames' timestamps while playing.
INIT_JS = """
(() => {
  const txt = (e) => (e ? e.textContent.replace(/\\s+/g, ' ').trim() : null);
  window.__vis = (e) => {
    if (!e) return false;
    for (let n = e; n && n.nodeType === 1; n = n.parentElement) {
      if (n.hidden) return false;
      const cs = getComputedStyle(n);
      if (cs.display === 'none' || cs.visibility === 'hidden') return false;
    }
    return e.getClientRects().length > 0;
  };
  window.__ui = () => {
    const g = (i) => document.getElementById(i);
    const b = (i) => ({text: txt(g(i)), disabled: g(i).disabled, pressed: g(i).getAttribute('aria-pressed')});
    return {play: b('play'), bcast: b('view-broadcast'), plan: b('view-plan'), v0: b('variant-v0'),
            v1: b('variant-v1'), caption: txt(g('stage-caption')),
            scrub: {value: g('scrub').value, valuetext: g('scrub').getAttribute('aria-valuetext')}};
  };
  window.__log = [];
  let last = '';
  setInterval(() => {
    const c = window.camera;
    if (!c || !c.state) return;
    const s = c.state();
    const sig = [s.view, s.phase, s.i, s.tab].join('|');
    if (sig !== last) {
      last = sig;
      window.__log.push({ts: performance.now(), view: s.view, phase: s.phase, i: s.i, t: s.t, tab: s.tab});
    }
  }, 10);
  window.__frames = [];
  const sample = (now) => {
    const c = window.camera;
    if (c && c.state) {
      const s = c.state();
      if (s.phase === 'playing') {
        window.__frames.push(now);
        if (window.__playing === undefined) window.__playing = performance.now();
      }
    }
    requestAnimationFrame(sample);
  };
  requestAnimationFrame(sample);
  for (const C of [window.WebGL2RenderingContext, window.WebGLRenderingContext]) {
    if (!C) continue;
    for (const n of ['drawElements', 'drawArrays']) {
      const f = C.prototype[n];
      C.prototype[n] = function (...a) {
        if (window.__firstDraw === undefined && this.canvas && this.canvas.id === 'pitch') {
          window.__firstDraw = performance.now();
          requestAnimationFrame(() => { window.__firstPaint = performance.now(); });
        }
        return f.apply(this, a);
      };
    }
  }
})();
"""

# Connected components of pixels near a colour, read from the WebGL canvas (labels are DOM, so
# none of them can leak into this read).
SCAN_JS = """
([hexes, tol]) => {
  const c = document.getElementById('pitch');
  const t = document.createElement('canvas');
  t.width = c.width; t.height = c.height;
  const cx = t.getContext('2d');
  cx.drawImage(c, 0, 0);
  const W = c.width, H = c.height, d = cx.getImageData(0, 0, W, H).data;
  const sx = c.width / c.clientWidth, sy = c.height / c.clientHeight;
  const out = {};
  for (const hex of hexes) {
    const r = parseInt(hex.slice(1, 3), 16), g = parseInt(hex.slice(3, 5), 16), b = parseInt(hex.slice(5, 7), 16);
    const mask = new Uint8Array(W * H);
    let count = 0;
    for (let i = 0; i < W * H; i++) {
      if (Math.abs(d[4*i] - r) <= tol && Math.abs(d[4*i+1] - g) <= tol && Math.abs(d[4*i+2] - b) <= tol) {
        mask[i] = 1; count++;
      }
    }
    const comps = [];
    for (let i = 0; i < W * H; i++) {
      if (mask[i] !== 1) continue;
      const stack = [i]; mask[i] = 2;
      let n = 0, mx = 0, my = 0;
      while (stack.length) {
        const k = stack.pop(), x = k % W, y = (k - x) / W;
        n++; mx += x + 0.5; my += y + 0.5;
        for (const [dx, dy] of [[1,0],[-1,0],[0,1],[0,-1]]) {
          const xx = x + dx, yy = y + dy;
          if (xx < 0 || yy < 0 || xx >= W || yy >= H) continue;
          const kk = yy * W + xx;
          if (mask[kk] === 1) { mask[kk] = 2; stack.push(kk); }
        }
      }
      comps.push({n: n, x: mx / n / sx, y: my / n / sy});
    }
    out[hex] = {count: count, comps: comps};
  }
  return out;
}
"""

# The ink across each sampled edge point: the centre of the ink band along the edge's normal, in
# CSS pixels from the point (null where no ink is found within 6 px).
BAND_JS = """
(samples) => {
  const c = document.getElementById('pitch');
  const t = document.createElement('canvas');
  t.width = c.width; t.height = c.height;
  const cx = t.getContext('2d');
  cx.drawImage(c, 0, 0);
  const W = c.width, d = cx.getImageData(0, 0, W, c.height).data, s = c.width / c.clientWidth;
  const ink = (x, y) => { const k = 4 * (Math.round(y * s - 0.5) * W + Math.round(x * s - 0.5));
                          const v = (d[k] + d[k+1] + d[k+2]) / 3; return Math.max(0, 150 - v); };
  return samples.map(([x, y, nx, ny]) => {
    let w = 0, m = 0;
    for (let o = -6; o <= 6; o += 0.25) { const v = ink(x + nx * o, y + ny * o); w += v; m += v * o; }
    return w > 0 ? m / w : null;
  });
}
"""

# Pixel of a clip-frame point through camera(): independent of the page's own `project`.
PROJ_JS = """
(pts) => {
  const cam = camera.camera(), W = cam.world, P = cam.projection, V = cam.view;
  const mul = (m, v) => [0,1,2,3].map(r => m[r]*v[0] + m[4+r]*v[1] + m[8+r]*v[2] + m[12+r]*v[3]);
  return pts.map(([x, y, z]) => {
    const q = mul(P, mul(V, mul(W, [x, y, z, 1])));
    return [(q[0]/q[3]*0.5 + 0.5) * cam.width, (1 - (q[1]/q[3]*0.5 + 0.5)) * cam.height];
  });
}
"""

# The page's scroll: the document against the window, both ways.
SCROLL_JS = """() => { const de = document.documentElement, b = document.body;
  return {sh: Math.max(de.scrollHeight, b.scrollHeight), ih: innerHeight, sw: Math.max(de.scrollWidth, b.scrollWidth), iw: innerWidth}; }"""

# Every visible piece of text: its element, the text, its box, font size, whether it is prose
# (a p or li of 60 characters or more), its colour and the colour under it (the backgrounds of
# its ancestors composited; text over the canvas with no opaque card under it is named), and
# whether a disabled control holds it (exempt from contrast, as WCAG has it). Text inside a
# tab's body counts where it can be scrolled to; elsewhere, where it is on screen.
TEXT_JS = """() => {
  const parse = s => { const m = s && s.match(/rgba?\\(([^)]+)\\)/); if (!m) return null;
    const p = m[1].split(/[\\s,\\/]+/).filter(Boolean).map(Number); return [p[0], p[1], p[2], p.length > 3 ? p[3] : 1]; };
  const over = (top, bottom) => [0, 1, 2].map(i => top[i] * top[3] + bottom[i] * (1 - top[3])).concat([1]);
  const lum = c => { const [r, g, b] = c.slice(0, 3).map(v => { v /= 255; return v <= 0.04045 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); });
                     return 0.2126 * r + 0.7152 * g + 0.0722 * b; };
  const stage = document.getElementById('stage');
  const seen = new Set(), out = [];
  const walk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let n = walk.nextNode(); n; n = walk.nextNode()) {
    const e = n.parentElement;
    if (!e || seen.has(e) || !n.textContent.trim()) continue;
    if (e.closest('script, style, .sr, title') || !__vis(e)) continue;
    seen.add(e);
    const r = e.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) continue;
    const cs = getComputedStyle(e), svg = e instanceof SVGElement;
    let fg = parse(svg ? cs.fill : cs.color) || [0, 0, 0, 1], opacity = 1;
    const chain = [];
    for (let a = e; a && a.nodeType === 1; a = a.parentElement) { chain.push(a); opacity *= parseFloat(getComputedStyle(a).opacity); }
    let bg = [255, 255, 255, 1], card = false;
    for (const a of chain.slice().reverse()) {
      const c = parse(getComputedStyle(a).backgroundColor);
      if (c && c[3] > 0) { bg = over(c, bg); if (stage.contains(a) && a !== stage && c[3] >= 0.99) card = true; }
    }
    fg = [fg[0], fg[1], fg[2], fg[3] * opacity];
    const shown = over(fg, bg), L1 = lum(shown), L2 = lum(bg);
    const ratio = (Math.max(L1, L2) + 0.05) / (Math.min(L1, L2) + 0.05);
    const own = [...e.childNodes].filter(c => c.nodeType === 3).map(c => c.textContent).join('').trim();
    const pane = e.closest('.tabpanel');
    out.push({id: e.id || (e.className && e.className.baseVal === undefined ? e.className : '') || e.tagName, text: own.slice(0, 40),
              len: (e.innerText || e.textContent).trim().length, tag: e.tagName.toLowerCase(),
              x: r.left, y: r.top, w: r.width, h: r.height, size: parseFloat(cs.fontSize),
              ratio: +ratio.toFixed(2), overCanvas: stage.contains(e) && !card,
              disabled: Boolean(e.closest('button[disabled], input[disabled]')), pane: pane ? pane.id : null}); }
  return out; }"""

# The boxes that hold writing on the stage and in the control bar, for the overlap rows: each
# visible tag, the counter, the key (on the stage), the buttons, the ticks' label, the tabs.
BOXES_JS = """() => { const box = (e, name) => { const b = e.getBoundingClientRect(); return {name, x: b.left, y: b.top, w: b.width, h: b.height}; };
  const out = [];
  for (const t of document.querySelectorAll('#tags .tag')) if (!t.hidden) out.push(box(t, 'tag ' + t.textContent.trim().slice(0, 14)));
  for (const id of ['count', 'play', 'view-broadcast', 'view-plan', 'variant-v0', 'variant-v1'])
    if (__vis(document.getElementById(id))) out.push(box(document.getElementById(id), id));
  const key = document.getElementById('key');
  if (__vis(key) && document.getElementById('stage').contains(key)) out.push(box(key, 'key'));
  for (const l of document.querySelectorAll('#ticks .tick-label')) out.push(box(l, 'ticks'));
  for (const t of document.querySelectorAll('[role=tab]')) out.push(box(t, 'tab ' + t.dataset.tab));
  return out; }"""


class Report:
    """Collects one line per check; `ok` is the exit-code decision."""

    def __init__(self) -> None:
        self.rows: list[tuple[bool, str, str]] = []

    def check(self, name: str, ok: bool, detail: str = "") -> bool:
        ok = bool(ok)
        self.rows.append((ok, name, detail))
        print(
            f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  [{detail}]" if detail else ""), flush=True
        )
        return ok

    @property
    def ok(self) -> bool:
        return all(r[0] for r in self.rows)


R = Report()
# What the layout rows measured, per viewport, for the summary table at the end.
MEASURED: dict[tuple[int, int], dict[str, object]] = {}


def guarded(fn):
    """A crash inside one group of checks is a FAIL line, not a silent skip of the rest."""

    def run(*a, **k):
        try:
            return fn(*a, **k)
        except Exception as e:  # noqa: BLE001 - the report must name the failing group
            R.check(f"{fn.__name__} ran to the end", False, f"{type(e).__name__}: {str(e)[:300]}")

    return run


# ---------------------------------------------------------------- expected values, from files


class Data:
    def __init__(self) -> None:
        self.doc = json.loads((REPORTS / "camera" / "camera.json").read_text(encoding="utf-8"))
        d = self.doc
        self.n, self.fps, self.key = d["n_frames"], d["fps"], d["key"]["index"]
        ent = d["entities"]
        self.rivals = np.array(ent["rivals"]["xy"], dtype=float)  # (n, 11, 2)
        self.me = np.array(ent["me"]["xy"], dtype=float)
        self.ball = np.array(ent["ball"]["xy"], dtype=float)
        self.mates = np.array(
            [[[np.nan, np.nan] if p[0] is None else p for p in f] for f in ent["mates"]["xy"]],
            dtype=float,
        )
        self.seen = np.array(ent["rivals"]["detected"], dtype=bool)
        self.gap = np.array(ent["rivals"]["gap"], dtype=int)
        self.corners = np.array(d["camera"]["corners"], dtype=float)
        with (REPORTS / "reliability.csv").open(encoding="utf-8", newline="") as f:
            self.csv = list(csv.DictReader(f))

    def pick(self, path: str):
        node = self.doc
        for part in path.split("."):
            node = node[int(part)] if isinstance(node, list) else node[part]
        return node

    def at(self, tau: float) -> dict:
        f = min(max(tau * self.fps, 0.0), self.n - 1)
        i = min(int(math.floor(f + 1e-9)), self.n - 1)
        j, a = min(i + 1, self.n - 1), max(0.0, f - i)

        def lerp(arr):
            return arr[i] + (arr[j] - arr[i]) * a

        return {"rivals": lerp(self.rivals), "me": lerp(self.me), "ball": lerp(self.ball), "i": i}

    def cell(self, metric: str, variant: str, col: str) -> float:
        rows = [
            r
            for r in self.csv
            if r["match_id"] == str(self.doc["match_id"])
            and r["metric"] == metric
            and r["ball_stratum"] == "all"
            and r["variant"] == variant
        ]
        return float(rows[0][col])


def clip_frame(corners: np.ndarray) -> list[tuple[float, float, int]]:
    """The frame clipped to the pitch and its apron (Sutherland-Hodgman), as the page does: each
    vertex with the frame edge its outgoing side lies on (-1 along the apron)."""
    poly = [(float(x), float(y), k) for k, (x, y) in enumerate(corners)]
    for axis, side in ((0, 1), (0, -1), (1, 1), (1, -1)):
        lim = side * (HALF_L + APRON if axis == 0 else HALF_W + APRON)
        out = []
        for k, p in enumerate(poly):
            q = poly[(k + 1) % len(poly)]
            inside_p, inside_q = (
                side * p[axis] <= side * lim + 1e-9,
                side * q[axis] <= side * lim + 1e-9,
            )
            u = (lim - p[axis]) / (q[axis] - p[axis]) if q[axis] != p[axis] else 0.0
            cut = (p[0] + (q[0] - p[0]) * u, p[1] + (q[1] - p[1]) * u)
            if inside_p:
                out.append(p)
                if not inside_q:
                    out.append((*cut, -1))
            elif inside_q:
                out.append((*cut, p[2]))
        poly = out
    return poly


def in_poly(pt, poly) -> bool:
    """Point in a convex polygon (pixels), either orientation."""
    signs = []
    for k in range(len(poly)):
        a, b = poly[k], poly[(k + 1) % len(poly)]
        signs.append((b[0] - a[0]) * (pt[1] - a[1]) - (b[1] - a[1]) * (pt[0] - a[0]))
    return all(s >= 0 for s in signs) or all(s <= 0 for s in signs)


def meets(a: dict, b: dict, pad: float = 0.5) -> bool:
    """Two boxes ({x, y, w, h}) overlap by more than `pad` px both ways."""
    return (
        min(a["x"] + a["w"], b["x"] + b["w"]) - max(a["x"], b["x"]) > pad
        and min(a["y"] + a["h"], b["y"] + b["h"]) - max(a["y"], b["y"]) > pad
    )


# ---------------------------------------------------------------- browser helpers


def open_page(browser, target: str, *, width=1440, height=900, reduced=False, touch=None):
    touch = (width, height) in TOUCH if touch is None else touch
    ctx = browser.new_context(
        viewport={"width": width, "height": height},
        device_scale_factor=1,
        reduced_motion="reduce" if reduced else "no-preference",
        has_touch=True,
        is_mobile=touch,
    )
    ctx.add_init_script(INIT_JS)
    pg = ctx.new_page()
    errors: list[str] = []
    requests: list[str] = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    pg.on("request", lambda r: requests.append(r.url))
    pg.goto(target, wait_until="load")
    pg.wait_for_function(
        "window.camera && camera.state && document.getElementById('play')", timeout=30000
    )
    pg.errors, pg.requests = errors, requests
    return ctx, pg


def settle(pg) -> None:
    pg.evaluate("new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")


def go(pg, view: str, t: float | None = None) -> None:
    pg.evaluate(f"camera.flight({1 if view == 'plan' else 0})")
    if t is not None:
        pg.evaluate(f"camera.seek({t})")
    settle(pg)


def proj(pg, pts) -> np.ndarray:
    return np.array(pg.evaluate(PROJ_JS, [list(map(float, p)) for p in pts]), dtype=float)


def shot(pg, shots: Path, name: str) -> None:
    shots.mkdir(parents=True, exist_ok=True)
    pg.screenshot(path=str(shots / f"{name}.png"))


def has_tabs(pg) -> bool:
    return bool(pg.evaluate("document.querySelectorAll('[role=tab]').length"))


def tab(pg, name: str) -> None:
    """Open a tab through the page's API; the Camera tab rises to the plan, so wait for it."""
    pg.evaluate(f"camera.tab && camera.tab('{name}')")
    pg.wait_for_function("camera.state().view !== 'rising'", timeout=10000)
    settle(pg)


def vp(width: int, height: int) -> str:
    return f"{width}x{height}"


# ---------------------------------------------------------------- the check groups


@guarded
def check_startup(D: Data, p, target: str) -> None:
    """Start-up and frame time (2.6), each in a fresh browser: the first painted frame of the
    stage, the first `playing`, the frame times while the hook plays at 1440 px."""
    names = ("start-up: first stage frame painted", "start-up: playing", "frame time while playing")
    if not TIMED["on"]:
        for name in names:
            R.check(name, False, SOFTWARE)
        return
    runs = []
    for _ in range(3):
        browser = p.chromium.launch(args=CHROMIUM_ARGS)
        ctx, pg = open_page(browser, target)
        pg.wait_for_function(
            "camera.state().view !== 'broadcast' || camera.state().phase === 'ended'", timeout=15000
        )
        runs.append(
            pg.evaluate("""() => { const f = window.__frames, d = [];
            for (let i = 1; i < f.length; i++) d.push(f[i] - f[i - 1]);
            d.sort((a, b) => a - b);
            return {paint: window.__firstPaint, playing: window.__playing, median: d[d.length >> 1], n: d.length}; }""")
        )
        ctx.close()
        browser.close()
    R.check(
        f"{names[0]} within {FIRST_FRAME_S} s of navigation, three cold loads",
        all(r["paint"] / 1000 <= FIRST_FRAME_S for r in runs),
        ", ".join(f"{r['paint'] / 1000:.2f}" for r in runs) + " s",
    )
    R.check(
        f"{names[1]} within {PLAYING_S} s of navigation, three cold loads",
        all(r["playing"] / 1000 <= PLAYING_S for r in runs),
        ", ".join(f"{r['playing'] / 1000:.2f}" for r in runs) + " s",
    )
    R.check(
        f"{names[2]} at 1440 px: median <= {FRAME_MEDIAN_MS} ms",
        all(r["median"] <= FRAME_MEDIAN_MS and r["n"] > 60 for r in runs),
        "; ".join(f"{r['median']:.1f} ms over {r['n']}" for r in runs),
    )


def run_times(clock: list[dict], key_s: float) -> tuple[bool, str]:
    """The natural run on the page's clock: each span between two of its moments against the
    storyboard, allowing the steps the page itself counted (a frame that crosses the end, and the
    time lost to frames longer than STEP_MAX, which slow the clip on purpose)."""
    first = {}
    for c in clock:
        first.setdefault(c["e"], c)
    need = ("play", "reception", "rise", "land", "faded")
    if any(e not in first for e in need):
        return False, f"clock has {sorted(first)}"
    play, rec, rise, land, faded = (first[e] for e in need)
    eps = 1.0  # ms
    tk = rec["t"] - play["t"]
    want_k = key_s / RATE * 1000 + rec["lost"]
    th = rise["t"] - rec["t"]
    tf = land["t"] - rise["t"]
    want_f = FLIGHT_S * 1000 + land["lost"]
    tm = faded["t"] - land["t"]
    ok = (
        want_k - eps <= tk <= want_k + rec["step"] + eps
        and HOLD_S * 1000 - eps <= th <= (HOLD_S + HOLD_SLACK_S) * 1000
        and want_f - eps <= tf <= want_f + land["step"] + eps
        and FADE_S * 1000 - eps <= tm <= FADE_S * 1000 + 2 * faded["step"] + eps
    )
    said = (
        f"reception {tk / 1000:.3f} s (frame up to {rec['step']:.0f} ms, lost {rec['lost']:.0f} ms);"
        f" hold {th / 1000:.3f} s; flight {tf / 1000:.3f} s (frame up to {land['step']:.0f} ms,"
        f" lost {land['lost']:.0f} ms); fade {tm / 1000:.3f} s"
    )
    return ok, said


@guarded
def check_hook(D: Data, browser, target: str, shots: Path) -> None:
    """The natural run from load, no click (3): broadcast i = 0 playing, the reception at 3.0 s,
    ended, rising after HOLD_S, plan after FLIGHT_S, the plan's measures faded in; one rise per
    load. Timed by the page's own clock."""
    ctx, pg = open_page(browser, target)
    c = pg.evaluate(
        "({T: camera.T, T_KEY: camera.T_KEY, RATE: camera.RATE, HOLD: camera.HOLD_S,"
        " FLIGHT: camera.FLIGHT_S, FADE: camera.FADE_S})"
    )
    R.check(
        "constants: T = n_frames / fps and T_KEY = key.index / fps, from the sidecar",
        abs(c["T"] - D.n / D.fps) < 1e-9 and abs(c["T_KEY"] - D.key / D.fps) < 1e-9,
        json.dumps(c),
    )
    R.check(
        "constants: RATE, HOLD_S, FLIGHT_S, FADE_S as the storyboard's table",
        (c["RATE"], c["HOLD"], c["FLIGHT"], c["FADE"]) == (RATE, HOLD_S, FLIGHT_S, FADE_S),
    )
    pg.wait_for_timeout(1200)
    shot(pg, shots, "hook_1440_broadcast_playing")
    pg.wait_for_function("camera.state().view === 'rising'", timeout=15000)
    pg.wait_for_timeout(700)
    shot(pg, shots, "hook_1440_rising")
    pg.wait_for_function("camera.state().view === 'plan'", timeout=15000)
    pg.wait_for_function("camera.clock && camera.clock().some(c => c.e === 'faded')", timeout=15000)
    pg.wait_for_timeout(200)
    shot(pg, shots, "hook_1440_plan_landed")
    log = pg.evaluate("window.__log")
    first = log[0] if log else {}
    R.check(
        "natural run: opens in broadcast at i = 0",
        first.get("view") == "broadcast" and first.get("i") == 0,
    )
    if not TIMED["on"]:
        R.check(
            "natural run: the reception at 3.0 s, the hold, the rise, the fade", False, SOFTWARE
        )
    else:
        ok, said = run_times(pg.evaluate("camera.clock()"), D.key / D.fps)
        R.check(
            "natural run, on the page's clock: the reception (i = 30) 3.0 s after playing starts,"
            " rising HOLD_S later, plan FLIGHT_S later, the measures faded in FADE_S later",
            ok,
            said,
        )
    shown = pg.evaluate(
        "[...document.querySelectorAll('#tags .tag.measure')].filter(t => !t.hidden).map(t => t.dataset.unit)"
    )
    R.check(
        "natural run: lands on the reception (i = 30, t = 0) with the line and the block tagged",
        pg.evaluate("camera.state().i") == D.key and sorted(shown) == ["block", "line"],
        f"i {pg.evaluate('camera.state().i')}; measure tags {shown}",
    )
    # once per load: back to broadcast, play to the end, no second rise
    pg.evaluate("camera.view('broadcast'); camera.seek(-3); camera.play()")
    pg.wait_for_function("camera.state().phase === 'ended'", timeout=20000)
    pg.wait_for_timeout(int(HOLD_S * 1000) + 400)
    s = pg.evaluate("camera.state()")
    later = [e for e in pg.evaluate("window.__log")[len(log) :] if e["view"] == "rising"]
    R.check(
        "the rise happens once per load: a second broadcast run ends at i = 99 and stays",
        s["view"] == "broadcast" and s["i"] == D.n - 1 and not later,
        f"view {s['view']}, i {s['i']}, rising entries after landing {len(later)}",
    )
    R.check(
        "hook page: no console error and no request outside the page",
        not pg.errors and all(u == target or u.startswith(("data:", "blob:")) for u in pg.requests),
        f"errors {pg.errors[:3]}; requests {[u for u in pg.requests if u != target][:3]}",
    )
    ctx.close()


@guarded
def check_hook_upright(D: Data, browser, target: str, shots: Path) -> None:
    """The natural run on a portrait screen (390 x 844): the clip plays from above, opening in
    plan at i = 0, freezes on the reception (i = 30) and never rises."""
    ctx, pg = open_page(browser, target, width=390, height=844)
    pg.wait_for_function("camera.state().phase === 'ended'", timeout=15000)
    pg.wait_for_timeout(int((HOLD_S + FLIGHT_S) * 1000) + 300)
    shot(pg, shots, "hook_390_plan_reception")
    log = pg.evaluate("window.__log")
    first = log[0] if log else {}
    s = pg.evaluate("camera.state()")
    R.check(
        "390px natural run: opens in plan at i = 0, plays, freezes on the reception (i = 30) and"
        " never rises",
        first.get("view") == "plan"
        and first.get("i") == 0
        and any(e["phase"] == "playing" for e in log)
        and not any(e["view"] != "plan" for e in log)
        and (s["view"], s["i"], s["phase"]) == ("plan", D.key, "ended"),
        f"first {json.dumps(first)}; now {s['view']} {s['i']} {s['phase']}",
    )
    ctx.close()


@guarded
def check_transport(D: Data, browser, target: str) -> None:
    """seek pins the positions to the sidecar interpolated, clamps; play/pause return what the
    API says; rising ignores every call (5.1)."""
    ctx, pg = open_page(browser, target)
    pg.evaluate("camera.pause()")
    worst = 0.0
    for t in (-3.0, -2.55, 0.0, 0.37, 2.5, 6.9):
        pg.evaluate(f"camera.seek({t})")
        s = pg.evaluate("camera.state()")
        want = D.at(t + D.key / D.fps)
        got = np.array(s["positions"]["rivals"], dtype=float)
        worst = max(
            worst,
            float(np.abs(got - want["rivals"]).max()),
            float(np.abs(np.array(s["positions"]["me"]) - want["me"]).max()),
            float(np.abs(np.array(s["positions"]["ball"][:2]) - want["ball"]).max()),
        )
    R.check(
        "seek: positions equal the sidecar interpolated to 1e-6 (six times, between frames too)",
        worst <= 1e-6,
        f"worst {worst:.2e} m",
    )
    lo = pg.evaluate("camera.seek(-10), camera.state()")
    hi = pg.evaluate("camera.seek(99), camera.state()")
    R.check(
        "seek clamps to i = 0 (t = -3.0) and i = 99 (t = +6.9)",
        lo["i"] == 0 and abs(lo["t"] + D.key / D.fps) < 1e-9 and hi["i"] == D.n - 1,
        f"{lo['i']} {lo['t']}, {hi['i']} {hi['t']}",
    )
    pg.evaluate("camera.seek(-3)")
    a = pg.evaluate("[camera.play(), camera.play(), camera.state().phase]")
    b = pg.evaluate("[camera.pause(), camera.state().phase]")
    R.check(
        "play() true then false while playing; pause() true and idle",
        a == [True, False, "playing"] and b == [True, "idle"],
        f"{a} {b}",
    )
    pg.evaluate("camera.view('plan')")
    pg.wait_for_function("camera.state().view === 'rising'", timeout=5000)
    r = pg.evaluate(
        "[camera.play(), camera.pause(), camera.seek(0), camera.view('broadcast'),"
        " camera.variant('V1'), camera.state().view]"
    )
    R.check(
        "rising ignores play, pause, seek, view and variant (all false)",
        r == [False, False, False, False, False, "rising"],
        str(r),
    )
    pg.wait_for_function("camera.state().view === 'plan'", timeout=5000)
    R.check(
        "view('plan') from broadcast rises and lands in plan; view of the same view is true",
        pg.evaluate("camera.view('plan')") is True
        and pg.evaluate("camera.view('sideways')") is False,
    )
    ctx.close()


@guarded
def check_plan_truth(D: Data, browser, target: str) -> None:
    """Top-down for real (8.3): an orthographic camera in plan; the colour centroids of the four
    seen defenders' discs and of the receiver's black ring map back (unproject) to < 0.1 m of
    the sidecar at the reception; in V1 the filled-in markers lose their exact colour."""
    ctx, pg = open_page(browser, target)
    go(pg, "plan", 0.0)
    R.check(
        "plan: the camera is orthographic", pg.evaluate("camera.camera().type") == "orthographic"
    )
    scan = pg.evaluate(SCAN_JS, [[VERMILION, INK], 6])
    key = D.key
    seen = [k for k in range(D.seen.shape[1]) if D.seen[key, k]]
    errs = []
    for comp in [c for c in scan[VERMILION]["comps"] if c["n"] >= 20]:
        xy = np.array(pg.evaluate(f"camera.unproject({comp['x']}, {comp['y']})"), dtype=float)
        d = np.hypot(*(D.rivals[key] - xy).T)
        k = int(np.argmin(d))
        if k in seen:
            errs.append((k, float(d[k])))
    me = [c for c in scan[INK]["comps"] if c["n"] >= 20]
    me_err = min(
        float(
            np.hypot(*(np.array(pg.evaluate(f"camera.unproject({c['x']}, {c['y']})")) - D.me[key]))
        )
        for c in me
    )
    R.check(
        "plan: the four seen discs and the receiver's ring unproject to < 0.1 m of the sidecar (i = 30)",
        sorted(k for k, _ in errs) == seen and all(e < 0.1 for _, e in errs) and me_err < 0.1,
        f"discs {[(k, round(e, 3)) for k, e in errs]} of {seen}; receiver {me_err:.3f} m",
    )
    n_v0 = len([c for c in scan[VERMILION]["comps"] if c["n"] >= 20])
    pg.evaluate("camera.variant('V1')")
    settle(pg)
    n_v1 = len(
        [c for c in pg.evaluate(SCAN_JS, [[VERMILION], 6])[VERMILION]["comps"] if c["n"] >= 20]
    )
    R.check(
        "V1: the filled-in markers fade (vermilion markers of exact colour: every defender in V0,"
        " the seen ones in V1)",
        n_v0 == D.seen.shape[1] and n_v1 == len(seen),
        f"{n_v0} -> {n_v1}",
    )
    ctx.close()


@guarded
def check_frame(D: Data, browser, target: str) -> None:
    """The camera's frame (8.3): in broadcast the clipped corners project inside the canvas in
    the 100 frames; in plan the drawn border sits on the sidecar's edges (< 0.5 px), the seen
    defenders project inside the polygon and the filled-in ones outside."""
    ctx, pg = open_page(browser, target)
    go(pg, "broadcast")
    w, h = pg.evaluate("[camera.camera().width, camera.camera().height]")
    out = []
    for i in range(D.n):
        pg.evaluate(f"camera.seek({(i - D.key) / D.fps})")
        poly = clip_frame(D.corners[i])
        px = proj(pg, [(x, y, 0) for x, y, _ in poly])
        if (
            (px[:, 0] < 0).any()
            or (px[:, 0] > w).any()
            or (px[:, 1] < 0).any()
            or (px[:, 1] > h).any()
        ):
            out.append(i)
    R.check(
        "broadcast: the clipped frame projects inside the canvas in the 100 frames",
        not out,
        f"outside at {out[:5]}",
    )
    go(pg, "plan", 0.0)
    poly = clip_frame(D.corners[D.key])
    px = proj(pg, [(x, y, 0) for x, y, _ in poly])
    samples = []
    for k, (_, _, edge) in enumerate(poly):
        if edge < 0 or edge == 2:  # the apron's border is not drawn; the far edge is dashed
            continue
        a, b = px[k], px[(k + 1) % len(poly)]
        L = float(np.hypot(*(b - a)))
        nx, ny = -(b - a)[1] / L, (b - a)[0] / L
        for u in np.linspace(0.15, 0.85, 12):
            p = a + (b - a) * u
            samples.append([float(p[0]), float(p[1]), nx, ny])
    offs = [o for o in pg.evaluate(BAND_JS, samples) if o is not None]
    med = float(np.median(np.abs(offs))) if offs else math.inf
    R.check(
        "plan: the drawn border lies on the sidecar's edges (median offset < 0.5 px)",
        len(offs) >= 0.8 * len(samples) and med < 0.5,
        f"{len(offs)}/{len(samples)} samples, median {med:.2f} px",
    )
    pts = proj(pg, [(x, y, 0) for x, y in D.rivals[D.key]])
    inside = [in_poly(p, px) for p in pts]
    want = list(D.seen[D.key])
    R.check(
        "plan: the seen defenders project inside the frame and the filled-in ones outside (i = 30)",
        inside == want,
        f"inside {sum(inside)}, seen {sum(want)}",
    )
    ctx.close()


@guarded
def check_measure_only_in_plan(D: Data, browser, target: str) -> None:
    """No measure on the scene outside plan (8.3): the bracket's grey is on the canvas in plan
    and nowhere in broadcast, the line's and the block's tags are shown in plan only; in
    broadcast, V0 to V1 changes no pixel."""
    ctx, pg = open_page(browser, target)
    tick = (D.doc["units"]["block"]["index"] - D.key) / D.fps  # the bracket at full intensity

    def grey() -> int:
        comps = pg.evaluate(SCAN_JS, [[GREY], 4])[GREY]["comps"]
        return sum(c["n"] for c in comps if c["n"] >= 10)

    def measure_tags() -> int:
        return pg.evaluate(
            "[...document.querySelectorAll('#tags .tag.measure')].filter(t => !t.hidden).length"
        )

    go(pg, "plan", tick)
    grey_plan, tags_plan = grey(), measure_tags()
    go(pg, "broadcast", tick)
    grey_b, tags_b = grey(), measure_tags()
    before = pg.evaluate("document.getElementById('pitch').toDataURL()")
    pg.evaluate("camera.variant('V1')")
    settle(pg)
    after = pg.evaluate("document.getElementById('pitch').toDataURL()")
    R.check(
        "the bracket's grey and the measure tags drawn in plan and absent in broadcast;"
        " V1 in broadcast changes no pixel",
        grey_plan > 50 and grey_b == 0 and tags_plan == 2 and tags_b == 0 and before == after,
        f"grey px plan {grey_plan}, broadcast {grey_b}; measure tags {tags_plan}, {tags_b};"
        f" pixels equal {before == after}",
    )
    ctx.close()


@guarded
def check_variant_and_ui(D: Data, browser, target: str) -> None:
    """V0/V1 (4.2, 5.3): the big number of each readout row, aria-pressed, the caption, the
    buttons in each view; V1 fades the filled-in defenders' tags."""
    ctx, pg = open_page(browser, target)
    go(pg, "broadcast", -3.0)
    u = pg.evaluate("__ui()")
    R.check(
        "broadcast: caption and pressed button as 5.3",
        u["bcast"]["pressed"] == "true"
        and u["caption"].startswith(
            f"Match {D.doc['match_id']} · reception at frame {D.doc['key']['frame']} · from the camera's side"
        ),
        u["caption"],
    )
    go(pg, "plan", 0.0)
    rows = {}
    for v in ("V0", "V1"):
        pg.evaluate(f"camera.variant('{v}')")
        settle(pg)
        u = pg.evaluate("__ui()")
        on = pg.evaluate(
            """() => [...document.querySelectorAll('#panel-table td.on .num .q')].map(e => +e.dataset.value)"""
        )
        col = pg.evaluate(
            """() => [...document.querySelectorAll('#metrics td.on')].map(e => e.classList.contains('v1') ? 'V1' : 'V0')"""
        )
        rows[v] = (on, u["v0"]["pressed"], u["v1"]["pressed"], u["caption"], sorted(set(col)))
    want = {
        v: [D.cell("line_height_m", v, "mean"), D.cell("block_length_m", v, "mean")]
        for v in ("V0", "V1")
    }
    R.check(
        "V0/V1: the readout's big numbers are the CSV's line depth and block length of the"
        " variant, aria-pressed follows, the caption names it, the metrics table marks its column",
        rows["V0"][0] == want["V0"]
        and rows["V1"][0] == want["V1"]
        and rows["V0"][1:3] == ("true", "false")
        and rows["V1"][1:3] == ("false", "true")
        and rows["V0"][3].endswith("every unit")
        and rows["V1"][3].endswith("players seen throughout")
        and rows["V0"][4] == ["V0"]
        and rows["V1"][4] == ["V1"],
        f"{rows['V0'][0]} -> {rows['V1'][0]}; columns {rows['V0'][4]} -> {rows['V1'][4]}",
    )
    diffs = pg.evaluate(
        "() => [...document.querySelectorAll('#panel-table td.diff .q')].map(e => [+e.dataset.value, e.textContent])"
    )
    refs = pg.evaluate(
        "() => [...document.querySelectorAll('#panel-table tr.ref th')].map(e => e.textContent)"
    )
    want = [
        D.cell(m, "V1", "mean") - D.cell(m, "V0", "mean")
        for m in ("line_height_m", "block_length_m")
    ]
    R.check(
        "V0/V1: the readout shows V1 - V0 of each metric (the CSV's cells, at its rounding) and what"
        " it measures (line depth from halfway toward own goal; block length deepest to furthest)",
        len(diffs) == 2
        and all(
            abs(v - w) < 1e-6 and shown_matches(s, w) for (v, s), w in zip(diffs, want, strict=True)
        )
        and len(refs) == 2
        and refs[0].startswith("line depth")
        and "halfway toward own goal" in refs[0]
        and refs[1].startswith("block length")
        and "deepest to furthest" in refs[1],
        f"{diffs}; {refs}",
    )
    # V1 fades the filled-in markers' tags too (ink to grey, still legible); V0 leaves them whole
    fades = {}
    for v in ("V0", "V1"):
        pg.evaluate(f"camera.variant('{v}')")
        settle(pg)
        fades[v] = pg.evaluate(
            "() => [...document.querySelectorAll('#tags .tag.rival')].filter(t => !t.hidden)"
            ".map(t => t.classList.contains('faded'))"
        )
    R.check(
        "V0/V1: in V1 the tags of the filled-in defenders fade with their markers",
        fades["V0"]
        and not any(fades["V0"])
        and len(fades["V1"]) == len(fades["V0"])
        and all(fades["V1"]),
        json.dumps(fades),
    )
    tab(pg, "metrics")
    rows = pg.evaluate(
        "() => [...document.querySelectorAll('#metrics tbody tr')].map(r => [r.dataset.metric,"
        " getComputedStyle(r).cursor])"
    )
    hint = pg.evaluate("__vis(document.getElementById('table-hint'))")
    linked = sorted(m for m, c in rows if c == "pointer")
    R.check(
        "the table: the rows that ring players take the pointer cursor, a hint says so",
        hint
        and linked
        == sorted(["line_height_m", "block_length_m", "pressure_index", "nearest_rival_m"]),
        f"pointer on {linked}; hint shown {hint}",
    )
    ctx.close()


def shown_matches(text: str, value: float) -> bool:
    """The first number of a text is the value rounded half up to the text's decimals (a % is the
    value x 100), as the README's gate rounds."""
    m = re.search(r"([+\-−]?)([0-9][0-9,]*(?:\.[0-9]+)?)(\s*%)?", text)
    if not m:
        return False
    digits = m.group(2).replace(",", "")
    shown = Decimal(digits) * (-1 if m.group(1) in ("-", "−") else 1)
    v = Decimal(repr(value * 100 if m.group(3) else value))
    want = v.quantize(Decimal(1).scaleb(-len(digits.partition(".")[2])), rounding=ROUND_HALF_UP)
    return want == shown or (want == 0 and shown == 0)


@guarded
def check_numbers(D: Data, browser, target: str) -> None:
    """Every number shown (8.3): in the panel (each tab opened in turn), the counter, the header,
    the ticks and the tab labels, its data-value is the sidecar's value at its path and its text
    that value at the text's rounding; the match's cells are the CSV's. At i = 0, 30 and 99. The
    strips' "this match" labels are the match's V1 - V0 at the table's decimals."""
    ctx, pg = open_page(browser, target)
    bad, seen, paths = [], 0, set()
    for t in (-3.0, 0.0, 6.9):
        go(pg, "plan", t)
        for name in TABS:
            tab(pg, name)
            items = pg.evaluate("""() => [...document.querySelectorAll('#panel [data-path], #count [data-path], #top [data-path], #ticks [data-path], #tablist [data-path]')]
                .filter(e => __vis(e) && e.classList.contains('q')).map(e => [e.dataset.path, e.dataset.value, e.textContent])""")
            for path, value, text in items:
                seen += 1
                paths.add(path)
                want = D.pick(path)
                ok = str(want) == value or (
                    isinstance(want, int | float) and abs(float(value) - want) < 1e-12
                )
                if path.startswith("frames."):
                    ok = ok and shown_matches(text, (want - D.doc["key"]["frame"]) / D.fps)
                elif path.endswith((".frame",)) and path.startswith("units."):
                    ok = ok and shown_matches(text, (D.doc["key"]["frame"] - want) / D.fps)
                elif "gap_len" in path:
                    ok = ok and shown_matches(text, want / D.fps)
                elif isinstance(want, int | float) and not isinstance(want, bool):
                    ok = ok and shown_matches(text, want)
                m = re.match(r"match\.rows\.(\d+)\.(V[01])\.(mean|n)$", path)
                if m:
                    row = D.doc["match"]["rows"][int(m.group(1))]
                    ok = ok and abs(D.cell(row["metric"], m.group(2), m.group(3)) - want) < 1e-12
                if not ok:
                    bad.append((path, value, text))
    tab(pg, "matches")
    labels = pg.evaluate(
        "() => [...document.querySelectorAll('#strips text[data-path]')].map(e => [e.dataset.path, e.textContent])"
    )
    wrong_labels = []
    for path, text in labels:
        k = int(path.split(".")[2])
        row = D.doc["match"]["rows"][k]
        decimals = (3 if row["metric"] == "pressure_index" else 1) + 1
        m = re.search(r"([+\-−])([0-9.]+)", text)
        if (
            not m
            or len(m.group(2).partition(".")[2]) != decimals
            or not shown_matches(text.split("match ", 1)[1], row["diff"])
        ):
            wrong_labels.append(text)
    R.check(
        "numbers: every number in the panel's tabs, the counter, the header, the ticks and the tab"
        " labels is the sidecar's at its path, shown at its rounding; the match's cells are"
        " reliability.csv's (i = 0, 30, 99)",
        seen > 100 and not bad,
        f"{seen} checked over {len(paths)} paths; wrong {bad[:4]}",
    )
    R.check(
        "numbers: the strips' 'this match' labels read V1 - V0 at the table's decimals (no '0.0'"
        " for a difference that is not nought)",
        len(labels) == len(D.doc["match"]["rows"]) and not wrong_labels,
        f"{[t for _, t in labels]}; wrong {wrong_labels}",
    )
    ticks = pg.evaluate(
        "() => [...document.querySelectorAll('#strips g.strip')].map(g => [g.dataset.metric,"
        " [...g.querySelectorAll('text.small:not([data-path])')].map(t => t.textContent)])"
    )
    odd = []
    for metric, texts in ticks:
        decs = {len(t.replace("−", "-").partition(".")[2]) for t in texts}
        values = [float(t.replace("−", "-")) for t in texts]
        if len(decs) != 1 or len(set(values)) != len(values) or values != sorted(values):
            odd.append((metric, texts))
    R.check(
        "the strips' axes: each axis's ticks share their decimals, distinct and in order",
        ticks and not odd,
        f"{odd[:2]}" if odd else "; ".join(f"{m}: {' '.join(t)}" for m, t in ticks[:3]),
    )
    ctx.close()


@guarded
def check_reduced_motion(D: Data, browser, target: str) -> None:
    """Reduced motion (5.2): loads in plan at i = 30, idle, the measures tagged; a view never
    rises."""
    ctx, pg = open_page(browser, target, reduced=True)
    pg.wait_for_timeout(500)
    s = pg.evaluate("camera.state()")
    shown = pg.evaluate(
        "[...document.querySelectorAll('#tags .tag.measure')].filter(t => !t.hidden).length"
    )
    pg.evaluate("camera.view('broadcast'); camera.view('plan')")
    pg.wait_for_timeout(300)
    log = pg.evaluate("window.__log")
    R.check(
        "reduced motion: plan, i = 30, idle, the measures tagged; the views cut, never rising",
        s["view"] == "plan"
        and s["i"] == D.key
        and s["phase"] == "idle"
        and shown == 2
        and not any(e["view"] == "rising" for e in log)
        and pg.evaluate("camera.state().view") == "plan",
        f"{s['view']} {s['i']} {s['phase']}, measure tags {shown}",
    )
    ctx.close()


# ---------------------------------------------------------------- one screen, per viewport


@guarded
def check_one_screen(D: Data, browser, target: str, size: tuple[int, int]) -> None:
    """No page scroll (the acceptance's first row): the document is no taller and no wider than
    the window at load, through the natural run, and with every tab open in either view."""
    w, h = size
    ctx, pg = open_page(browser, target, width=w, height=h)
    worst = {"sh": 0, "sw": 0}
    where = []

    def measure(label: str) -> None:
        m = pg.evaluate(SCROLL_JS)
        if m["sh"] > m["ih"] + 1 or m["sw"] > m["iw"]:
            where.append(f"{label} {m['sw']}x{m['sh']}")
        worst["sh"] = max(worst["sh"], m["sh"])
        worst["sw"] = max(worst["sw"], m["sw"])

    measure("load")
    pg.wait_for_function("camera.state().phase === 'ended'", timeout=15000)
    pg.wait_for_function("camera.state().view !== 'rising'", timeout=15000)
    pg.wait_for_timeout(int((HOLD_S + FLIGHT_S + FADE_S) * 1000) + 300)
    measure("after the run")
    for view in ("broadcast", "plan"):
        for name in TABS if has_tabs(pg) else ("",):
            if name:
                tab(pg, name)
            go(pg, view, 0.0)
            measure(f"{view} {name}".strip())
    MEASURED.setdefault(size, {})["page_h"] = worst["sh"]
    R.check(
        f"{vp(w, h)}: no page scroll (scrollHeight <= innerHeight + 1, scrollWidth <= innerWidth)"
        " at load, after the run, each tab in either view",
        not where,
        f"page {worst['sw']}x{worst['sh']} in {w}x{h}" + (f"; {where[:3]}" if where else ""),
    )
    ctx.close()


@guarded
def check_tabs(D: Data, browser, target: str, size: tuple[int, int], shots: Path) -> None:
    """The tabs: ARIA roles; each opens by mouse, by tap and by keyboard (arrows, Home, End, and
    the focus follows); its body shows inside the panel and on screen, no wider than the panel,
    and scrolls to its last line; at 1440 x 900 Story, Metrics and the matches fit unscrolled."""
    w, h = size
    ctx, pg = open_page(browser, target, width=w, height=h)
    pg.evaluate("camera.pause()")
    roles = pg.evaluate("""() => { const list = document.querySelector('[role=tablist]');
      const tabs = [...document.querySelectorAll('[role=tab]')];
      return {list: Boolean(list), tabs: tabs.map(t => [t.dataset.tab, t.getAttribute('aria-controls'),
        document.getElementById(t.getAttribute('aria-controls'))?.getAttribute('role'),
        document.getElementById(t.getAttribute('aria-controls'))?.getAttribute('aria-labelledby') === t.id])}; }""")
    R.check(
        f"{vp(w, h)} tabs: a tablist of five tabs, each controlling a tabpanel labelled by it",
        roles["list"]
        and [t[0] for t in roles["tabs"]] == list(TABS)
        and all(t[2] == "tabpanel" and t[3] for t in roles["tabs"]),
        json.dumps(roles["tabs"]),
    )
    state_js = """() => ({sel: [...document.querySelectorAll('[role=tab]')].filter(t => t.getAttribute('aria-selected') === 'true').map(t => t.dataset.tab),
        open: [...document.querySelectorAll('[role=tabpanel]')].filter(p => !p.hidden).map(p => p.id),
        tabindex: [...document.querySelectorAll('[role=tab]')].map(t => t.tabIndex),
        focus: document.activeElement && document.activeElement.dataset ? document.activeElement.dataset.tab || null : null})"""

    def opened(name: str, s: dict) -> bool:
        return (
            s["sel"] == [name]
            and s["open"] == [f"tp-{name}"]
            and sorted(s["tabindex"]) == [-1, -1, -1, -1, 0]
        )

    bad = {"mouse": [], "tap": [], "keys": []}
    for name in (*TABS[1:], TABS[0]):
        pg.click(f"#tab-{name}")
        pg.wait_for_function("camera.state().view !== 'rising'", timeout=10000)
        if not opened(name, pg.evaluate(state_js)):
            bad["mouse"].append(name)
        pg.tap(f"#tab-{name}")
        pg.wait_for_function("camera.state().view !== 'rising'", timeout=10000)
        if not opened(name, pg.evaluate(state_js)):
            bad["tap"].append(name)
    pg.focus("#tab-story")
    pg.keyboard.press("Home")
    seq = [("ArrowRight", n) for n in (*TABS[1:], TABS[0])]
    seq += [("ArrowLeft", TABS[-1]), ("Home", TABS[0]), ("End", TABS[-1]), ("ArrowDown", TABS[0])]
    for key, name in seq:
        pg.keyboard.press(key)
        pg.wait_for_function("camera.state().view !== 'rising'", timeout=10000)
        s = pg.evaluate(state_js)
        if not opened(name, s) or s["focus"] != name:
            bad["keys"].append(f"{key}->{name}")
    R.check(
        f"{vp(w, h)} tabs: each opens by mouse, by tap and by the arrow keys, Home and End (the"
        " focus follows; one tab selected, one panel shown, roving tabindex)",
        not any(bad.values()),
        json.dumps(bad),
    )
    inner, cut, fit = {}, [], []
    for name in TABS:
        tab(pg, name)
        if name == "matches":
            pg.wait_for_timeout(100)
        m = pg.evaluate(f"""() => {{ const p = document.getElementById('tp-{name}'), r = p.getBoundingClientRect();
          const kids = [...p.querySelectorAll('*')].filter(e => __vis(e) && !(e.closest('svg') && e.tagName !== 'svg'));
          const wide = kids.map(e => [e.id || e.tagName, e.getBoundingClientRect()])
            .filter(([, b]) => b.width > 0 && (b.left < r.left - 0.5 || b.right > r.left + p.clientWidth + 0.5)).map(([n, b]) => [n, Math.round(b.left), Math.round(b.right)]);
          p.scrollTop = p.scrollHeight;
          const last = p.lastElementChild.getBoundingClientRect(), r2 = p.getBoundingClientRect();
          const out = {{sh: p.scrollHeight, ch: p.clientHeight, sw: p.scrollWidth, cw: p.clientWidth, top: r.top, bottom: r.bottom,
                       overflow: getComputedStyle(p).overflowY, lastIn: last.bottom <= r2.bottom + 1 && last.bottom >= r2.top, wide: wide.slice(0, 3), ih: innerHeight, iw: innerWidth, right: r.right}};
          p.scrollTop = 0; return out; }}""")
        inner[name] = max(0, m["sh"] - m["ch"])
        if (
            m["sw"] > m["cw"] + 1
            or m["wide"]
            or not m["lastIn"]
            or m["bottom"] > m["ih"] + 0.5
            or m["right"] > m["iw"] + 0.5
            or (inner[name] > 0 and m["overflow"] not in ("auto", "scroll"))
        ):
            cut.append((name, m))
        if size == (1440, 900) and name in FIT_TABS and inner[name] > 0:
            fit.append(name)
        if size in ((1440, 900), (390, 844)):
            shot(pg, shots, f"{vp(w, h)}_tab_{name}")
    MEASURED.setdefault(size, {})["inner"] = inner
    R.check(
        f"{vp(w, h)} tabs: each body shows inside the panel and on screen, no wider than the panel,"
        " and scrolls (not clips) to its last line",
        not cut,
        "; ".join(f"{n}: {json.dumps(m)[:200]}" for n, m in cut[:2])
        or ", ".join(f"{n} {px}" for n, px in inner.items()) + " px to scroll",
    )
    if size == (1440, 900):
        R.check(
            "1440x900 tabs: Story, Metrics and the matches fit their body with no inner scroll",
            not fit,
            ", ".join(f"{n} {inner[n]} px over" for n in fit) or "all three fit",
        )
    ctx.close()


@guarded
def check_text(D: Data, browser, target: str, size: tuple[int, int], shots: Path) -> None:
    """Text (the acceptance's third and fourth rows): prose at 16 px, every caption, tick and tag
    at 12 px, every piece of text at 4.5:1 against what is under it (no text straight on the
    canvas), every visible button, tab, link and the scrubber 44 px each way; and no two pieces of
    writing on the stage and in the control bar overlap, at load, at the reception in either view
    and variant, and with each tab open; the strips' labels overlap nowhere. The header holds the
    title on one line and the thesis that says the change is a different sample, not an error."""
    w, h = size
    ctx, pg = open_page(browser, target, width=w, height=h)
    small, faint, canvas_text, hits, cut = [], [], [], [], []
    seen_targets: dict[str, tuple[float, float]] = {}

    def look(label: str) -> None:
        for t in pg.evaluate(TEXT_JS):
            if t["size"] < LABEL_MIN_PX or (
                t["tag"] in ("p", "li") and t["len"] >= 60 and t["size"] < BODY_MIN_PX
            ):
                small.append((label, t["id"], t["text"], t["size"]))
            if not t["disabled"] and t["ratio"] < CONTRAST_MIN:
                faint.append((label, t["id"], t["text"], t["ratio"]))
            if t["overCanvas"]:
                canvas_text.append((label, t["id"], t["text"]))
            if t["pane"] is None and (
                t["x"] < -0.5
                or t["y"] < -0.5
                or t["x"] + t["w"] > w + 0.5
                or t["y"] + t["h"] > h + 0.5
            ):
                cut.append((label, t["id"], t["text"]))
        boxes = pg.evaluate(BOXES_JS)
        for n, a in enumerate(boxes):
            for b in boxes[n + 1 :]:
                if meets(a, b):
                    hits.append((label, a["name"], b["name"]))
        for e in pg.evaluate("""() => [...document.querySelectorAll('a, button, input, [role=tab]')].filter(__vis)
            .map(e => { const q = e.getBoundingClientRect(); return [e.id || e.textContent.trim().slice(0, 20), q.width, q.height]; })"""):
            seen_targets[e[0]] = (
                min(e[1], seen_targets.get(e[0], (e[1], e[2]))[0]),
                min(e[2], seen_targets.get(e[0], (e[1], e[2]))[1]),
            )

    look("load")
    shot(pg, shots, f"{vp(w, h)}_load")
    pg.wait_for_function("camera.state().phase === 'ended'", timeout=15000)
    pg.wait_for_function("camera.state().view !== 'rising'", timeout=15000)
    pg.wait_for_timeout(int((HOLD_S + FLIGHT_S + FADE_S) * 1000) + 300)
    look("run ended")
    shot(pg, shots, f"{vp(w, h)}_reception_freeze")
    for view in ("broadcast", "plan"):
        for variant in ("V0", "V1"):
            go(pg, view, 0.0)
            pg.evaluate(f"camera.variant('{variant}')")
            settle(pg)
            look(f"{view} {variant}")
            if variant == "V1" and view == "plan":
                shot(pg, shots, f"{vp(w, h)}_topdown_V1")
            if variant == "V0" and view == "broadcast":
                shot(pg, shots, f"{vp(w, h)}_broadcast_reception")
    pg.evaluate("camera.variant('V0')")
    if has_tabs(pg):
        for name in TABS:
            tab(pg, name)
            look(f"tab {name}")
        tab(pg, "story")
    texts = []
    if has_tabs(pg):
        tab(pg, "matches")
        pg.wait_for_timeout(100)
    texts = pg.evaluate(
        "() => [...document.querySelectorAll('#strips text')].map(e => { const b = e.getBoundingClientRect();"
        " return {x: b.left, y: b.top, w: b.width, h: b.height, t: e.textContent}; })"
    )
    strip_hits = [
        (a["t"], b["t"]) for n, a in enumerate(texts) for b in texts[n + 1 :] if meets(a, b)
    ]
    small_t = sorted(
        {k for k, (tw, th) in seen_targets.items() if tw < TARGET_PX or th < TARGET_PX}
    )
    R.check(
        f"{vp(w, h)}: prose (p, li of 60+ characters) >= {BODY_MIN_PX} px; every other text,"
        f" tick and tag >= {LABEL_MIN_PX} px",
        not small,
        json.dumps(sorted(set(small))[:4]),
    )
    R.check(
        f"{vp(w, h)}: every piece of text at >= {CONTRAST_MIN}:1 against what is under it (the"
        " tags too), none straight on the canvas",
        not faint and not canvas_text,
        f"faint {sorted(set(faint))[:4]}; on the canvas {sorted(set(canvas_text))[:3]}",
    )
    R.check(
        f"{vp(w, h)}: every visible button, tab, link and the scrubber at least {TARGET_PX} px each way",
        seen_targets and not small_t,
        f"{len(seen_targets)} targets; under: {small_t[:4]}",
    )
    R.check(
        f"{vp(w, h)}: no two of the tags, the counter, the key, the buttons, the ticks and the tabs"
        " overlap (load, run, either view and variant, each tab); nothing outside the panel is cut"
        " by the window",
        not hits and not cut,
        f"overlaps {sorted(set(hits))[:3]}; cut {sorted(set(cut))[:3]}",
    )
    R.check(
        f"{vp(w, h)}: the strips' labels overlap nowhere (names, 'this match', the axes' numbers)",
        len(texts) > 7 and not strip_hits,
        f"{len(texts)} labels; overlaps {strip_hits[:3]}",
    )
    head = pg.evaluate("""() => { const h1 = document.querySelector('h1'), th = document.getElementById('thesis');
      const b = th.getBoundingClientRect();
      return {h: h1.getBoundingClientRect().height, lh: parseFloat(getComputedStyle(h1).lineHeight), sw: h1.scrollWidth, cw: h1.clientWidth,
              thesis: th.textContent, tb: b.bottom, tt: b.top, vis: __vis(th)}; }""")
    R.check(
        f"{vp(w, h)}: the title on one line; the thesis on screen and saying '{THESIS_SAYS}'",
        head["h"] <= 1.5 * head["lh"]
        and head["sw"] <= head["cw"]
        and head["vis"]
        and head["tt"] >= 0
        and head["tb"] <= h
        and THESIS_SAYS in head["thesis"],
        f"{head['thesis'][:90]}",
    )
    ctx.close()


@guarded
def check_framing(D: Data, browser, target: str, size: tuple[int, int], shots: Path) -> None:
    """The broadcast fit (2.4) and the plan's scale: the receiver, the ball and the clipped frame
    inside the canvas in the 100 frames; a defender outside it, seen or filled in, has his tag on
    that edge with an arrow and his seconds (or 'seen'); at most 10 % of the height between the
    lowest and the counter and key; the median drawn height of the defenders in the canvas at
    least LEGIBLE_PX; at most EMPTY_MAX of the stage bare sky; in plan a defender's disc at least
    DISC_MIN_PX across, and the frame's far edge inside the stage (the window closes)."""
    w0, h0 = size
    ctx, pg = open_page(browser, target, width=w0, height=h0)
    go(pg, "broadcast")
    w, h = pg.evaluate("[camera.camera().width, camera.camera().height]")
    foot = pg.evaluate(
        "document.getElementById('foot').getBoundingClientRect().top"
        " - document.getElementById('stage').getBoundingClientRect().top"
    )
    bad, edge_bad, low, heights, left_out = [], [], 0.0, [], set()
    arrows = {"left": "←", "right": "→", "top": "↑", "bottom": "↓"}
    for i in range(D.n):
        pg.evaluate(f"camera.seek({(i - D.key) / D.fps})")
        k = len(D.rivals[i])
        feet = [(x, y, 0) for x, y in D.rivals[i]]
        heads = [(x, y, BODY_H) for x, y in D.rivals[i]]
        rest = [(*D.me[i], 0), (*D.me[i], BODY_H), (*D.ball[i], 0)]
        rest += [(x, y, 0) for x, y, _ in clip_frame(D.corners[i])]
        px = proj(pg, feet + heads + rest)

        def inside(p) -> bool:
            return -0.5 <= p[0] <= w + 0.5 and -0.5 <= p[1] <= h + 0.5

        shown = [inside(px[j]) and inside(px[k + j]) for j in range(k)]
        if not all(inside(p) for p in px[2 * k :]):
            bad.append(i)
        tags = {t["k"]: t for t in pg.evaluate(TAGS_JS) if t["kind"] == "rival"}
        for j in range(k):
            a = px[k + j]
            side = (
                "left"
                if a[0] < 0
                else "right"
                if a[0] > w
                else "top"
                if a[1] < 0
                else "bottom"
                if a[1] > h
                else ""
            )
            if not side:
                continue
            left_out.add(j)
            t = tags.get(j)
            says = "seen" if D.seen[i, j] else f"{D.gap[i, j] / D.fps:.1f} s"
            at_edge = t is not None and (
                (side == "left" and t["x"] <= 4)
                or (side == "right" and t["x"] + t["w"] >= w - 4)
                or (side == "top" and t["y"] <= 4)
                or (side == "bottom" and t["y"] + t["h"] >= min(h, foot) - 8)
            )
            if (
                t is None
                or t["edge"] != side
                or says not in t["text"]
                or arrows[side] not in t["text"]
                or not at_edge
            ):
                edge_bad.append(i)
        pts = [px[j] for j in range(k) if shown[j]] + [px[k + j] for j in range(k) if shown[j]]
        low = max(low, max(float(p[1]) for p in [*pts, *px[2 * k :]]))
        heights += [float(px[j][1] - px[k + j][1]) for j in range(k) if shown[j]]
    med = float(np.median(heights))
    R.check(
        f"{vp(w0, h0)} broadcast: the receiver, the ball and the frame inside the canvas in the 100 frames",
        not bad,
        f"outside at {bad[:5]}",
    )
    R.check(
        f"{vp(w0, h0)} broadcast: a defender outside the canvas (any side, seen or filled in) has his"
        " tag on that edge with an arrow and his seconds or 'seen' (100 frames)",
        not edge_bad,
        f"left out: {sorted(D.doc['entities']['rivals']['ids'][j] for j in left_out)}; wrong at {sorted(set(edge_bad))[:5]}",
    )
    R.check(
        f"{vp(w0, h0)} broadcast: at most 10% of the height between the lowest point and the"
        " counter under it",
        (min(h, foot) - low) / h <= 0.10,
        f"{(min(h, foot) - low) / h:.3f}",
    )
    R.check(
        f"{vp(w0, h0)} broadcast: the median drawn height of the defenders in the canvas >= {LEGIBLE_PX[size]} px",
        med >= LEGIBLE_PX[size],
        f"{med:.1f} px",
    )
    pg.evaluate("camera.seek(0)")
    settle(pg)
    sky = sky_share(pg)
    R.check(
        f"{vp(w0, h0)} broadcast: at most {EMPTY_MAX[size]:.0%} of the stage is bare sky",
        sky <= EMPTY_MAX[size],
        f"{sky:.3f}",
    )
    go(pg, "plan", 0.0)
    one = proj(pg, [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0)])
    disc = 2 * DISC_R * float(np.hypot(*(one[1] - one[0])))
    region_y1 = foot - 6
    far = [
        proj(pg, [(x, y, 0)])[0]
        for i in range(D.n)
        for x, y, edge in clip_frame(D.corners[i])
        if edge == 2
    ]
    far_in = all(-0.5 <= p[1] <= region_y1 + 0.5 for p in far)
    R.check(
        f"{vp(w0, h0)} plan: a defender's disc >= {DISC_MIN_PX[size]} px across; the frame's far"
        " edge inside the stage in the 100 frames (the window closes)",
        disc >= DISC_MIN_PX[size] and far_in,
        f"disc {disc:.1f} px; far edge y {min(p[1] for p in far):.0f}..{max(p[1] for p in far):.0f} px in 0..{region_y1:.0f}",
    )
    MEASURED.setdefault(size, {}).update({"players_px": med, "sky": sky, "disc_px": disc})
    ctx.close()


def sky_share(pg) -> float:
    """The share of the canvas that is the bare sky's colour."""
    return pg.evaluate(
        """(hex) => { const c = document.getElementById('pitch'), t = document.createElement('canvas');
      t.width = c.width; t.height = c.height; const x = t.getContext('2d'); x.drawImage(c, 0, 0);
      const d = x.getImageData(0, 0, c.width, c.height).data;
      const r = parseInt(hex.slice(1, 3), 16), g = parseInt(hex.slice(3, 5), 16), b = parseInt(hex.slice(5, 7), 16);
      let n = 0, k = 0;
      for (let y = 0; y < c.height; y++) for (let i = 0; i < c.width; i++) {
        const o = 4 * (y * c.width + i); n++;
        if (Math.abs(d[o] - r) <= 2 && Math.abs(d[o + 1] - g) <= 2 && Math.abs(d[o + 2] - b) <= 2) k++; }
      return k / n; }""",
        SKY,
    )


# Each visible tag with its box in the stage, its edge (a defender outside the canvas) and the
# end of its leader (null when the leader is hidden): tags and leaders are built in one order.
TAGS_JS = """() => { const s = document.getElementById('stage').getBoundingClientRect();
  const leads = [...document.querySelectorAll('#tags .lead')];
  return [...document.querySelectorAll('#tags .tag')].map((t, n) => [t, leads[n]]).filter(([t]) => !t.hidden)
    .map(([t, l]) => { const b = t.getBoundingClientRect();
      return {kind: t.dataset.kind, k: t.dataset.k === undefined ? null : +t.dataset.k, text: t.textContent,
              edge: t.dataset.edge || null, x: b.left - s.left, y: b.top - s.top, w: b.width, h: b.height,
              anchor: l.style.display === 'none' ? null : [+l.getAttribute('x2'), +l.getAttribute('y2')]}; }); }"""


@guarded
def check_tags(D: Data, browser, target: str, size: tuple[int, int]) -> None:
    """The tags (2.3) in the 100 frames, both views: each anchor nearer its player than any
    other (a tag on the canvas's edge: its player outside on that side), no two boxes overlap,
    none covers the ball, none meets the counter or the key, and no player stands under the
    counter or the key; a tag left out for lack of room is counted (none above 360 px wide)."""
    w0, h0 = size
    ctx, pg = open_page(browser, target, width=w0, height=h0)
    crowded_max = 0
    for view in ("broadcast", "plan"):
        go(pg, view)
        w, h = pg.evaluate("[camera.camera().width, camera.camera().height]")
        z = BODY_H if view == "broadcast" else 0.0
        boxes = pg.evaluate("""() => { const s = document.getElementById('stage').getBoundingClientRect();
          return ['count', 'key'].map(id => document.getElementById(id)).filter(e => __vis(e) && document.getElementById('stage').contains(e))
            .map(e => { const b = e.getBoundingClientRect(); return {x: b.left - s.left, y: b.top - s.top, w: b.width, h: b.height}; }); }""")
        wrong, overlap, ball, foot, under = [], [], [], [], []
        for i in range(D.n):
            pg.evaluate(f"camera.seek({(i - D.key) / D.fps})")
            tags = pg.evaluate(TAGS_JS)
            crowded_max = max(
                crowded_max,
                pg.evaluate("document.querySelectorAll('#tags .tag[data-crowded]').length"),
            )
            people = proj(pg, [(x, y, z) for x, y in D.rivals[i]] + [(*D.me[i], z)])
            bpx = proj(pg, [(*D.ball[i], 0)])[0]
            others = [(x, y, z) for x, y in D.mates[i] if not np.isnan(x)] + [(*D.ball[i], 0)]
            for px, py in [*people, *proj(pg, others)]:
                if any(
                    b["x"] - 4 <= px <= b["x"] + b["w"] + 4
                    and b["y"] - 4 <= py <= b["y"] + b["h"] + 4
                    for b in boxes
                ):
                    under.append(i)
            for t in tags:
                if t["kind"] in ("rival", "me"):
                    own = t["k"] if t["kind"] == "rival" else len(people) - 1
                    if t["edge"]:
                        x, y = people[own]
                        off = {"left": x < 0, "right": x > w, "top": y < 0, "bottom": y > h}
                        if not off.get(t["edge"], False):
                            wrong.append(i)
                        continue
                    if t["anchor"] is None:
                        wrong.append(i)
                        continue
                    d = np.hypot(*(people - np.array(t["anchor"])).T)
                    if int(np.argmin(d)) != own:
                        wrong.append(i)
                if (
                    t["x"] - 1 < bpx[0] < t["x"] + t["w"] + 1
                    and t["y"] - 1 < bpx[1] < t["y"] + t["h"] + 1
                ):
                    ball.append(i)
                if any(meets(t, b) for b in boxes):
                    foot.append(i)
            for m, s in enumerate(tags):
                for t in tags[m + 1 :]:
                    if meets(s, t):
                        overlap.append(i)
        R.check(
            f"{vp(w0, h0)} {view}: tags in the 100 frames: each anchor nearest its player, no overlap,"
            " none over the ball or on the counter and key; no player under the counter or key",
            not wrong and not overlap and not ball and not foot and not under,
            f"wrong anchor {sorted(set(wrong))[:5]}, overlaps {sorted(set(overlap))[:5]}, ball"
            f" {sorted(set(ball))[:5]}, on the foot {sorted(set(foot))[:5]}, players under it {sorted(set(under))[:5]}",
        )
    MEASURED.setdefault(size, {})["crowded"] = crowded_max
    R.check(
        f"{vp(w0, h0)}: tags left out for lack of room, at most {0 if w0 > 360 else 2} in a frame",
        crowded_max <= (0 if w0 > 360 else 2),
        f"{crowded_max}",
    )
    ctx.close()


@guarded
def check_controls(D: Data, browser, target: str, size: tuple[int, int]) -> None:
    """The control bar: Play, the scrubber, Broadcast | Top-down and V0 | V1 on screen; the ticks
    read on one line; the scrubber's thumb takes a press 20 px either side of its centre; the key
    and the readout on the first screen (on the stage and over the tabs, or opening Story)."""
    w, h = size
    ctx, pg = open_page(browser, target, width=w, height=h)
    m = pg.evaluate("""() => { const r = id => document.getElementById(id).getBoundingClientRect().toJSON();
      const l = document.querySelector('#ticks .tick-label');
      return {ids: ['play', 'scrub', 'view-broadcast', 'view-plan', 'variant-v0', 'variant-v1'].map(id => [id, r(id), __vis(document.getElementById(id))]),
              ticks: {h: l.getBoundingClientRect().height, lh: parseFloat(getComputedStyle(l).lineHeight), n: document.querySelectorAll('#ticks .tick-label').length},
              key: [r('key'), __vis(document.getElementById('key'))], readout: [r('panel-table'), __vis(document.getElementById('panel-table'))]}; }""")
    off = [
        i
        for i, b, v in m["ids"]
        if not v or b["bottom"] > h + 0.5 or b["right"] > w + 0.5 or b["left"] < -0.5
    ]
    R.check(
        f"{vp(w, h)}: Play, the scrubber, Broadcast | Top-down and V0 | V1 on screen; the ticks on one line",
        not off and m["ticks"]["n"] == 1 and m["ticks"]["h"] <= 1.5 * m["ticks"]["lh"],
        f"off screen {off}; ticks {json.dumps(m['ticks'])}",
    )
    # compact (portrait or short): the key opens the Story tab and the readout follows it there
    k, r = m["key"], m["readout"]
    compact = pg.evaluate("matchMedia('(orientation: portrait), (max-height: 560px)').matches")
    R.check(
        f"{vp(w, h)}: the key (vermilion defenders, blue receiving team) on the first screen, and the"
        " V0/V1 readout too where the panel heads with it",
        k[1]
        and r[1]
        and 0 <= k[0]["top"] <= h - 24
        and (compact or 0 <= r[0]["top"] and r[0]["bottom"] <= h),
        f"key top {k[0]['top']:.0f}, readout top {r[0]['top']:.0f} of {h}"
        + (" (compact: the readout in Story)" if compact else ""),
    )
    go(pg, "broadcast")
    pg.evaluate("camera.pause(); camera.seek(1.5)")
    settle(pg)
    want = pg.evaluate("document.getElementById('scrub').value")
    b = pg.evaluate("document.getElementById('scrub').getBoundingClientRect().toJSON()")
    f = int(want) / (D.n - 1)
    cx = b["left"] + 22 + f * (b["width"] - 44)
    seen = []
    for dx in (0, -20, 20):
        pg.evaluate("camera.seek(1.5)")
        pg.mouse.click(cx + dx, b["top"] + b["height"] / 2)
        settle(pg)
        seen.append(pg.evaluate("document.getElementById('scrub').value"))
    R.check(
        f"{vp(w, h)}: the scrubber's thumb takes a press 20 px either side of its centre",
        all(v == want for v in seen),
        f"{want}: {seen}",
    )
    ctx.close()


@guarded
def check_camera_tab(D: Data, browser, target: str, shots: Path) -> None:
    """The Camera tab reuses the scene: from broadcast it rises to the plan, framed to hold where
    the frame's side edges meet (the clip's apexes and the virtual camera's tag on screen);
    leaving it frames the reception again."""
    ctx, pg = open_page(browser, target)
    go(pg, "broadcast", 0.0)
    tab(pg, "camera")
    s = pg.evaluate("camera.state()")
    w, h = pg.evaluate("[camera.camera().width, camera.camera().height]")
    apex = proj(pg, [(x, y, 0) for x, y in D.doc["camera"]["apex"]])
    inside = bool(
        ((apex[:, 0] >= 0) & (apex[:, 0] <= w) & (apex[:, 1] >= 0) & (apex[:, 1] <= h)).all()
    )
    tag = pg.evaluate(
        "[...document.querySelectorAll('#tags .tag.measure')].filter(t => !t.hidden && t.dataset.unit === 'camera').map(t => t.textContent)"
    )
    pg.wait_for_timeout(int(FADE_S * 1000) + 200)
    shot(pg, shots, "1440x900_camera_tab_scene")
    height = f"{D.doc['camera']['drawn_height_m']:.0f} m"
    R.check(
        "Camera tab: from broadcast the scene rises to the plan with every apex of the clip on the"
        " stage and the virtual camera tagged with its drawn height",
        s["view"] == "plan"
        and s["tab"] == "camera"
        and inside
        and len(tag) == 1
        and height in tag[0],
        f"view {s['view']}; apexes inside {inside}; tag {tag}",
    )
    tab(pg, "story")
    apex2 = proj(pg, [(x, y, 0) for x, y in D.doc["camera"]["apex"]])
    gone = pg.evaluate(
        "[...document.querySelectorAll('#tags .tag.measure')].filter(t => !t.hidden && t.dataset.unit === 'camera').length"
    )
    R.check(
        "Camera tab: leaving it frames the reception again (the apexes off the stage, no camera tag)",
        gone == 0 and bool((apex2[:, 1] > h).all()),
        f"camera tags {gone}; apex y from {apex2[:, 1].min():.0f} px in {h}",
    )
    ctx.close()


# ---------------------------------------------------------------- main


def summary() -> None:
    """The per-viewport measures, as one table (page height, players, sky, disc, inner scroll)."""
    print("\nviewport    page_h  players_px  sky    disc_px  crowded  inner scroll per tab (px)")
    for size in VIEWPORTS:
        m = MEASURED.get(size, {})
        inner = m.get("inner") or {}
        print(
            f"{vp(*size):<11} {m.get('page_h', '-')!s:>6}  {m.get('players_px', float('nan')):>10.1f}"
            f"  {m.get('sky', float('nan')):>5.3f}  {m.get('disc_px', float('nan')):>7.1f}"
            f"  {m.get('crowded', '-')!s:>7}  " + " ".join(f"{k} {v}" for k, v in inner.items())
        )


def main(argv: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("target", nargs="?", default=str(DEFAULT_PAGE))
    parser.add_argument("--shots", type=Path, default=ROOT / "build" / "camera")
    parser.add_argument("--only", choices=["one-screen"], default=None)
    args = parser.parse_args(argv[1:])
    target = (
        args.target
        if re.match(r"^https?://", args.target)
        else Path(args.target).resolve().as_uri()
    )
    D = Data()
    print(f"target: {target}", flush=True)
    t0 = time.time()
    with sync_playwright() as p:
        browser = p.chromium.launch(args=CHROMIUM_ARGS)
        ctx, pg = open_page(browser, target)
        live = pg.evaluate("""() => { const c = document.createElement('canvas');
                              return !!(c.getContext('webgl2') || c.getContext('webgl')); }""")
        live = live and pg.evaluate("camera.camera() !== null && camera.camera().width > 0")
        if not live:
            R.check(
                "WebGL is live in the browser being driven",
                False,
                "no webgl: nothing else can be trusted",
            )
            browser.close()
            return 1
        renderer = pg.evaluate("""() => { const gl = document.createElement('canvas').getContext('webgl2');
                                  const ext = gl && gl.getExtension('WEBGL_debug_renderer_info');
                                  return ext ? gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) : 'unknown'; }""")
        TIMED["on"] = "swiftshader" not in renderer.lower()
        R.check(
            "WebGL is live in the browser being driven",
            True,
            renderer + ("" if TIMED["on"] else f"; {SOFTWARE}"),
        )
        ctx.close()
        browser.close()
        if args.only == "one-screen":
            browser = p.chromium.launch(args=CHROMIUM_ARGS)
            for size in VIEWPORTS:
                check_one_screen(D, browser, target, size)
            browser.close()
        else:
            check_startup(D, p, target)
            browser = p.chromium.launch(args=CHROMIUM_ARGS)
            check_hook(D, browser, target, args.shots)
            check_hook_upright(D, browser, target, args.shots)
            check_transport(D, browser, target)
            check_plan_truth(D, browser, target)
            check_frame(D, browser, target)
            check_measure_only_in_plan(D, browser, target)
            check_variant_and_ui(D, browser, target)
            check_numbers(D, browser, target)
            check_reduced_motion(D, browser, target)
            check_camera_tab(D, browser, target, args.shots)
            for size in VIEWPORTS:
                check_one_screen(D, browser, target, size)
                check_tabs(D, browser, target, size, args.shots)
                check_text(D, browser, target, size, args.shots)
                check_controls(D, browser, target, size)
                check_framing(D, browser, target, size, args.shots)
                check_tags(D, browser, target, size)
            browser.close()
    n_fail = sum(1 for r in R.rows if not r[0])
    summary()
    print(f"\n{len(R.rows) - n_fail} passed, {n_fail} failed, {time.time() - t0:.0f} s")
    print("not covered: the hidden-tab clock (headless Chromium cannot hide a tab)")
    return 0 if R.ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
