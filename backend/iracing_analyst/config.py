import os
from pathlib import Path

from platformdirs import user_data_dir


APP_NAME = "iRacing Analyst"


def data_dir() -> Path:
    path = Path(os.environ.get("IRACING_ANALYST_DATA_DIR", user_data_dir(APP_NAME, "iRacingAnalyst")))
    path.mkdir(parents=True, exist_ok=True)
    return path
