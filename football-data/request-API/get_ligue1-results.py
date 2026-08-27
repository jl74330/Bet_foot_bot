import requests



API_KEY = "f87996cf41cc4a65a8d1179a41a2e769"

headers = {
    "X-Auth-Token": API_KEY
}

url = "https://api.football-data.org/v4/competitions/FL1/matches"

response = requests.get(url, headers=headers)

data = response.json()

matches = data["matches"]

for match in matches[:10]:
    home = match["homeTeam"]["name"]
    away = match["awayTeam"]["name"]
    score = match["score"]["fullTime"]

    print(f"{home} vs {away} -> {score}")