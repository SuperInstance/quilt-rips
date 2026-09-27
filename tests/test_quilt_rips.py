"""FAIL-first tests for quilt-rips: GUDHI TDA as a 5-opcode quilt cell.

Doctrine: bind the cloud, link the complex, effect the projection
(metric signal -> topological structure), view the barcode, seal the
receipt. Persistence pairs ARE the receipt-shaped object: birth/death
intervals, hash-chained, replayable.
"""
import json
import os
import subprocess
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from quilt_rips import QuiltRipsKernel, fnv1a64, verify_chain


def synthetic_reef(rng, n_blob=40, n_circle=60, noise=0.05):
    """Two dense blobs + one circle: H0 top-2 + exactly one significant H1."""
    a = rng.normal((0, 0), noise, size=(n_blob, 2))
    b = rng.normal((4, 0), noise, size=(n_blob, 2))
    t = np.linspace(0, 2 * np.pi, n_circle, endpoint=False)
    c = np.stack([2 + np.cos(t), 3 + np.sin(t)], axis=1) + rng.normal(0, noise, size=(n_circle, 2))
    return np.vstack([a, b, c])


class TestOpcodes:
    def test_bind_links_state(self, tmp_path):
        rng = np.random.default_rng(7)
        k = QuiltRipsKernel()
        k.bind(synthetic_reef(rng), max_edge_length=2.0)
        k.link("rips", max_dimension=2)
        assert k.state["max_edge_length"] == 2.0
        assert k.state["complex"] == "rips"

    def test_effect_returns_intervals(self):
        rng = np.random.default_rng(7)
        k = QuiltRipsKernel()
        k.bind(synthetic_reef(rng), max_edge_length=2.0)
        k.link("rips", max_dimension=2)
        bars = k.effect_persistence()
        dims = {d for d, _, _ in bars}
        assert 0 in dims and 1 in dims

    def test_reef_topology_recovered(self):
        """Two blobs -> 2 dominant H0 bars; one circle -> exactly 1 significant H1."""
        rng = np.random.default_rng(7)
        k = QuiltRipsKernel()
        k.bind(synthetic_reef(rng), max_edge_length=2.0)
        k.link("rips", max_dimension=2)
        bars = k.effect_persistence()
        h0 = sorted([death - birth for d, birth, death in bars if d == 0], reverse=True)
        h1 = [(birth, death) for d, birth, death in bars if d == 1 and np.isfinite(death)]
        assert len(h0) >= 2
        assert h0[0] > 1.5 and h0[1] > 1.5, f"two blobs should give two long H0 bars: {h0[:4]}"
        sig_h1 = [p for p in h1 if p[1] - p[0] > 0.8]
        assert len(sig_h1) == 1, f"circle should give exactly one significant H1: {h1}"

    def test_view_barcode_svg(self, tmp_path):
        rng = np.random.default_rng(7)
        k = QuiltRipsKernel()
        k.bind(synthetic_reef(rng), max_edge_length=2.0)
        k.link("rips", max_dimension=2)
        k.effect_persistence()
        out = tmp_path / "barcode.svg"
        k.view_barcode(str(out))
        text = out.read_text()
        assert "<svg" in text and "H1" in text


class TestReceipts:
    def test_seal_produces_verifying_chain(self, tmp_path):
        rng = np.random.default_rng(7)
        k = QuiltRipsKernel()
        k.bind(synthetic_reef(rng), max_edge_length=2.0)
        k.link("rips", max_dimension=2)
        k.effect_persistence()
        k.view_barcode(str(tmp_path / "barcode.svg"))
        receipt = tmp_path / "receipts.jsonl"
        k.seal(str(receipt), label="reef-demo")
        assert verify_chain(str(receipt)), "sealed chain must verify"

    def test_chain_tamper_detected(self, tmp_path):
        rng = np.random.default_rng(7)
        k = QuiltRipsKernel()
        k.bind(synthetic_reef(rng), max_edge_length=2.0)
        k.link("rips", max_dimension=2)
        k.effect_persistence()
        receipt = tmp_path / "receipts.jsonl"
        k.seal(str(receipt), label="tamper-test")
        lines = receipt.read_text().splitlines()
        rec = json.loads(lines[0])
        rec["o"] = "deadbeef"
        lines[0] = json.dumps(rec)
        receipt.write_text("\n".join(lines) + "\n")
        assert not verify_chain(str(receipt)), "tampered chain must fail"

    def test_ops_recorded_in_order(self, tmp_path):
        rng = np.random.default_rng(7)
        k = QuiltRipsKernel()
        k.bind(synthetic_reef(rng), max_edge_length=2.0)
        k.link("rips", max_dimension=2)
        k.effect_persistence()
        receipt = tmp_path / "receipts.jsonl"
        k.seal(str(receipt), label="order-test")
        ops = [json.loads(l)["op"] for l in receipt.read_text().splitlines()]
        assert ops == ["BIND", "LINK", "EFFECT"], f"opcode order: {ops}"

    def test_replay_determinism(self, tmp_path):
        """Same seed -> same persistence -> same output hashes."""
        def run():
            rng = np.random.default_rng(11)
            k = QuiltRipsKernel()
            k.bind(synthetic_reef(rng), max_edge_length=2.0)
            k.link("rips", max_dimension=2)
            bars = k.effect_persistence()
            return fnv1a64(json.dumps(sorted(bars), default=float).__repr__().encode())
        assert run() == run()


def test_cli_verify_roundtrip(tmp_path):
    rng = np.random.default_rng(7)
    k = QuiltRipsKernel()
    k.bind(synthetic_reef(rng), max_edge_length=2.0)
    k.link("rips", max_dimension=2)
    k.effect_persistence()
    receipt = tmp_path / "receipts.jsonl"
    k.seal(str(receipt), label="cli-test")
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    r = subprocess.run(
        [sys.executable, os.path.join(here, "quilt_rips.py"), "verify", str(receipt)],
        capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
