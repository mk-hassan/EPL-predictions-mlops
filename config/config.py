"""Configuration settings for the application."""

from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).parent.parent
ENV_FILE_PATH = PROJECT_ROOT / ".env"


class Config(BaseSettings):
    """Configuration settings for the application."""

    model_config = SettingsConfigDict(
        env_file=ENV_FILE_PATH,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="forbid",
    )

    # Application Settings
    app_name: str = Field(..., description="Application name")

    # Database Settings
    postgres_user: str = Field(..., description="PostgreSQL username", required=True)
    postgres_password: str = Field(..., description="PostgreSQL password", required=True)
    postgres_server: str = Field(..., description="PostgreSQL server host", required=True)
    postgres_port: int = Field(default=5432, description="PostgreSQL port", required=True)
    postgres_db: str = Field(..., description="PostgreSQL database name", required=True)
    table_name: str = Field(..., description="Database table name", required=True)

    # AWS Settings
    aws_region: str = Field(..., description="AWS region")
    aws_access_key_id: SecretStr = Field(..., description="AWS access key ID")
    aws_secret_access_key: SecretStr = Field(..., description="AWS secret access key")

    # Prefect Configuration
    prefect_table_name_variable: str = Field(default="table-name", description="Database table name")
    prefect_cloud_api_key: SecretStr = Field(default=None, description="Prefect Cloud API Key")

    @classmethod
    @field_validator("environment")
    def validate_environment(cls, v):
        """Validate environment value."""
        allowed_environments = ["development", "staging", "production"]
        if v not in allowed_environments:
            raise ValueError(f"Environment must be one of: {allowed_environments}")
        return v

    @property
    def database_url(self) -> str:
        """Generate database URL from components."""
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_server}:{self.postgres_port}/{self.postgres_db}"
        )


def get_config() -> Config:
    """Get the application configuration."""
    return Config()
