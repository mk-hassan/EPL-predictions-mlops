import pandas as pd
from pandas.errors import ParserError


def parse_match_date(date_str):
    """Parse football data dates which can be in various formats."""
    if pd.isna(date_str):
        return pd.NaT

    # Try different date formats
    formats = [
        "%d/%m/%Y",  # 15/08/2005
        "%d/%m/%y",  # 15/08/05
        "%Y-%m-%d",  # 2005-08-15
        "%d-%m-%Y",  # 15-08-2005
        "%d-%m-%y",  # 15-08-05
    ]

    for fmt in formats:
        try:
            parsed_date = pd.to_datetime(date_str, format=fmt)
            # Handle 2-digit year ambiguity
            if parsed_date.year < 1950:  # Assume it's 20xx, not 19xx
                parsed_date = parsed_date.replace(year=parsed_date.year + 100)
            return parsed_date
        except (ParserError, ValueError):
            continue

    # Fallback to pandas automatic parsing
    try:
        return pd.to_datetime(date_str, format="%Y/%m/%d", errors="coerce")
    except (ParserError, ValueError):
        return pd.NaT
