"""
Data Ingestion Pipeline Package

Handles fetching and storing EPL match data from various sources.
"""

from .data_ingestion_common_tasks import (
    ensure_division,
    load_data_to_db,
    get_current_season,
    get_season_results,
)

__all__ = [
    "ensure_division",
    "get_current_season",
    "get_season_results",
    "load_data_to_db",
]
