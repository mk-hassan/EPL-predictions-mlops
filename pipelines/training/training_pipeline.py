import io
import sys
import json
from pathlib import Path
from datetime import datetime, timedelta

import boto3
import mlflow
import pandas as pd
from mlflow import MlflowClient
from prefect import flow, task, get_run_logger
from catboost import Pool, CatBoostClassifier
from prefect_aws import AwsCredentials
from prefect.futures import wait
from sklearn.metrics import (
    f1_score,
    recall_score,
    roc_auc_score,
    accuracy_score,
    precision_score,
    classification_report,
)
from prefect.variables import Variable
from prefect.cache_policies import INPUTS, RUN_ID
from sklearn.model_selection import train_test_split

# Add project root to Python path
sys.path.append(str(Path(__file__).resolve().parent.parent))
from pipelines.utils.hooks import retry_handler


@task(
    retries=3,
    retry_condition_fn=retry_handler,
    persist_result=True,
    cache_policy=RUN_ID,
    cache_expiration=timedelta(hours=6),
)
def load_data_from_s3():
    """Load processed features from S3 using AWS credentials."""
    logger = get_run_logger()

    # Get S3 bucket from Prefect Variable
    data_bucket_name = Variable.get("s3-epl-matches-datastore")
    if not data_bucket_name:
        raise ValueError("S3 bucket name not found in Prefect Variable 's3-epl-matches-datastore'")

    # Load AWS credentials
    aws_credentials_block = AwsCredentials.load("aws-prefect-client-credentials")

    s3_client = boto3.client(
        service_name="s3",
        aws_access_key_id=aws_credentials_block.aws_access_key_id,
        aws_secret_access_key=aws_credentials_block.aws_secret_access_key.get_secret_value(),
        region_name=aws_credentials_block.region_name,
        endpoint_url=aws_credentials_block.aws_client_parameters.endpoint_url,
    )

    file_name = "processed/epl_features.parquet"

    logger.info(f"Loading data from S3: s3://{data_bucket_name}/{file_name}")

    try:
        response = s3_client.get_object(Bucket=data_bucket_name, Key=file_name)
        df = pd.read_parquet(io.BytesIO(response["Body"].read()))

        if df.empty:
            raise ValueError("Loaded DataFrame is empty")

        logger.info(f"✅ Loaded {len(df)} rows, {len(df.columns)} columns from S3")
        return df

    except Exception as e:
        logger.error(f"❌ Failed to load data from S3: {str(e)}")
        raise


@task(persist_result=True, cache_policy=INPUTS, cache_expiration=timedelta(hours=2))
def prepare_features(df: pd.DataFrame):
    """Prepare features and target variables with validation."""
    logger = get_run_logger()

    if df.empty:
        raise ValueError("Input DataFrame is empty")

    # Fill missing values
    df_ml = df.fillna(0.0, inplace=False)

    # Define feature columns
    feature_cols = [
        col
        for col in df_ml.columns
        if not col.startswith("target_") and col not in ["match_id", "date", "div", "season"]
    ]

    if not feature_cols:
        raise ValueError("No feature columns found in DataFrame")

    X = df_ml[feature_cols]
    y = df_ml["target_result"]

    # Validate target variable
    if y.isnull().sum() > 0:
        logger.warning(f"Found {y.isnull().sum()} null values in target variable")
        # Drop rows with null targets
        mask = y.notnull()
        X = X[mask]
        y = y[mask]

    # Get categorical columns
    categorical_cols = df_ml.select_dtypes(include=["object"]).columns.tolist()
    categorical_cols = [col for col in categorical_cols if col in feature_cols]

    logger.info(f"✅ Prepared {len(feature_cols)} features, {len(categorical_cols)} categorical")
    logger.info(f"✅ Dataset shape: {X.shape}, Target classes: {y.unique()}")

    return X, y, feature_cols, categorical_cols


@task(persist_result=True, cache_policy=INPUTS, cache_expiration=timedelta(hours=2))
def split_data(X: pd.DataFrame, y: pd.Series):
    """Split data into train and validation sets with stratification."""
    logger = get_run_logger()

    if len(X) != len(y):
        raise ValueError(f"Feature matrix and target have different lengths: {len(X)} vs {len(y)}")

    # Check class distribution
    class_counts = y.value_counts()
    logger.info(f"Class distribution: {class_counts.to_dict()}")

    # Ensure minimum samples per class for stratification
    min_class_size = class_counts.min()
    if min_class_size < 2:
        logger.warning(f"Minimum class size is {min_class_size}, stratification may fail")

    X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.2, stratify=y, random_state=42)

    logger.info(f"✅ Split data: Train={len(X_train)}, Val={len(X_val)}")
    logger.info(f"Train class distribution: {y_train.value_counts().to_dict()}")
    logger.info(f"Val class distribution: {y_val.value_counts().to_dict()}")

    return X_train, X_val, y_train, y_val


@task(retries=2, retry_delay_seconds=30)
def get_mlflow_config():
    """Get MLflow configuration from Prefect Variables."""
    logger = get_run_logger()

    # Get MLflow tracking URI from Variable (fallback to localhost)
    mlflow_uri = Variable.get("mlflow-tracking-uri", default="http://localhost:5000")
    experiment_name = Variable.get("mlflow-experiment-name", default="epl_predictions")

    logger.info(f"Using MLflow URI: {mlflow_uri}")
    logger.info(f"Using experiment: {experiment_name}")

    return mlflow_uri, experiment_name


@task(
    retries=3,
    retry_condition_fn=retry_handler,
    persist_result=True,
    cache_expiration=timedelta(minutes=30),
)
def train_catboost_model(
    X_train: pd.DataFrame,
    X_val: pd.DataFrame,
    y_train: pd.Series,
    y_val: pd.Series,
    categorical_cols: list,
):
    """Train the final CatBoost model with comprehensive logging."""
    logger = get_run_logger()

    # Get MLflow configuration
    mlflow_uri, experiment_name = get_mlflow_config()

    # Set up MLflow
    mlflow.set_tracking_uri(mlflow_uri)
    mlflow.set_experiment(experiment_name)

    # Create CatBoost pools
    train_pool = Pool(X_train, label=y_train, cat_features=categorical_cols)
    val_pool = Pool(X_val, label=y_val, cat_features=categorical_cols)

    # Get best parameters from Variable or use defaults
    try:
        best_params_json = Variable.get("catboost-best-params")
        if best_params_json:
            best_params = json.loads(best_params_json)
            logger.info("✅ Loaded best parameters from Prefect Variable")
        else:
            raise ValueError("No parameters found")
    except Exception as e:
        logger.warning(f"Could not load parameters from Variable: {e}")
        # Default parameters
        best_params = {
            "depth": 6,
            "learning_rate": 0.1,
            "l2_leaf_reg": 3.0,
            "iterations": 200,
            "loss_function": "MultiClass",
            "verbose": 0,
            "cat_features": categorical_cols,
        }
        logger.info("Using default parameters")

    logger.info(f"🚀 Training CatBoost model with params: {best_params}")

    run_name = f"catboost_final_model_prefect_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    with mlflow.start_run(
        run_name=run_name,
        tags={
            "model": "catboost",
            "type": "final",
            "pipeline": "prefect",
            "environment": "production",
        },
        description="Final CatBoost model trained via Prefect pipeline",
    ):
        # Train model
        model = CatBoostClassifier(**best_params)
        model.fit(train_pool, eval_set=val_pool, early_stopping_rounds=30)

        # Make predictions
        y_pred = model.predict(X_val)
        y_pred_proba = model.predict_proba(X_val)

        # Calculate comprehensive metrics
        metrics = {
            "accuracy": accuracy_score(y_val, y_pred),
            "f1_macro": f1_score(y_val, y_pred, average="macro"),
            "f1_weighted": f1_score(y_val, y_pred, average="weighted"),
            "precision_macro": precision_score(y_val, y_pred, average="macro"),
            "recall_macro": recall_score(y_val, y_pred, average="macro"),
            "roc_auc": roc_auc_score(y_val, y_pred_proba, multi_class="ovr", average="macro"),
            "train_size": len(X_train),
            "val_size": len(X_val),
            "num_features": len(X_train.columns),
            "num_categorical": len(categorical_cols),
        }

        # Log parameters and metrics
        mlflow.log_params(best_params)
        for metric_name, metric_value in metrics.items():
            mlflow.log_metric(metric_name, metric_value)

        # Log classification report
        report = classification_report(y_val, y_pred, output_dict=True)
        mlflow.log_dict(report, "classification_report.json")

        # Log feature importance
        feature_importance = pd.DataFrame(
            {"feature": X_train.columns, "importance": model.feature_importances_}
        ).sort_values("importance", ascending=False)

        mlflow.log_dict(feature_importance.to_dict("records"), "feature_importance.json")

        # Log model
        mlflow.catboost.log_model(model, "model", registered_model_name="epl-predictions-catboost")

        # Get run info
        run_id = mlflow.active_run().info.run_id

        logger.info("✅ Model training completed!")
        logger.info(f"📊 Metrics: {metrics}")
        logger.info(f"🔗 MLflow Run ID: {run_id}")

        return model, metrics, run_id


@task(retries=3, retry_delay_seconds=5)
def register_model(run_id: str):
    """Register the model in MLflow Model Registry with comprehensive metadata."""
    logger = get_run_logger()

    mlflow_uri, _ = get_mlflow_config()
    mlflow.set_tracking_uri(mlflow_uri)

    client = MlflowClient()
    model_name = "epl-predictions-catboost"

    try:
        # Create registered model if it doesn't exist
        try:
            client.create_registered_model(
                name=model_name,
                tags={
                    "creator": "prefect-pipeline",
                    "problem": "epl-predictions",
                    "model_type": "catboost",
                    "created_date": datetime.now().isoformat(),
                },
                description="CatBoost model for EPL match predictions trained via Prefect pipeline",
            )
            logger.info(f"✅ Created new registered model: {model_name}")
        except Exception:
            logger.info(f"📝 Model {model_name} already exists")

        # Create model version
        model_version = client.create_model_version(
            name=model_name,
            source=f"runs:/{run_id}/model",
            tags={
                "pipeline": "prefect",
                "type": "catboost",
                "training_date": datetime.now().isoformat(),
                "run_id": run_id,
            },
            description=f"CatBoost model from Prefect pipeline - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        )

        # Set alias for latest version
        client.set_registered_model_alias(model_name, "production", model_version.version)

        # Also set staging alias
        client.set_registered_model_alias(model_name, "staging", model_version.version)

        logger.info(f"✅ Registered model version: {model_version.version}")
        logger.info(f"🏷️ Set 'production' and 'staging' aliases to version {model_version.version}")

        return model_version.version

    except Exception as e:
        logger.error(f"❌ Error registering model: {e}")
        raise


@task
def validate_model_performance(metrics: dict):
    """Validate model performance against thresholds."""
    logger = get_run_logger()

    # Get performance thresholds from Variables
    min_accuracy = float(Variable.get("min-model-accuracy", default="0.4"))
    min_f1_macro = float(Variable.get("min-model-f1-macro", default="0.35"))

    logger.info("Validating model performance against thresholds:")
    logger.info(f"  Minimum accuracy: {min_accuracy}")
    logger.info(f"  Minimum F1-macro: {min_f1_macro}")

    if metrics["accuracy"] < min_accuracy:
        raise ValueError(f"Model accuracy {metrics['accuracy']:.4f} below threshold {min_accuracy}")

    if metrics["f1_macro"] < min_f1_macro:
        raise ValueError(f"Model F1-macro {metrics['f1_macro']:.4f} below threshold {min_f1_macro}")

    logger.info("✅ Model performance validation passed!")
    return True


@flow(
    name="EPL CatBoost Training Pipeline",
    log_prints=True,
    retries=2,
    retry_delay_seconds=60,
    cache_result_in_memory=False,
)
def epl_training_pipeline():
    """Main training pipeline for EPL predictions using CatBoost with comprehensive orchestration."""
    logger = get_run_logger()

    logger.info("🚀 Starting EPL CatBoost Training Pipeline")

    try:
        # Step 1: Load data
        df_future = load_data_from_s3.submit()

        # Step 2: Prepare features
        features_future = prepare_features.submit(df_future)
        X, y, feature_cols, categorical_cols = features_future.result()  # disable pylint: disable=unused-variable

        # Step 3: Split data
        split_future = split_data.submit(X, y)
        X_train, X_val, y_train, y_val = split_future.result()

        # Step 4: Train model
        training_future = train_catboost_model.submit(X_train, X_val, y_train, y_val, categorical_cols)
        model, metrics, run_id = training_future.result()  # disable pylint: disable=unused-variable

        # Step 5: Validate performance
        validation_future = validate_model_performance.submit(metrics)

        # Step 6: Register model (only if validation passes)
        registration_future = register_model.submit(run_id)

        # Wait for all tasks to complete
        wait([validation_future, registration_future])

        validation_result = validation_future.result()
        model_version = registration_future.result()

        logger.info("🎉 Pipeline completed successfully!")
        logger.info(f"📈 Final Accuracy: {metrics['accuracy']:.4f}")
        logger.info(f"📈 Final F1-Macro: {metrics['f1_macro']:.4f}")
        logger.info(f"🔗 Model Version: {model_version}")

        return {
            "metrics": metrics,
            "run_id": run_id,
            "model_version": model_version,
            "validation_passed": validation_result,
        }

    except Exception as e:
        logger.error(f"❌ Pipeline failed: {str(e)}")
        raise


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Deploy EPL training pipeline")
    parser.add_argument(
        "--static",
        action="store_true",
        help="Deploy static serve deployment instead of managed dynamic cloud deployment",
    )

    args = parser.parse_args()

    if args.static:
        epl_training_pipeline.serve(
            name="epl-catboost-training-pipeline-static",
            tags=["training", "catboost", "epl-predictions"],
            description="CatBoost training pipeline for EPL match predictions",
            limit=1,  # Only one training job at a time
        )
    else:
        epl_training_pipeline.from_source(
            source="https://github.com/mk-hassan/EPL-predictions-mlops",
            entrypoint="pipelines/training_pipeline.py:epl_training_pipeline",
        ).deploy(
            name="epl-catboost-training-pipeline",
            work_pool_name="epl-predictions-pool",
            concurrency_limit=1,
            description="CatBoost training pipeline for EPL match predictions",
            tags=["training", "catboost", "epl-predictions"],
            job_variables={
                "pip_packages": [
                    "boto3==1.39.9",
                    "pandas==2.3.1",
                    "prefect-aws",
                    "catboost",
                    "scikit-learn",
                    "mlflow",
                ]
            },
            schedule={
                "cron": "0 2 * * 1",  # Every Monday at 2:00 AM
                "timezone": "UTC",
            },
        )
