"""Start the API:  python -m uvicorn main:app --reload   (then open http://127.0.0.1:8000/docs)"""
import os
from pathlib import Path

from movematch.api import create_app

# The working data file is created from movematch/seed.json on the first start.
app = create_app(Path(os.environ.get("MOVEMATCH_DATA_FILE", Path(__file__).with_name("movematch-data.json"))))
