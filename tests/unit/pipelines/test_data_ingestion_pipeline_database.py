import json
from unittest.mock import MagicMock, patch

import pytest
from prefect.logging import disable_run_logger

from pipelines.data_ingestion_pipeline import _get_database_url


@patch("pipelines.data_ingestion_pipeline.AwsSecret")
@patch("pipelines.data_ingestion_pipeline.AwsCredentials.load")
@patch("pipelines.data_ingestion_pipeline.Variable.get")
def test_get_database_url(mock_variable_get, mock_aws_creds_load, mock_aws_secret_class):
    """Test the _get_database_url function."""
    # Mock Variable.get to return the secret name
    mock_variable_get.return_value = "test-secret-name"

    # Mock the AwsCredentials.load to return a mock credentials object
    mock_aws_creds = MagicMock()
    mock_aws_creds_load.return_value = mock_aws_creds

    # Mock the AwsSecret instance and its read_secret method
    mock_aws_secret_instance = MagicMock()
    mock_aws_secret_class.return_value = mock_aws_secret_instance

    # read_secret should return a JSON string, not a dict
    mock_credentials = {
        "username": "test_user",
        "password": "test_password",
        "host": "test_host",
        "port": 5432,
        "dbname": "test_db",
    }
    mock_aws_secret_instance.read_secret.return_value = json.dumps(mock_credentials)

    with disable_run_logger():
        db_url = _get_database_url.fn()

    # Verify the function was called correctly
    mock_variable_get.assert_called_once_with("database-secrets")
    mock_aws_secret_class.assert_called_once()
    mock_aws_secret_instance.read_secret.assert_called_once()

    # Check if the database URL is correct
    expected_url = "postgresql+psycopg://test_user:test_password@test_host:5432/test_db"
    assert db_url == expected_url
    assert isinstance(db_url, str)
    assert db_url.startswith("postgresql+psycopg://")


@patch("pipelines.data_ingestion_pipeline.Variable.get")
def test_get_database_url_variable_not_found(mock_variable_get):
    """Test the _get_database_url function when Variable.get returns None."""
    # Mock Variable.get to return None (variable not found)
    mock_variable_get.return_value = None

    with disable_run_logger():
        with pytest.raises(ValueError, match="Database secrets not found in Prefect Variable 'database-secrets'"):
            _get_database_url.fn()

    # Verify the function was called
    mock_variable_get.assert_called_once_with("database-secrets")


@patch("pipelines.data_ingestion_pipeline.Variable.get")
def test_get_database_url_empty_variable(mock_variable_get):
    """Test the _get_database_url function when Variable.get returns empty string."""
    # Mock Variable.get to return empty string
    mock_variable_get.return_value = ""

    with disable_run_logger():
        with pytest.raises(ValueError, match="Database secrets not found in Prefect Variable 'database-secrets'"):
            _get_database_url.fn()

    # Verify the function was called
    mock_variable_get.assert_called_once_with("database-secrets")


@patch("pipelines.data_ingestion_pipeline.AwsSecret")
@patch("pipelines.data_ingestion_pipeline.AwsCredentials.load")
@patch("pipelines.data_ingestion_pipeline.Variable.get")
def test_get_database_url_invalid_json(mock_variable_get, mock_aws_creds_load, mock_aws_secret_class):
    """Test the _get_database_url function when read_secret returns invalid JSON."""
    # Mock Variable.get to return valid secret name
    mock_variable_get.return_value = "test-secret-name"

    # Mock the AwsCredentials.load to return a mock credentials object
    mock_aws_creds = MagicMock()
    mock_aws_creds_load.return_value = mock_aws_creds

    # Mock the AwsSecret instance and its read_secret method
    mock_aws_secret_instance = MagicMock()
    mock_aws_secret_class.return_value = mock_aws_secret_instance

    # Make read_secret return invalid JSON
    mock_aws_secret_instance.read_secret.return_value = "invalid-json-string"

    with disable_run_logger():
        with pytest.raises(json.JSONDecodeError):
            _get_database_url.fn()

    # Verify the functions were called
    mock_variable_get.assert_called_once_with("database-secrets")
    mock_aws_secret_class.assert_called_once()
    mock_aws_secret_instance.read_secret.assert_called_once()


@patch("pipelines.data_ingestion_pipeline.AwsSecret")
@patch("pipelines.data_ingestion_pipeline.AwsCredentials.load")
@patch("pipelines.data_ingestion_pipeline.Variable.get")
def test_get_database_url_missing_credentials_fields(mock_variable_get, mock_aws_creds_load, mock_aws_secret_class):
    """Test the _get_database_url function when credentials are missing required fields."""
    # Mock Variable.get to return valid secret name
    mock_variable_get.return_value = "test-secret-name"

    # Mock the AwsCredentials.load to return a mock credentials object
    mock_aws_creds = MagicMock()
    mock_aws_creds_load.return_value = mock_aws_creds

    # Mock the AwsSecret instance
    mock_aws_secret_instance = MagicMock()
    mock_aws_secret_class.return_value = mock_aws_secret_instance

    # Mock credentials missing required fields
    incomplete_credentials = {
        "username": "test_user",
        # Missing password, host, dbname
    }
    mock_aws_secret_instance.read_secret.return_value = json.dumps(incomplete_credentials)

    with disable_run_logger():
        with pytest.raises(KeyError):
            _get_database_url.fn()

    # Verify the functions were called
    mock_variable_get.assert_called_once_with("database-secrets")
    mock_aws_secret_class.assert_called_once()
    mock_aws_secret_instance.read_secret.assert_called_once()
