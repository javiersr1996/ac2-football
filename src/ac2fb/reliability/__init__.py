"""Layer 2: reliability of the tracking data.

The public API for reusing it on your own silver (``examples/sensitivity.py`` runs it end to
end on a synthetic match). Every name below is in the ``__all__`` of its module, and
``tests/test_public_api.py`` resolves each one, so this list cannot name what is gone. The
package itself re-exports nothing: ``amputate`` and ``sensitivity`` are each a module and its
main function, so a flat re-export would shadow the module.

1. Read the silver through the guarded door, :mod:`ac2fb.protocol.data`:
   ``ac2fb.protocol.data.read_frames``, ``ac2fb.protocol.data.read_events`` and
   ``ac2fb.protocol.data.read_dim``. They refuse the held-out matches of ``protocol/split.json``
   and no other module opens the silver.
2. Make the long table, one row per entity and frame with ``gap_len``:
   ``ac2fb.reliability.long.long_table``. Its schema is
   ``ac2fb.reliability.long.LONG_SCHEMA`` (the one place it is written).
3. V0 against V1 (and V2) of a metric: ``ac2fb.reliability.sensitivity.sensitivity`` takes a
   ``Metric`` (a function of ``ac2fb.reliability.sensitivity.WindowFrames`` that returns a
   ``ac2fb.reliability.sensitivity.Reading``) and the units as
   ``ac2fb.reliability.sensitivity.Window``. The seven metrics of the reliability map and their
   units are ``ac2fb.reliability.metrics.metric_units``, built on
   ``ac2fb.reliability.match.build_match``.
4. The error of filling a gap with a straight line: ``ac2fb.reliability.amputate.amputate``,
   with ``ac2fb.reliability.amputate.hiding`` for how the camera hides players in the match.
"""

__all__: list[str] = []
