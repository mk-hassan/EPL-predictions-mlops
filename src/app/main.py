import os
from datetime import datetime
from contextlib import asynccontextmanager

import mlflow
import pandas as pd
import uvicorn
from fastapi import Query, FastAPI, HTTPException, BackgroundTasks
from pydantic import Field, BaseModel, validator
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware


# Models for request/response
class MatchRequest(BaseModel):
    home_team: str = Field(..., description="Home team name")
    away_team: str = Field(..., description="Away team name")
    match_date: str | None = Field(None, description="Match date (YYYY-MM-DD)")
    home_form_last_5: float | None = Field(2.0, description="Home team form last 5 matches")
    away_form_last_5: float | None = Field(2.0, description="Away team form last 5 matches")

    @validator("home_team", "away_team")
    def validate_teams(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError("Team name cannot be empty")
        return v.strip()


class BulkMatchRequest(BaseModel):
    matches: list[MatchRequest] = Field(..., description="List of matches to predict")

    @validator("matches")
    def validate_matches(cls, v):
        if len(v) == 0:
            raise ValueError("At least one match is required")
        if len(v) > 50:
            raise ValueError("Maximum 50 matches allowed per request")
        return v


class PredictionResponse(BaseModel):
    home_team: str
    away_team: str
    predicted_result: str
    confidence: float
    probabilities: dict[str, float]
    model_version: str
    prediction_timestamp: str


class BulkPredictionResponse(BaseModel):
    predictions: list[PredictionResponse]
    total_matches: int
    processing_time: float


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    model_version: str | None
    uptime: str
    timestamp: str


class ModelInfo(BaseModel):
    name: str
    version: str
    accuracy: float | None
    f1_score: float | None
    last_trained: str | None
    features_count: int | None


class FeatureImportance(BaseModel):
    feature_name: str
    importance: float
    rank: int


# Global variables for model and metadata
model = None
model_metadata = {}
app_start_time = datetime.now()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management."""
    # Startup
    await load_model()
    yield
    # Shutdown
    cleanup_resources()


# Initialize FastAPI app
app = FastAPI(
    title="EPL Match Predictions API",
    description="FastAPI service for predicting English Premier League match outcomes using CatBoost ML model",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure based on your needs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Utility functions
async def load_model():
    """Load the latest CatBoost model from MLflow."""
    global model, model_metadata

    try:
        # Set MLflow tracking URI
        mlflow_uri = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000")
        mlflow.set_tracking_uri(mlflow_uri)

        # Load model from registry
        model_name = "epl-predictions-catboost"
        model_alias = "production"

        model_uri = f"models:/{model_name}@{model_alias}"
        model = mlflow.catboost.load_model(model_uri)

        # Get model metadata
        client = mlflow.MlflowClient()
        model_version = client.get_model_version_by_alias(model_name, model_alias)

        # Get run metrics
        run = client.get_run(model_version.run_id)

        model_metadata = {
            "name": model_name,
            "version": model_version.version,
            "alias": model_alias,
            "run_id": model_version.run_id,
            "accuracy": run.data.metrics.get("accuracy"),
            "f1_score": run.data.metrics.get("f1_macro"),
            "last_trained": model_version.creation_timestamp,
            "features_count": run.data.metrics.get("num_features"),
        }

        print(f"✅ Model loaded successfully: {model_name} v{model_version.version}")

    except Exception as e:
        print(f"❌ Failed to load model: {str(e)}")
        raise


def cleanup_resources():
    """Clean up resources on shutdown."""
    global model
    model = None
    print("🔄 Resources cleaned up")


async def get_model():
    """Dependency to ensure model is loaded."""
    if model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    return model


def create_feature_vector(match_request: MatchRequest) -> pd.DataFrame:
    """Create feature vector for prediction."""
    # This is a simplified feature creation
    # In production, you'd calculate actual features based on team statistics
    features = {
        "hometeam": [match_request.home_team],
        "awayteam": [match_request.away_team],
        "home_form_last_5": [match_request.home_form_last_5],
        "away_form_last_5": [match_request.away_form_last_5],
        # Add other features with default values
        "home_avg_goals": [1.5],
        "away_avg_goals": [1.3],
        "home_avg_goals_conceded": [1.2],
        "away_avg_goals_conceded": [1.4],
        "home_win_rate": [0.5],
        "away_win_rate": [0.45],
        "head_to_head_home_wins": [2],
        "head_to_head_away_wins": [1],
        "head_to_head_draws": [1],
    }

    return pd.DataFrame(features)


# API Endpoints


@app.get("/", response_model=dict[str, str])
async def root():
    """Root endpoint with API information."""
    return {"message": "EPL Match Predictions API", "version": "1.0.0", "docs": "/docs", "health": "/health"}


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    uptime = datetime.now() - app_start_time

    return HealthResponse(
        status="healthy" if model is not None else "unhealthy",
        model_loaded=model is not None,
        model_version=model_metadata.get("version"),
        uptime=str(uptime),
        timestamp=datetime.now().isoformat(),
    )


@app.get("/model/info", response_model=ModelInfo)
async def get_model_info():
    """Get information about the loaded model."""
    if model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    return ModelInfo(
        name=model_metadata.get("name", "Unknown"),
        version=model_metadata.get("version", "Unknown"),
        accuracy=model_metadata.get("accuracy"),
        f1_score=model_metadata.get("f1_score"),
        last_trained=model_metadata.get("last_trained"),
        features_count=model_metadata.get("features_count"),
    )


@app.get("/model/feature-importance", response_model=list[FeatureImportance])
async def get_feature_importance(top_n: int = Query(10, ge=1, le=50)):
    """Get top N feature importances from the model."""
    current_model = await get_model()

    try:
        # Get feature importance (this assumes you have feature names stored)
        feature_names = [f"feature_{i}" for i in range(len(current_model.feature_importances_))]
        importances = current_model.feature_importances_

        # Create feature importance list
        feature_importance = [
            FeatureImportance(feature_name=name, importance=float(importance), rank=rank + 1)
            for rank, (name, importance) in enumerate(
                sorted(zip(feature_names, importances, strict=False), key=lambda x: x[1], reverse=True)[:top_n]
            )
        ]

        return feature_importance

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting feature importance: {str(e)}") from e


@app.post("/predict", response_model=PredictionResponse)
async def predict_match(match_request: MatchRequest):
    """Predict the outcome of a single match."""
    current_model = await get_model()

    try:
        # Create feature vector
        features_df = create_feature_vector(match_request)

        # Make prediction
        prediction = current_model.predict(features_df)[0]
        probabilities = current_model.predict_proba(features_df)[0]

        # Map probabilities to class names
        class_names = ["A", "D", "H"]  # Away, Draw, Home
        prob_dict = {
            "away_win": float(probabilities[0]),
            "draw": float(probabilities[1]),
            "home_win": float(probabilities[2]),
        }

        confidence = float(max(probabilities))

        return PredictionResponse(
            home_team=match_request.home_team,
            away_team=match_request.away_team,
            predicted_result=prediction,
            confidence=confidence,
            probabilities=prob_dict,
            model_version=model_metadata.get("version", "unknown"),
            prediction_timestamp=datetime.now().isoformat(),
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction error: {str(e)}") from e


@app.post("/predict/bulk", response_model=BulkPredictionResponse)
async def predict_bulk_matches(bulk_request: BulkMatchRequest):
    """Predict outcomes for multiple matches."""
    start_time = datetime.now()
    current_model = await get_model()

    try:
        predictions = []

        for match_request in bulk_request.matches:
            # Create feature vector
            features_df = create_feature_vector(match_request)

            # Make prediction
            prediction = current_model.predict(features_df)[0]
            probabilities = current_model.predict_proba(features_df)[0]

            # Map probabilities to class names
            prob_dict = {
                "away_win": float(probabilities[0]),
                "draw": float(probabilities[1]),
                "home_win": float(probabilities[2]),
            }

            confidence = float(max(probabilities))

            predictions.append(
                PredictionResponse(
                    home_team=match_request.home_team,
                    away_team=match_request.away_team,
                    predicted_result=prediction,
                    confidence=confidence,
                    probabilities=prob_dict,
                    model_version=model_metadata.get("version", "unknown"),
                    prediction_timestamp=datetime.now().isoformat(),
                )
            )

        processing_time = (datetime.now() - start_time).total_seconds()

        return BulkPredictionResponse(
            predictions=predictions, total_matches=len(predictions), processing_time=processing_time
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Bulk prediction error: {str(e)}") from e


@app.get("/teams", response_model=list[str])
async def get_available_teams():
    """Get list of available teams that the model can predict for."""
    # This would typically come from your data or model metadata
    epl_teams = [
        "Arsenal",
        "Chelsea",
        "Liverpool",
        "Manchester City",
        "Manchester United",
        "Tottenham",
        "Newcastle United",
        "Brighton",
        "Aston Villa",
        "West Ham",
        "Crystal Palace",
        "Fulham",
        "Wolves",
        "Everton",
        "Brentford",
        "Nottingham Forest",
        "Leicester City",
        "Bournemouth",
        "Sheffield United",
        "Burnley",
    ]
    return sorted(epl_teams)


@app.post("/model/reload")
async def reload_model(background_tasks: BackgroundTasks):
    """Reload the model from MLflow (admin endpoint)."""
    background_tasks.add_task(load_model)
    return {"message": "Model reload initiated in background"}


@app.get("/predictions/simulate")
async def simulate_gameweek(gameweek: int = Query(..., ge=1, le=38, description="Premier League gameweek number")):
    """Simulate predictions for an entire gameweek (demo endpoint)."""
    current_model = await get_model()

    # Sample matches for demonstration
    sample_matches = [
        ("Arsenal", "Chelsea"),
        ("Manchester City", "Liverpool"),
        ("Manchester United", "Tottenham"),
        ("Newcastle United", "Brighton"),
        ("Aston Villa", "West Ham"),
    ]

    predictions = []

    for home_team, away_team in sample_matches:
        match_request = MatchRequest(
            home_team=home_team, away_team=away_team, match_date=datetime.now().date().isoformat()
        )

        features_df = create_feature_vector(match_request)
        prediction = current_model.predict(features_df)[0]
        probabilities = current_model.predict_proba(features_df)[0]

        predictions.append(
            {
                "match": f"{home_team} vs {away_team}",
                "prediction": prediction,
                "confidence": float(max(probabilities)),
                "probabilities": {
                    "home_win": float(probabilities[2]),
                    "draw": float(probabilities[1]),
                    "away_win": float(probabilities[0]),
                },
            }
        )

    return {"gameweek": gameweek, "predictions": predictions, "total_matches": len(predictions)}


# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code, content={"error": exc.detail, "timestamp": datetime.now().isoformat()}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "message": str(exc), "timestamp": datetime.now().isoformat()},
    )


# Development server
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True, log_level="info")
