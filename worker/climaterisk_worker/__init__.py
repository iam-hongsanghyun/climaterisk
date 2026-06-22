"""CLIMADA worker — runs in a separate conda env (heavy geospatial stack).

The orchestration backend invokes this package as a subprocess:

    conda run -n <env> python -m climaterisk_worker.run_job <run_dir>

It reads ``<run_dir>/request.json`` (shape: PhysicalRunRequest from
``climaterisk.engines.base``), runs CLIMADA, and writes ``<run_dir>/result.json``
(shape: PhysicalRunResult). It must NOT import the ``climaterisk`` backend package
(different environment) — the JSON contract is the only coupling.
"""

__version__ = "0.1.0"
