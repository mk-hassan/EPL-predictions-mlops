from pathlib import Path

import pandas as pd

# sys.path.append(str(Path(__file__).resolve().parent.parent))
from ..IDataStore import IDataStore


class LocalDataStore(IDataStore):
    """Local file system data store implementation."""

    def load_data(self, path: Path) -> pd.DataFrame:
        """Load data from a local file."""
        # check if path exists
        if not path.exists():
            raise FileNotFoundError(f"Path {path} does not exist")
        if path.suffix not in [".csv", ".parquet"]:
            raise ValueError(f"Unsupported file extension: {path.suffix}. Supported extensions are .csv and .parquet")

        # load data based on extension
        if path.suffix == ".csv":
            data = pd.read_csv(path)
        elif path.suffix == ".parquet":
            data = pd.read_parquet(path)
        else:
            raise ValueError(f"Unsupported file extension: {path.suffix}. Supported extensions are .csv and .parquet")
        return data

    def save_data(self, path: Path, data: pd.DataFrame) -> None:
        """Save data to a local file."""
        # create path if not exists
        path.parent.mkdir(parents=True, exist_ok=True)
        # save data based on extension
        if path.suffix == ".csv":
            data.to_csv(path, index=False)
        elif path.suffix == ".parquet":
            data.to_parquet(path, index=False)
        else:
            raise ValueError(f"Unsupported file extension: {path.suffix}. Supported extensions are .csv and .parquet")
