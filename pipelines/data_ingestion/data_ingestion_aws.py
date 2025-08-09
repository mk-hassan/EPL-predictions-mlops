"""
AWS Data Ingestion Pipeline for EPL Predictions

Fetches English Premier League match data from football-data.co.uk,
processes and stores it in AWS S3 and PostgreSQL database.

Main Functions:
- ingest_data(): Orchestrates the full pipeline
- upload_to_s3(): Stores data as parquet in S3
- _get_database_url(): Retrieves database connection from AWS Secrets Manager

Usage:
    from pipelines.data_ingestion.data_ingestion_aws import ingest_data
    ingest_data(season="2425", division="E0")

    # Run with arguments
    python data_ingestion_aws.py --static
"""

import json
from io import BytesIO
from datetime import timedelta

import boto3
import pandas as pd
from prefect import flow, task, get_run_logger
from prefect_aws import AwsSecret, AwsCredentials
from prefect.states import StateType
from prefect.futures import wait
from prefect.variables import Variable
from prefect.cache_policies import RUN_ID

from config import get_config
from src.models.DivisionEnum import Division

from .data_ingestion_common_tasks import ensure_division, load_data_to_db, get_current_season, get_season_results


@task(
    retries=1,
    retry_delay_seconds=10,
    persist_result=True,
    cache_policy=RUN_ID,
    cache_expiration=timedelta(hours=1),
)
def _get_database_url() -> str:
    """Get the database URL from environment variables or configuration."""
    logger = get_run_logger()

    secret_name = Variable.get("database-secrets")
    if not secret_name:
        raise ValueError("Database secrets not found in Prefect Variable 'database-secrets'")

    try:
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
    except Exception as e:
        logger.error(f"Failed to access AWS Secrets Manager for database URL: {str(e)[:100]}")
        logger.warning("Failed to retrieve database URL from AWS Secrets Manager, using config instead")
        return get_config().database_url


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
    s3_client.put_object(Bucket=data_bucket_name, Key=f"raw/{file_name}", Body=parquet_buffer.getvalue())

    logger.info(f"Data uploaded to S3 bucket '{data_bucket_name}' with file name '{file_name}'")


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
    upload_s3_future = upload_to_s3.submit(file_name, df)

    # Ensure table exists and load data to PostgreSQL
    database_url = _get_database_url.submit()
    ingestion_future = load_data_to_db.submit(df, database_url.result())

    # Wait for all tasks to complete
    done, _ = wait([upload_s3_future, ingestion_future])
    if any(result.state.type == StateType.FAILED for result in done):
        logger.error("One or more tasks failed during data ingestion")
        raise RuntimeError("Data ingestion pipeline failed")

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
