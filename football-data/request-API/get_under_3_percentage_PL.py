import requests

# API Details
BASE_URL = "https://api.football-data.org/v4/"
API_KEY = "f87996cf41cc4a65a8d1179a41a2e769"  # Replace with your Football-Data.org API key

# Headers for authentication
headers = {"X-Auth-Token": API_KEY}

def fetch_matches(competition, season_start, season_end):
    """
    Fetch match data for a given competition.
    """
    endpoint = f"competitions/{competition}/matches"
    response = requests.get(BASE_URL + endpoint, headers=headers)

    if response.status_code != 200:
        print(f"API Error for {competition}: {response.status_code} - {response.text}")
        return []

    return response.json().get('matches', [])

def calculate_under_3_percentage(matches):
    """
    Calculate the percentage of matches under 2.5 goals.
    """
    total_matches = 0
    under_3_goals = 0

    for match in matches:
        try:
            # Check if match result exists
            if match['score']['fullTime']['homeTeam'] is None or match['score']['fullTime']['awayTeam'] is None:
                continue

            # Calculate total goals
            total_goals = match['score']['fullTime']['homeTeam'] + match['score']['fullTime']['awayTeam']
            total_matches += 1

            # Check if total goals are under 2.5
            if total_goals < 3:
                under_3_goals += 1
        except KeyError:
            # Handle cases where score or other keys are missing
            print(f"Missing data for match: {match.get('id', 'unknown')}")
            continue
    # Avoid division by zero
    if total_matches == 0:
        return 0

    # Calculate percentage
    percentage = (under_3_goals / total_matches) * 100
    return percentage

def main():
    competition = "PL"  # Example: Premier League (PL)
    season_start = "2023-08-01"  # Start date of the 2023 season
    season_end = "2024-06-30"    # End date of the 2023 season

    matches = fetch_matches(competition, season_start, season_end)

    if not matches:
        print("No matches found.")
        return

    percentage_under_3 = calculate_under_3_percentage(matches)
    print(f"Percentage of matches under 2.5 goals in {competition}: {percentage_under_3:.2f}%")

# Execute the script
if __name__ == "__main__":
    main()
