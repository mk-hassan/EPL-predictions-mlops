import json

import boto3
import pytest
from prefect_aws import AwsCredentials, AwsClientParameters
from prefect.variables import Variable
from testcontainers.postgres import PostgresContainer
from prefect.testing.utilities import prefect_test_harness
from testcontainers.localstack import LocalStackContainer

DEFAULT_AWS_REGION = "us-west-1"


@pytest.fixture(scope="session")
def postgres_container():
    """Start PostgreSQL container for testing."""
    with PostgresContainer(image="postgres:15", driver="psycopg") as postgres:
        yield postgres


@pytest.fixture(scope="session")
def localstack_container():
    """Start LocalStack container for AWS services."""
    with LocalStackContainer(image="localstack/localstack:latest", region_name=DEFAULT_AWS_REGION) as localstack:
        yield localstack


@pytest.fixture(scope="session")
def aws_credentials(localstack_container: LocalStackContainer):
    """Create AWS credentials for LocalStack."""
    return {
        "aws_access_key_id": "test",
        "aws_secret_access_key": "test",
        "region_name": localstack_container.region_name,
        "endpoint_url": localstack_container.get_url(),
    }


@pytest.fixture(scope="session")
def s3_bucket(aws_credentials: dict):
    """Create S3 bucket in LocalStack."""
    s3_client = boto3.client(service_name="s3", **aws_credentials)

    bucket_name = "test-epl-bucket"
    s3_client.create_bucket(
        Bucket=bucket_name, CreateBucketConfiguration={"LocationConstraint": aws_credentials["region_name"]}
    )

    return bucket_name


@pytest.fixture(scope="session")
def secrets_manager_secret(aws_credentials: dict, postgres_container: PostgresContainer):
    """Create database secret in LocalStack Secrets Manager."""
    secrets_client = boto3.client(service_name="secretsmanager", **aws_credentials)

    secret_name = "test-db-credentials"
    secrets_client.create_secret(
        Name=secret_name,
        SecretString=json.dumps(
            {
                "username": "test",
                "password": "test",
                "host": postgres_container.get_container_host_ip(),
                "port": postgres_container.get_exposed_port(5432),
                "dbname": "test",
            }
        ),
    )
    return secret_name


@pytest.fixture(scope="function")
def prefect_functional_setup(
    postgres_container: PostgresContainer,
    localstack_container: LocalStackContainer,
    s3_bucket: str,
    secrets_manager_secret: str,
    aws_credentials: dict,
):
    """Setup Prefect environment with real containers."""
    with prefect_test_harness():
        # Set Prefect Variables
        Variable.set("s3-epl-matches-datastore", s3_bucket)
        Variable.set("database-secrets", secrets_manager_secret)
        Variable.set("table-name", "english_football_data")

        # Create AWS Credentials block pointing to LocalStack
        aws_creds_block = AwsCredentials(
            aws_access_key_id=aws_credentials["aws_access_key_id"],
            aws_secret_access_key=aws_credentials["aws_secret_access_key"],
            region_name=aws_credentials["region_name"],
            aws_client_parameters=AwsClientParameters(endpoint_url=aws_credentials["endpoint_url"]),
        )
        aws_creds_block.save("aws-prefect-client-credentials")

        yield {
            "postgres": postgres_container,
            "localstack": localstack_container,
            "bucket_name": s3_bucket,
            "secret_name": secrets_manager_secret,
            "aws_credentials": aws_credentials,
        }
