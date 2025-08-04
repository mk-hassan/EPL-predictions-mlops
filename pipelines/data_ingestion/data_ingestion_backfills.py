import time

from prefect.deployments import run_deployment


def generate_seasons(start_year: int = 2000, end_year: int = 2024) -> list[str]:
    """Generate season strings from start_year to end_year."""
    seasons = []
    for year in range(start_year, end_year + 1):
        # Convert to 2-digit format: 2000 -> "0001", 2024 -> "2425"
        season = f"{str(year)[-2:]}{str(year + 1)[-2:]}"
        seasons.append(season)
    return seasons


def run_backfill_deployments(
    deployment_name: str = "data-ingestion-pipeline",
    start_year: int = 2000,
    end_year: int = 2024,
    delay_seconds: int = 10,
):
    """Run deployment for multiple seasons."""
    seasons = generate_seasons(start_year, end_year)
    total_seasons = len(seasons)

    print(f"🚀 Starting backfill for {total_seasons} seasons: {seasons[0]} to {seasons[-1]}")

    successful_runs = []
    failed_runs = []

    for i, season in enumerate(seasons, 1):
        try:
            print(f"\n📊 [{i}/{total_seasons}] Running deployment for season {season}...")

            # Run the deployment with season parameter
            flow_run = run_deployment(
                name=deployment_name,
                parameters={"season": season, "division": "E0"},  # Premier League
                timeout=300,  # 5 minutes timeout
            )

            if not flow_run.state.is_completed():
                print(f"   ❌ Season {season} failed: {flow_run.state}")
                failed_runs.append((season, str(flow_run.state)))
                continue

            print(f"   ✅ Season {season} completed successfully")
            print(f"   📝 Flow run ID: {flow_run.id}")
            successful_runs.append(season)

        except Exception as e:
            print(f"   ❌ Error running deployment for season {season}: {str(e)}")
            print(f"   ❌ Season {season} failed: {str(e)}")
            failed_runs.append((season, str(e)))

        # Add delay between runs to avoid overwhelming the server
        if i < total_seasons:
            print(f"   ⏳ Waiting {delay_seconds} seconds before next run...")
            time.sleep(delay_seconds)

    # Summary
    print(f"\n{'=' * 60}")
    print("📈 BACKFILL SUMMARY")
    print(f"{'=' * 60}")
    print(f"✅ Successful: {len(successful_runs)}/{total_seasons}")
    print(f"❌ Failed: {len(failed_runs)}/{total_seasons}")

    if successful_runs:
        print(f"\n✅ Successful seasons: {successful_runs}")

    if failed_runs:
        print("\n❌ Failed seasons:")
        for season, error in failed_runs:
            print(f"   • {season}: {error[:100]}...")

    return successful_runs, failed_runs


if __name__ == "__main__":
    # Option 1: Run all seasons from 2000 to 2024
    import argparse

    parser = argparse.ArgumentParser(description="Run backfill deployments for multiple seasons")
    parser.add_argument("--flow-name", required=True, help="Flow name (e.g., 'data-ingestion')")
    parser.add_argument(
        "--deployment-name",
        required=True,
        help="Deployment name (e.g., 'data-ingestion-pipeline')",
    )
    parser.add_argument("--start-year", type=int, default=2000, help="Start year for backfill")
    parser.add_argument("--end-year", type=int, default=2024, help="End year for backfill")

    args = parser.parse_args()

    # Construct full deployment name
    full_deployment_name = f"{args.flow_name}/{args.deployment_name}"

    print(f"🎯 Using deployment: {full_deployment_name}")

    successful, failed = run_backfill_deployments(
        deployment_name=full_deployment_name,
        start_year=args.start_year,
        end_year=args.end_year,
        delay_seconds=5,
    )
