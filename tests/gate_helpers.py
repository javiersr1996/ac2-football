"""Synthetic silver under the ids of the real split, and throwaway git checkouts.

The base's synthetic match is written twice, under the id of a calibration match and of a
held-out match of ``protocol/split.json``, and built by the base's own CLI into one data dir.
So the gate is tested on silver files it could open and must refuse, and never on real data.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import shutil
import subprocess
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path

from ftbase.cli import main as ftbase_main
from ftbase.fixtures import PlantedRun, write_synthetic_match

from ac2fb.protocol import data

ROOT = Path(__file__).resolve().parent.parent
CAL, HELD = 1874553, 1899585  # the first id of each set in protocol/split.json
READS = ("layer2",)  # the reads of a throwaway layer2.json: the commands of ac2fb.cli
# What the freeze covers, in the order of `git ls-tree`, written out here so a test never
# borrows the constant it checks: `src` whole and the three files that pin what runs it.
GUARDED = (".python-version", "pyproject.toml", "src", "uv.lock")
# A file of each kind that reaches the frozen code; the checkout holds every one of them.
FROZEN_FILES = (
    ".python-version",
    "pyproject.toml",
    "uv.lock",
    "src/ac2fb/cli.py",
    "src/ac2fb/protocol/data.py",
    "src/ac2fb/defence/__init__.py",
    "src/ac2fb/reliability/__init__.py",
)
POISON = b"not a parquet file: a held-out file was opened\n"


def build_silver_pair(root: Path) -> Path:
    """Silver for two synthetic matches, ``CAL`` and ``HELD``; returns its data dir."""
    fx = root / "fx"
    listed: list[object] = []
    files: list[dict[str, object]] = []
    for match_id, seed in ((CAL, 1), (HELD, 2)):
        match = write_synthetic_match(fx, match_id=match_id, seed=seed)
        listed += json.loads((match.root / "data" / "matches.json").read_bytes())
        manifest = json.loads(match.manifest.read_bytes())
        files += [f for f in manifest["sources"][0]["files"] if f["role"] != "matches"]
    # Each call wrote matches.json and the manifest for its own match only: merge the two.
    body = json.dumps(listed).encode("utf-8")
    (match.root / "data" / "matches.json").write_bytes(body)
    digest = hashlib.sha256(body).hexdigest()
    files.append(
        {"path": "data/matches.json", "bytes": len(body), "sha256": digest}
        | {"lfs": False, "role": "matches", "match_id": None}
    )
    manifest["sources"][0]["files"] = files
    match.manifest.write_bytes((json.dumps(manifest, indent=2) + "\n").encode("utf-8"))

    data = root / "data"
    args = ["--manifest", str(match.manifest), "--data-dir", str(data)]
    assert ftbase_main(["ingest", *args, "--from-existing", str(match.root)]) == 0
    assert ftbase_main(["bronze", *args]) == 0
    assert ftbase_main(["silver", *args]) == 0
    return data


def poisoned_copy(data: Path, dest: Path) -> Path:
    """A copy of ``data`` where every per-match file of ``HELD`` is garbage.

    A route that opens one of them fails loudly instead of returning held-out rows.
    """
    shutil.copytree(data, dest)
    poisoned = list(dest.rglob(f"{HELD}.parquet"))
    assert len(poisoned) >= 2, "silver frames and events of HELD must be among them"
    for path in poisoned:
        path.write_bytes(POISON)
    return dest


@dataclass(frozen=True)
class Checkout:
    """A small git repository laid out like this one, for the guard to judge."""

    root: Path

    def git(self, *args: str) -> str:
        done = subprocess.run(["git", "-C", str(self.root), *args], capture_output=True, check=True)
        return done.stdout.decode("utf-8")

    def write(self, rel: str, text: str) -> None:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode("utf-8"))  # bytes: LF on every platform

    def commit(self, message: str = "step") -> None:
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)

    def tree_sha(self) -> str:
        """The documented definition, computed here with git alone."""
        listing = subprocess.run(
            ["git", "-C", str(self.root), "ls-tree", "HEAD", "--", *GUARDED],
            capture_output=True,
            check=True,
        ).stdout
        assert listing.count(b"\n") == len(GUARDED)
        return hashlib.sha256(listing).hexdigest()

    def set_protocol(self, stage: str) -> None:
        """``protocol/protocol.json`` (layer 3) in ``stage``, committed."""
        body = {"stage": stage, "code_tree_sha": None}
        self.write("protocol/protocol.json", json.dumps(body, indent=2) + "\n")
        self.commit(f"protocol to {stage}")

    def set_layer2(
        self, stage: str, code_tree_sha: str | None, reads: Sequence[str] = READS, **extra: object
    ) -> None:
        """``protocol/layer2.json`` in ``stage``, committed."""
        body = {"stage": stage, "code_tree_sha": code_tree_sha, "reads": list(reads), **extra}
        self.write("protocol/layer2.json", json.dumps(body, indent=2) + "\n")
        self.commit(f"layer2 to {stage}")

    def freeze(self, stage: str = "frozen", reads: Sequence[str] = READS) -> None:
        """``layer2.json`` frozen on the code at HEAD; in ``read``, with the record of a reading."""
        extra: dict[str, object] = {}
        if stage == "read":
            heldout = json.loads((self.root / "protocol" / "split.json").read_bytes())["heldout"]
            frozen = self.git("rev-parse", "HEAD").strip()
            extra["reading"] = {"frozen_commit": frozen, "heldout": heldout, "date": "2026-01-01"}
        self.set_layer2(stage, self.tree_sha(), reads, **extra)


@contextlib.contextmanager
def inside_the_reading() -> Iterator[None]:
    """What only ``read_heldout`` does in the package: serve the held-out while it runs."""
    token = data._READING.set(True)
    try:
        yield
    finally:
        data._READING.reset(token)


def make_checkout(root: Path) -> Checkout:
    """A checkout with layer 3 dead and ``layer2.json`` in ``design``, the real split and every
    frozen file."""
    checkout = Checkout(root)
    root.mkdir(parents=True)
    checkout.git("init", "-q")
    for key, value in (
        ("user.name", "gate test"),
        ("user.email", "gate@test.invalid"),
        ("core.autocrlf", "false"),
        ("commit.gpgsign", "false"),
    ):
        checkout.git("config", key, value)
    checkout.write("protocol/split.json", (ROOT / "protocol" / "split.json").read_text("utf-8"))
    checkout.write("protocol/protocol.json", '{"stage": "dead", "code_tree_sha": null}\n')
    checkout.write(
        "protocol/layer2.json",
        json.dumps({"stage": "design", "code_tree_sha": None, "reads": list(READS)}) + "\n",
    )
    for path in FROZEN_FILES:
        checkout.write(path, f"# {path}\n")
    checkout.write("README.md", "throwaway checkout for the gate tests\n")
    checkout.commit("start")
    return checkout


def build_one(root: Path, *, match_id: int, seed: int, runs: Sequence[PlantedRun]) -> Path:
    """Silver for one synthetic match with the given planted runs; returns its data dir.

    ``match_id`` may be any id: the base's own readers do not know the split.
    """
    match = write_synthetic_match(root / "fx", match_id=match_id, seed=seed, runs=runs)
    data = root / "data"
    args = ["--manifest", str(match.manifest), "--data-dir", str(data)]
    assert ftbase_main(["ingest", *args, "--from-existing", str(match.root)]) == 0
    assert ftbase_main(["bronze", *args]) == 0
    assert ftbase_main(["silver", *args]) == 0
    return data
