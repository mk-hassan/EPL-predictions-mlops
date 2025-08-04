"""
This module provides functions to load football data from an external source
football-data.co.uk  and save it to a local directory
or upload it to an S3 bucket,  as well as load the data into a PostgreSQL database.
"""

import sys
import json
from io import BytesIO
from pathlib import Path
from datetime import datetime, timedelta

import boto3
import pandas as pd
import requests
from prefect import flow, task, get_run_logger
from sqlalchemy import text, inspect, create_engine
from prefect_aws import AwsSecret, AwsCredentials
from prefect.futures import wait
from prefect.variables import Variable
from prefect.cache_policies import INPUTS, RUN_ID

# Add project root to Python path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
from pipelines.hooks import retry_handler
from pipelines.helpers import parse_football_date
from src.models.DivisionEnum import Division


# helpers
@task(retries=1, retry_delay_seconds=5)
def _get_current_season() -> str:
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
    """Snake casing column names, clean and format the date column in the DataFrame."""
    if len(df) == 0:
        raise ValueError("Received empty DataFrame, cannot clean data")

    logger = get_run_logger()

    df_cleaned = df.copy()  # Create a copy to avoid modifying original

    df_cleaned.columns = df_cleaned.columns.str.lower().str.replace(" ", "_")

    df_cleaned["date"] = df_cleaned["date"].apply(parse_football_date)
    df_cleaned = df_cleaned.dropna(subset=["date", "hometeam", "awayteam"])  # Drop rows with invalid dates

    df_cleaned["season"] = season
    df_cleaned = df_cleaned.drop_duplicates(subset=["date", "hometeam", "awayteam", "season", "div"])

    logger.info(f"Cleaned data: {len(df_cleaned)} rows, {len(df_cleaned.columns)} columns")

    return df_cleaned


@task(
    retries=1,
    retry_delay_seconds=10,
    persist_result=True,
    cache_policy=RUN_ID,
    cache_expiration=timedelta(hours=1),
)
def _get_database_url() -> str:
    """Get the database URL from environment variables or configuration."""
    secret_name = Variable.get("database-secrets")
    if not secret_name:
        raise ValueError("Database secrets not found in Prefect Variable 'database-secrets'")

    aws_credentials_block = AwsCredentials.load("aws-prefect-client-credentials")

    database_credentials = AwsSecret(
        aws_credentials=aws_credentials_block,
        secret_name=secret_name,
    ).read_secret()

    database_credentials = json.loads(database_credentials)

    return (
        f"postgresql+psycopg://{database_credentials['username']}:{database_credentials['password']}"
        f"@{database_credentials['host']}:{database_credentials['port']}/{database_credentials['dbname']}"
    )


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
    cleaned_df = _clean_data(season, df)

    data_definition_path = Path(__file__).parent.parent / "src/core/required_columns.json"
    if not data_definition_path.exists():
        logger.error(f"Data definition file not found: {data_definition_path}")
        raise FileNotFoundError(f"Data definition file not found: {data_definition_path}")

    with open(data_definition_path, encoding="utf-8") as f:
        data_definition = json.load(f)

    if "required_columns" not in data_definition:
        logger.error("Data definition JSON must contain 'required_columns' key")
        raise ValueError("Data definition JSON must contain 'required_columns' key")

    # raise if the columns are not present in the DataFrame
    missing_columns = set(data_definition["required_columns"]) - set(cleaned_df.columns)
    if missing_columns:
        logger.error(f"Missing required columns in DataFrame: {missing_columns}")
        raise ValueError(f"Missing required columns in DataFrame: {missing_columns}")

    required_columns = data_definition["required_columns"]
    return cleaned_df[required_columns]


@task(retries=3, retry_delay_seconds=5)
def upload_to_s3(file_name: str, df: pd.DataFrame) -> None:
    """Upload data to S3 bucket as parquet file."""
    logger = get_run_logger()
    logger.info(f"Uploading data to S3 bucket: {file_name}")

    if df.empty:
        logger.error("DataFrame is empty, cannot upload to S3")
        raise ValueError("DataFrame is empty, cannot upload to S3")

    # Ensure the bucket name is set in Prefect Variable
    data_bucket_name = Variable.get("s3-epl-matches-datastore")
    if data_bucket_name is None:
        raise ValueError("S3 bucket name is not set in Prefect Variable 's3-epl-matches-datastore'")

    aws_credentials_block = AwsCredentials.load("aws-prefect-client-credentials")
    s3_client = boto3.client(
        service_name="s3",
        aws_access_key_id=aws_credentials_block.aws_access_key_id,
        aws_secret_access_key=aws_credentials_block.aws_secret_access_key.get_secret_value(),
        region_name=aws_credentials_block.region_name,
        endpoint_url=aws_credentials_block.aws_client_parameters.endpoint_url,
    )

    parquet_buffer = BytesIO()
    df.to_parquet(parquet_buffer, index=False)
    s3_client.put_object(Bucket=data_bucket_name, Key=file_name, Body=parquet_buffer.getvalue())

    logger.info(f"Data uploaded to S3 bucket '{data_bucket_name}' with file name '{file_name}'")


@task(retries=3, retry_delay_seconds=5)
def load_data_to_db(df: pd.DataFrame) -> None:
    """Load DataFrame to PostgreSQL database using delete-then-insert by season."""
    database_url = _get_database_url()
    table_name = "english_league_data"
    logger = get_run_logger()

    if df.empty:
        logger.info("No data to load - DataFrame is empty")
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
                    delete_query = f"DELETE FROM {table_name} WHERE season = :season"
                    result = connection.execute(text(delete_query), {"season": season})
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


def _ensure_division(division: Division | str | None) -> Division:
    logger = get_run_logger()

    """Ensure division is a valid Division enum or string."""
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


@flow(
    name="epl-data-ingestion-aws",
    log_prints=True,
    retries=3,
    retry_delay_seconds=10,
    cache_result_in_memory=False,
)
def ingest_data(season: str | None = None, division: Division | str | None = Division.PREMIER_LEAGUE) -> None:
    """Main function to fetch, process, and store football data."""
    if season is None:
        season = _get_current_season()

    division = _ensure_division(division)

    logger = get_run_logger()
    logger.info(f"Starting data ingestion pipeline for season: {season}, division: {division.value}")

    # Fetch and clean data
    try:
        df = get_season_results(season, division.value)
        logger.debug(f"Data fetched and cleaned: {len(df)} rows, {len(df.columns)} columns")
    except Exception as e:
        logger.error(f"Failed to fetch or clean data for season {season}, division {division.value}: {str(e)[:100]}")
        raise

    # Upload to S3 and load to PostgreSQL
    file_name = f"{season}_{division.value}.parquet"
    upload_s3_future = upload_to_s3.submit(file_name, df)

    # Ensure table exists and load data to PostgreSQL
    ingestion_future = load_data_to_db.submit(df)

    # Wait for all tasks to complete
    wait([upload_s3_future, ingestion_future])
    logger.info("Data ingestion pipeline completed successfully")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Deploy EPL data ingestion pipeline")
    parser.add_argument(
        "--static",
        action="store_true",
        help="Deploy static serve deployment instead of dynamic cloud deployment",
    )

    args = parser.parse_args()

    if args.static:
        ingest_data.serve(
            name="aws-static-data-ingestion-pipeline",
            tags=["data-ingestion", "epl-predictions"],
            description="Football data ingestion pipeline for the English Premier League",
            parameters={"division": Division.PREMIER_LEAGUE.value},
            limit=5,
        )
    else:
        ingest_data.from_source(
            source="https://github.com/mk-hassan/EPL-predictions-mlops",
            entrypoint="pipelines/data_inggestion/data_inggestion_aws.py:ingest_data",
        ).deploy(
            name="aws-dynamic-data-ingestion-pipeline",
            flow_name="data-ingestion",
            work_pool_name="epl-predictions-pool",
            parameters={"division": Division.PREMIER_LEAGUE.value},
            concurrency_limit=1,
            description="Football data ingestion pipeline for the English Premier League",
            tags=["data-ingestion", "epl-predictions"],
            job_variables={"pip_packages": ["boto3==1.39.9", "pandas==2.3.1", "prefect-aws"]},
            schedule={
                "cron": "0 0 * 8-12,1-6 6",  # Every Saturday at 12:00 AM (midnight) from August to end of May
                "timezone": "UTC",
            },
        )
