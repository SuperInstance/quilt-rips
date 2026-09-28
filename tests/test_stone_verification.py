"""Stone verification pin: quilt-rips demo receipts projected onto a
stone-v1 chain verify UNDER THE CANONICAL VERIFIER (SuperInstance/quilt-stone).

Doctrine: the fleet verifies through stone. quilt-rips' NATIVE chain is its
own local dialect (fnv1a-64, `prev`/`h` link fields, body-subset hashing of
{v,op,i,o,t}) — stone.mjs does not detect it, and this pin says so honestly
instead of pretending. The lane is a PROJECTION: strip the native link fields,
prepend a stone.header row that names the origin and the native dialect, and
re-seal with stone's own sealChain under the stone-v1 forward format. The
projection then verifies (or fails, on tamper) under quilt-stone's
verifyChain — live, by running node against a real checkout.

Checkout-gated: QUILT_STONE_PATH points at a quilt-stone checkout (the dir
containing stone.mjs). Absent checkout or absent node -> skip, never fake
green. Tamper coverage: a payload edit in the projected chain must come back
as ok:false, 'hash mismatch', at the exact edited index.
"""
import json
import os
import shutil
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from quilt_rips import verify_chain  # noqa: E402

STONE_PATH = os.environ.get("QUILT_STONE_PATH", "")
STONE_MJS = os.path.join(STONE_PATH, "stone.mjs") if STONE_PATH else ""

needs_stone = pytest.mark.skipif(
    not (STONE_PATH and os.path.isfile(STONE_MJS))
    or shutil.which("node") is None,
    reason="QUILT_STONE_PATH checkout (or node) absent — abstain, never fake green",
)

# One node program, two modes. Reads the native receipts, strips the native
# link fields, prepends a stone.header that NAMES the native dialect (no
# laundering), seals with stone's sealChain, verifies with stone's verifyChain.
# mode=tamper flips one op payload after sealing; the verdict must name it.
NODE_PROGRAM = """
import { readFileSync } from 'node:fs';
import { sealChain, verifyChain } from %(stone_mjs_json)s;

const mode = process.argv[2];
const rows = readFileSync(process.argv[3], 'utf8').trim().split('\\n').map(JSON.parse);
const ops = rows.map(({ prev, h, ...rest }) => rest);
const header = {
  kind: 'stone.header', alg: 'stone-v1', origin: 'quilt-rips',
  native_dialect: 'fnv1a64-prev-h body-subset {v,op,i,o,t} (local)',
  genesis: 'STONE-GENESIS-1',
};
const chain = sealChain([header, ...ops.map(r => ({ ...r }))], { alg: 'stone-v1' });
if (mode === 'tamper') {
  const body = chain[2];
  body.complex = body.complex === 'alpha' ? 'rips' : 'alpha';
}
console.log(JSON.stringify(verifyChain(chain)));
"""


def _demo_receipts(tmp_path):
    """Run the sealed demo into tmp_path; return the receipts file."""
    out = tmp_path / "out"
    r = subprocess.run(
        [sys.executable, "quilt_rips.py", "demo", str(out)],
        capture_output=True, text=True, timeout=300,
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    )
    assert r.returncode == 0, f"demo failed: {r.stderr[-500:]}"
    receipt = out / "receipts.jsonl"
    assert receipt.is_file()
    return receipt


def _run_stone(mode, receipt, tmp_path):
    prog = tmp_path / "stone_project.mjs"
    prog.write_text(NODE_PROGRAM % {"stone_mjs_json": json.dumps(STONE_MJS)})
    r = subprocess.run(["node", str(prog), mode, str(receipt)],
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, f"node projection failed: {r.stderr[-500:]}"
    return json.loads(r.stdout.strip().splitlines()[-1])


@needs_stone
class TestStoneVerification:
    def test_native_chain_ground_truth(self, tmp_path):
        """The native chain replays under the kernel's own verify_chain."""
        receipt = _demo_receipts(tmp_path)
        assert verify_chain(str(receipt)) is True

    def test_projection_verifies_under_stone(self, tmp_path):
        """stone-v1 projection of the demo receipts verifies ok under
        quilt-stone's canonical verifyChain — live from the checkout."""
        receipt = _demo_receipts(tmp_path)
        v = _run_stone("clean", receipt, tmp_path)
        assert v["ok"] is True, f"stone rejected the projection: {v}"
        assert v["alg"] == "stone-v1"
        assert v["links"] >= 5  # header + BIND/LINK/EFFECT/VIEW/TICK

    def test_projection_header_names_origin_and_dialect(self, tmp_path):
        """Honesty pin: the projection's header row names quilt-rips as
        origin and records the native dialect — the dialect difference is
        declared, never laundered into a silent stone claim."""
        receipt = _demo_receipts(tmp_path)
        v = _run_stone("clean", receipt, tmp_path)
        assert v["ok"] is True
        # re-derive the projection and inspect its header directly
        r = subprocess.run(
            ["node", "-e",
             "import('node:fs').then(async fs => {"
             " const s = await import(" + json.dumps(STONE_MJS) + ");"
             " const rows = fs.readFileSync(process.argv[1], 'utf8').trim()"
             " .split('\\n').map(JSON.parse);"
             " const ops = rows.map(({prev, h, ...rest}) => rest);"
             " const header = {kind: 'stone.header', alg: 'stone-v1',"
             "  origin: 'quilt-rips',"
             "  native_dialect: 'fnv1a64-prev-h body-subset {v,op,i,o,t} (local)',"
             "  genesis: 'STONE-GENESIS-1'};"
             " const c = s.sealChain([header, ...ops], {alg: 'stone-v1'});"
             " console.log(JSON.stringify(c[0]));"
             " })", str(receipt)],
            capture_output=True, text=True, timeout=120)
        assert r.returncode == 0, r.stderr[-500:]
        header = json.loads(r.stdout.strip().splitlines()[-1])
        assert header["origin"] == "quilt-rips"
        assert "fnv1a64" in header["native_dialect"]

    def test_tamper_named_by_stone(self, tmp_path):
        """A one-field payload edit in the projected chain fails under
        quilt-stone with 'hash mismatch' at the exact edited index."""
        receipt = _demo_receipts(tmp_path)
        v = _run_stone("tamper", receipt, tmp_path)
        assert v["ok"] is False
        assert v["why"] == "hash mismatch"
        assert v["firstBadIndex"] == 2  # header(0) BIND(1) LINK(2) — edited row
