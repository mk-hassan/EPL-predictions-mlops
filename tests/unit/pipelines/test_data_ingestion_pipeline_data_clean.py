import pandas as pd
import pytest
from prefect.logging import disable_run_logger

from pipelines.data_ingestion_pipeline import _clean_data


def test_clean_data_basic_functionality():
    """Test the basic functionality of _clean_data function."""
    # Create test DataFrame with mixed case columns and various data
    test_data = {
        "Date": ["15/08/2024", "22/08/2024", "29/08/2024"],
        "HomeTeam": ["Arsenal", "Chelsea", "Liverpool"],
        "AwayTeam": ["Brighton", "Newcastle", "Manchester City"],
        "FTHG": [2, 1, 0],
        "FTAG": [0, 1, 2],
        "FTR": ["H", "D", "A"],
        "Div": ["E0", "E0", "E0"],
    }
    df = pd.DataFrame(test_data)
    season = "2425"

    with disable_run_logger():
        result = _clean_data.fn(season, df)

    # Check column names are snake_case
    expected_columns = ["date", "hometeam", "awayteam", "fthg", "ftag", "ftr", "div", "season"]
    assert all(col in result.columns for col in expected_columns)
    assert all(col.islower() for col in result.columns)
    assert all("_" not in col or col.replace("_", "").isalnum() for col in result.columns)

    # Check date conversion
    assert pd.api.types.is_datetime64_any_dtype(result["date"])
    assert result["date"].iloc[0] == pd.Timestamp("2024-08-15")

    # Check season column added
    assert (result["season"] == season).all()

    # Check original data preserved
    assert len(result) == 3
    assert result["hometeam"].iloc[0] == "Arsenal"


def test_clean_data_with_invalid_dates():
    """Test _clean_data function with invalid dates."""
    test_data = {
        "Date": ["15/08/2024", "invalid-date", "29/08/2024", ""],
        "HomeTeam": ["Arsenal", "Chelsea", "Liverpool", "Tottenham"],
        "AwayTeam": ["Brighton", "Newcastle", "Manchester City", "West Ham"],
        "Div": ["E0", "E0", "E0", "E0"],
    }
    df = pd.DataFrame(test_data)
    season = "2425"

    with disable_run_logger():
        result = _clean_data.fn(season, df)

    # Should drop rows with invalid dates
    assert len(result) == 2
    assert result["date"].iloc[0] == pd.Timestamp("2024-08-15")
    assert result["hometeam"].iloc[0] == "Arsenal"


def test_clean_data_with_duplicates():
    """Test _clean_data function removes duplicates."""
    test_data = {
        "Date": ["15/08/2024", "15/08/2024", "22/08/2024"],
        "HomeTeam": ["Arsenal", "Arsenal", "Chelsea"],
        "AwayTeam": ["Brighton", "Brighton", "Newcastle"],
        "Div": ["E0", "E0", "E0"],
    }
    df = pd.DataFrame(test_data)
    season = "2425"

    with disable_run_logger():
        result = _clean_data.fn(season, df)

    # Should remove duplicate matches
    assert len(result) == 2  # One duplicate removed
    assert result["hometeam"].tolist() == ["Arsenal", "Chelsea"]


def test_clean_data_with_spaces_in_column_names():
    """Test _clean_data function handles column names with spaces."""
    test_data = {
        "Date": ["15/08/2024"],
        "HomeTeam": ["Arsenal"],
        "AwayTeam": ["Brighton"],
        "Full Time Home Goals": [2],
        "Full Time Away Goals": [0],
        "Div": ["E0"],
    }
    df = pd.DataFrame(test_data)
    season = "2425"

    with disable_run_logger():
        result = _clean_data.fn(season, df)

    # Check spaces replaced with underscores
    expected_columns = ["date", "hometeam", "awayteam", "full_time_home_goals", "full_time_away_goals", "div", "season"]
    assert all(col in result.columns for col in expected_columns)


def test_clean_data_empty_dataframe():
    """Test _clean_data function with empty DataFrame."""
    df = pd.DataFrame()
    season = "2425"

    # Check for ValueError
    with pytest.raises(ValueError):
        _clean_data.fn(season, df)


def test_clean_data_missing_date_column():
    """Test _clean_data function when date column is missing."""
    test_data = {"HomeTeam": ["Arsenal"], "AwayTeam": ["Brighton"], "Div": ["E0"]}
    df = pd.DataFrame(test_data)
    season = "2425"

    with disable_run_logger():
        with pytest.raises(KeyError):
            _clean_data.fn(season, df)


def test_clean_data_all_null_dates():
    """Test _clean_data function when all dates are null."""
    test_data = {
        "Date": [None, "", "invalid"],
        "HomeTeam": ["Arsenal", "Chelsea", "Liverpool"],
        "AwayTeam": ["Brighton", "Newcastle", "Manchester City"],
        "Div": ["E0", "E0", "E0"],
    }
    df = pd.DataFrame(test_data)
    season = "2425"

    with disable_run_logger():
        result = _clean_data.fn(season, df)

    # Should return empty DataFrame after dropping invalid dates
    assert len(result) == 0
    assert "season" in result.columns
