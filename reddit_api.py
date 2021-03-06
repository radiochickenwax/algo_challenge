import requests
import json
import re
from bson import json_util
import os
from models import User, Team, Game, Challenge
from datetime import datetime
from random import shuffle
from slackclient import SlackClient

num_teams = int(os.environ['NUM_TEAMS'])
team_members = int(os.environ['NUM_MEMBERS'])
token = os.environ["SLACK_TOKEN"]

sc = SlackClient(token)


def get_random_post(requested_difficulty='Easy', any_difficulty=False):
    r = requests.get('http://reddit.com/r/dailyprogrammer/random.json', headers = {'User-agent': 'reddit_daily_algo_bot 0.1'})
    data = r.json()
    post = data[0]['data']['children'][0]['data']
    title = post['title']

    regex = r"\[[^)]+\].*?\[([^)]+)\]"
    try:
        difficulty = re.search(regex, title).group(1)
    except:
        return get_random_post(requested_difficulty)


    # if difficulty != requested_difficulty and not any_difficulty:
    #     print("wrong difficulty", difficulty)
    #     return get_random_post(requested_difficulty)

    description = post['selftext']
    description = description.replace('\n', '\\n')
    regex = r"^#(.*?)\\n#"
    try:
        description = re.search(regex, description).group(1)
    except:
        # print("regex failed for desc",post['selftext'])
        return get_random_post(requested_difficulty)

    description = description.replace('\\n', '\n')
    try:
        Challenge.objects.get(description=description)
        print("challenge already exists")
        return get_random_post(requested_difficulty)
    except:
        pass

    url = post['url']
    data = {
        'title': title,
        'description': description,
        'url': url,
        'difficulty': difficulty
    }
    return data

def diff_color(diff):
    if diff == "Hard":
        return "#CB3535"
    elif diff == "Intermediate":
        return "#E7AB17"
    elif diff == "Easy":
        return "#54D600"
    else:
        return "#2E5DFF"


def background_worker(response_url, channel):
    data = []
    for i in range(3):
        challenge = get_random_post(any_difficulty=True)
        new_challenge = Challenge(
            title=challenge['title'],
            description=challenge['description'],
            difficulty=challenge['difficulty'],
            url=challenge['url'])
        data.append(new_challenge.save())
    game = Game(choices=data)
    game = game.save()
    game_id = json.loads(json_util.dumps(game.id))
    message = {
        "response_type": "in_channel",
        "text": "Here are three random Algorithm challenges!",
        "attachments": []}
    choices = {
        "title": "Choose which Algo you'd like to solve!",
        "callback_id": game_id['$oid'],
        "attachment_type": "default",
        "actions": []
    }
    for i, chall in enumerate(data):
        challenge_attachment = {}
        challenge_attachment["title"] = "<" + chall.url + "|" + chall.title + ">"
        challenge_attachment["text"] = chall.description
        challenge_attachment["color"] = diff_color(chall.difficulty)
        message["attachments"].append(challenge_attachment)
        choice = {}
        choice["name"] = "choice"
        choice["text"] = "Challenge #" + str(i+1)
        choice["type"] = "button"
        choice["value"] = json.loads(json_util.dumps(chall.id))["$oid"]
        choices["actions"].append(choice)
    message["attachments"].append(choices)

    sc.api_call(
        "chat.postMessage",
        channel=channel,
        text=message["text"],
        response_type=message["response_type"],
        attachments=message["attachments"]
    )


def randomize_teams(names, no_teams, game):
    teams = []
    shuffle(names)
    for _ in range(no_teams):
        teams.append([])

    last_game = Game.objects.first()
    last = last_game.teams

    while names:
        for team in teams:
            if names:
                team.append(names.pop())

    for team in teams:
        if team in last:
            return randomize_teams(names, no_teams, game)

    
    teams_object = []
    for team in teams:
        max_driver_time = datetime.now()
        current_driver = ""
        for (idx, member) in enumerate(team):
            if 'last_lead' in member:
                if member.last_lead < max_driver_time:
                    max_driver_time = member.last_lead
                    current_driver = idx
            else:
                current_driver = idx
                break
        temp = team[0]
        team[0] = team[current_driver]
        team[current_driver] = temp
        team[0].last_lead = datetime.now()
        team[0].save()
        team = Team(members=team)
        teams_object.append(team)
    
    print(teams,teams_object)
    game.teams = teams_object
    game.save()

    return teams


if __name__ == "__main__":
    get_random_post()
