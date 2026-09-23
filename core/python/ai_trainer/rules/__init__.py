"""Deterministic training rules.

- ``eligibility``  — the gates every request passes first (spec §5.2 priority order)
- ``progression``  — double progression on comparable evidence (TB-04)
- ``adjustments``  — shorten / substitute / reschedule a session (TB-02, TB-03, TB-06)
- ``program``      — initial program selection from a profile (TB-01)

No module here has a clock, random IDs, persistence or I/O.
"""
