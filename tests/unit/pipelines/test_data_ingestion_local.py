import sys
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from prefect.states import StateType
from prefect.logging import disable_run_logger

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parents[3]))

from src.models.DivisionEnum import Division
from pipelines.data_ingestion.data_ingestion_local import save_local, ingest_data


class TestSaveLocal:
    """Test cases for save_local function."""

    def test_save_local_success_with_real_file(self, tmpdir, raw_football_df):
        # Create unique test file name to avoid conflicts
        test_file_name = f"test_{uuid.uuid4().hex[:8]}_2425_E0.parquet"

        # Create the expected directory structure
        data_dir = Path(tmpdir) / "data" / "raw"
        expected_file_path = data_dir / test_file_name

        # Mock Path(__file__) to return a path in our temp directory
        mock_file_path = Path(tmpdir) / "pipelines" / "data_ingestion" / "data_ingestion_local.py"

        with patch("pipelines.data_ingestion.data_ingestion_local.__file__", new=str(mock_file_path)):
            # When Path(__file__) is called, return our mock path
            with disable_run_logger():
                save_local.fn(test_file_name, raw_football_df)

        # Verify file was actually created
        assert expected_file_path.exists(), f"File {expected_file_path} was not created"

        # Verify file content
        df_saved = pd.read_parquet(expected_file_path)
        pd.testing.assert_frame_equal(raw_football_df.reset_index(drop=True), df_saved.reset_index(drop=True))

    def test_save_local_empty_dataframe(self, empty_df):
        """Test save_local with empty DataFrame."""
        with disable_run_logger():
            with pytest.raises(ValueError, match="DataFrame is empty, cannot save locally"):
                save_local.fn("test_file.parquet", empty_df)

    def test_save_local_creates_directory_structure(self, tmpdir, raw_football_df):
        """Test that save_local creates directory structure if it doesn't exist."""
        test_file_name = f"test_{uuid.uuid4().hex[:8]}_structure.parquet"

        # Start with empty temp directory (no data/raw structure)
        mock_file_path = Path(tmpdir) / "pipelines" / "data_ingestion" / "data_ingestion_local.py"
        expected_data_dir = Path(tmpdir) / "data" / "raw"
        expected_file_path = expected_data_dir / test_file_name

        # Verify directories don't exist initially
        assert not expected_data_dir.exists()

        with patch("pipelines.data_ingestion.data_ingestion_local.__file__", new=str(mock_file_path)):
            with disable_run_logger():
                save_local.fn(test_file_name, raw_football_df)

        # Verify directory structure was created
        assert expected_data_dir.exists(), "data/raw directory was not created"
        assert expected_file_path.exists(), "File was not created"

    def test_save_local_with_different_file_formats(self, tmpdir, raw_football_df):
        """Test save_local with different file names."""
        test_files = [
            f"test_{uuid.uuid4().hex[:8]}_2425_E0.parquet",
            f"test_{uuid.uuid4().hex[:8]}_2324_E1.parquet",
            f"test_{uuid.uuid4().hex[:8]}_championship_2425.parquet",
        ]

        mock_file_path = Path(tmpdir) / "pipelines" / "data_ingestion" / "data_ingestion_local.py"

        for file_name in test_files:
            expected_file_path = Path(tmpdir) / "data" / "raw" / file_name

            with patch("pipelines.data_ingestion.data_ingestion_local.__file__", new=str(mock_file_path)):
                with disable_run_logger():
                    save_local.fn(file_name, raw_football_df)

            assert expected_file_path.exists(), f"File {file_name} was not created"

    def test_save_local_permission_error(self, tmpdir, raw_football_df):
        """Test save_local when file system raises permission error."""
        mock_file_path = Path(tmpdir) / "pipelines" / "data_ingestion" / "data_ingestion_local.py"

        with patch("pipelines.data_ingestion.data_ingestion_local.__file__", new=str(mock_file_path)):
            # Mock to_parquet to raise PermissionError
            with patch.object(pd.DataFrame, "to_parquet") as mock_to_parquet:
                mock_to_parquet.side_effect = PermissionError("Permission denied")

                with disable_run_logger():
                    with pytest.raises(PermissionError, match="Permission denied"):
                        save_local.fn("test_file.parquet", raw_football_df)

    def test_save_local_with_betting_data(self, tmpdir, minimal_betting_df):
        """Test save_local with DataFrame containing betting odds."""
        test_file_name = f"test_{uuid.uuid4().hex[:8]}_betting.parquet"
        mock_file_path = Path(tmpdir) / "pipelines" / "data_ingestion" / "data_ingestion_local.py"
        expected_file_path = Path(tmpdir) / "data" / "raw" / test_file_name

        with patch("pipelines.data_ingestion.data_ingestion_local.__file__", new=str(mock_file_path)):
            with disable_run_logger():
                save_local.fn(test_file_name, minimal_betting_df)

        # Verify file exists and contains betting data
        assert expected_file_path.exists()
        df_saved = pd.read_parquet(expected_file_path)
        assert "WHH" in df_saved.columns
        assert "WHD" in df_saved.columns
        assert "WHA" in df_saved.columns

    def test_save_local_file_already_exists(self, tmpdir, raw_football_df):
        """Test overwriting existing file."""
        test_file_name = f"test_{uuid.uuid4().hex[:8]}_overwrite.parquet"
        mock_file_path = Path(tmpdir) / "pipelines" / "data_ingestion" / "data_ingestion_local.py"
        expected_file_path = Path(tmpdir) / "data" / "raw" / test_file_name

        # Create the file first
        expected_file_path.parent.mkdir(parents=True, exist_ok=True)
        raw_football_df.iloc[:1].to_parquet(expected_file_path, index=False)  # Save 1 row

        # Verify file exists with 1 row
        assert expected_file_path.exists()
        df_original = pd.read_parquet(expected_file_path)
        assert len(df_original) == 1

        with patch("pipelines.data_ingestion.data_ingestion_local.__file__", new=str(mock_file_path)):
            with disable_run_logger():
                save_local.fn(test_file_name, raw_football_df)  # Save full dataset

        # Verify file was overwritten with full dataset
        df_new = pd.read_parquet(expected_file_path)
        assert len(df_new) == len(raw_football_df)  # Should be full dataset now


class TestIngestData:
    """Test cases for ingest_data flow function."""

    @patch("pipelines.data_ingestion.data_ingestion_local.get_config")
    @patch("pipelines.data_ingestion.data_ingestion_local.load_data_to_db")
    @patch("pipelines.data_ingestion.data_ingestion_local.save_local")
    @patch("pipelines.data_ingestion.data_ingestion_local.get_season_results")
    @patch("pipelines.data_ingestion.data_ingestion_local.get_current_season")
    def test_ingest_data_success_with_default_season(
        self,
        mock_get_current_season,
        mock_get_season_results,
        mock_save_local,
        mock_load_data_to_db,
        mock_get_config,
        raw_football_df,
    ):
        """Test successful data ingestion with default season."""
        # Setup mocks
        mock_get_current_season.return_value = "2425"
        mock_get_season_results.return_value = raw_football_df

        mock_config = MagicMock()
        mock_config.database_url = "postgresql://test:test@localhost:5432/test"
        mock_get_config.return_value = mock_config

        # Mock successful task futures
        mock_save_future = MagicMock()
        mock_save_future.state.type = StateType.COMPLETED
        mock_save_local.submit.return_value = mock_save_future

        mock_load_future = MagicMock()
        mock_load_future.state.type = StateType.COMPLETED
        mock_load_data_to_db.submit.return_value = mock_load_future

        # Mock wait function
        with patch("pipelines.data_ingestion.data_ingestion_local.wait") as mock_wait:
            mock_wait.return_value = ([mock_save_future, mock_load_future], [])

            with disable_run_logger():
                ingest_data.fn()

        # Verify function calls
        mock_get_current_season.assert_called_once()
        mock_get_season_results.assert_called_once_with("2425", "E0")
        mock_save_local.submit.assert_called_once_with("2425_E0.parquet", raw_football_df)
        mock_load_data_to_db.submit.assert_called_once_with(
            raw_football_df, "postgresql://test:test@localhost:5432/test"
        )

    @patch("pipelines.data_ingestion.data_ingestion_local.get_config")
    @patch("pipelines.data_ingestion.data_ingestion_local.load_data_to_db")
    @patch("pipelines.data_ingestion.data_ingestion_local.save_local")
    @patch("pipelines.data_ingestion.data_ingestion_local.get_season_results")
    def test_ingest_data_success_with_custom_parameters(
        self, mock_get_season_results, mock_save_local, mock_load_data_to_db, mock_get_config, raw_football_df
    ):
        """Test successful data ingestion with custom season and division."""
        # Setup mocks
        mock_get_season_results.return_value = raw_football_df

        mock_config = MagicMock()
        mock_config.database_url = "postgresql://test:test@localhost:5432/test"
        mock_get_config.return_value = mock_config

        # Mock successful task futures
        mock_save_future = MagicMock()
        mock_save_future.state.type = StateType.COMPLETED
        mock_save_local.submit.return_value = mock_save_future

        mock_load_future = MagicMock()
        mock_load_future.state.type = StateType.COMPLETED
        mock_load_data_to_db.submit.return_value = mock_load_future

        with patch("pipelines.data_ingestion.data_ingestion_local.wait") as mock_wait:
            mock_wait.return_value = ([mock_save_future, mock_load_future], [])

            with disable_run_logger():
                ingest_data.fn(season="2324", division=Division.CHAMPIONSHIP)

        # Verify function calls with custom parameters
        mock_get_season_results.assert_called_once_with("2324", "E1")  # Championship division
        mock_save_local.submit.assert_called_once_with("2324_E1.parquet", raw_football_df)

    @patch("pipelines.data_ingestion.data_ingestion_local.get_config")
    @patch("pipelines.data_ingestion.data_ingestion_local.load_data_to_db")
    @patch("pipelines.data_ingestion.data_ingestion_local.save_local")
    @patch("pipelines.data_ingestion.data_ingestion_local.get_season_results")
    def test_ingest_data_with_string_division(
        self, mock_get_season_results, mock_save_local, mock_load_data_to_db, mock_get_config, raw_football_df
    ):
        """Test data ingestion with division passed as string."""
        # Setup mocks
        mock_get_season_results.return_value = raw_football_df

        mock_config = MagicMock()
        mock_config.database_url = "postgresql://test:test@localhost:5432/test"
        mock_get_config.return_value = mock_config

        mock_save_future = MagicMock()
        mock_save_future.state.type = StateType.COMPLETED
        mock_save_local.submit.return_value = mock_save_future

        mock_load_future = MagicMock()
        mock_load_future.state.type = StateType.COMPLETED
        mock_load_data_to_db.submit.return_value = mock_load_future

        with patch("pipelines.data_ingestion.data_ingestion_local.wait") as mock_wait:
            mock_wait.return_value = ([mock_save_future, mock_load_future], [])

            with disable_run_logger():
                ingest_data.fn(season="2425", division="E0")

        # Verify string division is properly converted
        mock_get_season_results.assert_called_once_with("2425", "E0")
        mock_save_local.submit.assert_called_once_with("2425_E0.parquet", raw_football_df)

    @patch("pipelines.data_ingestion.data_ingestion_local.get_season_results")
    def test_ingest_data_fetch_data_failure(self, mock_get_season_results):
        """Test handling of data fetching failure."""
        mock_get_season_results.side_effect = Exception("API connection failed")

        with disable_run_logger():
            with pytest.raises(Exception, match="API connection failed"):
                ingest_data.fn(season="2425")

    @patch("pipelines.data_ingestion.data_ingestion_local.get_config")
    @patch("pipelines.data_ingestion.data_ingestion_local.load_data_to_db")
    @patch("pipelines.data_ingestion.data_ingestion_local.save_local")
    @patch("pipelines.data_ingestion.data_ingestion_local.get_season_results")
    def test_ingest_data_task_failure(
        self, mock_get_season_results, mock_save_local, mock_load_data_to_db, mock_get_config, raw_football_df
    ):
        """Test handling when one of the tasks fails."""
        # Setup mocks
        mock_get_season_results.return_value = raw_football_df

        mock_config = MagicMock()
        mock_config.database_url = "postgresql://test:test@localhost:5432/test"
        mock_get_config.return_value = mock_config

        # Mock one successful and one failed task
        mock_save_future = MagicMock()
        mock_save_future.state.type = StateType.COMPLETED
        mock_save_local.submit.return_value = mock_save_future

        mock_load_future = MagicMock()
        mock_load_future.state.type = StateType.FAILED  # This task fails
        mock_load_data_to_db.submit.return_value = mock_load_future

        with patch("pipelines.data_ingestion.data_ingestion_local.wait") as mock_wait:
            mock_wait.return_value = ({mock_save_future, mock_load_future}, {})

            with disable_run_logger():
                with pytest.raises(RuntimeError, match="pipeline failed"):
                    ingest_data.fn(season="2425")

    @patch("pipelines.data_ingestion.data_ingestion_local.get_config")
    @patch("pipelines.data_ingestion.data_ingestion_local.load_data_to_db")
    @patch("pipelines.data_ingestion.data_ingestion_local.save_local")
    @patch("pipelines.data_ingestion.data_ingestion_local.get_season_results")
    def test_ingest_data_with_empty_dataframe(
        self, mock_get_season_results, mock_save_local, mock_load_data_to_db, mock_get_config, empty_df
    ):
        """Test data ingestion with empty DataFrame from API."""
        # Setup mocks
        mock_get_season_results.return_value = empty_df

        mock_config = MagicMock()
        mock_config.database_url = "postgresql://test:test@localhost:5432/test"
        mock_get_config.return_value = mock_config

        mock_save_future = MagicMock()
        mock_save_future.state.type = StateType.COMPLETED
        mock_save_local.submit.return_value = mock_save_future

        mock_load_future = MagicMock()
        mock_load_future.state.type = StateType.COMPLETED
        mock_load_data_to_db.submit.return_value = mock_load_future

        with patch("pipelines.data_ingestion.data_ingestion_local.wait") as mock_wait:
            mock_wait.return_value = ([mock_save_future, mock_load_future], [])

            with disable_run_logger():
                ingest_data.fn(season="2425")

        # Should still attempt to save and load (error handling happens in tasks)
        mock_save_local.submit.assert_called_once_with("2425_E0.parquet", empty_df)
        mock_load_data_to_db.submit.assert_called_once_with(empty_df, "postgresql://test:test@localhost:5432/test")

    @patch("pipelines.data_ingestion.data_ingestion_local.get_config")
    @patch("pipelines.data_ingestion.data_ingestion_local.load_data_to_db")
    @patch("pipelines.data_ingestion.data_ingestion_local.save_local")
    @patch("pipelines.data_ingestion.data_ingestion_local.get_season_results")
    def test_ingest_data_file_name_generation(
        self, mock_get_season_results, mock_save_local, mock_load_data_to_db, mock_get_config, raw_football_df
    ):
        """Test that file names are generated correctly for different divisions."""
        test_cases = [
            ("2425", Division.PREMIER_LEAGUE, "2425_E0.parquet"),
            ("2324", Division.CHAMPIONSHIP, "2324_E1.parquet"),
            ("2223", "E2", "2223_E2.parquet"),  # League One
        ]

        for season, division, expected_filename in test_cases:
            # Setup mocks for each test case
            mock_get_season_results.return_value = raw_football_df

            mock_config = MagicMock()
            mock_config.database_url = "postgresql://test:test@localhost:5432/test"
            mock_get_config.return_value = mock_config

            mock_save_future = MagicMock()
            mock_save_future.state.type = StateType.COMPLETED
            mock_save_local.submit.return_value = mock_save_future

            mock_load_future = MagicMock()
            mock_load_future.state.type = StateType.COMPLETED
            mock_load_data_to_db.submit.return_value = mock_load_future

            with patch("pipelines.data_ingestion.data_ingestion_local.wait") as mock_wait:
                mock_wait.return_value = ([mock_save_future, mock_load_future], [])

                with disable_run_logger():
                    ingest_data.fn(season=season, division=division)

            # Verify correct file name was generated
            mock_save_local.submit.assert_called_with(expected_filename, raw_football_df)

            # Reset mocks for next iteration
            mock_save_local.reset_mock()
            mock_load_data_to_db.reset_mock()
