import os
import argparse

from prefect_aws import AwsCredentials
from prefect.variables import Variable

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Setup Prefect variables and AWS credentials")

    # Prefect variables
    parser.add_argument("--database-secrets", help="Database secrets name")
    parser.add_argument("--s3-bucket", help="S3 bucket name")

    # AWS credentials
    parser.add_argument("--aws-access-key", help="AWS access key ID")
    parser.add_argument("--aws-secret-key", help="AWS secret access key")
    parser.add_argument("--aws-region", help="AWS region")

    args = parser.parse_args()

    # Use args or fallback to environment variables
    database_secrets = args.database_secrets or os.getenv("AWS_DATABASE_SECRETS_NAME")
    s3_bucket = args.s3_bucket or os.getenv("AWS_S3_BUCKET_NAME")
    aws_access_key = args.aws_access_key or os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret_key = args.aws_secret_key or os.getenv("AWS_SECRET_ACCESS_KEY")
    aws_region = args.aws_region or os.getenv("AWS_REGION")

    print("Setting up Prefect variables...")
    Variable.set(
        name="database-secrets",
        value=database_secrets,
        tags=["epl-predictions", "secrets"],
        overwrite=True,
    )

    Variable.set(
        name="s3-epl-matches-datastore",
        value=s3_bucket,
        tags=["epl-predictions", "s3"],
        overwrite=True,
    )

    print("Setting up AWS credentials...")
    AwsCredentials(
        aws_access_key_id=aws_access_key,
        aws_secret_access_key=aws_secret_key,
        region_name=aws_region,
    ).save("aws-prefect-client-credentials", overwrite=True)

    print("Setup complete!")
