"""Standalone production worker entry point."""

from __future__ import annotations

import time

from database import SessionLocal
from production.worker import ProductionWorker

if __name__ == "__main__":
    while True:
        db = SessionLocal()
        try:
            ProductionWorker(db).run_once()
            db.commit()
        finally:
            db.close()
        time.sleep(1)
