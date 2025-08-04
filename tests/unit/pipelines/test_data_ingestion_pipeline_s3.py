from io import BytesIO
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from pydantic import SecretStr
from prefect.logging import disable_run_logger

from pipelines.data_ingestion_pipeline import upload_to_s3


@patch("pipelines.data_ingestion_pipeline.Variable.get")
@patch("pipelines.data_ingestion_pipeline.AwsCredentials.load")
@patch("pipelines.data_ingestion_pipeline.boto3.client")
def test_upload_to_s3_success(mock_boto3_client, mock_aws_creds_load, mock_variable_get):
    """Test successful S3 upload."""
    # Setup mocks
    mock_variable_get.return_value = "test-bucket"

    mock_aws_creds = MagicMock()
    mock_aws_creds.aws_access_key_id = "test-access-key"
    mock_aws_creds.aws_secret_access_key = SecretStr("test-secret-key")
    mock_aws_creds.region_name = "us-east-1"
    mock_aws_creds.aws_client_parameters.endpoint_url = "http://localhost:4566"
    mock_aws_creds_load.return_value = mock_aws_creds

    mock_s3_client = MagicMock()
    mock_boto3_client.return_value = mock_s3_client

    # Test data
    test_df = pd.DataFrame({"date": ["2024-01-01"], "hometeam": ["Arsenal"], "awayteam": ["Chelsea"]})

    with disable_run_logger():
        upload_to_s3.fn("test_file.parquet", test_df)

    # Verify boto3 client was created with correct parameters
    mock_boto3_client.assert_called_once_with(
        service_name="s3",
        aws_access_key_id="test-access-key",
        aws_secret_access_key="test-secret-key",
        region_name="us-east-1",
        endpoint_url="http://localhost:4566",
    )

    # Verify put_object was called
    mock_s3_client.put_object.assert_called_once()
    call_args = mock_s3_client.put_object.call_args
    call_kwargs = call_args.kwargs

    assert call_kwargs["Bucket"] == "test-bucket"
    assert call_kwargs["Key"] == "test_file.parquet"
    assert isinstance(call_kwargs["Body"], bytes)  # parquet data


@patch("pipelines.data_ingestion_pipeline.Variable.get")
def test_upload_to_s3_missing_bucket_name(mock_variable_get):
    """Test error when S3 bucket name is not set."""
    mock_variable_get.return_value = None

    test_df = pd.DataFrame({"col1": [1]})

    with disable_run_logger():
        with pytest.raises(ValueError, match="S3 bucket name is not set"):
            upload_to_s3.fn("test.parquet", test_df)


@patch("pipelines.data_ingestion_pipeline.Variable.get")
@patch("pipelines.data_ingestion_pipeline.AwsCredentials.load")
@patch("pipelines.data_ingestion_pipeline.boto3.client")
def test_upload_to_s3_upload_failure(mock_boto3_client, mock_aws_creds_load, mock_variable_get):
    """Test S3 upload failure."""
    # Setup mocks
    mock_variable_get.return_value = "test-bucket"

    mock_aws_creds = MagicMock()
    mock_aws_creds.aws_access_key_id = "test-access-key"
    mock_aws_creds.aws_secret_access_key = SecretStr("test-secret-key")
    mock_aws_creds.region_name = "us-east-1"
    mock_aws_creds.aws_client_parameters.endpoint_url = "http://localhost:4566"
    mock_aws_creds_load.return_value = mock_aws_creds

    mock_s3_client = MagicMock()
    mock_s3_client.put_object.side_effect = Exception("S3 upload failed")
    mock_boto3_client.return_value = mock_s3_client

    test_df = pd.DataFrame({"col1": [1]})

    with disable_run_logger():
        with pytest.raises(Exception, match="S3 upload failed"):
            upload_to_s3.fn("test.parquet", test_df)


@patch("pipelines.data_ingestion_pipeline.Variable.get")
@patch("pipelines.data_ingestion_pipeline.AwsCredentials.load")
@patch("pipelines.data_ingestion_pipeline.boto3.client")
def test_upload_to_s3_empty_dataframe(mock_boto3_client, mock_aws_creds_load, mock_variable_get):
    """Test upload with empty DataFrame."""
    # Setup mocks
    mock_variable_get.return_value = "test-bucket"
    mock_aws_creds_load.return_value = MagicMock()
    mock_s3_client = MagicMock()
    mock_boto3_client.return_value = mock_s3_client

    # Empty DataFrame
    empty_df = pd.DataFrame()

    with disable_run_logger():
        with pytest.raises(ValueError, match="DataFrame is empty, cannot upload to S3"):
            upload_to_s3.fn("empty.parquet", empty_df)

    # Verify boto3 client and put_object were never called for empty DataFrame
    mock_boto3_client.assert_not_called()
    mock_s3_client.put_object.assert_not_called()


@patch("pipelines.data_ingestion_pipeline.Variable.get")
@patch("pipelines.data_ingestion_pipeline.AwsCredentials.load")
@patch("pipelines.data_ingestion_pipeline.boto3.client")
def test_upload_to_s3_parquet_conversion(mock_boto3_client, mock_aws_creds_load, mock_variable_get):
    """Test that DataFrame is properly converted to parquet format."""
    # Setup mocks
    mock_variable_get.return_value = "test-bucket"

    mock_aws_creds = MagicMock()
    mock_aws_creds.aws_access_key_id = "test-access-key"
    mock_aws_creds.aws_secret_access_key = SecretStr("test-secret-key")
    mock_aws_creds.region_name = "us-east-1"
    mock_aws_creds.aws_client_parameters.endpoint_url = "http://localhost:4566"
    mock_aws_creds_load.return_value = mock_aws_creds

    mock_s3_client = MagicMock()
    mock_boto3_client.return_value = mock_s3_client

    test_df = pd.DataFrame({"date": pd.to_datetime(["2024-01-01"]), "hometeam": ["Arsenal"], "awayteam": ["Chelsea"]})

    with disable_run_logger():
        upload_to_s3.fn("test.parquet", test_df)

    # Check that put_object was called with bytes (parquet data)
    call_args = mock_s3_client.put_object.call_args
    call_kwargs = call_args.kwargs
    uploaded_data = call_kwargs["Body"]

    assert isinstance(uploaded_data, bytes)
    assert len(uploaded_data) > 0  # Should have some data

    # Verify we can read back the parquet data
    reconstructed_df = pd.read_parquet(BytesIO(uploaded_data))
    assert len(reconstructed_df) == 1
    assert "hometeam" in reconstructed_df.columns
    assert reconstructed_df["hometeam"].iloc[0] == "Arsenal"


@patch("pipelines.data_ingestion_pipeline.Variable.get")
@patch("pipelines.data_ingestion_pipeline.AwsCredentials.load")
@patch("pipelines.data_ingestion_pipeline.boto3.client")
def test_upload_to_s3_aws_credentials_loading(mock_boto3_client, mock_aws_creds_load, mock_variable_get):
    """Test that AWS credentials are properly loaded and used."""
    # Setup mocks
    mock_variable_get.return_value = "test-bucket"

    mock_aws_creds = MagicMock()
    mock_aws_creds.aws_access_key_id = "custom-access-key"
    mock_aws_creds.aws_secret_access_key = SecretStr("custom-secret-key")
    mock_aws_creds.region_name = "eu-west-1"
    mock_aws_creds.aws_client_parameters.endpoint_url = "https://custom-endpoint.com"
    mock_aws_creds_load.return_value = mock_aws_creds

    mock_s3_client = MagicMock()
    mock_boto3_client.return_value = mock_s3_client

    test_df = pd.DataFrame({"col1": [1, 2, 3]})

    with disable_run_logger():
        upload_to_s3.fn("credentials_test.parquet", test_df)

    # Verify AwsCredentials.load was called with correct block name
    mock_aws_creds_load.assert_called_once_with("aws-prefect-client-credentials")

    # Verify boto3.client was called with the correct credentials
    mock_boto3_client.assert_called_once_with(
        service_name="s3",
        aws_access_key_id="custom-access-key",
        aws_secret_access_key="custom-secret-key",
        region_name="eu-west-1",
        endpoint_url="https://custom-endpoint.com",
    )


@patch("pipelines.data_ingestion_pipeline.Variable.get")
@patch("pipelines.data_ingestion_pipeline.AwsCredentials.load")
@patch("pipelines.data_ingestion_pipeline.boto3.client")
def test_upload_to_s3_large_dataframe(mock_boto3_client, mock_aws_creds_load, mock_variable_get):
    """Test upload with larger DataFrame to ensure parquet compression works."""
    # Setup mocks
    mock_variable_get.return_value = "test-bucket"

    mock_aws_creds = MagicMock()
    mock_aws_creds.aws_access_key_id = "test-key"
    mock_aws_creds.aws_secret_access_key = SecretStr("test-secret")
    mock_aws_creds.region_name = "us-east-1"
    mock_aws_creds.aws_client_parameters.endpoint_url = "http://localhost:4566"
    mock_aws_creds_load.return_value = mock_aws_creds

    mock_s3_client = MagicMock()
    mock_boto3_client.return_value = mock_s3_client

    # Create larger test DataFrame
    large_df = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-01"] * 1000),
            "hometeam": ["Arsenal"] * 1000,
            "awayteam": ["Chelsea"] * 1000,
            "season": ["2425"] * 1000,
            "div": ["E0"] * 1000,
        }
    )

    with disable_run_logger():
        upload_to_s3.fn("large_test.parquet", large_df)

    # Verify put_object was called
    mock_s3_client.put_object.assert_called_once()
    call_kwargs = mock_s3_client.put_object.call_args.kwargs

    assert call_kwargs["Bucket"] == "test-bucket"
    assert call_kwargs["Key"] == "large_test.parquet"

    # Verify the uploaded data can be reconstructed
    uploaded_data = call_kwargs["Body"]
    reconstructed_df = pd.read_parquet(BytesIO(uploaded_data))

    assert len(reconstructed_df) == 1000
    assert list(reconstructed_df.columns) == ["date", "hometeam", "awayteam", "season", "div"]
    assert reconstructed_df["hometeam"].iloc[0] == "Arsenal"
