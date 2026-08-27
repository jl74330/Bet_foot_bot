#!/bin/python
## source https://www.football-data.org/blog
import matplotlib
import matplotlib.pyplot as plt
import requests
import json

YOUR_TOKEN_HERE= "f87996cf41cc4a65a8d1179a41a2e769"
HOME_TEAM= "BRENTFORD"

def get_home_wins_for_competition(competition_code):
    base_uri = 'https://api.football-data.org/v4/competitions/' + competition_code + '/matches'
    headers = { 'X-Auth-Token': YOUR_TOKEN_HERE, 'Accept-Encoding': '' }
    retVal = []
    seasons = [str(x) for x in range(2010,2020)]
    for year in seasons:
      uri = base_uri + "?season=" + str(year)
      response = requests.get(uri, headers=headers)
      print(response.json())  # Print the full response
      matches = response.json()['matches']
      home_wins = 0; match_counter = 0;
      for m in matches:
        if (m['score']['winner'] == "HOME_TEAM"):
          home_wins += 1
        if (m['score']['winner'] is not None and m['score']['winner'] != "DRAW"):
          match_counter += 1
      retVal.append(round((home_wins/match_counter)*100, 2))

    return retVal


competitions = ['BL1', 'PL', 'PD', 'SA', 'FL1', 'DED']
seasons = [str(x) for x in range(2010,2025)]
values = {}

for key in competitions:
    values[key] = get_home_wins_for_competition(key)

plt.xlabel('season')
plt.ylabel('% of home wins')
plt.ylim(40.0, 70.0)

for key in competitions:
    plt.plot(seasons, values[key], label = key)

plt.legend()
plt.suptitle('less home wins during covid')
plt.show()
