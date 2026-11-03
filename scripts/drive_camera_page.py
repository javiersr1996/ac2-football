"""Drive the built camera page from the browser console and check it against the storyboard.

    uv run --with playwright playwright install chromium        # once
    uv run --with playwright python scripts/drive_camera_page.py [path-or-url] [--shots DIR]
        [--sizes 1440x900,390x844]                              # some of the viewports

The default target is ``reports/camera/what_the_camera_saw.html``; after publishing, the same
driver runs against the Pages URL. The expected values are read from ``reports/camera/camera.json``
and ``reports/reliability.csv``, never typed and never read from the page's source. One line per
check; exit 0 if every check passes and 1 otherwise. Screenshots of the whole page go to
``build/camera/`` (ignored) or ``--shots``.

The page scrolls by design: one column read top to bottom, blocks 1 and 2 side by side from
``SIDE_BY_SIDE_FROM`` px. The rows: the page loads nothing and throws nothing; each of the two
receptions (the video's, the sidecar's top level, and the second, its ``second``) is the
sidecar's at three frames (the frame's corners, every player, the rings and their labels); Play
advances the frame and the count follows it; the labels pinned are those of gaps over
``LABEL_GAP_S``, the rest show on tap; the pick between the receptions, by mouse and keyboard,
says of each what the sidecar says (counts in V1 or not, its units' players seen) and clears what
was pinned; the V0/V1 switch moves the live block and line to the
match's means and the bars and the table follow; every number shown is the sidecar's at its path,
at the text's rounding, and the match's cells are the CSV's; the strips hold every point of
figure 1 in the README's groups, one colour per group, green only for the metrics that survive;
and at seven viewports (``VIEWPORTS``): no horizontal scroll, prose at 16 px and every other text
at 12 px, text at 4.5:1, the marks that carry meaning at 3:1, no two pieces of writing
overlapping, every control 44 px, the two blocks side by side or stacked as the width says, and
every <details> opening.

Copied, with a declaration, from the author's basketball entry
(github.com/javiersr1996/nobody-helps-the-helper, ``scripts/drive_wind_page.py``, MIT): ``Report``
and ``R.check``, ``guarded``, ``TEXT_JS`` (adapted) and the layout rows.
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

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
DEFAULT_PAGE = REPORTS / "camera" / "what_the_camera_saw.html"
# The seven viewports (width, height; the last four are touch screens).
VIEWPORTS = [(1440, 900), (1280, 720), (1024, 768), (844, 390), (390, 844), (360, 780), (320, 568)]
TOUCH = {(844, 390), (390, 844), (360, 780), (320, 568)}
# The storyboard's numbers the checks are written from: blocks 1 and 2 sit side by side from
# SIDE_BY_SIDE_FROM px; the legibility floors (prose, every other text, a control, text contrast,
# the contrast of a mark that carries meaning); the viewports whose first screen must hold the
# twenty matches' finding and the recommendation. The gap over which a ring's label stays pinned
# is the sidecar's (label_gap_s), as every other expected value.
SIDE_BY_SIDE_FROM = 1024
FIRST_SCREEN = {(390, 844), (1440, 900)}
BODY_MIN_PX, LABEL_MIN_PX, TARGET_PX, CONTRAST_MIN, MARK_MIN = 16, 12, 44, 4.5, 3.0
# Play: the frames the clip must advance within PLAY_WAIT_S of pressing Play (10 fps: a loaded
# machine may drop some).
PLAY_FRAMES, PLAY_WAIT_S = 6, 3.0
HALF_LENGTH = 52.5  # the goal line of the plan in block 2 (ac2fb.clip's pitch)

# In-page helpers, installed before the page's own script runs: `__vis(el)` (really visible:
# rendered, not hidden, not transparent).
INIT_JS = """
(() => {
  window.__vis = (e) => {
    if (!e) return false;
    for (let n = e; n && n.nodeType === 1; n = n.parentElement) {
      if (n.hidden) return false;
      const cs = getComputedStyle(n);
      if (cs.display === 'none' || cs.visibility === 'hidden' || parseFloat(cs.opacity) === 0) return false;
    }
    return e.getClientRects().length > 0;
  };
})();
"""

# The page's scroll: the document against the window, both ways.
SCROLL_JS = """() => { const de = document.documentElement, b = document.body;
  return {sh: Math.max(de.scrollHeight, b.scrollHeight), ih: innerHeight, sw: Math.max(de.scrollWidth, b.scrollWidth), iw: innerWidth}; }"""

# Every visible piece of text: its element, the text, its box, its font size as rendered (an SVG
# text's user units through its screen matrix), whether it is prose (a p or li of 60 characters or
# more), its colour and the colour under it (the backgrounds of its ancestors composited), and
# whether a disabled control holds it (exempt from contrast, as WCAG has it).
TEXT_JS = """() => {
  const parse = s => { const m = s && s.match(/rgba?\\(([^)]+)\\)/); if (!m) return null;
    const p = m[1].split(/[\\s,\\/]+/).filter(Boolean).map(Number); return [p[0], p[1], p[2], p.length > 3 ? p[3] : 1]; };
  const over = (top, bottom) => [0, 1, 2].map(i => top[i] * top[3] + bottom[i] * (1 - top[3])).concat([1]);
  const lum = c => { const [r, g, b] = c.slice(0, 3).map(v => { v /= 255; return v <= 0.04045 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); });
                     return 0.2126 * r + 0.7152 * g + 0.0722 * b; };
  const seen = new Set(), out = [];
  const walk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let n = walk.nextNode(); n; n = walk.nextNode()) {
    const e = n.parentElement;
    if (!e || seen.has(e) || !n.textContent.trim()) continue;
    if (e.closest('script, style, title') || !__vis(e)) continue;
    seen.add(e);
    const r = e.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) continue;
    const cs = getComputedStyle(e), svg = e instanceof SVGElement;
    const scale = svg && e.getScreenCTM ? e.getScreenCTM().a : 1;
    let fg = parse(svg ? cs.fill : cs.color) || [0, 0, 0, 1], opacity = 1;
    const chain = [];
    for (let a = e; a && a.nodeType === 1; a = a.parentElement) { chain.push(a); opacity *= parseFloat(getComputedStyle(a).opacity); }
    let bg = [255, 255, 255, 1];
    for (const a of chain.slice().reverse()) {
      const c = parse(getComputedStyle(a).backgroundColor);
      if (c && c[3] > 0) bg = over(c, bg);
    }
    fg = [fg[0], fg[1], fg[2], fg[3] * opacity];
    const shown = over(fg, bg), L1 = lum(shown), L2 = lum(bg);
    const ratio = (Math.max(L1, L2) + 0.05) / (Math.min(L1, L2) + 0.05);
    const own = [...e.childNodes].filter(c => c.nodeType === 3).map(c => c.textContent).join('').trim();
    out.push({id: e.id || (typeof e.className === 'string' ? e.className : e.getAttribute('class') || '') || e.tagName, text: own.slice(0, 40),
              len: (e.innerText || e.textContent).trim().length, tag: e.tagName.toLowerCase(),
              x: r.left, y: r.top, w: r.width, h: r.height, size: parseFloat(cs.fontSize) * scale,
              ratio: +ratio.toFixed(2), disabled: Boolean(e.closest('button[disabled], input[disabled]')),
              prose: ['P', 'LI', 'CAPTION'].includes(e.tagName), legend: Boolean(e.closest('.legend'))}); }
  return out; }"""

# The first screen: the boxes of the finding's numbers and of the recommendation in the header.
FOLD_JS = """() => [...document.querySelectorAll('#finding .q, #finding')].map(e => { const r = e.getBoundingClientRect();
  return [e.textContent.trim().slice(0, 60), r.top, r.bottom]; })"""

# The centres of the rings at the current frame (the dots' boxes), in page pixels.
RINGS_JS = """() => [...document.querySelectorAll('#rivals .riv .dot')].map(c => { const r = c.getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; })"""

# Two pieces of writing overlap when a line box of one text node crosses a line box of another by
# more than a pixel both ways (text nodes inside one element abut, they do not cross).
OVERLAP_JS = """() => {
  const rects = [];
  const walk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let n = walk.nextNode(); n; n = walk.nextNode()) {
    const e = n.parentElement;
    if (!e || !n.textContent.trim() || e.closest('script, style, title') || !__vis(e)) continue;
    const range = document.createRange(); range.selectNodeContents(n);
    for (const r of range.getClientRects()) if (r.width > 0 && r.height > 0)
      rects.push({t: n.textContent.trim().slice(0, 24), x: r.left, y: r.top, w: r.width, h: r.height, n});
  }
  const hits = [];
  for (let i = 0; i < rects.length; i++) for (let j = i + 1; j < rects.length; j++) {
    const a = rects[i], b = rects[j];
    if (a.n === b.n) continue;
    const dx = Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x), dy = Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y);
    if (dx > 1 && dy > 1) hits.push([a.t, b.t]);
  }
  return {n: rects.length, hits: hits.slice(0, 6)}; }"""

# The marks that carry meaning, each against what it lies on (its colour composited at its
# opacity): a seen defender and a filled-in ring on the grass and outside the frame (the pitch
# faded), the receiver, the frame's edge, the ghosts and the live shapes of block 2, each verdict
# group's dots and median, the zero line, the count bars' fill. The pitch's lines are reported,
# not gated: they are the map under the marks, white on the grass as the mockup has them.
MARKS_JS = """() => {
  const parse = s => { const m = s && s.match(/rgba?\\(([^)]+)\\)/); if (!m) return null;
    const p = m[1].split(/[\\s,\\/]+/).filter(Boolean).map(Number); return [p[0], p[1], p[2], p.length > 3 ? p[3] : 1]; };
  const over = (top, bottom) => [0, 1, 2].map(i => top[i] * top[3] + bottom[i] * (1 - top[3])).concat([1]);
  const lum = c => { const [r, g, b] = c.slice(0, 3).map(v => { v /= 255; return v <= 0.04045 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); });
                     return 0.2126 * r + 0.7152 * g + 0.0722 * b; };
  const ratio = (f, b) => { const s = over(f, b), x = lum(s), y = lum(b); return +((Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05)).toFixed(2); };
  const cs = e => getComputedStyle(e), q = s => document.querySelector(s);
  const paint = (e, prop, op) => { const c = parse(cs(e)[prop]); if (!c) return null; const o = op ? parseFloat(cs(e)[op]) : 1; return [c[0], c[1], c[2], c[3] * o]; };
  const paper = parse(cs(document.body).backgroundColor);
  const grass = paint(q('#pitch .grass'), 'fill', 'fillOpacity');
  const faded = over(paint(q('#fade'), 'fill', 'fillOpacity'), grass);
  const out = {};
  const put = (name, fg, bg) => { if (fg && bg) out[name] = ratio(fg, bg); };
  put('seen defender on the grass', paint(q('#rivals .riv.seen .dot'), 'fill', 'fillOpacity'), grass);
  put('seen defender outside the frame', paint(q('#rivals .riv.seen .dot'), 'fill', 'fillOpacity'), faded);
  put('filled-in ring on the grass', paint(q('#rivals .riv:not(.seen) .dot'), 'stroke', 'strokeOpacity'), grass);
  put('filled-in ring outside the frame', paint(q('#rivals .riv:not(.seen) .dot'), 'stroke', 'strokeOpacity'), faded);
  const meSeen = q('#me').classList.contains('seen');  // seen: a disc; filled in: a ring
  put('receiver on the grass', paint(q('#me .dot'), meSeen ? 'fill' : 'stroke', meSeen ? 'fillOpacity' : 'strokeOpacity'), grass);
  put('receiver outside the frame', paint(q('#me .dot'), meSeen ? 'fill' : 'stroke', meSeen ? 'fillOpacity' : 'strokeOpacity'), faded);
  if (q('#mates .mate.seen .dot')) put('seen teammate on the grass', paint(q('#mates .mate.seen .dot'), 'fill', 'fillOpacity'), grass);
  if (q('#mates .mate:not(.seen) .dot')) put('filled-in teammate on the grass', paint(q('#mates .mate:not(.seen) .dot'), 'stroke', 'strokeOpacity'), grass);
  put('the frame on the grass', paint(q('#frame'), 'stroke', 'strokeOpacity'), grass);
  put('the frame outside', paint(q('#frame'), 'stroke', 'strokeOpacity'), faded);
  put('ghost block', paint(q('.ghosts .blk'), 'stroke', 'strokeOpacity'), grass);
  put('ghost line', paint(q('.ghosts .ln line'), 'stroke', 'strokeOpacity'), grass);
  put('live block', paint(q('#blk-live'), 'stroke', 'strokeOpacity'), grass);
  put('live line', paint(q('#ln-live line'), 'stroke', 'strokeOpacity'), grass);
  for (const g of document.querySelectorAll('.vgroup')) {
    const c = paint(g.querySelector('.swatch'), 'backgroundColor');
    put('dots of ' + g.dataset.group, c, paper);
    put('median of ' + g.dataset.group, paint(g.querySelector('.med'), 'backgroundColor', 'opacity'), paper);
  }
  put('zero line', paint(q('.zero'), 'borderLeftColor'), paper);
  put('count bar', paint(q('.fill'), 'backgroundColor'), paint(q('.track'), 'backgroundColor'));
  return {gated: out, pitchLines: ratio(paint(q('#pitch .pl rect'), 'stroke', 'strokeOpacity'), grass)}; }"""

# The scene at the current frame: the frame's corners, the fade path, every marker's place and
# state, the labels on and their text, the count and the clock.
SCENE_JS = """() => {
  const xy = g => { const m = g.style.transform.match(/translate\\(([-\\d.e]+)px,\\s*([-\\d.e]+)px\\)/); return m ? [+m[1], +m[2]] : null; };
  return {
    i: camera.state().i,
    points: document.getElementById('frame').getAttribute('points'),
    fade: document.getElementById('fade').getAttribute('d'),
    rivals: [...document.querySelectorAll('#rivals .riv')].map(g => ({xy: xy(g), seen: g.classList.contains('seen'), shown: g.style.display !== 'none'})),
    mates: [...document.querySelectorAll('#mates .mate')].map(g => ({xy: xy(g), seen: g.classList.contains('seen'), shown: g.style.display !== 'none'})),
    me: xy(document.getElementById('me')), ball: xy(document.getElementById('ball')),
    labels: [...document.querySelectorAll('#labels .lab')].map(l => ({on: l.classList.contains('on'), text: l.textContent.trim(), seen: l.classList.contains('seen')})),
    count: document.getElementById('count-n').textContent.trim(),
    of: document.getElementById('count-of').textContent.trim(),
    clock: document.getElementById('clock').textContent.trim(),
    scrub: document.getElementById('scrub').value,
    play: document.getElementById('play').textContent.trim(),
  }; }"""

# Block 2 as shown: the live block's geometry, the live line's shift, the pressed buttons, the
# bars' text and width, the highlighted column of the table.
SWITCH_JS = """() => {
  const b = document.getElementById('blk-live'), ln = document.getElementById('ln-live');
  const num = a => +b.getAttribute(a);
  const m = ln.style.transform.match(/translate\\(([-\\d.e]+)px/);
  const on = v => getComputedStyle(document.querySelector('#panel-table td.' + v)).backgroundColor;
  return {variant: document.getElementById('sw').dataset.v, x: num('x'), width: num('width'), y: num('y'), height: num('height'),
          line: m ? +m[1] : null,
          pressed: [document.getElementById('variant-v0').getAttribute('aria-pressed'), document.getElementById('variant-v1').getAttribute('aria-pressed')],
          clLine: document.getElementById('cl-line').textContent.trim(), clBlock: document.getElementById('cl-block').textContent.trim(),
          fillLine: document.getElementById('fill-line').style.width, fillBlock: document.getElementById('fill-block').style.width,
          td: {v0: on('v0'), v1: on('v1')}}; }"""


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


RECEPTIONS = ("the video's reception", "the second reception")


class Data:
    """The expected values of one reception: 0 the video's (the sidecar's top level), 1 the second
    (its ``second``); ``pre`` is the prefix of its paths."""

    def __init__(self, reception: int = 0) -> None:
        self.doc = json.loads((REPORTS / "camera" / "camera.json").read_text(encoding="utf-8"))
        self.reception, self.pre = reception, ("", "second.")[reception]
        self.name = RECEPTIONS[reception]
        d = self.play = self.doc if reception == 0 else self.doc["second"]
        self.n, self.fps, self.key = d["n_frames"], self.doc["fps"], d["key"]["index"]
        self.label_gap_s = self.doc["label_gap_s"]
        ent = d["entities"]
        self.rivals, self.seen, self.gap = (
            ent["rivals"]["xy"],
            ent["rivals"]["detected"],
            ent["rivals"]["gap"],
        )
        self.mates, self.mates_seen = ent["mates"]["xy"], ent["mates"]["detected"]
        self.me, self.ball = ent["me"]["xy"], ent["ball"]["xy"]
        self.corners = d["camera"]["corners"]
        self.rows = {r["metric"]: (k, r) for k, r in enumerate(self.doc["match"]["rows"])}
        with (REPORTS / "reliability.csv").open(encoding="utf-8", newline="") as f:
            self.csv = list(csv.DictReader(f))

    def pick(self, path: str):
        node = self.doc
        for part in path.split("."):
            node = node[int(part)] if isinstance(node, list) else node[part]
        return node

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

    def labels_on(self, i: int) -> list[bool]:
        """The rings whose label is pinned at frame i: filled in, gap over the sidecar's
        label_gap_s."""
        return [
            not s and g > self.label_gap_s * self.fps
            for s, g in zip(self.seen[i], self.gap[i], strict=True)
        ]


def close(a, b, tol: float = 1e-6) -> bool:
    return a is not None and b is not None and abs(float(a) - float(b)) <= tol


def same_xy(got, want) -> bool:
    if want is None or want[0] is None:
        return got is None
    return got is not None and close(got[0], want[0]) and close(got[1], want[1])


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


# ---------------------------------------------------------------- browser helpers


def open_page(browser, target: str, *, width=1440, height=900, reduced=False):
    ctx = browser.new_context(
        viewport={"width": width, "height": height},
        device_scale_factor=1,
        reduced_motion="reduce" if reduced else "no-preference",
        has_touch=True,
        is_mobile=(width, height) in TOUCH,
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


def pick(pg, D: Data) -> None:
    """Show D's reception (the page opens on the video's)."""
    pg.evaluate(f"camera.reception({D.reception})")
    settle(pg)


def settle(pg) -> None:
    pg.evaluate("new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")


def seek(pg, i: int) -> None:
    pg.evaluate(f"camera.seek({i})")
    settle(pg)


def open_details(pg) -> list[str]:
    """Open every <details> by its summary (a click, as a reader does); the ones that stay shut."""
    shut = []
    for d in pg.query_selector_all("details"):
        if not d.evaluate("e => e.open"):
            d.query_selector("summary").click()
        pg.wait_for_timeout(50)
        body = d.query_selector(".dbody")
        if not d.evaluate("e => e.open") or not body or not body.evaluate("e => __vis(e)"):
            shut.append(d.get_attribute("id") or "?")
    settle(pg)
    return shut


def shot(pg, shots: Path, name: str) -> None:
    shots.mkdir(parents=True, exist_ok=True)
    pg.screenshot(path=str(shots / f"{name}.png"), full_page=True)


def vp(width: int, height: int) -> str:
    return f"{width}x{height}"


# ---------------------------------------------------------------- the check groups


@guarded
def check_load(D: Data, browser, target: str) -> None:
    """The page loads nothing but itself and throws nothing; it opens at the reception."""
    ctx, pg = open_page(browser, target)
    pg.wait_for_timeout(300)
    own = [
        u
        for u in pg.requests
        if not (
            u == target
            or u.endswith("what_the_camera_saw.html")
            or u.rstrip("/").endswith("what-the-camera-saw")
        )
    ]
    R.check(
        "load: the page requests nothing but itself (no font, script, image or fetch) and throws no error",
        not own and not pg.errors,
        f"requests {pg.requests[:3]}; errors {pg.errors[:2]}",
    )
    s = pg.evaluate("camera.state()")
    R.check(
        "load: the page opens on the video's reception, at the reception, paused, on V0, nothing pinned",
        s["i"] == D.key
        and not s["playing"]
        and s["variant"] == "v0"
        and s["pinned"] == []
        and s["reception"] == 0,
        json.dumps(s),
    )
    ctx.close()


def scene_problems(D: Data, got: dict, i: int) -> list[str]:
    """Where the scene shown differs from the sidecar at frame i."""
    bad = []
    pts = [tuple(map(float, p.split(","))) for p in got["points"].split()]
    if len(pts) != 4 or not all(
        close(a, b)
        for p, c in zip(pts, D.corners[i], strict=True)
        for a, b in zip(p, c, strict=True)
    ):
        bad.append(f"frame corners {got['points'][:60]}")
    if not got["fade"].endswith("Z") or "Z M" not in got["fade"]:
        bad.append("the fade is not the crop less the frame")
    for k, r in enumerate(got["rivals"]):
        if not same_xy(r["xy"], D.rivals[i][k]) or r["seen"] != bool(D.seen[i][k]):
            bad.append(f"defender {k} at {r['xy']} seen {r['seen']}")
    for k, m in enumerate(got["mates"]):
        want = D.mates[i][k]
        if want[0] is None:
            if m["shown"]:
                bad.append(f"teammate {k} drawn without a row")
        elif not same_xy(m["xy"], want) or m["seen"] != bool(D.mates_seen[i][k]):
            bad.append(f"teammate {k} at {m['xy']}")
    if not same_xy(got["me"], D.me[i]) or not same_xy(got["ball"], D.ball[i]):
        bad.append(f"receiver {got['me']} ball {got['ball']}")
    want_on = D.labels_on(i)
    for k, lab in enumerate(got["labels"]):
        if lab["on"] != want_on[k]:
            bad.append(f"label {k} on={lab['on']}, gap {D.gap[i][k]} seen {D.seen[i][k]}")
        elif lab["on"] and not shown_matches(lab["text"], D.gap[i][k] / D.fps):
            bad.append(f"label {k} says {lab['text']!r} for gap {D.gap[i][k]}")
    if got["count"] != str(D.play["key"]["defenders_extrapolated_by_frame"][i]) or got["of"] != str(
        D.play["n_defenders"]
    ):
        bad.append(f"count {got['count']} of {got['of']}")
    rel = (i - D.key) / D.fps
    if i == D.key:
        if got["clock"] != "at the reception":
            bad.append(f"clock {got['clock']!r}")
    elif not shown_matches(got["clock"], rel) or "from the reception" not in got["clock"]:
        bad.append(f"clock {got['clock']!r}")
    if int(got["scrub"]) != i:
        bad.append(f"scrub at {got['scrub']}")
    return bad


@guarded
def check_scene(D: Data, browser, target: str) -> None:
    """The reception drawn is the sidecar's: at the reception, the first and the last frame, the
    frame's corners, the fade outside it, every player's place and state, the rings' labels (on for
    a gap over label_gap_s, with its seconds), the count of defenders filled in and the clock."""
    ctx, pg = open_page(browser, target)
    pick(pg, D)
    for i in (D.key, 0, D.n - 1):
        seek(pg, i)
        got = pg.evaluate(SCENE_JS)
        bad = scene_problems(D, got, i)
        R.check(
            f"{D.name}, scene at frame {i}: the frame's corners, the fade, {len(got['rivals'])} defenders, {len(got['mates'])} teammates, the receiver and the ball are camera.json's;"
            f" the labels on are the gaps over {D.label_gap_s:g} s (camera.json's label_gap_s) with their seconds; the count and the clock follow the frame",
            got["i"] == i and not bad,
            f"{sum(D.labels_on(i))} labels on, count {got['count']} of {got['of']}, clock {got['clock']!r}; wrong {bad[:4]}",
        )
    ctx.close()


@guarded
def check_play(D: Data, browser, target: str) -> None:
    """Play advances the frame counter and the count follows; the clip stops at its last frame;
    the scrubber seeks and pauses."""
    ctx, pg = open_page(browser, target)
    pick(pg, D)
    pg.click("#play")
    t0 = time.time()
    try:
        pg.wait_for_function(
            f"camera.state().i >= {D.key + PLAY_FRAMES}", timeout=int(PLAY_WAIT_S * 1000)
        )
        advanced = True
    except Exception:  # noqa: BLE001 - a slow machine is a FAIL line with its frame
        advanced = False
    s = pg.evaluate("camera.state()")
    got = pg.evaluate(SCENE_JS)
    R.check(
        f"{D.name}, Play: pressed at the reception the clip advances {PLAY_FRAMES} frames within {PLAY_WAIT_S:.0f} s, the button reads Pause, the count follows the frame",
        advanced
        and s["playing"]
        and got["play"] == "Pause"
        and got["count"] == str(D.play["key"]["defenders_extrapolated_by_frame"][s["i"]]),
        f"frame {s['i']} after {time.time() - t0:.1f} s; count {got['count']}; button {got['play']}",
    )
    pg.click("#play")
    paused = pg.evaluate("camera.state()")
    seek(pg, D.n - 2)
    pg.click("#play")
    pg.wait_for_timeout(int(2500 / D.fps))
    end = pg.evaluate("camera.state()")
    got = pg.evaluate(SCENE_JS)
    R.check(
        f"{D.name}, Play: Pause stops it; from the last frame but one it reaches the last frame and stops there, the button reading Play",
        not paused["playing"]
        and end["i"] == D.n - 1
        and not end["playing"]
        and got["play"] == "Play",
        f"paused at {paused['i']}; ended at {end['i']} playing {end['playing']}",
    )
    pg.fill("#scrub", str(D.key))  # a scrub input: seeks and pauses
    pg.dispatch_event("#scrub", "input")
    settle(pg)
    s = pg.evaluate("camera.state()")
    R.check(
        f"{D.name}: the scrubber seeks to its frame and pauses",
        s["i"] == D.key and not s["playing"],
        json.dumps(s),
    )
    ctx.close()


@guarded
def check_tap(D: Data, browser, target: str) -> None:
    """A ring's label shows on tap (pinned until the next tap) and on hover; a seen defender's
    says seen; the labels pinned by themselves stay."""
    ctx, pg = open_page(browser, target)
    pick(pg, D)
    seek(pg, D.key)
    pg.evaluate(
        "document.getElementById('stage').scrollIntoView({block: 'center'})"
    )  # every ring on screen
    pg.wait_for_timeout(200)  # the markers' slide, if any, ends before their centres are read
    on0 = D.labels_on(D.key)
    k_seen = next(k for k, s in enumerate(D.seen[D.key]) if s)
    quiet = [k for k, s in enumerate(D.seen[D.key]) if not s and not on0[k]]
    centres = pg.evaluate(RINGS_JS)  # a tap lands on the page, not on an element
    pg.mouse.click(*centres[k_seen])
    settle(pg)
    labs = pg.evaluate(SCENE_JS)["labels"]
    pinned = pg.evaluate("camera.state().pinned")
    ok = (
        labs[k_seen]["on"]
        and labs[k_seen]["text"] == "seen"
        and labs[k_seen]["seen"]
        and pinned == [k_seen]
    )
    ok = ok and all(labs[k]["on"] == on0[k] for k in range(len(labs)) if k != k_seen)
    pg.mouse.click(*centres[k_seen])
    pg.mouse.move(0, 0)  # the pointer leaves the ring: a hover would hold the label on
    settle(pg)
    off = pg.evaluate(SCENE_JS)["labels"]
    ok = ok and not off[k_seen]["on"] and pg.evaluate("camera.state().pinned") == []
    detail = f"defender {k_seen}: tap {labs[k_seen]['text']!r} on={labs[k_seen]['on']}, second tap on={off[k_seen]['on']}"
    if quiet:
        k = quiet[0]
        pg.mouse.move(*centres[k])
        settle(pg)
        hov = pg.evaluate(SCENE_JS)["labels"][k]
        ok = ok and hov["on"] and shown_matches(hov["text"], D.gap[D.key][k] / D.fps)
        detail += f"; hover on ring {k} shows {hov['text']!r} for gap {D.gap[D.key][k]}"
        pg.mouse.move(0, 0)
        settle(pg)
    R.check(
        f"{D.name}, tap: a defender's label pins on tap and unpins on the next; a seen defender's reads 'seen'; a hover shows a ring's seconds; the pinned labels stay",
        ok,
        detail,
    )
    # two close rings: a tap between them, nearer one, pins that one and not the other
    pairs = sorted(
        (
            (math.dist(centres[a], centres[b]), a, b)
            for a in range(len(centres))
            for b in range(a + 1, len(centres))
        ),
    )
    d_ab, a, b = pairs[0]
    at = [
        centres[a][0] + (centres[b][0] - centres[a][0]) / 3,
        centres[a][1] + (centres[b][1] - centres[a][1]) / 3,
    ]
    pg.mouse.click(*at)
    pg.mouse.move(0, 0)
    settle(pg)
    pinned = pg.evaluate("camera.state().pinned")
    R.check(
        f"{D.name}, tap: between the two closest defenders ({d_ab:.0f} px apart) a tap nearer one pins that one alone, the taps of close rings never swallowing each other",
        pinned == [a],
        f"defenders {a} and {b}; pinned {pinned}",
    )
    ctx.close()


@guarded
def check_dot_tap(D: Data, browser, target: str) -> None:
    """A strip's dots: a tap between the two closest dots, nearer one, shows that one's match in
    the tip; a tap elsewhere hides it."""
    ctx, pg = open_page(browser, target)
    pg.evaluate("document.getElementById('verdict').scrollIntoView()")
    settle(pg)
    dots = pg.evaluate("""() => [...document.querySelector('.strip .srow.cal').querySelectorAll('.d')]
        .map(d => { const r = d.getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2, d.dataset.match]; })""")
    pairs = sorted(
        (abs(p[0] - q[0]), i, j)
        for i, p in enumerate(dots)
        for j, q in enumerate(dots)
        if i < j and abs(p[0] - q[0]) > 2
    )
    gap, i, j = pairs[0]
    a, b = dots[i], dots[j]
    pg.mouse.click(a[0] + (b[0] - a[0]) / 3, a[1])
    settle(pg)
    tip = pg.evaluate(
        "() => { const t = document.getElementById('tip'); return [t.hidden, t.textContent]; }"
    )
    pg.mouse.click(5, 5)
    settle(pg)
    gone = pg.evaluate("document.getElementById('tip').hidden")
    R.check(
        f"dots: a tap between the two closest dots of a strip ({gap:.0f} px apart), nearer one, names that one's match; a tap elsewhere hides the tip",
        not tip[0] and tip[1].startswith(f"match {a[2]}:") and gone,
        f"tip {tip[1]!r} for match {a[2]} (the other {b[2]}); hidden after {gone}",
    )
    ctx.close()


@guarded
def check_switch(D: Data, browser, target: str) -> None:
    """V0/V1: the live block is the match's mean block (length from the goal line, width centred),
    the live line sits at the mean line depth, the buttons' aria-pressed follow, the bars say how
    many units count and the table marks the column; the ghosts are the other variant."""
    ctx, pg = open_page(browser, target)
    li, line = D.rows["line_height_m"]
    bi, block = D.rows["block_length_m"]
    wi, width = D.rows["block_width_m"]
    got = {}
    for v in ("v0", "v1"):
        pg.click(f"#variant-{v}")
        pg.wait_for_timeout(700)  # the transition
        got[v] = pg.evaluate(SWITCH_JS)
    bad = []
    for v in ("v0", "v1"):
        V = v.upper()
        g = got[v]
        if not (
            close(g["x"], HALF_LENGTH - block[V]["mean"], 0.006)
            and close(g["width"], block[V]["mean"], 0.006)
        ):
            bad.append(f"{V} block x {g['x']} width {g['width']}")
        if not (
            close(g["y"], -width[V]["mean"] / 2, 0.006)
            and close(g["height"], width[V]["mean"], 0.006)
        ):
            bad.append(f"{V} block y {g['y']} height {g['height']}")
        if not close(g["line"], line[V]["mean"], 0.006):
            bad.append(f"{V} line at {g['line']}")
        if g["variant"] != v or g["pressed"] != (
            ["true", "false"] if v == "v0" else ["false", "true"]
        ):
            bad.append(f"{V} pressed {g['pressed']}")
        if not (
            g["clLine"].startswith(f"{line[V]['n']:,} of {line['V0']['n']:,} receptions")
            and g["clBlock"].startswith(f"{block[V]['n']:,} of {block['V0']['n']:,} phases")
        ):
            bad.append(f"{V} bars {g['clLine']!r} {g['clBlock']!r}")
        if not (
            close(float(g["fillLine"].rstrip("%")), 100 * line[V]["n"] / line["V0"]["n"], 0.01)
            and close(
                float(g["fillBlock"].rstrip("%")), 100 * block[V]["n"] / block["V0"]["n"], 0.01
            )
        ):
            bad.append(f"{V} fills {g['fillLine']} {g['fillBlock']}")
        if g["td"][v] == g["td"]["v1" if v == "v0" else "v0"]:
            bad.append(f"{V}: the table's columns look alike")
    ghosts = pg.evaluate(
        """() => [...document.querySelectorAll('.ghosts .blk')].map(b => [+b.getAttribute('x'), +b.getAttribute('width')])"""
    )
    want_ghosts = sorted([[HALF_LENGTH - block[V]["mean"], block[V]["mean"]] for V in ("V0", "V1")])
    if (
        not all(
            close(a, b, 0.006)
            for g, w in zip(sorted(ghosts), want_ghosts, strict=False)
            for a, b in zip(g, w, strict=True)
        )
        or len(ghosts) != 2
    ):
        bad.append(f"ghosts {ghosts}")
    R.check(
        "V0/V1: the live block and line move to the variant's means of reliability.csv (block from the goal line, width centred), the ghosts are the other variant,"
        " aria-pressed follows, the bars count the units and the table marks the column",
        not bad,
        f"line {got['v0']['line']} -> {got['v1']['line']}; block width {got['v0']['width']} -> {got['v1']['width']}; wrong {bad[:3]}",
    )
    ctx.close()


@guarded
def check_numbers(D: Data, browser, target: str) -> None:
    """Every number shown (every span.q, the details open, at the reception and at the first and
    last frame): its data-value is the sidecar's value at its path and its text that value at the
    text's rounding (a frame as seconds from the reception, a gap as seconds); the match's cells
    are the CSV's; the strips' dots are figure 1's points."""
    ctx, pg = open_page(browser, target)
    open_details(pg)
    bad, seen, paths = [], 0, set()
    for P in (D, Data(1)):
        pick(pg, P)
        for i in (P.key, 0, P.n - 1):
            seek(pg, i)
            items = pg.evaluate("""() => [...document.querySelectorAll('.q[data-path]')].filter(__vis)
                .map(e => [e.dataset.path, e.dataset.value, e.textContent.trim()])""")
            for path, value, text in items:
                seen += 1
                paths.add(path)
                if not number_ok(D, path, value, text):
                    bad.append((path, value, text))
    pick(pg, D)
    R.check(
        "numbers: every number shown is the sidecar's at its path, at the text's rounding (details open; both receptions at the reception, the first and the last frame);"
        " the match's cells are reliability.csv's",
        seen > 300 and any(p.startswith("second.") for p in paths) and not bad,
        f"{seen} checked over {len(paths)} paths ({sum(p.startswith('second.') for p in paths)} of the second reception); wrong {bad[:4]}",
    )
    strips_and_verdict(D, pg)
    ctx.close()


def number_ok(D: Data, path: str, value: str, text: str) -> bool:
    """A number shown: its data-value is the sidecar's at its path and its text that value at the
    text's rounding (a frame as seconds from its reception's key frame, a gap as seconds); the
    match's cells are the CSV's."""
    want = D.pick(path)
    numeric = isinstance(want, int | float) and not isinstance(want, bool)
    ok = str(want) == value or (numeric and close(value, want, 1e-12))
    frame = re.match(r"(second\.)?frames\.", path)
    if frame:
        key = D.pick(f"{frame.group(1) or ''}key.frame")
        ok = ok and shown_matches(text, (want - key) / D.fps)
    elif "gap_len" in path or ".gap." in path:  # frames of gap, shown as seconds
        ok = ok and shown_matches(text, want / D.fps)
    elif numeric:
        ok = ok and shown_matches(text, want)
    else:
        ok = ok and text == str(want)
    m = re.match(r"match\.rows\.(\d+)\.(V[01])\.(mean|n)$", path)
    if m:
        row = D.doc["match"]["rows"][int(m.group(1))]
        ok = ok and close(D.cell(row["metric"], m.group(2), m.group(3)), want, 1e-12)
    return ok


def strips_and_verdict(D: Data, pg) -> None:
    """The strips' dots are figure 1's points in the README's groups; the verdict's colours and
    words."""
    dots = pg.evaluate("""() => [...document.querySelectorAll('.strip')].map(s => [s.dataset.metric, s.closest('.vgroup').dataset.group,
        [...s.querySelectorAll('.d')].map(d => [d.classList.contains('cal') ? 'calibration' : 'held-out', d.dataset.match, +d.dataset.value, parseFloat(d.style.left)])])""")
    wrong, groups = [], {}
    for metric, group, pts in dots:
        groups[metric] = group
        for split in ("calibration", "held-out"):
            want = sorted(
                (p["match"], p["value"])
                for p in D.doc["strips"]["metrics"][metric][split]["points"]
            )
            got = sorted((m, v) for s, m, v, _ in pts if s == split)
            if got != want:
                wrong.append((metric, split))
        order = sorted(pts, key=lambda p: p[2])
        if [p[3] for p in order] != sorted(p[3] for p in order):
            wrong.append((metric, "dots out of order"))
    verdict = {m: g["group"] for g in D.doc["findings"]["verdict"] for m in g["metrics"]}
    R.check(
        "strips: every dot is a point of figure 1 (match and V1 minus V0, both splits), in value order, and each metric sits in the README's verdict group",
        len(dots) == 7 and not wrong and groups == verdict,
        f"{len(dots)} strips; wrong {wrong[:3]}; groups {groups}",
    )
    colours = pg.evaluate(
        """() => [...document.querySelectorAll('.vgroup')].map(g => [g.dataset.group, getComputedStyle(g.querySelector('.swatch')).backgroundColor, g.className])"""
    )
    keep = pg.evaluate("document.getElementById('keep').textContent.trim()")
    words = pg.evaluate(
        "[...document.querySelectorAll('.vgroup .gwords')].map(p => p.textContent.trim())"
    )
    want_words = [g["words"] for g in D.doc["findings"]["verdict"]]
    R.check(
        "verdict: four groups in the README's order, one colour each, green only for the metrics that survive; the README's words under each; the closing sentence is the README's",
        [c[0] for c in colours] == [g["group"] for g in D.doc["findings"]["verdict"]]
        and len({c[1] for c in colours}) == 4
        and [c[0] for c in colours if "c-green" in c[2]] == ["survive"]
        and keep == D.doc["findings"]["keep"]
        and all(
            w.rstrip(".").lower() == ww.lower() for w, ww in zip(words, want_words, strict=True)
        ),
        f"{[(c[0], c[1]) for c in colours]}; keep {keep!r}",
    )


# ---------------------------------------------------------------- the pick between receptions

# The hook as shown: the pick's buttons, the lead, the units' rows, the rule's sentence, block 2's
# note, the state.
PICK_JS = """() => ({pressed: [...document.querySelectorAll('.pick button')].map(b => b.getAttribute('aria-pressed')),
  lead: document.getElementById('counted-lead').textContent.trim(),
  rows: [...document.querySelectorAll('#counted-body tr')].map(r => [...r.cells].map(c => c.textContent.trim())),
  rule: document.getElementById('counted-rule').textContent.trim(),
  note: document.getElementById('sw-note').textContent.trim(), state: camera.state()})"""
UNIT_ORDER = ("line", "block", "pressure", "nearest")


@guarded
def check_pick(D: Data, browser, target: str) -> None:
    """The pick: a click, Enter or Space on a button shows its reception and presses it; the hook
    says it counts in V1 exactly when every unit of the sidecar does, each unit's players seen are
    the sidecar's, the rule named is the reception's, block 2's note follows; what was pinned and
    a running clip do not survive the pick."""
    ctx, pg = open_page(browser, target)
    seek(pg, D.key)
    k = next(k for k, s in enumerate(D.seen[D.key]) if s)
    pg.evaluate(
        f"document.querySelectorAll('#rivals .riv')[{k}].dispatchEvent(new KeyboardEvent('keydown', {{key: 'Enter'}}))"
    )
    pinned = pg.evaluate("camera.state().pinned")
    got, bad = {}, []
    for how, p in (("click", 1), ("Enter", 0), ("Space", 1)):
        pg.evaluate("camera.play()")
        if how == "click":
            pg.click(f"#pick-{p}")
        else:
            pg.focus(f"#pick-{p}")
            pg.keyboard.press(how)
        settle(pg)
        got[how] = g = pg.evaluate(PICK_JS)
        P = Data(p)
        units = [P.play["units"][u] for u in UNIT_ORDER]
        counts = all(u["v1"] for u in units)
        if g["state"]["reception"] != p or g["pressed"] != (
            ["false", "true"] if p else ["true", "false"]
        ):
            bad.append(f"{how}: reception {g['state']['reception']} pressed {g['pressed']}")
        if g["lead"] != ("This one counts in V1." if counts else "This one counts for V0 only."):
            bad.append(f"{how}: lead {g['lead']!r}")
        want = [[f"{u['n_seen']} of {u['n_players']}", "yes" if u["v1"] else "no"] for u in units]
        if [r[1:] for r in g["rows"]] != want:
            bad.append(f"{how}: rows {g['rows']}")
        if ("second.rule" in g["rule"]) != bool(p) or ("counts in V1" in g["note"]) != counts:
            bad.append(f"{how}: rule {g['rule'][:40]!r} note {g['note'][:40]!r}")
        if g["state"]["pinned"] or g["state"]["playing"] or g["state"]["i"] != P.key:
            bad.append(f"{how}: state {g['state']}")
    one_way = Data(0).play["units"]["line"]["v1"] is False and all(
        u["v1"] for u in Data(1).play["units"].values()
    )
    R.check(
        "pick: a click, Enter and Space each show their reception and press its button; the hook says 'counts in V1' exactly when every unit of the sidecar does,"
        " each unit's players seen and its V1 are the sidecar's, the rule named is the reception's (clip.json's or second.rule), block 2's note follows;"
        " the pick stops a running clip, unpins and opens at the reception",
        pinned == [k] and one_way and not bad,
        f"pinned before {pinned}; leads {[g['lead'] for g in got.values()]}; wrong {bad[:3]}",
    )
    ctx.close()


# ---------------------------------------------------------------- the layout, per viewport


@guarded
def check_layout(D: Data, browser, target: str, size: tuple[int, int], shots: Path) -> None:
    """At one viewport: every <details> opens; no horizontal scroll; prose at 16 px and every
    other text at 12 px; text at 4.5:1; the marks that carry meaning at 3:1; no two pieces of
    writing overlap (at the reception, the first and the last frame, in V0 and V1); every control
    44 px each way; blocks 1 and 2 side by side from SIDE_BY_SIDE_FROM px and stacked below; a
    screenshot of the whole page."""
    w, h = size
    ctx, pg = open_page(browser, target, width=w, height=h)
    fold = pg.evaluate(FOLD_JS)  # before any scroll: the finding and the recommendation
    MEASURED.setdefault(size, {})["fold"] = round(max(b for _, _, b in fold))
    if size in FIRST_SCREEN:
        numbers = [t for t, _, _ in fold[:-1]]
        whole = fold[-1][0]
        R.check(
            f"{vp(w, h)}: the first screen holds the twenty matches' finding (its numbers) and the recommendation, before any scroll",
            len(numbers) >= 5
            and all(0 <= top and bottom <= h for _, top, bottom in fold)
            and "Keep the fill" in pg.evaluate("document.getElementById('finding').textContent"),
            f"numbers {numbers}; the paragraph {whole[:40]!r}… ends at {fold[-1][2]:.0f} px of {h}",
        )
    shut = open_details(pg)
    R.check(
        f"{vp(w, h)}: every <details> opens on a click of its summary and shows its body",
        not shut,
        f"shut {shut}",
    )
    sc = pg.evaluate(SCROLL_JS)
    MEASURED.setdefault(size, {})["page_h"] = sc["sh"]
    R.check(
        f"{vp(w, h)}: no horizontal scroll with every detail open (the page scrolls down by design; a phone would zoom out on a wider layout)",
        sc["sw"] <= w + 0.5 and sc["iw"] <= w + 0.5,
        f"scroll width {sc['sw']} in a window of {sc['iw']} ({w} asked); height {sc['sh']}",
    )
    boxes = pg.evaluate(
        """() => { const r = id => document.getElementById(id).getBoundingClientRect().toJSON(); return {hook: r('hook'), sw: r('sw')}; }"""
    )
    beside = (
        boxes["hook"]["right"] <= boxes["sw"]["left"] + 0.5
        and abs(boxes["hook"]["top"] - boxes["sw"]["top"]) < 2
    )
    stacked = boxes["hook"]["bottom"] <= boxes["sw"]["top"] + 0.5
    R.check(
        f"{vp(w, h)}: blocks 1 and 2 {'side by side' if w >= SIDE_BY_SIDE_FROM else 'stacked'} ({'from' if w >= SIDE_BY_SIDE_FROM else 'under'} {SIDE_BY_SIDE_FROM} px)",
        beside if w >= SIDE_BY_SIDE_FROM else stacked,
        f"hook right {boxes['hook']['right']:.0f} bottom {boxes['hook']['bottom']:.0f}; switch left {boxes['sw']['left']:.0f} top {boxes['sw']['top']:.0f}",
    )
    small, faint, hits = [], [], []
    for t in pg.evaluate(TEXT_JS):
        if t["size"] < LABEL_MIN_PX - 0.01 or (
            ((t["prose"] and t["len"] >= 60) or t["legend"]) and t["size"] < BODY_MIN_PX - 0.01
        ):
            small.append((t["id"], t["text"], round(t["size"], 1)))
        if not t["disabled"] and t["ratio"] < CONTRAST_MIN:
            faint.append((t["id"], t["text"], t["ratio"]))
    R.check(
        f"{vp(w, h)}: prose (p, li, caption of 60+ characters, the legend) >= {BODY_MIN_PX} px; every other text, tick and label >= {LABEL_MIN_PX} px",
        not small,
        json.dumps(small[:4]),
    )
    R.check(
        f"{vp(w, h)}: every piece of text at >= {CONTRAST_MIN}:1 against what is under it (the labels too)",
        not faint,
        json.dumps(faint[:4]),
    )
    n_rects = 0
    for P in (Data(1), D):  # the video's last: the rows after this one read it
        pick(pg, P)
        for v in ("v0", "v1"):
            pg.evaluate(f"camera.variant('{v}')")
            for i in (P.key, 0, P.n - 1):
                seek(pg, i)
                pg.wait_for_timeout(200)  # a label that goes off fades out
                found = pg.evaluate(OVERLAP_JS)
                n_rects = max(n_rects, found["n"])
                hits += [(f"{P.reception} {v} frame {i}", *pair) for pair in found["hits"]]
    pg.evaluate("camera.variant('v0')")
    seek(pg, D.key)
    R.check(
        f"{vp(w, h)}: no two pieces of writing overlap (the rings' labels, the plan's texts, the strips, the tables; both receptions; V0 and V1; the reception, the first and the last frame)",
        n_rects > 200 and not hits,
        f"{n_rects} line boxes; overlaps {hits[:3]}",
    )
    targets = pg.evaluate("""() => { const box = (e, name) => { const q = e.getBoundingClientRect(); return [name, +q.width.toFixed(1), +q.height.toFixed(1)]; };
        const out = [...document.querySelectorAll('button:not(.d), input[type=range], summary')].filter(__vis).map(e => box(e, e.id || e.textContent.trim().slice(0, 24)));
        document.querySelectorAll('#rivals .riv .hit').forEach((c, k) => out.push(box(c, 'ring ' + k)));
        document.querySelectorAll('.d').forEach((d, k) => { const r = d.getBoundingClientRect(), a = getComputedStyle(d, '::after'), inset = parseFloat(a.top || '0');
          out.push(['dot ' + k, r.width - 2 * inset, r.height - 2 * inset]); });
        return out; }""")
    under = [t for t in targets if t[1] < TARGET_PX - 0.01 or t[2] < TARGET_PX - 0.01]
    kinds = {t[0].split(" ")[0] for t in targets}
    R.check(
        f"{vp(w, h)}: every button (the pick's two too), the scrubber, every summary, every ring's hit area and every dot's press area (its ::after) at least {TARGET_PX} px each way",
        {"ring", "dot", "play", "scrub", "pick-0", "pick-1"} <= kinds and not under,
        f"{len(targets)} targets ({len([t for t in targets if t[0].startswith('ring')])} rings, {len([t for t in targets if t[0].startswith('dot')])} dots); under: {under[:4]}",
    )
    marks = pg.evaluate(MARKS_JS)
    low = {k: v for k, v in marks["gated"].items() if v < MARK_MIN}
    MEASURED[size].update({"marks": min(marks["gated"].values()), "lines": marks["pitchLines"]})
    R.check(
        f"{vp(w, h)}: the marks that carry meaning at >= {MARK_MIN}:1 against what they lie on (seen discs, rings, the receiver, the frame's edge, the ghosts and live shapes, each group's dots and median, the zero line, the bars)",
        len(marks["gated"]) >= 18 and not low,
        f"{len(marks['gated'])} marks, the least {min(marks['gated'].values()):.2f}; under: {low}; the pitch's lines (the map, not gated) {marks['pitchLines']:.2f}",
    )
    shot(pg, shots, f"{vp(w, h)}_full")
    ctx.close()


@guarded
def check_reduced_motion(D: Data, browser, target: str) -> None:
    """Reduced motion: the page opens the same (paused at the reception) and Play still runs on
    request; the switch still moves the shapes (without the transition)."""
    ctx, pg = open_page(browser, target, reduced=True)
    s = pg.evaluate("camera.state()")
    pg.click("#variant-v1")
    pg.wait_for_timeout(50)
    g = pg.evaluate(SWITCH_JS)
    _, line = D.rows["line_height_m"]
    R.check(
        "reduced motion: opens paused at the reception; the switch moves the line without a transition",
        s["i"] == D.key and not s["playing"] and close(g["line"], line["V1"]["mean"], 0.006),
        f"{json.dumps(s)}; line {g['line']}",
    )
    ctx.close()


def summary() -> None:
    """The per-viewport measures, as one table."""
    print("\nviewport    page_h  fold_end  least mark  pitch lines")
    for size in VIEWPORTS:
        m = MEASURED.get(size)
        if m:
            print(
                f"{vp(*size):<11} {m.get('page_h', '-')!s:>6}  {m.get('fold', '-')!s:>8}  {m.get('marks', float('nan')):>10.2f}  {m.get('lines', float('nan')):>11.2f}"
            )


def main(argv: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("target", nargs="?", default=str(DEFAULT_PAGE))
    parser.add_argument("--shots", type=Path, default=ROOT / "build" / "camera")
    parser.add_argument("--sizes", default=None, help="viewports to run, e.g. 1440x900,390x844")
    args = parser.parse_args(argv[1:])
    target = (
        args.target
        if re.match(r"^https?://", args.target)
        else Path(args.target).resolve().as_uri()
    )
    D, D2 = Data(0), Data(1)
    sizes = [s for s in VIEWPORTS if vp(*s) in args.sizes.split(",")] if args.sizes else VIEWPORTS
    print(f"target: {target}" + (f" (viewports {args.sizes})" if args.sizes else ""), flush=True)
    t0 = time.time()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        check_load(D, browser, target)
        for P in (D, D2):
            check_scene(P, browser, target)
            check_play(P, browser, target)
            check_tap(P, browser, target)
        check_pick(D, browser, target)
        check_dot_tap(D, browser, target)
        check_switch(D, browser, target)
        check_numbers(D, browser, target)
        check_reduced_motion(D, browser, target)
        for size in sizes:
            check_layout(D, browser, target, size, args.shots)
        browser.close()
    n_fail = sum(1 for r in R.rows if not r[0])
    summary()
    print(f"\n{len(R.rows) - n_fail} passed, {n_fail} failed, {time.time() - t0:.0f} s")
    return 0 if R.ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
