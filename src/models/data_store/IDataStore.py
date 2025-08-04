from abc import ABC, abstractmethod
from pathlib import Path

import pandas as pd


class IDataStore(ABC):
    """Abstract base class for data stores."""

    @abstractmethod
    def load_data(self, path: Path) -> pd.DataFrame:
        """Load data method to be implemented by subclasses."""
        pass

    @abstractmethod
    def save_data(self, path: Path, data: pd.DataFrame) -> None:
        """Save data method to be implemented by subclasses."""
        pass
