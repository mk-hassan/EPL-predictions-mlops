import sys
from io import StringIO
from pathlib import Path

import boto3
import pandas as pd

sys.path.append(str(Path(__file__).resolve().parent.parent))
from ..IDataStore import IDataStore


class S3Store(IDataStore):
    """Concrete implementation of IDataStore for S3 storage."""

    def __init__(self, bucket_name: str, s3_client=None):
        self.bucket_name = bucket_name
        self.s3_client = s3_client or boto3.client("s3")

    def load_data(self, path: Path) -> pd.DataFrame:
        """Load data from S3."""
        obj = self.s3_client.get_object(Bucket=self.bucket_name, Key=str(path))
        return pd.read_csv(obj["Body"])

    def save_data(self, path: Path, data: pd.DataFrame) -> None:
        """Save data to S3."""
        csv_buffer = StringIO()
        data.to_csv(csv_buffer, index=False)
        self.s3_client.put_object(Bucket=self.bucket_name, Key=str(path), Body=csv_buffer.getvalue())
