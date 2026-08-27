
import requests

# API Details
BASE_URL = "https://api.football-data.org/v4/"
API_KEY = "f87996cf41cc4a65a8d1179a41a2e769"  

# Set up headers for authentication
headers = {
    "X-Auth-Token": API_KEY
}

def get_competitions():
    response = requests.get(BASE_URL + "competitions", headers=headers)
    return response.json() if response.status_code == 200 else None

competitions = get_competitions()
if competitions:
    for comp in competitions['competitions']:
        print(f"Name: {comp['name']}, Code: {comp['code']}")
