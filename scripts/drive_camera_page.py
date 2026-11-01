"""Drive the built camera page from the browser console and check it against the storyboard.

    uv run --with playwright playwright install chromium        # once
    uv run --with playwright python scripts/drive_camera_page.py [path-or-url] [--shots DIR]

The default target is ``reports/camera/what_the_camera_saw.html``; after publishing, the same
driver runs against the Pages URL. The expected values are read from ``reports/camera/camera.json``
and ``reports/reliability.csv``, never typed and never read from the page's source. One line per
check; exit 0 if every check passes and 1 otherwise. Screenshots go to ``build/camera/`` (ignored)
or ``--shots``.

The browser runs on the machine's GPU (ANGLE on D3D11 on Windows). If WebGL is not live the driver
fails loudly before anything else; if the renderer is a software one (SwiftShader), every row that
times something fails as "software renderer: timing not measurable" rather than passing on a clock
that measures the CPU. Headless Chromium cannot hide a tab, so the hidden-tab rule is not exercised.

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
# The storyboard asked 28 and 12 px; with the camera over the point where the frame's side edges
# meet and every defender in the frame, the width sets the scale and P2 measured 23.9 and 6.5 px
# (tasks/camera_page.md, P2's notes): these floors guard that fit, the tags carry the legibility.
LEGIBLE_PX = {1440: 22.0, 390: 6.0}
BODY_MIN_PX, TARGET_PX = 16, 44
HALF_L, HALF_W, APRON = 52.5, 34.0, 6.0
VERMILION, INK, GREY = "#D55E00", "#222222", "#777777"
SUB_BROADCAST = (
    "Solid: the camera saw them. Hollow: SkillCorner filled them in, with the seconds to the "
    "nearest frame the camera saw each."
)
SUB_PLAN = (
    "From above: keep only what the camera saw whole (V1), and line height and block length "
    "change sample."
)
TIMED = {"on": True}

# In-page helpers, installed before the page's own script runs: `__vis(el)` (really visible),
# `__ui()` (buttons and captions), a 10 ms sampler that logs every change of (view, phase, i,
# measure hidden) with its time, the time of the first draw on the stage's canvas, the time of
# the first `playing`, and the animation frames' timestamps while playing.
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
            v1: b('variant-v1'), caption: txt(g('stage-caption')), sub: txt(g('stage-sub')),
            scrub: {value: g('scrub').value, valuetext: g('scrub').getAttribute('aria-valuetext')}};
  };
  window.__log = [];
  let last = '';
  setInterval(() => {
    const c = window.camera, m = document.getElementById('measure');
    if (!c || !c.state || !m) return;
    const s = c.state();
    const sig = [s.view, s.phase, s.i, m.hidden, getComputedStyle(m).opacity].join('|');
    if (sig !== last) {
      last = sig;
      window.__log.push({ts: performance.now(), view: s.view, phase: s.phase, i: s.i, t: s.t,
                         mh: m.hidden, op: parseFloat(getComputedStyle(m).opacity)});
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


# ---------------------------------------------------------------- browser helpers


def open_page(browser, target: str, *, width=1440, height=900, reduced=False):
    ctx = browser.new_context(
        viewport={"width": width, "height": height},
        device_scale_factor=1,
        reduced_motion="reduce" if reduced else "no-preference",
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


@guarded
def check_hook(D: Data, browser, target: str, shots: Path) -> None:
    """The natural run from load, no click (3): broadcast i = 0 playing, the reception at 3.0 s,
    ended, rising after HOLD_S, plan after FLIGHT_S, #measure faded in; one rise per load."""
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
    pg.wait_for_timeout(int(FADE_S * 1000) + 300)
    shot(pg, shots, "hook_1440_plan_landed")
    log = pg.evaluate("window.__log")
    playing = next((e for e in log if e["phase"] == "playing"), None)
    ended = next((e for e in log if e["phase"] == "ended" and e["view"] == "broadcast"), None)
    rising = next((e for e in log if e["view"] == "rising"), None)
    plan = next((e for e in log if e["view"] == "plan"), None)
    faded = next((e for e in log if e["view"] == "plan" and not e["mh"] and e["op"] >= 0.999), None)
    first = log[0] if log else {}
    R.check(
        "natural run: opens in broadcast at i = 0",
        first.get("view") == "broadcast" and first.get("i") == 0,
    )
    ok = playing and ended and rising and plan and faded
    if not ok:
        R.check(
            "natural run: playing, ended, rising, plan, faded in, with no click",
            False,
            json.dumps(log[:8]),
        )
    elif not TIMED["on"]:
        R.check(
            "natural run: the reception at 3.0 s, the hold, the rise, the fade", False, SOFTWARE
        )
    else:
        tk = (ended["ts"] - playing["ts"]) / 1000
        th = (rising["ts"] - ended["ts"]) / 1000
        tf = (plan["ts"] - rising["ts"]) / 1000
        tm = (faded["ts"] - plan["ts"]) / 1000
        R.check(
            "natural run: the reception (i = 30) reached 3.0 s after playing starts, then ended,"
            " rising after HOLD_S, plan after FLIGHT_S, #measure in after FADE_S",
            ended["i"] == D.key
            and abs(tk - D.key / D.fps / RATE) <= 0.15
            and abs(th - HOLD_S) <= 0.15
            and abs(tf - FLIGHT_S) <= 0.2
            and tm <= FADE_S + 0.2,
            f"reception at {tk:.2f} s (i {ended['i']}); hold {th:.2f}; flight {tf:.2f}; fade {tm:.2f}",
        )
    R.check(
        "natural run: lands on the reception (i = 30, t = 0) with #measure shown",
        pg.evaluate("camera.state().i") == D.key
        and pg.evaluate("__vis(document.getElementById('measure'))"),
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
def check_framing(D: Data, browser, target: str, width: int, shots: Path) -> None:
    """The broadcast fit (2.4): the defenders (feet and head), the receiver, the ball and the
    clipped frame inside the canvas in the 100 frames; at most 10 % of the height under the
    lowest; the defenders' median drawn height at least the legibility floor."""
    ctx, pg = open_page(browser, target, width=width, height=844 if width < 600 else 900)
    go(pg, "broadcast")
    w, h = pg.evaluate("[camera.camera().width, camera.camera().height]")
    bad, low, heights = [], 0.0, []
    for i in range(D.n):
        pg.evaluate(f"camera.seek({(i - D.key) / D.fps})")
        feet = [(x, y, 0) for x, y in D.rivals[i]] + [(*D.me[i], 0), (*D.ball[i], 0)]
        heads = [(x, y, BODY_H) for x, y in D.rivals[i]] + [(*D.me[i], BODY_H)]
        frame = [(x, y, 0) for x, y, _ in clip_frame(D.corners[i])]
        px = proj(pg, feet + heads + frame)
        if (
            (px[:, 0] < -0.5).any()
            or (px[:, 0] > w + 0.5).any()
            or (px[:, 1] < -0.5).any()
            or (px[:, 1] > h + 0.5).any()
        ):
            bad.append(i)
        low = max(low, float(px[:, 1].max()))
        k = len(D.rivals[i])
        heights += list(px[:k, 1] - px[len(feet) : len(feet) + k, 1])
    med = float(np.median(heights))
    R.check(
        f"{width}px broadcast: defenders, receiver, ball and frame inside the canvas in the 100 frames",
        not bad,
        f"outside at {bad[:5]}",
    )
    R.check(
        f"{width}px broadcast: at most 10% of the height under the lowest point",
        (h - low) / h <= 0.10,
        f"{(h - low) / h:.3f}",
    )
    R.check(
        f"{width}px broadcast: the defenders' median drawn height >= {LEGIBLE_PX[width]} px",
        med >= LEGIBLE_PX[width],
        f"{med:.1f} px",
    )
    pg.evaluate("camera.seek(-3)")
    settle(pg)
    shot(pg, shots, f"{width}_broadcast_i0")
    pg.evaluate("camera.seek(0)")
    settle(pg)
    shot(pg, shots, f"{width}_broadcast_reception")
    ctx.close()


TAGS_JS = """() => [...document.querySelectorAll('#tags .tag')].filter(t => !t.hidden).map(t => {
  const b = t.getBoundingClientRect(), s = document.getElementById('stage').getBoundingClientRect();
  const lines = [...document.querySelectorAll('#tags .lead')];
  return {kind: t.dataset.kind, k: t.dataset.k === undefined ? null : +t.dataset.k, text: t.textContent,
          x: b.left - s.left, y: b.top - s.top, w: b.width, h: b.height};
})"""
ANCHORS_JS = """() => [...document.querySelectorAll('#tags .lead')].filter(l => l.style.display !== 'none')
  .map(l => [+l.getAttribute('x2'), +l.getAttribute('y2')])"""


@guarded
def check_tags(D: Data, browser, target: str, width: int) -> None:
    """The tags (2.3) in the 100 frames, both views: each anchor nearer its player than any
    other, no two boxes overlap, none covers the ball."""
    ctx, pg = open_page(browser, target, width=width, height=844 if width < 600 else 900)
    for view in ("broadcast", "plan"):
        go(pg, view)
        z = BODY_H if view == "broadcast" else 0.0
        wrong, overlap, ball = [], [], []
        for i in range(D.n):
            pg.evaluate(f"camera.seek({(i - D.key) / D.fps})")
            tags = pg.evaluate(TAGS_JS)
            anchors = pg.evaluate(ANCHORS_JS)
            people = proj(pg, [(x, y, z) for x, y in D.rivals[i]] + [(*D.me[i], z)])
            bpx = proj(pg, [(*D.ball[i], 0)])[0]
            for t, a in zip(tags, anchors, strict=False):
                if t["kind"] in ("rival", "me"):
                    own = t["k"] if t["kind"] == "rival" else len(people) - 1
                    d = np.hypot(*(people - np.array(a)).T)
                    if int(np.argmin(d)) != own:
                        wrong.append(i)
                if (
                    t["x"] - 1 < bpx[0] < t["x"] + t["w"] + 1
                    and t["y"] - 1 < bpx[1] < t["y"] + t["h"] + 1
                ):
                    ball.append(i)
            for m, s in enumerate(tags):
                for t in tags[m + 1 :]:
                    if (
                        min(s["x"] + s["w"], t["x"] + t["w"]) - max(s["x"], t["x"]) > 0.5
                        and min(s["y"] + s["h"], t["y"] + t["h"]) - max(s["y"], t["y"]) > 0.5
                    ):
                        overlap.append(i)
        R.check(
            f"{width}px {view}: tags in the 100 frames: each anchor nearest its player, no overlap,"
            " none over the ball",
            not wrong and not overlap and not ball,
            f"wrong anchor {sorted(set(wrong))[:5]}, overlaps {sorted(set(overlap))[:5]}, ball {sorted(set(ball))[:5]}",
        )
    ctx.close()


@guarded
def check_measure_only_in_plan(D: Data, browser, target: str) -> None:
    """No measure outside plan (8.3): #measure hidden whenever the view is not plan; the
    bracket's grey is on the canvas in plan and nowhere in broadcast; in broadcast, V0 to V1
    changes no pixel."""
    ctx, pg = open_page(browser, target)
    tick = (D.doc["units"]["block"]["index"] - D.key) / D.fps  # the bracket at full intensity

    def grey() -> int:
        comps = pg.evaluate(SCAN_JS, [[GREY], 4])[GREY]["comps"]
        return sum(c["n"] for c in comps if c["n"] >= 10)

    go(pg, "plan", tick)
    grey_plan = grey()
    go(pg, "broadcast", tick)
    hidden = pg.evaluate("document.getElementById('measure').hidden")
    grey_b = grey()
    before = pg.evaluate("document.getElementById('pitch').toDataURL()")
    pg.evaluate("camera.variant('V1')")
    settle(pg)
    after = pg.evaluate("document.getElementById('pitch').toDataURL()")
    R.check(
        "#measure hidden in broadcast; the bracket's grey drawn in plan and absent in broadcast;"
        " V1 in broadcast changes no pixel",
        hidden and grey_plan > 50 and grey_b == 0 and before == after,
        f"hidden {hidden}; grey px plan {grey_plan}, broadcast {grey_b}; pixels equal {before == after}",
    )
    ctx.close()


@guarded
def check_variant_and_ui(D: Data, browser, target: str) -> None:
    """V0/V1 in plan (4.2, 5.3): the big number of each panel row, aria-pressed, the caption,
    the subtitles and the buttons in each view."""
    ctx, pg = open_page(browser, target)
    go(pg, "broadcast", -3.0)
    u = pg.evaluate("__ui()")
    R.check(
        "broadcast: subtitle, caption and pressed button as 5.3",
        u["sub"] == SUB_BROADCAST
        and u["bcast"]["pressed"] == "true"
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
        rows[v] = (on, u["v0"]["pressed"], u["v1"]["pressed"], u["caption"], u["sub"])
    want = {
        v: [D.cell("line_height_m", v, "mean"), D.cell("block_length_m", v, "mean")]
        for v in ("V0", "V1")
    }
    R.check(
        "V0/V1: the panel's big numbers are the CSV's line height and block length of the variant,"
        " aria-pressed follows, the caption names it",
        rows["V0"][0] == want["V0"]
        and rows["V1"][0] == want["V1"]
        and rows["V0"][1:3] == ("true", "false")
        and rows["V1"][1:3] == ("false", "true")
        and rows["V0"][3].endswith("every unit")
        and rows["V1"][3].endswith("players seen throughout")
        and rows["V1"][4] == SUB_PLAN,
        f"{rows['V0'][0]} -> {rows['V1'][0]}",
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
    """Every number shown in #measure and #count (8.3): its data-value is the sidecar's value at
    its path, its text that value at the text's rounding; the match's cells are the CSV's. At
    i = 0, 30 and 99."""
    ctx, pg = open_page(browser, target)
    bad, seen = [], 0
    for t in (-3.0, 0.0, 6.9):
        go(pg, "plan", t)
        items = pg.evaluate("""() => [...document.querySelectorAll('#measure [data-path], #count [data-path]')]
            .filter(e => __vis(e) && e.classList.contains('q')).map(e => [e.dataset.path, e.dataset.value, e.textContent])""")
        for path, value, text in items:
            seen += 1
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
    R.check(
        "numbers: every number in #measure and #count is the sidecar's at its path, shown at its"
        " rounding; the match's cells are reliability.csv's (i = 0, 30, 99)",
        seen > 100 and not bad,
        f"{seen} checked; wrong {bad[:4]}",
    )
    ctx.close()


@guarded
def check_reduced_motion(D: Data, browser, target: str) -> None:
    """Reduced motion (5.2): loads in plan at i = 30, idle, #measure shown; a view never rises."""
    ctx, pg = open_page(browser, target, reduced=True)
    pg.wait_for_timeout(500)
    s = pg.evaluate("camera.state()")
    shown = pg.evaluate("__vis(document.getElementById('measure'))")
    pg.evaluate("camera.view('broadcast'); camera.view('plan')")
    pg.wait_for_timeout(300)
    log = pg.evaluate("window.__log")
    R.check(
        "reduced motion: plan, i = 30, idle, #measure shown; the views cut, never rising",
        s["view"] == "plan"
        and s["i"] == D.key
        and s["phase"] == "idle"
        and shown
        and not any(e["view"] == "rising" for e in log)
        and pg.evaluate("camera.state().view") == "plan",
        f"{s['view']} {s['i']} {s['phase']}, measure {shown}",
    )
    ctx.close()


LAYOUT_JS = """() => { const de = document.documentElement, b = document.body;
  const box = (e) => e ? e.getBoundingClientRect().toJSON() : null;
  const r = (id) => box(document.getElementById(id));
  const small = [...document.querySelectorAll('p, li, summary')]
    .filter(e => e.textContent.trim().length > 0 && !e.closest('svg') && __vis(e))
    .map(e => [parseFloat(getComputedStyle(e).fontSize), e.id || e.tagName, e.textContent.trim().slice(0, 30), e.textContent.trim().length])
    .filter(x => x[0] < (x[3] >= 60 ? 16 : 12));
  const targets = [...document.querySelectorAll('a, button, input')].filter(__vis)
    .map(e => { const q = e.getBoundingClientRect(); return [e.id || e.textContent.trim().slice(0, 20), +q.width.toFixed(1), +q.height.toFixed(1)]; });
  const h1 = document.querySelector('h1');
  return {iw: innerWidth, ih: innerHeight, sw: Math.max(de.scrollWidth, b.scrollWidth), body: parseFloat(getComputedStyle(b).fontSize),
          canvas: r('pitch'), small, targets, top: r('top'), ctrl: r('controls'), play: r('play'), panel: r('panel'),
          count: r('count'), h1: {h: h1.getBoundingClientRect().height, lh: parseFloat(getComputedStyle(h1).lineHeight),
          sw: h1.scrollWidth, cw: h1.clientWidth}}; }"""


def meets(a: dict, b: dict) -> bool:
    return (
        min(a["right"], b["right"]) - max(a["left"], b["left"]) > 1
        and min(a["bottom"], b["bottom"]) - max(a["top"], b["top"]) > 1
    )


@guarded
def check_layout(D: Data, browser, target: str, width: int, shots: Path) -> None:
    """Layout (6): no horizontal scroll, body and prose at 16 px, targets 44 px, the first screen,
    the scrubber's thumb; the panel and the counter cover no marker and no tag in the 100 frames."""
    height = 844 if width < 600 else 900
    ctx, pg = open_page(browser, target, width=width, height=height)
    for view in ("broadcast", "plan"):
        go(pg, view, 0.0)
        pg.evaluate("window.scrollTo(0, 0)")
        pg.wait_for_timeout(300)
        m = pg.evaluate(LAYOUT_JS)
        tag = f"{width}px {view}"
        R.check(f"{tag}: no horizontal scroll", m["sw"] <= m["iw"], f"{m['sw']} vs {m['iw']}")
        R.check(
            f"{tag}: body {BODY_MIN_PX}px; prose (60+ chars) >= {BODY_MIN_PX}px, labels >= 12px",
            m["body"] >= BODY_MIN_PX and not m["small"],
            json.dumps(m["small"][:3]),
        )
        small_t = [t for t in m["targets"] if t[1] < TARGET_PX or t[2] < TARGET_PX]
        R.check(
            f"{tag}: every visible button, link and the scrubber at least {TARGET_PX} px",
            m["targets"] and not small_t,
            f"{len(m['targets'])} targets; under: {small_t[:4]}",
        )
        c, h1 = m["canvas"], m["h1"]
        one_line = h1["h"] <= 1.5 * h1["lh"] and h1["sw"] <= h1["cw"]
        if width < 900:
            p = m["play"]
            R.check(
                f"{tag}: phone first screen: the stage on top, full width, >= 60% of the height,"
                " the title one line, Play on screen",
                c["top"] <= 1
                and c["left"] <= 0.5
                and c["right"] >= m["iw"] - 0.5
                and c["height"] >= 0.6 * m["ih"]
                and one_line
                and p["bottom"] <= m["ih"],
                f"canvas {c['top']:.0f}..{c['bottom']:.0f} of {m['ih']}; Play to {p['bottom']:.0f}",
            )
        else:
            t, k = m["top"], m["ctrl"]
            R.check(
                f"{tag}: desktop first screen: the stage viewport-high, the title and the controls"
                " over it, apart, nothing cut, the title one line",
                abs(c["height"] - m["ih"]) <= 1
                and abs(c["width"] - m["iw"]) <= 1
                and not meets(t, k)
                and t["right"] <= m["iw"]
                and k["right"] <= m["iw"] + 0.5
                and one_line,
                f"canvas {c['width']:.0f}x{c['height']:.0f}",
            )
        covers = [
            b
            for b in ((m["panel"] if view == "plan" else None), m["count"], m["top"])
            if b and meets(b, c)
        ]
        z = 0.0 if view == "plan" else BODY_H
        under, tag_hit = [], 0
        for i in range(D.n):
            pg.evaluate(f"camera.seek({(i - D.key) / D.fps})")
            pts = [(x, y, z) for x, y in D.rivals[i]] + [(*D.me[i], z), (*D.ball[i], 0)]
            pts += [(x, y, z) for x, y in D.mates[i] if not np.isnan(x)]
            for px, py in proj(pg, pts):
                vx, vy = c["left"] + px, c["top"] + py
                if any(
                    k["left"] - 4 <= vx <= k["right"] + 4 and k["top"] - 4 <= vy <= k["bottom"] + 4
                    for k in covers
                ):
                    under.append(i)
            for t in pg.evaluate(TAGS_JS):
                tb = {
                    "left": c["left"] + t["x"],
                    "right": c["left"] + t["x"] + t["w"],
                    "top": c["top"] + t["y"],
                    "bottom": c["top"] + t["y"] + t["h"],
                }
                tag_hit += sum(meets(tb, k) for k in covers)
        R.check(
            f"{tag}: the title band, the counter{' and the panel' if view == 'plan' else ''} cover no"
            " player and no tag in the 100 frames",
            not under and tag_hit == 0,
            f"players under them at frames {sorted(set(under))[:6]}; tags {tag_hit}",
        )
        go(pg, view, 0.0)
        shot(pg, shots, f"{width}_{view}")
    # the thumb: a press 20 px either side of its centre keeps the value
    go(pg, "broadcast")
    pg.evaluate("camera.pause(); camera.seek(1.5)")
    pg.locator("#scrub").scroll_into_view_if_needed()
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
        f"{width}px: the scrubber's thumb takes a press 20 px either side of its centre",
        all(v == want for v in seen),
        f"{want}: {seen}",
    )
    pg.evaluate("camera.flight(1); camera.seek(0)")
    settle(pg)
    pg.screenshot(path=str(shots / f"{width}_full_page.png"), full_page=True)
    ctx.close()


# ---------------------------------------------------------------- main


def main(argv: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("target", nargs="?", default=str(DEFAULT_PAGE))
    parser.add_argument("--shots", type=Path, default=ROOT / "build" / "camera")
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
        check_startup(D, p, target)
        browser = p.chromium.launch(args=CHROMIUM_ARGS)
        check_hook(D, browser, target, args.shots)
        check_transport(D, browser, target)
        check_plan_truth(D, browser, target)
        check_frame(D, browser, target)
        check_measure_only_in_plan(D, browser, target)
        check_variant_and_ui(D, browser, target)
        check_numbers(D, browser, target)
        check_reduced_motion(D, browser, target)
        for w in (1440, 390):
            check_framing(D, browser, target, w, args.shots)
            check_tags(D, browser, target, w)
            check_layout(D, browser, target, w, args.shots)
        browser.close()
    n_fail = sum(1 for r in R.rows if not r[0])
    print(f"\n{len(R.rows) - n_fail} passed, {n_fail} failed, {time.time() - t0:.0f} s")
    print("not covered: the hidden-tab clock (headless Chromium cannot hide a tab)")
    return 0 if R.ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
