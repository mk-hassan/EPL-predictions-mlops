import sys
from pathlib import Path

import pandas as pd
import pytest

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parents[2]))


@pytest.fixture(scope="session")
def football_test_data():
    """
    Session-scoped fixture that yields comprehensive football test data.

    This fixture is created once per test session and shared across all tests.
    Yields a dictionary containing various test datasets for different scenarios.
    """
    data = {
        "raw_football_data": {
            "Date": ["15/08/2024", "22/08/2024", "29/08/2024"],
            "HomeTeam": ["Arsenal", "Chelsea", "Liverpool"],
            "AwayTeam": ["Brighton", "Newcastle", "Manchester City"],
            "Referee": ["M. Oliver", "A. Taylor", "P. Tierney"],
            "FTHG": [2, 1, 0],
            "FTAG": [0, 1, 2],
            "FTR": ["H", "D", "A"],
            "HTHG": [1, 0, 0],
            "HTAG": [0, 1, 1],
            "HTR": ["H", "D", "A"],
            "HS": [15, 12, 8],
            "AS": [6, 14, 18],
            "HST": [8, 5, 3],
            "AST": [2, 6, 12],
            "HC": [7, 4, 2],
            "AC": [3, 8, 9],
            "HF": [12, 15, 18],
            "AF": [8, 11, 14],
            "HY": [2, 3, 4],
            "AY": [1, 2, 3],
            "HR": [0, 0, 1],
            "AR": [0, 1, 0],
            "WHH": [1.85, 2.10, 3.50],
            "WHD": [3.60, 3.40, 3.25],
            "WHA": [4.20, 3.75, 2.05],
            "Div": ["E0", "E0", "E0"],
            "season": ["2425", "2021", "2425"],
        },
        "invalid_dates_data": {
            "Date": ["15/08/2024", "invalid-date", "29/08/2024", ""],
            "HomeTeam": ["Arsenal", "Chelsea", "Liverpool", "Tottenham"],
            "AwayTeam": ["Brighton", "Newcastle", "Manchester City", "West Ham"],
            "Div": ["E0", "E0", "E0", "E0"],
            "FTHG": [2, 1, 0, 3],
            "FTAG": [0, 1, 2, 1],
            "FTR": ["H", "D", "A", "H"],
        },
        "duplicate_matches_data": {
            "Date": ["15/08/2024", "15/08/2024", "22/08/2024"],
            "HomeTeam": ["Arsenal", "Arsenal", "Chelsea"],
            "AwayTeam": ["Brighton", "Brighton", "Newcastle"],
            "Div": ["E0", "E0", "E0"],
            "FTHG": [2, 2, 1],
            "FTAG": [0, 0, 1],
            "FTR": ["H", "H", "D"],
        },
        "minimal_betting_data": {
            "Date": ["15/08/2024"],
            "HomeTeam": ["Arsenal"],
            "AwayTeam": ["Brighton"],
            "WHH": [1.85],
            "WHD": [3.60],
            "WHA": [4.20],
            "Div": ["E0"],
            "FTHG": [2],
            "FTAG": [0],
            "FTR": ["H"],
        },
        "expected_columns": [
            "div",
            "date",
            "hometeam",
            "awayteam",
            "referee",
            "fthg",
            "ftag",
            "ftr",
            "hthg",
            "htag",
            "htr",
            "hs",
            "as",
            "hst",
            "ast",
            "hc",
            "ac",
            "hf",
            "af",
            "hy",
            "ay",
            "hr",
            "ar",
            "whh",
            "whd",
            "wha",
            "season",
        ],
    }

    yield data


@pytest.fixture(scope="session")
def raw_football_df(football_test_data):
    """Session fixture that yields a raw football DataFrame."""
    yield pd.DataFrame(football_test_data["raw_football_data"])


@pytest.fixture(scope="session")
def invalid_dates_df(football_test_data):
    """Session fixture that yields DataFrame with invalid dates."""
    yield pd.DataFrame(football_test_data["invalid_dates_data"])


@pytest.fixture(scope="session")
def duplicate_matches_df(football_test_data):
    """Session fixture that yields DataFrame with duplicate matches."""
    yield pd.DataFrame(football_test_data["duplicate_matches_data"])


@pytest.fixture(scope="session")
def minimal_betting_df(football_test_data):
    """Session fixture that yields DataFrame with minimal betting data."""
    yield pd.DataFrame(football_test_data["minimal_betting_data"])


@pytest.fixture(scope="function")
def empty_df():
    """Function-scoped fixture for empty DataFrame (recreated for each test)."""
    yield pd.DataFrame()


@pytest.fixture(scope="session")
def expected_columns(football_test_data):
    """Session fixture that yields expected column names after cleaning."""
    yield football_test_data["expected_columns"]


# Additional helper fixtures
@pytest.fixture(scope="session")
def test_assets():
    """Session fixture for common configurations."""
    return {
        "database_url": "postgresql+psycopg://admin:admin@localhost:5432/epl_predictions",
        "s3_bucket": "test-epl-bucket",
        "season": "2425",
        "file_name": "test_2425_E0.parquet",
        "table_name": "epl_predictions",
    }
