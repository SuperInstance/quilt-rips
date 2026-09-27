# quilt-rips

**Topological data analysis as a 5-opcode quilt cell.** GUDHI's persistence
pipeline — the survey's "most stone-v1-shaped object" — wrapped with
hash-chained receipts so every barcode can be replayed to its cloud.

Predecessor: [quilt-lens](https://github.com/SuperInstance/quilt-lens)
(clmm weak lensing, same afternoon).
Sibling next: quilt-tomo (TomoPy × ASTRA, scout-ranked #1).
Scout source: Cocapn discovery wave S3, 2026-09-27.

## Why

Weak lensing asks: *what invisible mass bends this light?* TDA asks the
same question one abstraction up: *what invisible structure persists in
this point cloud?* Both are signal→structure projections. Both deserve
receipts. The persistence barcode — birth/death intervals per homology
dimension — is already shaped like a ledger. We just seal it.

## The five opcodes

| Op | Here | Meaning |
|----|------|---------|
| BIND | `bind(points, max_edge_length)` | the cloud enters the cell |
| LINK | `link("rips", max_dimension=2)` | filtration recipe (rips/alpha/dtm) |
| EFFECT | `effect_persistence()` | projection: metric → topology |
| VIEW | `view_barcode(path)` | barcode SVG (essential classes dashed) |
| TICK | `seal(path)` | fnv1a-64 chain over ops, tamper-evident |

## Quickstart

```bash
pip install gudhi numpy pytest
python -m pytest tests/ -q          # 9 tests, topology ground-truth guarded
python quilt_rips.py demo out       # two blobs + a circle → sealed demo
python quilt_rips.py verify out/receipts.jsonl
```

The demo cloud (2 dense blobs + 1 noisy circle) is a topology ground
truth: the barcode must show exactly **2 long H0 bars** and exactly
**1 significant H1 bar**. The tests assert this — a green suite means
the cell recovers shape, not just runs.

## Receipts

`seal()` writes stone-v1-shaped JSONL: each op's payload hashed with
64-bit FNV-1a, chained `prev → h`. `verify_chain()` replays it; any
edited byte, wrong order, or truncation fails. The receipt above the
fold of every artifact:

```json
{"v":1,"op":"BIND","i":"0000000000000000","o":"6ade81d53fc99f54","t":...,"points_sha":"89c921cc51d72d86","n":140,"dim":2,"max_edge_length":2.0,"prev":"...","h":"..."}
```

## Honest limits

- `dtm` link path computes weights but applies the plain Rips filtration
  (weighted simplex trees are not exposed uniformly across GUDHI builds).
  Flagged, not hidden.
- Alpha complex ignores `max_edge_length` (it uses `max_alpha_square` =
  mel²) — an approximation by design.
- Receipts are integrity, not secrecy: fnv1a is the fleet's checksum
  habit, not a signature. Same honesty as pong-quilt's ledger.

## Doctrine line

> The barcode is the receipt; the cloud is the claim; `verify_chain()`
> is the argument that they still agree.

— kimi1, cell simzero, 2026-09-27
