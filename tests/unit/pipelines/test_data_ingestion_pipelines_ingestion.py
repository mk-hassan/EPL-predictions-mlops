from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from prefect.logging import disable_run_logger

from pipelines.data_ingestion_pipeline import load_data_to_db


@patch("pipelines.data_ingestion_pipeline.inspect")
@patch("pipelines.data_ingestion_pipeline.Variable.get")
@patch("pipelines.data_ingestion_pipeline.create_engine")
@patch("pipelines.data_ingestion_pipeline._get_database_url")
def test_load_data_to_db_success(mock_get_db_url, mock_create_engine, mock_variable_get, mock_inspect):
    """Test successful data loading to database."""
    # Setup mocks
    mock_get_db_url.return_value = "postgresql://test"
    mock_variable_get.return_value = "test_table"

    mock_engine = MagicMock()
    mock_create_engine.return_value = mock_engine
    mock_connection = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_connection

    # Mock inspector to show table exists
    mock_inspector = MagicMock()
    mock_inspector.get_table_names.return_value = ["test_table"]
    mock_inspect.return_value = mock_inspector

    # Test data
    test_df = pd.DataFrame(
        {"date": pd.to_datetime(["2024-01-01"]), "hometeam": ["Arsenal"], "awayteam": ["Chelsea"], "season": ["2425"]}
    )

    with patch.object(pd.DataFrame, "to_sql") as mock_to_sql:
        with disable_run_logger():
            load_data_to_db.fn(test_df)

    # Verify database operations
    mock_get_db_url.assert_called_once()
    mock_create_engine.assert_called_once_with("postgresql://test")
    mock_variable_get.assert_called_once_with("table-name", "english_league_data")

    # Verify to_sql was called with correct parameters (append for existing table)
    mock_to_sql.assert_called_once_with(
        "test_table", con=mock_connection, if_exists="append", index=False, method="multi"
    )


@patch("pipelines.data_ingestion_pipeline.inspect")
@patch("pipelines.data_ingestion_pipeline.Variable.get")
@patch("pipelines.data_ingestion_pipeline.create_engine")
@patch("pipelines.data_ingestion_pipeline._get_database_url")
def test_load_data_to_db_database_error(mock_get_db_url, mock_create_engine, mock_variable_get, mock_inspect):
    """Test database error handling during data loading."""
    # Setup mocks
    mock_get_db_url.return_value = "postgresql://test"
    mock_variable_get.return_value = "test_table"

    mock_engine = MagicMock()
    mock_create_engine.return_value = mock_engine
    mock_connection = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_connection

    # Mock inspector to show table exists
    mock_inspector = MagicMock()
    mock_inspector.get_table_names.return_value = ["test_table"]
    mock_inspect.return_value = mock_inspector

    test_df = pd.DataFrame({"season": ["2425", "2324", "2223"], "col1": [1, 2, 3]})

    # Mock to_sql to raise a database error
    with patch.object(pd.DataFrame, "to_sql") as mock_to_sql:
        mock_to_sql.side_effect = Exception("Database connection failed")

        with disable_run_logger():
            with pytest.raises(Exception, match="Database connection failed"):
                load_data_to_db.fn(test_df)

        # Verify to_sql was attempted
        mock_to_sql.assert_called_once_with(
            "test_table", con=mock_connection, if_exists="append", index=False, method="multi"
        )


@patch("pipelines.data_ingestion_pipeline.inspect")
@patch("pipelines.data_ingestion_pipeline.Variable.get")
@patch("pipelines.data_ingestion_pipeline.create_engine")
@patch("pipelines.data_ingestion_pipeline._get_database_url")
def test_load_data_to_db_uses_default_table_name(mock_get_db_url, mock_create_engine, mock_variable_get, mock_inspect):
    """Test that default table name is used when variable is not set."""
    # Setup mocks
    mock_get_db_url.return_value = "postgresql://test"
    mock_variable_get.return_value = "english_league_data"  # default value

    mock_engine = MagicMock()
    mock_create_engine.return_value = mock_engine
    mock_connection = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_connection

    # Mock inspector to show table doesn't exist
    mock_inspector = MagicMock()
    mock_inspector.get_table_names.return_value = []
    mock_inspect.return_value = mock_inspector

    test_df = pd.DataFrame({"season": ["2425"], "col1": [1]})

    with patch.object(pd.DataFrame, "to_sql") as mock_to_sql:
        with disable_run_logger():
            load_data_to_db.fn(test_df)

    # Verify default table name was used
    mock_variable_get.assert_called_once_with("table-name", "english_league_data")
    mock_to_sql.assert_called_once_with(
        "english_league_data", con=mock_connection, if_exists="replace", index=False, method="multi"
    )


@patch("pipelines.data_ingestion_pipeline.Variable.get")
@patch("pipelines.data_ingestion_pipeline.create_engine")
@patch("pipelines.data_ingestion_pipeline._get_database_url")
def test_load_data_to_db_connection_error(mock_get_db_url, mock_create_engine, mock_variable_get):
    """Test database connection error during data loading."""
    # Setup mocks
    mock_get_db_url.return_value = "postgresql://test"
    mock_variable_get.return_value = "test_table"

    mock_engine = MagicMock()
    mock_create_engine.return_value = mock_engine
    mock_engine.connect.side_effect = Exception("Connection failed")

    test_df = pd.DataFrame({"season": ["2425"], "col1": [1]})

    with disable_run_logger():
        with pytest.raises(Exception, match="Connection failed"):
            load_data_to_db.fn(test_df)


@patch("pipelines.data_ingestion_pipeline.Variable.get")
@patch("pipelines.data_ingestion_pipeline._get_database_url")
def test_load_data_to_db_empty_dataframe(mock_get_db_url, mock_variable_get):
    """Test loading empty DataFrame (should return early)."""
    # Setup mocks
    mock_get_db_url.return_value = "postgresql://test"
    mock_variable_get.return_value = "test_table"

    empty_df = pd.DataFrame()

    with disable_run_logger():
        load_data_to_db.fn(empty_df)

    # Verify early return - database operations should not be called
    mock_get_db_url.assert_called_once()
    mock_variable_get.assert_called_once()


@patch("pipelines.data_ingestion_pipeline._get_database_url")
def test_load_data_to_db_get_database_url_error(mock_get_db_url):
    """Test error during database URL retrieval."""
    mock_get_db_url.side_effect = Exception("Failed to get database URL")

    test_df = pd.DataFrame({"season": ["2425"], "col1": [1]})

    with disable_run_logger():
        with pytest.raises(Exception, match="Failed to get database URL"):
            load_data_to_db.fn(test_df)

    # Verify database URL retrieval was attempted
    mock_get_db_url.assert_called_once()


@patch("pipelines.data_ingestion_pipeline.Variable.get")
@patch("pipelines.data_ingestion_pipeline._get_database_url")
def test_load_data_to_db_variable_get_error(mock_get_db_url, mock_variable_get):
    """Test error during Variable.get for table name."""
    # Setup mocks
    mock_get_db_url.return_value = "postgresql://test"
    mock_variable_get.side_effect = Exception("Failed to get variable")

    test_df = pd.DataFrame({"season": ["2425"], "col1": [1]})

    with disable_run_logger():
        with pytest.raises(Exception, match="Failed to get variable"):
            load_data_to_db.fn(test_df)

    # Verify the order of operations
    mock_get_db_url.assert_called_once()
    mock_variable_get.assert_called_once_with("table-name", "english_league_data")
