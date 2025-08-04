# from uuid import uuid4

# import pytest
# from prefect.client.orchestration import get_client
# from prefect.testing.utilities import prefect_test_harness
# from prefect.variables import Variable
# from prefect_aws import AwsCredentials


# @pytest.fixture(scope="session")
# def prefect_test_fixture():
#     with prefect_test_harness():
#         yield

# @pytest.fixture(scope="session")
# def prefect_variables():
#     return {
#         "database-secrets": "epl-predictions-db-credentials",
#         "s3-epl-matches-datastore": "epl-predictions-data-storage",
#         "table-name": "english_league_data"
#     }

# @pytest.fixture(autouse=True, scope="session")
# def prefect_prequisites(prefect_test_fixture, prefect_variables):
#     for key, value in prefect_variables.items():
#         Variable.set(key, value)

#     aws_creds = AwsCredentials(
#         aws_access_key_id=str(uuid4()),
#         aws_secret_access_key=str(uuid4())
#     )
#     aws_creds.save("aws-prefect-client-credentials", overwrite=False)

#     yield

#     # teardown
#     # Delete variables
#     for key in prefect_variables.keys():
#         Variable.unset(key)

#     # Delete AWS credentials block
#     client = get_client(sync_client=True)
#     client.delete_block_document(aws_creds._block_document_id)
