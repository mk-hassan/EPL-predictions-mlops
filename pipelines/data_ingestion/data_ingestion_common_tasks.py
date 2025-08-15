"""
Common Data Ingestion Tasks for EPL Predictions

Shared functions used by both AWS and local data ingestion pipelines.
Handles data fetching, cleaning, validation, and database operations.

Main Functions:
- get_season_results(): Fetches and cleans football data from football-data.co.uk
- get_current_season(): Determines current football season based on date
- ensure_division(): Validates and converts division parameters
- load_data_to_db(): Loads data to PostgreSQL with transaction safety
- _clean_data(): Internal function for data cleaning and standardization

Usage:
    from data_ingestion_common_tasks import get_season_results, get_current_season

    season = get_current_season()
    df = get_season_results(season, "E0")
    load_data_to_db(df, database_url)
"""

from io import BytesIO
from datetime import datetime, timedelta

import pandas as pd
import requests
from prefect import task, get_run_logger
from sqlalchemy import text, inspect, create_engine
from prefect.cache_policies import INPUTS

from config import get_required_columns
from pipelines.utils import retry_handler, parse_match_date
from src.models.DivisionEnum import Division


def ensure_division(division: Division | str | None) -> Division:
    """Ensure division is a valid Division enum or string."""
    logger = get_run_logger()

    if isinstance(division, str):
        try:
            return Division(division)
        except ValueError as inner_error:
            valid_values = [d.value for d in Division]
            logger.error(f"Invalid division string: {division}. Must be one of: {valid_values}")
            raise ValueError(f"Invalid division: '{division}'. Valid division values: {valid_values}") from inner_error
    elif division is None:
        logger.warning(f"Division not provided, defaulting to Premier League ({Division.PREMIER_LEAGUE.value})")
        return Division.PREMIER_LEAGUE
    elif not isinstance(division, Division):
        logger.error(f"Invalid division type: {type(division)}. Expected Division enum or string.")
        raise ValueError(
            f"Invalid division type: {type(division)}. Expected Division enum or string, got {type(division)}."
        )
    return division


@task(retries=1, retry_delay_seconds=5)
def get_current_season() -> str:
    """Determine current football season based on current date."""

    current_date = datetime.now()
    current_month = current_date.month
    current_year = current_date.year

    # Football season typically runs from August to May
    # If current month is August or later, it's the start of a new season
    # If current month is before August, it's still the previous season
    if current_month >= 8:  # August onwards
        season_start_year = current_year
        season_end_year = current_year + 1
    else:  # January to July
        season_start_year = current_year - 1
        season_end_year = current_year

    # Format as "2425" style
    season = f"{str(season_start_year)[-2:]}{str(season_end_year)[-2:]}"

    logger = get_run_logger()
    logger.info(f"Current season determined as: {season} ({season_start_year}/{season_end_year})")

    return season


@task(retries=1, retry_delay_seconds=5)
def _clean_data(season: str, df: pd.DataFrame) -> pd.DataFrame:
    """Clean and standardize DataFrame with column formatting, date parsing, and validation."""
    logger = get_run_logger()

    # Step 1: Input validation
    if len(df) == 0:
        raise ValueError("Received empty DataFrame, cannot clean data")

    # Step 2: Create working copy and standardize column names
    df_cleaned = df.copy()
    df_cleaned.columns = df_cleaned.columns.str.lower().str.replace(" ", "_")
    logger.debug("Standardized column names to snake_case")

    # Step 3: Parse and clean date column
    df_cleaned["date"] = df_cleaned["date"].apply(parse_match_date)
    initial_rows = len(df_cleaned)
    df_cleaned = df_cleaned.dropna()
    for col in df_cleaned.select_dtypes(include=["object"]).columns:
        df_cleaned = df_cleaned[df_cleaned[col].str.strip() != ""]
    dropped_rows = initial_rows - len(df_cleaned)
    if dropped_rows > 0:
        logger.warning(f"Dropped {dropped_rows} rows with invalid dates or missing team names")

    # Step 4: Add season identifier and remove duplicates
    df_cleaned["season"] = season
    initial_rows = len(df_cleaned)
    df_cleaned = df_cleaned.drop_duplicates(subset=["date", "hometeam", "awayteam", "season", "div"])
    duplicate_rows = initial_rows - len(df_cleaned)
    if duplicate_rows > 0:
        logger.info(f"Removed {duplicate_rows} duplicate matches")

    # Step 5: Validate required columns
    required_columns = get_required_columns()
    if not required_columns:
        raise ValueError("No required columns found in configuration file")

    missing_columns = set(required_columns) - set(df_cleaned.columns)
    if missing_columns:
        logger.error(f"Missing required columns in DataFrame: {missing_columns}")
        raise ValueError(f"Missing required columns in DataFrame: {missing_columns}")

    # Step 6: Return final cleaned dataset
    logger.info(f"Data cleaning completed: {len(df_cleaned)} rows, {len(required_columns)} columns")
    return df_cleaned[required_columns]


@task(
    retries=3,
    retry_condition_fn=retry_handler,
    persist_result=True,
    cache_policy=INPUTS,
    cache_result_in_memory=False,
    cache_expiration=timedelta(days=6),
)
def get_season_results(season: str, division_code: str) -> pd.DataFrame:
    """Fetch football data for a specific season and division"""
    logger = get_run_logger()

    url = f"https://www.football-data.co.uk/mmz4281/{season}/{division_code}.csv"

    logger.info(f"Fetching data from URL: {url}")
    response = requests.get(url, timeout=10)
    response.raise_for_status()

    if not response.content:
        logger.error(f"Empty response received for season {season}, division {division_code}")
        raise ValueError(f"No data available for season {season}, division {division_code}")

    df = pd.read_csv(BytesIO(response.content))
    return _clean_data(season, df)


@task(retries=3, retry_delay_seconds=5)
def load_data_to_db(df: pd.DataFrame, database_url: str) -> None:
    """Load DataFrame to PostgreSQL database using delete-then-insert by season."""
    table_name = "english_league_data"
    logger = get_run_logger()

    if df.empty:
        logger.warning("No data to load - DataFrame is empty")
        return

    # Get the season from the DataFrame
    if "season" not in df.columns:
        logger.error("DataFrame must contain 'season' column")
        raise ValueError("DataFrame must contain 'season' column")

    seasons = df["season"].unique()
    logger.info(f"Processing data for seasons: {list(seasons)}")

    engine = create_engine(database_url)

    with engine.connect() as connection:
        # Check if table exists
        inspector = inspect(engine)
        table_exists = table_name in inspector.get_table_names()

        if table_exists:
            logger.info(f"Table '{table_name}' exists - deleting existing data for seasons: {list(seasons)}")

            # Start transaction for delete operations
            transaction = connection.begin()

            try:
                total_deleted = 0

                # Delete existing data for each season
                for season in seasons:
                    delete_query = text("DELETE FROM english_league_data WHERE season = :season")
                    result = connection.execute(delete_query, {"season": season})
                    deleted_count = result.rowcount
                    total_deleted += deleted_count
                    logger.info(f"Deleted {deleted_count} existing rows for season {season}")

                # Insert all new data
                df.to_sql(
                    table_name,
                    con=connection,
                    if_exists="append",
                    index=False,
                    method="multi",
                )
                inserted_count = len(df)

                # Commit the transaction
                transaction.commit()

                logger.info(
                    f"Data replacement completed: {total_deleted} rows deleted, {inserted_count} new rows inserted"
                )

            except Exception as e:
                # Rollback the transaction on error
                transaction.rollback()
                logger.error("Error during data loading, transaction rolled back")
                raise e
        else:
            logger.info(f"Table '{table_name}' does not exist - creating new table and inserting data")

            df.to_sql(
                table_name,
                con=connection,
                if_exists="replace",
                index=False,
                method="multi",
            )
            logger.info(f"Table '{table_name}' created and {len(df)} rows inserted")
