"""Run orchestration — submit physical-risk runs to the CLIMADA worker and track them.

The backend never imports CLIMADA. It writes ``data/runs/<id>/request.json``, spawns
the worker (the climada-env python running ``climaterisk_worker.run_job``) as a
non-blocking subprocess, and reads ``data/runs/<id>/result.json`` when it finishes.
"""
