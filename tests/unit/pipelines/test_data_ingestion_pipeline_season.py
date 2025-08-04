from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
import requests
from prefect.logging import disable_run_logger

from src.models.DivisionEnum import Division
from pipelines.data_ingestion_pipeline import get_season_results, _get_current_season


def test_get_current_season():
    """Test the _get_current_season function."""
    with disable_run_logger():
        season = _get_current_season.fn()

    # Check if the season is in the expected format "2425"
    assert len(season) == 4
    assert season.isdigit()

    # Check if the first two digits are less than or equal to 99
    assert int(season[:2]) <= 99
    assert int(season[2:]) <= 99

    # Check if the season is a valid football season (e.g., not in the future)
    from datetime import datetime

    current_year = datetime.now().year % 100
    assert int(season[:2]) <= current_year <= int(season[2:]) + 1


@patch("pipelines.data_ingestion_pipeline.requests.get")
def test_get_season_results_success(mock_get):
    """Test successful data fetch from external API."""
    # Mock successful response
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.content = b"Date,HomeTeam,AwayTeam,FTHG,FTAG\n15/08/2024,Arsenal,Brighton,2,0"
    mock_get.return_value = mock_response

    with disable_run_logger():
        result = get_season_results.fn("2425", Division.PREMIER_LEAGUE.value)

    # Verify API call
    expected_url = "https://www.football-data.co.uk/mmz4281/2425/E0.csv"
    mock_get.assert_called_once_with(expected_url, timeout=10)
    mock_response.raise_for_status.assert_called_once()

    # Verify result
    assert isinstance(result, pd.DataFrame)
    assert len(result) == 1
    assert "HomeTeam" in result.columns


@patch("pipelines.data_ingestion_pipeline.requests.get")
def test_get_season_results_http_error(mock_get):
    """Test HTTP error handling."""
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = requests.HTTPError("404 Not Found")
    mock_get.return_value = mock_response

    with disable_run_logger():
        with pytest.raises(requests.HTTPError):
            get_season_results.fn("9999", Division.PREMIER_LEAGUE.value)


@patch("pipelines.data_ingestion_pipeline.requests.get")
def test_get_season_results_timeout(mock_get):
    """Test timeout handling."""
    mock_get.side_effect = requests.Timeout("Request timed out")

    with disable_run_logger():
        with pytest.raises(requests.Timeout):
            get_season_results.fn("2425", Division.PREMIER_LEAGUE.value)


@patch("pipelines.data_ingestion_pipeline.requests.get")
def test_get_season_results_empty_response(mock_get):
    """Test empty CSV response."""
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.content = b""  # Empty content
    mock_get.return_value = mock_response

    with disable_run_logger():
        with pytest.raises(ValueError):
            get_season_results.fn("2425", Division.PREMIER_LEAGUE.value)


@patch("pipelines.data_ingestion_pipeline.requests.get")
def test_get_season_results_different_divisions(mock_get):
    """Test different division URLs are constructed correctly."""
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.content = b"Date,HomeTeam,AwayTeam\n15/08/2024,Arsenal,Brighton"
    mock_get.return_value = mock_response

    with disable_run_logger():
        # Test Championship
        get_season_results.fn("2425", Division.CHAMPIONSHIP.value)
        expected_url = "https://www.football-data.co.uk/mmz4281/2425/E1.csv"
        mock_get.assert_called_with(expected_url, timeout=10)
