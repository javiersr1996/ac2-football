"""The layer 2 commands that the single reading of the held-out runs (``ac2fb heldout read``).

:func:`ac2fb.protocol.data.read_heldout` takes its commands from :data:`LAYER2_READS` and from
nowhere else, by the names ``protocol/layer2.json`` lists, so no caller can hand it a function
of its own (one of layer 3, say) to run while the held-out is served.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from ac2fb.protocol.data import Command
from ac2fb.reliability import amputate, table
from ac2fb.reliability.report import layer2_report, write_report

__all__ = ["LAYER2_READS"]


def _layer2_artifacts(match_ids: list[int], reports_dir: Path) -> Path:
    """The ``layer2`` command as a command of the reading: its report, ``layer2.json``.

    The long Parquet stays out: no artefact reads it, and it would be written under ``data/``,
    outside the staging directory, next to the calibration's.
    """
    return write_report(layer2_report(match_ids), reports_dir)


# The layer 2 commands the reading may run, by the names protocol/layer2.json lists.
LAYER2_READS: Mapping[str, Command] = {
    "layer2": _layer2_artifacts,
    "reliability": table.write_table,
    "amputation": amputate.write_table,
}
