"""Persistence layer: the data lives in one JSON file (no database needed for Milestone 2)."""
import json
from pathlib import Path
from threading import RLock

SEED = Path(__file__).resolve().parent / "seed.json"


class JsonStore:
    """Loads and saves the whole data document. Creates the working file from seed.json on first start."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.lock = RLock()  # one request changes the file at a time
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.save(json.loads(SEED.read_text(encoding="utf-8")))

    def load(self) -> dict:
        # A damaged file is a setup error: never silently replace existing work.
        return json.loads(self.path.read_text(encoding="utf-8"))

    def save(self, data: dict) -> None:
        # Write a temporary file first, then replace: a crash cannot leave half a file behind.
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        temporary.replace(self.path)
