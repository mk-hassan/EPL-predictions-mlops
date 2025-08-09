import sys
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

import pandas as pd
import pytest
import requests
from sqlalchemy.exc import SQLAlchemyError
from prefect.logging import disable_run_logger

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parents[3]))

from src.models.DivisionEnum import Division
from pipelines.data_ingestion.data_ingestion_common_tasks import (
    _clean_data,
    ensure_division,
    load_data_to_db,
    get_current_season,
    get_season_results,
)


class TestCleanData:
    """Test cases for _clean_data function."""

    def test_clean_data_basic_functionality(self, raw_football_df, test_assets, expected_columns):
        """Test the basic functionality of _clean_data function."""
        with disable_run_logger():
            result = _clean_data.fn(test_assets["season"], raw_football_df)

        # Check all expected columns exist
        for col in expected_columns:
            assert col in result.columns, f"Column {col} missing from result"

        # Check column names are lowercase
        assert all(col.islower() for col in result.columns)

        # Check season column added
        assert (result["season"] == test_assets["season"]).all()

        # Check original data preserved
        assert len(result) == 3
        assert result["hometeam"].iloc[0] == "Arsenal"

    def test_clean_data_with_invalid_dates(self, invalid_dates_df, test_assets):
        """Test _clean_data function with invalid dates."""
        with disable_run_logger():
            result = _clean_data.fn(test_assets["season"], invalid_dates_df)

        # Should drop rows with invalid dates
        assert len(result) == 2
        assert result["hometeam"].iloc[0] == "Arsenal"

    def test_clean_data_with_duplicates(self, duplicate_matches_df, test_assets):
        """Test _clean_data function removes duplicates."""
        with disable_run_logger():
            result = _clean_data.fn(test_assets["season"], duplicate_matches_df)

        # Should remove duplicate matches
        assert len(result) == 2
        assert result["hometeam"].tolist() == ["Arsenal", "Chelsea"]

    def test_clean_data_empty_dataframe(self, empty_df, test_assets):
        """Test _clean_data function with empty DataFrame."""
        with disable_run_logger():
            with pytest.raises(ValueError, match="Received empty DataFrame"):
                _clean_data.fn(test_assets["season"], empty_df)

    def test_clean_data_preserves_betting_odds(self, minimal_betting_df, test_assets):
        """Test that betting odds columns are preserved."""
        with disable_run_logger():
            result = _clean_data.fn(test_assets["season"], minimal_betting_df)

        # Check betting odds columns are preserved
        assert "whh" in result.columns
        assert "whd" in result.columns
        assert "wha" in result.columns

        # Check values are preserved
        assert result["whh"].iloc[0] == 1.85
        assert result["whd"].iloc[0] == 3.60
        assert result["wha"].iloc[0] == 4.20

    def test_clean_data_with_spaces_in_column_names(self, test_assets):
        """Test _clean_data function handles column names with spaces."""
        test_data = {
            "Date": ["15/08/2024"],
            "HomeTeam": ["Arsenal"],
            "AwayTeam": ["Brighton"],
            "Div": ["E0"],
            "FTHG": [2],
            "FTAG": [0],
        }
        df = pd.DataFrame(test_data)

        with disable_run_logger():
            result = _clean_data.fn(test_assets["season"], df)

        # Check spaces replaced with underscores and converted to lowercase
        assert "home_team" in result.columns or "hometeam" in result.columns
        assert "away_team" in result.columns or "awayteam" in result.columns


class TestEnsureDivision:
    """Test cases for ensure_division function."""

    def test_ensure_division_with_string(self):
        """Test ensure_division with valid string input."""
        with disable_run_logger():
            result = ensure_division("E0")
        assert result == Division.PREMIER_LEAGUE
        assert isinstance(result, Division)

    def test_ensure_division_with_enum(self):
        """Test ensure_division with Division enum input."""
        with disable_run_logger():
            result = ensure_division(Division.PREMIER_LEAGUE)
        assert result == Division.PREMIER_LEAGUE
        assert isinstance(result, Division)

    def test_ensure_division_with_none(self):
        """Test ensure_division with None input (should default to Premier League)."""
        with disable_run_logger():
            result = ensure_division(None)
        assert result == Division.PREMIER_LEAGUE

    def test_ensure_division_with_invalid_string(self):
        """Test ensure_division with invalid string input."""
        with disable_run_logger():
            with pytest.raises(ValueError, match="Invalid division"):
                ensure_division("INVALID")

    def test_ensure_division_with_invalid_type(self):
        """Test ensure_division with invalid type input."""
        with disable_run_logger():
            with pytest.raises(ValueError, match="Invalid division type"):
                ensure_division(123)


class TestGetCurrentSeason:
    """Test cases for get_current_season function."""

    @patch("pipelines.data_ingestion.data_ingestion_common_tasks.datetime")
    def test_get_current_season_august_onwards(self, mock_datetime):
        """Test season calculation for August onwards (new season start)."""
        # Mock current date as August 15, 2024
        mock_now = Mock()
        mock_now.month = 8
        mock_now.year = 2024
        mock_datetime.now.return_value = mock_now

        with disable_run_logger():
            result = get_current_season.fn()

        assert result == "2425"  # 2024-25 season

    @patch("pipelines.data_ingestion.data_ingestion_common_tasks.datetime")
    def test_get_current_season_before_august(self, mock_datetime):
        """Test season calculation for before August (previous season continues)."""
        # Mock current date as March 15, 2024
        mock_now = Mock()
        mock_now.month = 3
        mock_now.year = 2024
        mock_datetime.now.return_value = mock_now

        with disable_run_logger():
            result = get_current_season.fn()

        assert result == "2324"  # 2023-24 season

    @patch("pipelines.data_ingestion.data_ingestion_common_tasks.datetime")
    def test_get_current_season_december(self, mock_datetime):
        """Test season calculation for December (mid-season)."""
        # Mock current date as December 15, 2024
        mock_now = Mock()
        mock_now.month = 12
        mock_now.year = 2024
        mock_datetime.now.return_value = mock_now

        with disable_run_logger():
            result = get_current_season.fn()

        assert result == "2425"  # 2024-25 season


class TestGetSeasonResults:
    """Test cases for get_season_results function."""

    @patch("pipelines.data_ingestion.data_ingestion_common_tasks.get_required_columns")
    @patch("pipelines.data_ingestion.data_ingestion_common_tasks.requests.get")
    def test_get_season_results_success(self, mock_requests_get, mock_get_required_columns, raw_football_df):
        """Test successful season results fetching."""
        # Setup mocks
        mock_response = Mock()
        mock_response.content = raw_football_df.to_csv(index=False).encode()
        mock_response.raise_for_status.return_value = None
        mock_requests_get.return_value = mock_response

        mock_get_required_columns.return_value = ["div", "date", "hometeam", "awayteam", "fthg", "ftag", "season"]

        with disable_run_logger():
            result = get_season_results.fn("2425", "E0")

        # Verify request was made
        mock_requests_get.assert_called_once_with("https://www.football-data.co.uk/mmz4281/2425/E0.csv", timeout=10)

        # Check result structure
        assert len(result) > 0
        assert "season" in result.columns
        assert (result["season"] == "2425").all()

    @patch("pipelines.data_ingestion.data_ingestion_common_tasks.requests.get")
    def test_get_season_results_empty_response(self, mock_requests_get):
        """Test handling of empty response."""
        # Setup mock for empty response
        mock_response = Mock()
        mock_response.content = b""
        mock_response.raise_for_status.return_value = None
        mock_requests_get.return_value = mock_response

        with disable_run_logger():
            with pytest.raises(ValueError, match="No data available"):
                get_season_results.fn("2425", "E0")

    @patch("pipelines.data_ingestion.data_ingestion_common_tasks.requests.get")
    def test_get_season_results_http_error(self, mock_requests_get):
        """Test handling of HTTP errors."""
        mock_requests_get.side_effect = requests.exceptions.HTTPError("404 Not Found")

        with disable_run_logger():
            with pytest.raises(requests.exceptions.HTTPError):
                get_season_results.fn("2425", "E0")

    @patch("pipelines.data_ingestion.data_ingestion_common_tasks.get_required_columns")
    @patch("pipelines.data_ingestion.data_ingestion_common_tasks.requests.get")
    def test_get_season_results_missing_columns(self, mock_requests_get, mock_get_required_columns, raw_football_df):
        """Test handling when required columns are missing."""
        # Setup mocks
        mock_response = Mock()
        mock_response.content = raw_football_df.to_csv(index=False).encode()
        mock_response.raise_for_status.return_value = None
        mock_requests_get.return_value = mock_response

        # Mock required columns that don't exist in test data
        mock_get_required_columns.return_value = ["nonexistent_column"]

        with disable_run_logger():
            with pytest.raises(ValueError, match="Missing required columns"):
                get_season_results.fn("2425", "E0")

    @patch("pipelines.data_ingestion.data_ingestion_common_tasks.get_required_columns")
    def test_get_season_results_no_required_columns_config(self, mock_get_required_columns):
        """Test handling when no required columns are configured."""
        mock_get_required_columns.return_value = None

        with disable_run_logger():
            with pytest.raises(ValueError, match="No required columns found"):
                get_season_results.fn("2425", "E0")


class TestLoadDataToDb:
    """Test cases for load_data_to_db function."""

    @patch("pipelines.data_ingestion.data_ingestion_common_tasks.inspect")
    @patch("pipelines.data_ingestion.data_ingestion_common_tasks.create_engine")
    def test_load_data_to_db_table_exists_append(self, mock_create_engine, mock_inspect, raw_football_df, test_assets):
        """Test data loading when table exists (should delete and insert)."""
        # Setup mocks
        mock_engine = MagicMock()
        mock_create_engine.return_value = mock_engine
        mock_connection = MagicMock()
        mock_engine.connect.return_value.__enter__.return_value = mock_connection

        # Mock inspector to show table exists
        mock_inspector = MagicMock()
        mock_inspector.get_table_names.return_value = ["english_league_data"]
        mock_inspect.return_value = mock_inspector

        # Mock transaction
        mock_transaction = MagicMock()
        mock_connection.begin.return_value = mock_transaction

        # Mock delete result
        mock_delete_result = MagicMock()
        mock_delete_result.rowcount = 5
        mock_connection.execute.return_value = mock_delete_result

        with patch.object(pd.DataFrame, "to_sql") as mock_to_sql:
            with disable_run_logger():
                load_data_to_db.fn(raw_football_df, test_assets["database_url"])

        # Verify database operations
        mock_create_engine.assert_called_once_with(test_assets["database_url"])
        mock_connection.begin.assert_called_once()
        mock_transaction.commit.assert_called_once()

        # Verify to_sql was called with append
        mock_to_sql.assert_called_once_with(
            "english_league_data", con=mock_connection, if_exists="append", index=False, method="multi"
        )

    @patch("pipelines.data_ingestion.data_ingestion_common_tasks.inspect")
    @patch("pipelines.data_ingestion.data_ingestion_common_tasks.create_engine")
    def test_load_data_to_db_table_not_exists(self, mock_create_engine, mock_inspect, raw_football_df, test_assets):
        """Test data loading when table doesn't exist (should create table)."""
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

        # Verify to_sql was called with replace (create table)
        mock_to_sql.assert_called_once_with(
            "english_league_data", con=mock_connection, if_exists="replace", index=False, method="multi"
        )

    def test_load_data_to_db_empty_dataframe(self, empty_df, test_assets):
        """Test loading empty DataFrame (should return early)."""
        with disable_run_logger():
            result = load_data_to_db.fn(empty_df, test_assets["database_url"])

        # Should return early without error
        assert result is None

    def test_load_data_to_db_missing_season_column(self, test_assets):
        """Test loading DataFrame without season column."""
        df_no_season = pd.DataFrame({"hometeam": ["Arsenal"], "awayteam": ["Chelsea"], "fthg": [2], "ftag": [1]})

        with disable_run_logger():
            with pytest.raises(ValueError, match="DataFrame must contain 'season' column"):
                load_data_to_db.fn(df_no_season, test_assets["database_url"])

    @patch("pipelines.data_ingestion.data_ingestion_common_tasks.inspect")
    @patch("pipelines.data_ingestion.data_ingestion_common_tasks.create_engine")
    def test_load_data_to_db_multiple_seasons(self, mock_create_engine, mock_inspect, test_assets):
        """Test loading DataFrame with multiple seasons."""
        # Create DataFrame with multiple seasons
        df_multi_season = pd.DataFrame(
            {
                "season": ["2324", "2324", "2425", "2425"],
                "hometeam": ["Arsenal", "Chelsea", "Liverpool", "Tottenham"],
                "awayteam": ["Brighton", "Newcastle", "Manchester City", "West Ham"],
                "fthg": [2, 1, 0, 3],
                "ftag": [0, 1, 2, 1],
            }
        )

        # Setup mocks
        mock_engine = MagicMock()
        mock_create_engine.return_value = mock_engine
        mock_connection = MagicMock()
        mock_engine.connect.return_value.__enter__.return_value = mock_connection

        mock_inspector = MagicMock()
        mock_inspector.get_table_names.return_value = ["english_league_data"]
        mock_inspect.return_value = mock_inspector

        mock_transaction = MagicMock()
        mock_connection.begin.return_value = mock_transaction

        mock_delete_result = MagicMock()
        mock_delete_result.rowcount = 2
        mock_connection.execute.return_value = mock_delete_result

        with patch.object(pd.DataFrame, "to_sql"):
            with disable_run_logger():
                load_data_to_db.fn(df_multi_season, test_assets["database_url"])

        # Verify delete was called for each season
        assert mock_connection.execute.call_count == 2  # Two unique seasons

    @patch("pipelines.data_ingestion.data_ingestion_common_tasks.inspect")
    @patch("pipelines.data_ingestion.data_ingestion_common_tasks.create_engine")
    def test_load_data_to_db_transaction_rollback(self, mock_create_engine, mock_inspect, raw_football_df, test_assets):
        """Test transaction rollback on error."""
        # Setup mocks
        mock_engine = MagicMock()
        mock_create_engine.return_value = mock_engine
        mock_connection = MagicMock()
        mock_engine.connect.return_value.__enter__.return_value = mock_connection

        mock_inspector = MagicMock()
        mock_inspector.get_table_names.return_value = ["english_league_data"]
        mock_inspect.return_value = mock_inspector

        mock_transaction = MagicMock()
        mock_connection.begin.return_value = mock_transaction

        # Mock delete to succeed but to_sql to fail
        mock_delete_result = MagicMock()
        mock_delete_result.rowcount = 5
        mock_connection.execute.return_value = mock_delete_result

        with patch.object(pd.DataFrame, "to_sql") as mock_to_sql:
            mock_to_sql.side_effect = SQLAlchemyError("Database error")

            with disable_run_logger():
                with pytest.raises(SQLAlchemyError):
                    load_data_to_db.fn(raw_football_df, test_assets["database_url"])

        # Verify transaction was rolled back
        mock_transaction.rollback.assert_called_once()
        mock_transaction.commit.assert_not_called()
