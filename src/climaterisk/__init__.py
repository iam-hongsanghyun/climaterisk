"""climaterisk — map-first climate physical- and transition-risk analysis platform.

The orchestration backend owns the model (per-session SQLite), serves the bundled
methodology libraries, runs the lightweight transition-risk math, and submits
physical-risk runs to a separate CLIMADA worker process. It deliberately imports
no geospatial / CLIMADA code (that lives in the conda-based ``worker/`` package).
"""

__version__ = "0.1.0"
