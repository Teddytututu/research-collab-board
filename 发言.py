"""Local assistant conversation helper."""
from pathlib import Path
import runpy
runpy.run_path(str(Path(__file__).resolve().parent/"scripts/post_message.py"),run_name="__main__")
