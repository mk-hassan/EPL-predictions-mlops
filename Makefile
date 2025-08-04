start-infra:
	cd terraform && terraform init
	cd terraform && terraform validate

apply-base-infra: start-infra
	cd terraform && terraform apply -auto-approve \
		-target=aws_s3_bucket.mlflow_artifacts \
		-target=aws_s3_bucket.data_storage \
		-target=aws_db_instance.postgres \
		-target=aws_secretsmanager_secret_version.db_credentials \
		-target=postgresql_database.mlflow_db

prefect-config-vars: apply-base-infra
	prefect variable set s3-epl-matches-datastore $$(cd terraform && terraform output -raw data_storage_bucket) --overwrite
	prefect variable set database-secrets $$(cd terraform && terraform output -raw db_credentials_secret_name) --overwrite

prefect-managed-pool:
# Create Prefect work pool
	prefect work-pool create epl-predictions-pool --type prefect:managed --set-as-default --overwrite

prefect-destroy:
	prefect variable unset s3-epl-matches-datastore
	prefect variable unset database-secrets

# Delete Prefect work pool
	prefect work-pool delete epl-predictions-pool

run-mlflow:
	mlflow server -h 0.0.0.0 -p 5000 \
	--backend-store-uri $$(cd terraform && terraform output -raw get_mlflow_database_uri) \
	--default-artifact-root s3://$$(cd terraform &&terraform output -raw mlflow_artifacts_bucket)
