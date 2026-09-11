"""Download verified public FlyEM data and build a compact, signed connectome.

Adapted from fruitflydev/flycoinrh's MIT-licensed build_graph.py. The public
dataset is separately CC BY 4.0; see NOTICE. No data is invented if unavailable.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import time
import urllib.request

import numpy as np
import scipy.sparse as sp

BASE = "https://storage.googleapis.com/flyem-male-cns/v1.0/connectome-data/flat-connectome/"
FILES = {
    "annotations.feather": ("body-annotations-male-cns-v1.0-minconf-0.5.feather", "50a7718770c57220f160ba4f431ab89e"),
    "neurotransmitters.feather": ("body-neurotransmitters-male-cns-v1.0.feather", "3d842b12fe5c49eefade528d7dd24a1f"),
    "weights.feather": ("connectome-weights-male-cns-v1.0-minconf-0.5-traced-only.feather", "6601d4ad0afa99fd03eb087965ef2423"),
}
SIGN = {"acetylcholine": 1, "gaba": -1, "glutamate": -1, "histamine": -1}


def digest(path: Path, algorithm="md5") -> str:
    h = hashlib.new(algorithm)
    with path.open("rb") as src:
        for block in iter(lambda: src.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def download(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for local, (remote, expected_md5) in FILES.items():
        dest = directory / local
        if dest.exists() and digest(dest) == expected_md5:
            print(f"Verified existing {local}", flush=True)
            continue
        temporary = dest.with_suffix(".partial")
        print(f"Downloading {remote}", flush=True)
        request = urllib.request.Request(BASE + remote, headers={"User-Agent": "Frankenfly/0.1"})
        with urllib.request.urlopen(request, timeout=90) as response, temporary.open("wb") as target:
            total = int(response.headers.get("Content-Length", "0"))
            count, last = 0, time.monotonic()
            while block := response.read(4 * 1024 * 1024):
                target.write(block)
                count += len(block)
                if time.monotonic() - last > 10:
                    print(f"  {count / 1e6:.0f} / {total / 1e6:.0f} MB", flush=True)
                    last = time.monotonic()
        if digest(temporary) != expected_md5:
            temporary.unlink(missing_ok=True)
            raise RuntimeError(f"Checksum mismatch for {remote}; file rejected")
        temporary.replace(dest)


def build(directory: Path) -> dict:
    import pandas as pd
    import pyarrow as pa
    import pyarrow.ipc as ipc

    for name, (_, expected) in FILES.items():
        if not (directory / name).exists() or digest(directory / name) != expected:
            raise RuntimeError(f"Missing or unverified source: {name}. Run prepare with download enabled.")
    ann = pd.read_feather(directory / "annotations.feather").drop_duplicates("bodyId").set_index("bodyId")
    keep = (ann.status == "Traced") & (ann.statusLabel != "Glia")
    bodies = np.sort(ann.index[keep].to_numpy(dtype=np.int64))
    ann = ann.reindex(bodies)
    types = ann["type"].fillna(ann["flywireType"]).fillna(ann["instance"]).fillna("").to_numpy(dtype=str)
    nt = pd.read_feather(directory / "neurotransmitters.feather")
    nt = nt.dropna(subset=["body"]).drop_duplicates("body").set_index("body")["consensus_nt"]
    neurotransmitters = nt.reindex(bodies).fillna("unknown").str.lower().to_numpy(dtype=str)
    signs = np.array([SIGN.get(value, 0) for value in neurotransmitters], np.float32)
    n = len(bodies)
    rows, cols, values = [], [], []
    print(f"Building graph for {n:,} traced neurons (streamed record batches)", flush=True)
    # Map segment IDs by sorted lookup. Never allocate a bitmap indexed by the
    # largest EM body ID, which can be arbitrarily larger than the neuron count.
    with pa.memory_map(str(directory / "weights.feather"), "r") as source:
        reader = ipc.open_file(source)
        for i in range(reader.num_record_batches):
            batch = reader.get_batch(i)
            pre = batch.column("body_pre").to_numpy()
            post = batch.column("body_post").to_numpy()
            weight = batch.column("weight").to_numpy()
            p, q = np.searchsorted(bodies, pre), np.searchsorted(bodies, post)
            p_safe, q_safe = np.minimum(p, n - 1), np.minimum(q, n - 1)
            valid = (p < n) & (q < n) & (bodies[p_safe] == pre) & (bodies[q_safe] == post)
            valid &= (weight >= 3) & (signs[p_safe] != 0)
            rows.append(q[valid].astype(np.int32))
            cols.append(p[valid].astype(np.int32))
            values.append((weight[valid] * .275 * signs[p[valid]]).astype(np.float32))
    w = sp.csc_matrix((np.concatenate(values), (np.concatenate(rows), np.concatenate(cols))), shape=(n, n), dtype=np.float32)
    w.sum_duplicates()
    del rows, cols, values
    xyz = np.full((n, 3), np.nan, np.float32)
    for i, value in enumerate(ann.somaLocation):
        if isinstance(value, (list, tuple, np.ndarray)) and len(value) == 3:
            xyz[i] = value
    payload = {
        "data": w.data, "indices": w.indices, "indptr": w.indptr,
        "bodies": bodies, "types": types, "nt": neurotransmitters,
        "side": ann.somaSide.fillna("").to_numpy(dtype=str),
        "hex1": ann.assignedOlHex1.to_numpy(dtype=np.float32),
        "hex2": ann.assignedOlHex2.to_numpy(dtype=np.float32), "xyz": xyz,
    }
    temp = directory / "connectome.partial.npz"
    np.savez_compressed(temp, **payload)
    temp.replace(directory / "connectome.npz")
    manifest = {
        "dataset": "FlyEM male CNS v1.0", "neurons": n, "edges": int(w.nnz),
        "format": "CSC: column=presynaptic, row=postsynaptic", "min_synapses": 3,
        "mv_per_synapse": .275, "graph_sha256": digest(directory / "connectome.npz", "sha256"),
        "sources": [{"url": BASE + remote, "md5": md5} for remote, md5 in FILES.values()],
        "license": "CC BY 4.0", "built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2), flush=True)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path(os.environ.get("FRANKENFLY_DATA_DIR", "data")))
    parser.add_argument("--no-download", action="store_true")
    args = parser.parse_args()
    if not args.no_download:
        download(args.data_dir)
    build(args.data_dir)


if __name__ == "__main__":
    main()
