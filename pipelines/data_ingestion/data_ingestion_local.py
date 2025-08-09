"""
Local Data Ingestion Pipeline for EPL Predictions

Fetches English Premier League match data from football-data.co.uk,
processes and stores it locally as parquet files and PostgreSQL database.

Main Functions:
- ingest_data(): Orchestrates the full pipeline
- save_local(): Stores data as parquet in local filesystem
- Uses local PostgreSQL database via configuration

Usage:
    from pipelines.data_ingestion.data_ingestion_local import ingest_data
    ingest_data(season="2425", division="E0")

    # Run with serve
    python data_ingestion_local.py
"""

from pathlib import Path

import pandas as pd
from prefect import flow, task, get_run_logger
from prefect.states import StateType
from prefect.futures import wait

from config import get_config
from src.models.DivisionEnum import Division

from .data_ingestion_common_tasks import ensure_division, load_data_to_db, get_current_season, get_season_results


@task(retries=3, retry_delay_seconds=5)
def save_local(file_name: str, df: pd.DataFrame) -> None:
    """Upload data to S3 bucket as parquet file."""
    logger = get_run_logger()
    logger.info(f"Uploading data to S3 bucket: {file_name}")

    if df.empty:
        logger.error("DataFrame is empty, cannot save locally")
        raise ValueError("DataFrame is empty, cannot save locally")

    # Create file path and ensure directory exists
    file_path = Path(__file__).parents[2] / "data" / "raw" / file_name
    file_path.parent.mkdir(parents=True, exist_ok=True)

    # Save the file
    df.to_parquet(file_path, index=False)

    logger.info(f"Data saved locally with file name '{file_name}'")


@flow(
    name="epl-data-ingestion-local",
    log_prints=True,
    retries=3,
    retry_delay_seconds=10,
    cache_result_in_memory=False,
)
def ingest_data(season: str | None = None, division: Division | str | None = Division.PREMIER_LEAGUE) -> None:
    """Main function to fetch, process, and store football data."""
    if season is None:
        season = get_current_season()

    division = ensure_division(division)

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
    save_local_future = save_local.submit(file_name, df)

    # Ensure table exists and load data to PostgreSQL
    database_url = get_config().database_url
    ingestion_future = load_data_to_db.submit(df, database_url)

    # Wait for all tasks to complete
    done, _ = wait([save_local_future, ingestion_future])
    if any(result.state.type == StateType.FAILED for result in done):
        logger.error("One or more tasks failed during data ingestion")
        raise RuntimeError("Data ingestion pipeline failed")

    logger.info("Data ingestion pipeline completed successfully")


if __name__ == "__main__":
    ingest_data.serve(
        name="local-data-ingestion-pipeline",
        tags=["data-ingestion", "epl-predictions"],
        description="Football data ingestion pipeline for the English Premier League",
        parameters={"division": Division.PREMIER_LEAGUE.value},
        limit=5,
    )
