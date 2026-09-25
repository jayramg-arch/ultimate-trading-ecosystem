"""The Web Commander source as tests should see it after the 25-Sep split: the router,
commander_core.py and every commander_pages/*.py. A test that reads only the router file
now misses the code it was written to check."""
import glob
import io
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(ROOT, "weinstein_commander_web_v4.0.py")
CORE = os.path.join(ROOT, "commander_core.py")


def app_files():
    pages = sorted(glob.glob(os.path.join(ROOT, "commander_pages", "*.py")))
    return [APP, CORE] + [p for p in pages if not p.endswith("__init__.py")]


def app_source():
    return "\n".join(io.open(p, encoding="utf-8").read() for p in app_files())
