"""Physical-risk engine boundary.

The orchestration backend imports **no** CLIMADA / geospatial code. It only
produces a :class:`PhysicalRunRequest` (JSON) and consumes a
:class:`PhysicalRunResult` (JSON) written by the separate CLIMADA worker
process. This module is the canonical contract for that JSON exchange.
"""
