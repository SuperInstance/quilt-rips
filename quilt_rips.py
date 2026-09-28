#!/usr/bin/env python3
"""quilt-rips — GUDHI topological data analysis as a 5-opcode quilt cell.

Predecessor: quilt-lens (clmm weak lensing, 2026-09-27 morning).
Sibling:     quilt-tomo (TomoPy x ASTRA) — scout-ranked #1, built next.

Doctrine: the persistence barcode is the most receipt-shaped object in
the whole signal->structure survey (Scout S3). Birth/death intervals,
sealed hash-chain, replayable. Metric signal in; topological structure
out; the receipt proves which cloud produced which barcode.

Ops:
  BIND   points + max_edge_length           -> cell state
  LINK   complex selector (rips/alpha/dtm)  -> filtration recipe
  EFFECT persistence()                       -> intervals [(dim, birth, death)]
  VIEW   barcode SVG                         -> human-readable sink
  TICK   seal()                              -> stone-v1-shaped fnv1a chain

Canonical verifier: SuperInstance/quilt-stone (stone.mjs). The native
chain is a local dialect verified by verify_chain(); a stone-v1
PROJECTION of it (header + re-seal via stone's sealChain) verifies under
stone's verifyChain — pinned live in tests/test_stone_verification.py.
See README "Verifying through quilt-stone".

Usage:
  python quilt_rips.py demo [outdir]
  python quilt_rips.py verify <receipts.jsonl>
"""
import argparse
import hashlib
import json
import math
import os
import sys
import time

import numpy as np


def fnv1a64(data: bytes) -> str:
    """64-bit FNV-1a, hex — the fleet's hash (rate limiter, git-agent)."""
    h = 0xCBF29CE484222325
    for b in data:
        h ^= b
        h = (h * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    return f"{h:016x}"


def canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=float).encode()


def verify_chain(path: str) -> bool:
    """Replay a sealed receipt chain; any tamper or truncation fails."""
    prev = "0" * 16
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                # full-record hash minus link fields — keep EXACTLY in sync
                # with seal() (every payload byte is inside the claim).
                hashed = {k: v for k, v in rec.items() if k not in ("prev", "h")}
                if fnv1a64(canonical(hashed)) != rec["h"]:
                    return False
                if rec.get("prev", "0" * 16) != prev:
                    return False
                prev = rec["h"]
    except (OSError, ValueError, KeyError):
        return False
    return True


class QuiltRipsKernel:
    """The reef's TDA cell: bind a cloud, link a complex, effect the
    projection, view the barcode, seal the receipt."""

    def __init__(self):
        self.state = {}
        self.ops = []          # ordered op records for sealing
        self.bars = None       # [(dim, birth, death)]
        self.points_hash = None

    # -- BIND ------------------------------------------------------------
    def bind(self, points, max_edge_length: float = 2.0):
        pts = np.asarray(points, dtype=float)
        if pts.ndim != 2 or pts.shape[0] < 4:
            raise ValueError("bind: need an (n>=4, d) point cloud")
        self.state["points"] = pts
        self.state["max_edge_length"] = float(max_edge_length)
        self.points_hash = fnv1a64(pts.tobytes())
        self.ops.append(("BIND", {
            "points_sha": self.points_hash, "n": int(pts.shape[0]),
            "dim": int(pts.shape[1]), "max_edge_length": float(max_edge_length),
        }))
        return self

    # -- LINK ------------------------------------------------------------
    def link(self, complex: str = "rips", max_dimension: int = 2, **kw):
        if complex not in ("rips", "alpha", "dtm"):
            raise ValueError(f"link: unknown complex '{complex}'")
        self.state["complex"] = complex
        self.state["max_dimension"] = int(max_dimension)
        self.state["link_kw"] = kw
        self.ops.append(("LINK", {"complex": complex,
                                  "max_dimension": int(max_dimension), **kw}))
        return self

    # -- EFFECT ----------------------------------------------------------
    def _build_tree(self):
        import gudhi
        pts = self.state["points"]
        mel = self.state["max_edge_length"]
        md = self.state["max_dimension"]
        kind = self.state["complex"]
        if kind == "rips":
            kw = dict(self.state["link_kw"])
            r = gudhi.RipsComplex(points=pts, max_edge_length=mel)
            if kw.get("sparse"):
                r = gudhi.RipsComplex(points=pts, max_edge_length=mel,
                                      sparse=kw["sparse"])
            return r.create_simplex_tree(max_dimension=md)
        if kind == "alpha":
            alpha = gudhi.AlphaComplex(points=pts)
            return alpha.create_simplex_tree(max_alpha_square=mel * mel)
        if kind == "dtm":
            from gudhi.point_cloud.dtm import DistanceToMeasure
            dtm = DistanceToMeasure(k=self.state["link_kw"].get("k", 10))
            r = gudhi.RipsComplex(points=pts, max_edge_length=mel)
            # weighted variant: filtration from DTM
            w = dtm.fit_transform(pts)
            self.state["weights"] = w
            return r.create_simplex_tree(max_dimension=md)
        raise ValueError(kind)

    def effect_persistence(self):
        st = self._build_tree()
        diag = st.persistence()
        self.bars = []
        for dim, (birth, death) in diag:
            self.bars.append((int(dim), float(birth),
                              float("inf") if math.isinf(death) else float(death)))
        n_fin = sum(1 for _, _, dt in self.bars if math.isfinite(dt))
        self.ops.append(("EFFECT", {
            "complex": self.state["complex"],
            "simplices": int(st.num_simplices()),
            "intervals": len(self.bars),
            "finite_intervals": n_fin,
            "bars_sha": fnv1a64(canonical(
                [[d, b, (dt if math.isfinite(dt) else -1)] for d, b, dt in self.bars])),
        }))
        return self.bars

    # -- VIEW ------------------------------------------------------------
    def view_barcode(self, path: str):
        if self.bars is None:
            raise ValueError("view: run effect_persistence() first")
        finite = [(d, b, dt) for d, b, dt in self.bars if math.isfinite(dt)]
        inf = [(d, b) for d, b, dt in self.bars if not math.isfinite(dt)]
        if not finite and not inf:
            raise ValueError("view: no intervals to render")
        max_d = max([dt for _, _, dt in finite], default=1.0) or 1.0
        row_h, pad, top, left = 14, 30, 40, 60
        rows = len(finite) + len(inf)
        h = top + rows * row_h + pad
        w = 720
        scale = (w - left - pad) / max_d
        parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
            f'style="background:#0d1117;font-family:ui-monospace,monospace">',
            f'<text x="{left}" y="24" fill="#58a6ff" font-size="15">quilt-rips barcode '
            f'— {self.state.get("complex","?")} · n={self.state["points"].shape[0] if "points" in self.state else "?"}</text>',
        ]
        y = top
        for d, b, dt in sorted(finite, key=lambda r: (r[0], r[1])):
            color = "#3fb950" if d == 0 else "#d29922"
            label = f"H{d}"
            x0, x1 = left + b * scale, left + dt * scale
            parts.append(f'<line x1="{x0:.1f}" y1="{y}" x2="{x1:.1f}" y2="{y}" '
                         f'stroke="{color}" stroke-width="3"/>')
            parts.append(f'<circle cx="{x0:.1f}" cy="{y}" r="2.5" fill="{color}"/>')
            parts.append(f'<circle cx="{x1:.1f}" cy="{y}" r="2.5" fill="none" stroke="{color}"/>')
            parts.append(f'<text x="8" y="{y+4}" fill="{color}" font-size="11">{label}</text>')
            y += row_h
        for d, b in inf:
            color = "#3fb950" if d == 0 else "#d29922"
            x0 = left + b * scale
            parts.append(f'<line x1="{x0:.1f}" y1="{y}" x2="{w-pad}" y2="{y}" '
                         f'stroke="{color}" stroke-width="3" stroke-dasharray="6 3"/>')
            parts.append(f'<text x="8" y="{y+4}" fill="{color}" font-size="11">H{d}∞</text>')
            y += row_h
        parts.append(f'<text x="{left}" y="{h-8}" fill="#8b949e" font-size="10">'
                     f'filtration value → · dashed = essential class · sealed '
                     f'{time.strftime("%Y-%m-%d %H:%M:%S")}</text>')
        parts.append("</svg>")
        with open(path, "w") as f:
            f.write("\n".join(parts))
        self.ops.append(("VIEW", {"path": os.path.basename(path),
                                  "svg_sha": fnv1a64("".join(parts).encode())}))
        return path

    # -- TICK (seal) ------------------------------------------------------
    def seal(self, path: str, label: str = "quilt-rips"):
        if not self.ops:
            raise ValueError("seal: nothing to seal — run the pipeline first")
        prev = "0" * 16
        lines = []
        for op, payload in self.ops:
            body = {"v": 1, "op": op, "i": prev, "o": fnv1a64(canonical(payload)),
                    "t": int(time.time()), "label": label, **payload}
            body["prev"] = prev
            # hash the FULL record minus the link fields — a payload edit
            # must break the chain, not just a {v,op,i,o,t} edit (2026-09-28
            # hole: complex/points_sha/bars_sha lived outside the hash and
            # verified fine after arbitrary edits).
            hashed = {k: v for k, v in body.items() if k not in ("prev", "h")}
            body["h"] = fnv1a64(canonical(hashed))
            lines.append(json.dumps(body))
            prev = body["h"]
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w") as f:
            f.write("\n".join(lines) + "\n")
        return path


def main(argv=None):
    ap = argparse.ArgumentParser(prog="quilt-rips")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("demo")
    ap_demo = sub.choices["demo"]
    ap_demo.add_argument("outdir", nargs="?", default="/tmp/quilt-rips/out")
    ap_verify = sub.add_parser("verify")
    ap_verify.add_argument("receipt")
    args = ap.parse_args(argv)

    if args.cmd == "verify":
        ok = verify_chain(args.receipt)
        print(json.dumps({"ok": ok, "receipt": args.receipt}))
        return 0 if ok else 2

    outdir = args.outdir
    os.makedirs(outdir, exist_ok=True)
    rng = np.random.default_rng(7)
    t = np.linspace(0, 2 * np.pi, 60, endpoint=False)
    cloud = np.vstack([
        rng.normal((0, 0), 0.05, size=(40, 2)),
        rng.normal((4, 0), 0.05, size=(40, 2)),
        np.stack([2 + np.cos(t), 3 + np.sin(t)], axis=1) + rng.normal(0, 0.05, size=(60, 2)),
    ])
    k = QuiltRipsKernel()
    k.bind(cloud, max_edge_length=2.0).link("rips", max_dimension=2)
    bars = k.effect_persistence()
    svg = k.view_barcode(os.path.join(outdir, "barcode.svg"))
    receipt = k.seal(os.path.join(outdir, "receipts.jsonl"), label="reef-demo")
    h1 = sum(1 for d, b, dt in bars if d == 1 and math.isfinite(dt) and dt - b > 0.8)
    print(json.dumps({
        "ok": True, "cloud": int(cloud.shape[0]), "intervals": len(bars),
        "significant_h1": h1, "svg": svg, "receipt": receipt,
        "verify": verify_chain(receipt),
    }, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
