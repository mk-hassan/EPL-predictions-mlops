import pandas as pd


class FootballFeatureEngineer:
    """Feature engineering for football match prediction."""

    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()
        self.df["date"] = pd.to_datetime(self.df["date"])
        self.df = self.df.sort_values(["date"]).reset_index(drop=True)

    def create_team_form_features(self, n_matches: int = 5) -> pd.DataFrame:
        """Create team form features based on last N matches."""
        features = []

        for idx, row in self.df.iterrows():
            current_date = row["date"]
            home_team = row["hometeam"]
            away_team = row["awayteam"]

            # Get historical data before current match
            historical = self.df[self.df["date"] < current_date]

            # Home team recent form
            home_recent = self._get_team_recent_matches(historical, home_team, n_matches)
            away_recent = self._get_team_recent_matches(historical, away_team, n_matches)

            # Calculate features
            match_features = {
                "match_id": idx,
                "date": current_date,
                "hometeam": home_team,
                "awayteam": away_team,
                # Home team form
                "home_wins_last_n": self._count_wins(home_recent, home_team),
                "home_draws_last_n": self._count_draws(home_recent),
                "home_losses_last_n": self._count_losses(home_recent, home_team),
                "home_goals_scored_last_n": self._goals_scored(home_recent, home_team),
                "home_goals_conceded_last_n": self._goals_conceded(home_recent, home_team),
                "home_form_points": self._calculate_points(home_recent, home_team),
                # Away team form
                "away_wins_last_n": self._count_wins(away_recent, away_team),
                "away_draws_last_n": self._count_draws(away_recent),
                "away_losses_last_n": self._count_losses(away_recent, away_team),
                "away_goals_scored_last_n": self._goals_scored(away_recent, away_team),
                "away_goals_conceded_last_n": self._goals_conceded(away_recent, away_team),
                "away_form_points": self._calculate_points(away_recent, away_team),
                # Head to head
                "h2h_home_wins": self._h2h_wins(historical, home_team, away_team, "home"),
                "h2h_away_wins": self._h2h_wins(historical, home_team, away_team, "away"),
                "h2h_draws": self._h2h_draws(historical, home_team, away_team),
                # Home average odds
                "whd_home_avg": self._calculate_avg(historical, home_team, "whd"),
                "wha_home_avg": self._calculate_avg(historical, home_team, "wha"),
                "whh_home_avg": self._calculate_avg(historical, home_team, "whh"),
                # Away average odds
                "whd_away_avg": self._calculate_avg(historical, away_team, "whd"),
                "wha_away_avg": self._calculate_avg(historical, away_team, "wha"),
                "whh_away_avg": self._calculate_avg(historical, away_team, "whh"),
                # Target variables
                "target_result": row["ftr"],
                "target_home_goals": row["fthg"],
                "target_away_goals": row["ftag"],
            }

            features.append(match_features)

        return pd.DataFrame(features)

    def _get_team_recent_matches(self, df: pd.DataFrame, team: str, n: int) -> pd.DataFrame:
        """Get last N matches for a team."""
        team_matches = df[(df["hometeam"] == team) | (df["awayteam"] == team)]
        return team_matches.tail(n)

    def _count_wins(self, matches: pd.DataFrame, team: str) -> int:
        """Count wins for a team."""
        home_wins = len(matches[(matches["hometeam"] == team) & (matches["ftr"] == "H")])
        away_wins = len(matches[(matches["awayteam"] == team) & (matches["ftr"] == "A")])
        return home_wins + away_wins

    def _count_draws(self, matches: pd.DataFrame) -> int:
        """Count draws."""
        return len(matches[matches["ftr"] == "D"])

    def _count_losses(self, matches: pd.DataFrame, team: str) -> int:
        """Count losses for a team."""
        home_losses = len(matches[(matches["hometeam"] == team) & (matches["ftr"] == "A")])
        away_losses = len(matches[(matches["awayteam"] == team) & (matches["ftr"] == "H")])
        return home_losses + away_losses

    def _goals_scored(self, matches: pd.DataFrame, team: str) -> int:
        """Total goals scored by team."""
        home_goals = matches[matches["hometeam"] == team]["fthg"].sum()
        away_goals = matches[matches["awayteam"] == team]["ftag"].sum()
        return home_goals + away_goals

    def _goals_conceded(self, matches: pd.DataFrame, team: str) -> int:
        """Total goals conceded by team."""
        home_conceded = matches[matches["hometeam"] == team]["ftag"].sum()
        away_conceded = matches[matches["awayteam"] == team]["fthg"].sum()
        return home_conceded + away_conceded

    def _calculate_points(self, matches: pd.DataFrame, team: str) -> int:
        """Calculate points (3 for win, 1 for draw)."""
        wins = self._count_wins(matches, team)
        draws = self._count_draws(matches)
        return wins * 3 + draws * 1

    def _h2h_wins(self, df: pd.DataFrame, home_team: str, away_team: str, venue: str) -> int:
        """Head-to-head wins."""
        if venue == "home":
            return len(df[(df["hometeam"] == home_team) & (df["awayteam"] == away_team) & (df["ftr"] == "H")])
        else:
            return len(df[(df["hometeam"] == home_team) & (df["awayteam"] == away_team) & (df["ftr"] == "A")])

    def _h2h_draws(self, df: pd.DataFrame, home_team: str, away_team: str) -> int:
        """Head-to-head draws."""
        return len(df[(df["hometeam"] == home_team) & (df["awayteam"] == away_team) & (df["ftr"] == "D")])

    def _calculate_avg(self, df: pd.DataFrame, team: str, column: str) -> float:
        """Calculate average of a column for a team."""
        home_avg = df[df["hometeam"] == team][column].mean()
        away_avg = df[df["awayteam"] == team][column].mean()
        return (home_avg + away_avg) / 2 if home_avg and away_avg else 0.0
