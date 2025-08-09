import json
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from prefect.logging import disable_run_logger

from pipelines.data_ingestion.data_ingestion_aws import upload_to_s3, _get_database_url
from pipelines.data_ingestion.data_ingestion_common_tasks import load_data_to_db


@patch("pipelines.data_ingestion.data_ingestion_common_tasks.inspect")
@patch("pipelines.data_ingestion.data_ingestion_common_tasks.create_engine")
def test_load_data_to_db_success(mock_create_engine, mock_inspect, raw_football_df, test_assets):
    """Test successful data loading to database via common tasks."""
    # Setup mocks
    mock_engine = MagicMock()
    mock_create_engine.return_value = mock_engine
    mock_connection = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_connection

    # Mock inspector to show table exists
    mock_inspector = MagicMock()
    mock_inspector.get_table_names.return_value = ["english_league_data"]
    mock_inspect.return_value = mock_inspector

    with patch.object(pd.DataFrame, "to_sql") as mock_to_sql:
        with disable_run_logger():
            load_data_to_db.fn(raw_football_df, test_assets["database_url"])

    # Verify database operations
    mock_create_engine.assert_called_once_with(test_assets["database_url"])

    # Verify to_sql was called with correct parameters (append for existing table)
    mock_to_sql.assert_called_once_with(
        "english_league_data", con=mock_connection, if_exists="append", index=False, method="multi"
    )


@patch("pipelines.data_ingestion.data_ingestion_aws.boto3.client")
@patch("pipelines.data_ingestion.data_ingestion_aws.AwsCredentials.load")
@patch("pipelines.data_ingestion.data_ingestion_aws.Variable.get")
def test_upload_to_s3_success(mock_variable_get, mock_aws_creds_load, mock_boto3_client, raw_football_df, test_assets):
    """Test successful S3 upload."""
    # Setup mocks
    mock_variable_get.return_value = test_assets["s3_bucket"]

    mock_aws_creds = MagicMock()
    mock_aws_creds.aws_access_key_id = "test-key"
    mock_aws_creds.aws_secret_access_key.get_secret_value.return_value = "test-secret"
    mock_aws_creds.region_name = "us-east-1"
    mock_aws_creds.aws_client_parameters.endpoint_url = None
    mock_aws_creds_load.return_value = mock_aws_creds

    mock_s3_client = MagicMock()
    mock_boto3_client.return_value = mock_s3_client

    with disable_run_logger():
        upload_to_s3.fn(test_assets["file_name"], raw_football_df)

    # Verify S3 operations
    mock_variable_get.assert_called_once_with("s3-epl-matches-datastore")
    mock_aws_creds_load.assert_called_once_with("aws-prefect-client-credentials")
    mock_boto3_client.assert_called_once_with(
        service_name="s3",
        aws_access_key_id="test-key",
        aws_secret_access_key="test-secret",
        region_name="us-east-1",
        endpoint_url=None,
    )
    mock_s3_client.put_object.assert_called_once()


@patch("pipelines.data_ingestion.data_ingestion_aws.Variable.get")
def test_upload_to_s3_empty_dataframe(mock_variable_get, empty_df, test_assets):
    """Test S3 upload with empty DataFrame."""
    mock_variable_get.return_value = test_assets["s3_bucket"]

    with disable_run_logger():
        with pytest.raises(ValueError, match="DataFrame is empty, cannot upload to S3"):
            upload_to_s3.fn(test_assets["file_name"], empty_df)


@patch("pipelines.data_ingestion.data_ingestion_aws.Variable.get")
def test_upload_to_s3_missing_bucket(mock_variable_get, raw_football_df, test_assets):
    """Test S3 upload with missing bucket configuration."""
    mock_variable_get.return_value = None

    with disable_run_logger():
        with pytest.raises(ValueError, match="S3 bucket name is not set"):
            upload_to_s3.fn(test_assets["file_name"], raw_football_df)


@patch("pipelines.data_ingestion.data_ingestion_aws.AwsSecret")
@patch("pipelines.data_ingestion.data_ingestion_aws.AwsCredentials.load")
@patch("pipelines.data_ingestion.data_ingestion_aws.Variable.get")
def test_get_database_url_success(mock_variable_get, mock_aws_creds_load, mock_aws_secret):
    """Test successful database URL retrieval from AWS Secrets Manager."""
    # Setup mocks
    mock_variable_get.return_value = "test-secret-name"

    mock_aws_creds = MagicMock()
    mock_aws_creds_load.return_value = mock_aws_creds

    mock_secret_instance = MagicMock()
    mock_secret_instance.read_secret.return_value = json.dumps(
        {"username": "test_user", "password": "test_pass", "host": "localhost", "port": 5432, "dbname": "test_db"}
    )
    mock_aws_secret.return_value = mock_secret_instance

    with disable_run_logger():
        result = _get_database_url.fn()

    expected_url = "postgresql+psycopg://test_user:test_pass@localhost:5432/test_db"
    assert result == expected_url

    mock_variable_get.assert_called_once_with("database-secrets")
    mock_aws_creds_load.assert_called_once_with("aws-prefect-client-credentials")


@patch("pipelines.data_ingestion.data_ingestion_aws.Variable.get")
def test_get_database_url_missing_secret(mock_variable_get):
    """Test database URL retrieval with missing secret configuration."""
    mock_variable_get.return_value = None

    with disable_run_logger():
        with pytest.raises(ValueError, match="Database secrets not found"):
            _get_database_url.fn()


# Additional tests using fixtures
@patch("pipelines.data_ingestion.data_ingestion_common_tasks.inspect")
@patch("pipelines.data_ingestion.data_ingestion_common_tasks.create_engine")
def test_load_data_to_db_table_not_exists(mock_create_engine, mock_inspect, raw_football_df, test_assets):
    """Test data loading when table doesn't exist (should replace/create)."""
    # Setup mocks
    mock_engine = MagicMock()
    mock_create_engine.return_value = mock_engine
    mock_connection = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_connection

    # Mock inspector to show table doesn't exist
    mock_inspector = MagicMock()
    mock_inspector.get_table_names.return_value = []
    mock_inspect.return_value = mock_inspector

    with patch.object(pd.DataFrame, "to_sql") as mock_to_sql:
        with disable_run_logger():
            load_data_to_db.fn(raw_football_df, test_assets["database_url"])

    # Verify to_sql was called with append
    mock_to_sql.assert_called_once_with(
        "english_league_data", con=mock_connection, if_exists="replace", index=False, method="multi"
    )


@patch("pipelines.data_ingestion.data_ingestion_common_tasks.inspect")
@patch("pipelines.data_ingestion.data_ingestion_common_tasks.create_engine")
def test_load_data_to_db_empty_dataframe(mock_create_engine, mock_inspect, empty_df, test_assets):
    """Test loading empty DataFrame (should return early)."""
    with disable_run_logger():
        result = load_data_to_db.fn(empty_df, test_assets["database_url"])

    # Should return early without creating engine or connection
    mock_create_engine.assert_not_called()
    mock_inspect.assert_not_called()
    assert result is None


@patch("pipelines.data_ingestion.data_ingestion_aws.boto3.client")
@patch("pipelines.data_ingestion.data_ingestion_aws.AwsCredentials.load")
@patch("pipelines.data_ingestion.data_ingestion_aws.Variable.get")
def test_upload_to_s3_with_betting_data(
    mock_variable_get, mock_aws_creds_load, mock_boto3_client, minimal_betting_df, test_assets
):
    """Test S3 upload with betting data."""
    # Setup mocks
    mock_variable_get.return_value = test_assets["s3_bucket"]

    mock_aws_creds = MagicMock()
    mock_aws_creds.aws_access_key_id = "test-key"
    mock_aws_creds.aws_secret_access_key.get_secret_value.return_value = "test-secret"
    mock_aws_creds.region_name = "eu-south-1"
    mock_aws_creds.aws_client_parameters.endpoint_url = None
    mock_aws_creds_load.return_value = mock_aws_creds

    mock_s3_client = MagicMock()
    mock_boto3_client.return_value = mock_s3_client

    with disable_run_logger():
        upload_to_s3.fn(test_assets["file_name"], minimal_betting_df)

    # Verify S3 operations succeeded
    mock_s3_client.put_object.assert_called_once()

    # Verify the parquet data contains betting columns
    call_args = mock_s3_client.put_object.call_args
    assert call_args[1]["Bucket"] == test_assets["s3_bucket"]
    assert call_args[1]["Key"] == f"raw/{test_assets['file_name']}"


@patch("pipelines.data_ingestion.data_ingestion_aws.boto3.client")
@patch("pipelines.data_ingestion.data_ingestion_aws.AwsCredentials.load")
@patch("pipelines.data_ingestion.data_ingestion_aws.Variable.get")
def test_upload_to_s3_with_invalid_data(
    mock_variable_get, mock_aws_creds_load, mock_boto3_client, invalid_dates_df, test_assets
):
    """Test S3 upload with DataFrame containing invalid data."""
    # Setup mocks
    mock_variable_get.return_value = test_assets["s3_bucket"]

    mock_aws_creds = MagicMock()
    mock_aws_creds.aws_access_key_id = "test-key"
    mock_aws_creds.aws_secret_access_key.get_secret_value.return_value = "test-secret"
    mock_aws_creds.region_name = "us-east-1"
    mock_aws_creds.aws_client_parameters.endpoint_url = None
    mock_aws_creds_load.return_value = mock_aws_creds

    mock_s3_client = MagicMock()
    mock_boto3_client.return_value = mock_s3_client

    with disable_run_logger():
        upload_to_s3.fn(test_assets["file_name"], invalid_dates_df)

    # Should still upload (data validation happens in cleaning, not uploading)
    mock_s3_client.put_object.assert_called_once()


@patch("pipelines.data_ingestion.data_ingestion_aws.boto3.client")
@patch("pipelines.data_ingestion.data_ingestion_aws.AwsCredentials.load")
@patch("pipelines.data_ingestion.data_ingestion_aws.Variable.get")
def test_upload_to_s3_boto3_error(
    mock_variable_get, mock_aws_creds_load, mock_boto3_client, raw_football_df, test_assets
):
    """Test S3 upload when boto3 raises an error."""
    # Setup mocks
    mock_variable_get.return_value = test_assets["s3_bucket"]

    mock_aws_creds = MagicMock()
    mock_aws_creds.aws_access_key_id = "test-key"
    mock_aws_creds.aws_secret_access_key.get_secret_value.return_value = "test-secret"
    mock_aws_creds.region_name = "us-east-1"
    mock_aws_creds.aws_client_parameters.endpoint_url = None
    mock_aws_creds_load.return_value = mock_aws_creds

    mock_s3_client = MagicMock()
    mock_s3_client.put_object.side_effect = Exception("S3 service error")
    mock_boto3_client.return_value = mock_s3_client

    with disable_run_logger():
        with pytest.raises(Exception, match="S3 service error"):
            upload_to_s3.fn(test_assets["file_name"], raw_football_df)
