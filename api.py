from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from typing import Optional
from pathlib import Path
import requests
import json
import os
import shutil
import re

app = FastAPI()

BASIC_HEADERS = {
    "x-api-key": "with_great_power",
    "Content-Type": "application/json",
    "accept-encoding": "gzip",
}


def get_session_token():
    home_folder = str(Path.home())
    utb_folder = home_folder + "/.underthebar"
    session_file = utb_folder + "/session.json"

    if os.path.exists(session_file):
        with open(session_file, "r") as f:
            # print session file
            # print("session file exists")
            # print(session_file)

            session_data = json.load(f)
            if session_data:
                return session_data.get("auth-token")
    return None


def get_session_token_header(auth_token: str = Depends(get_session_token)):
    headers = BASIC_HEADERS.copy()
    if auth_token is not None:
        headers.update({"auth-token": auth_token})
    return headers


@app.post("/login")
async def login(
    credentials: HTTPBasicCredentials, headers: dict = Depends(get_session_token_header)
):
    home_folder = str(Path.home())
    utb_folder = home_folder + "/.underthebar"

    if not os.path.exists(utb_folder):
        os.makedirs(utb_folder)
        os.makedirs(utb_folder + "/temp")

    headers = BASIC_HEADERS.copy()

    s = requests.Session()

    r = s.post(
        "https://api.hevyapp.com/login",
        data=json.dumps(
            {"emailOrUsername": credentials.username, "password": credentials.password}
        ),
        headers=headers,
    )
    if r.status_code == 200:
        json_content = r.json()
        s.headers.update({"auth-token": json_content["auth_token"]})

        auth_token = json_content["auth_token"]

        r = s.get("https://api.hevyapp.com/account", headers=headers)
        if r.status_code == 200:
            data = r.json()

            account_data = {"data": data, "Etag": r.headers["Etag"]}

            user_id = data["id"]

            user_folder = utb_folder + "/user_" + user_id

            if not os.path.exists(user_folder):
                os.makedirs(user_folder)
                os.makedirs(user_folder + "/workouts")

            with open(utb_folder + "/session.json", "w") as f:
                json.dump({"auth-token": auth_token, "user-id": user_id}, f)

            with open(user_folder + "/account.json", "w") as f:
                json.dump(account_data, f)

            imageurl = data["profile_pic"]
            response = requests.get(imageurl, stream=True)
            if response.status_code == 200:
                with open(user_folder + "/profileimage", "wb") as out_file:
                    shutil.copyfileobj(response.raw, out_file)

                r = s.get("https://api.hevyapp.com/workout_count", headers=headers)
                if r.status_code == 200:
                    data = r.json()

                    workout_count = {"data": data, "Etag": r.headers["Etag"]}

                    with open(user_folder + "/workout_count.json", "w") as f:
                        json.dump(workout_count, f)

                    return {"status_code": 200, "message": "Login successful."}
                else:
                    raise HTTPException(
                        status_code=r.status_code,
                        detail="Failed to fetch workout count.",
                    )
        else:
            raise HTTPException(
                status_code=r.status_code, detail="Failed to fetch account information."
            )
    else:
        raise HTTPException(status_code=r.status_code, detail="Invalid credentials.")


@app.post("/logout")
async def logout():
    # The folder to access/store data files
    home_folder = str(Path.home())
    utb_folder = home_folder + "/.underthebar"
    session_data = {}
    if os.path.exists(utb_folder + "/session.json"):
        with open(utb_folder + "/session.json", "r") as file:
            session_data = json.load(file)
    else:
        return {"success": False, "message": "No session data found."}
    if "auth-token" in session_data:
        del session_data["auth-token"]
    if "user-id" in session_data:
        del session_data["user-id"]
    with open(utb_folder + "/session.json", "w") as f:
        json.dump({}, f)
    return {"success": True, "message": "Logout successful."}


def is_logged_in():
    # The folder to access/store data files
    home_folder = str(Path.home())
    utb_folder = home_folder + "/.underthebar"

    session_data = {}
    if os.path.exists(utb_folder + "/session.json"):
        with open(utb_folder + "/session.json", "r") as file:
            session_data = json.load(file)
    else:
        return False, None, None

    try:
        auth_token = session_data["auth-token"]
        # this is the folder we'll save the data file to
        user_folder = utb_folder + "/user_" + session_data["user-id"]
        return True, user_folder, auth_token
    except:
        return False, None, None


@app.post("/workout/like/{workout_id}")
def like_workout(workout_id: str, like_it: bool):
    # Make sure user is logged in, have their folder, and auth-token
    user_data = is_logged_in()
    if user_data[0] == False:
        return {"status_code": 403}
    user_folder = user_data[1]
    auth_token = user_data[2]

    # Make the headers
    headers = BASIC_HEADERS.copy()
    headers["auth-token"] = auth_token

    url = f"https://api.hevyapp.com/workout/like/{workout_id}"
    if not like_it:
        url = f"https://api.hevyapp.com/workout/unlike/{workout_id}"

    with requests.Session() as s:
        r = s.post(url, headers=headers)

    return {"status_code": r.status_code}


@app.post("/feed_workouts/get_most_recent")
async def feed_workouts__get_most_recent():
    print("feed_workouts_paged")

    # Make sure user is logged in, have their folder, and auth-token
    user_data = is_logged_in()
    if user_data[0] == False:
        return {"status_code": 403}
    user_folder = user_data[1]
    auth_token = user_data[2]

    # Make the headers
    headers = BASIC_HEADERS.copy()
    headers["auth-token"] = auth_token

    url = "https://api.hevyapp.com/feed_workouts_paged/"

    # Do the request
    s = requests.Session()
    r = s.get(url, headers=headers)

    if r.status_code == 200:
        data = r.json()
        new_data = {"data": data, "Etag": r.headers["Etag"]}
        print("new_data", new_data)
        return new_data
    elif r.status_code == 304:
        return {"status_code": 304}
    else:
        return {"status_code": r.status_code}


@app.post("/feed_workouts/get_nth_last")
async def feed_workouts__get_nth_last(start_from: Optional[int] = 0):
    print("feed_workouts_paged", start_from)

    # Make sure user is logged in, have their folder, and auth-token
    user_data = is_logged_in()
    if user_data[0] == False:
        return {"status_code": 403}
    user_folder = user_data[1]
    auth_token = user_data[2]

    # Make the headers
    headers = BASIC_HEADERS.copy()
    headers["auth-token"] = auth_token

    url = "https://api.hevyapp.com/feed_workouts_paged/"
    if start_from != 0:
        url = url + str(start_from)

    # Do the request
    s = requests.Session()
    r = s.get(url, headers=headers)

    if r.status_code == 200:
        data = r.json()
        new_data = {"data": data, "Etag": r.headers["Etag"]}
        print("new_data", new_data)
        return new_data
    elif r.status_code == 304:
        return {"status_code": 304}
    else:
        return {"status_code": r.status_code}


@app.get("/workouts")
def get_workouts():
    # Make sure user is logged in, have their folder, and auth-token
    user_data = is_logged_in()
    if user_data[0] == False:
        return 403
    user_folder = user_data[1]

    # Workouts subfolder
    workouts_folder = user_folder + "/workouts"

    workouts = []
    for file in sorted(os.listdir(workouts_folder), reverse=True):
        match_workout = re.search("^workout_([A-Za-z0-9_-]+).json\Z", file)
        if match_workout:
            with open(workouts_folder + "/" + file, "r") as file:
                temp_data = json.load(file)
                workouts.append(temp_data)

    return workouts


@app.get("/workouts/{workout_number}")
def get_workout_by_number(workout_number: int):
    # Make sure user is logged in, have their folder, and auth-token
    user_data = is_logged_in()
    if user_data[0] == False:
        return 403
    user_folder = user_data[1]

    # Workouts subfolder
    workouts_folder = user_folder + "/workouts"

    workouts = []
    for file in sorted(os.listdir(workouts_folder), reverse=True):
        match_workout = re.search("^workout_([A-Za-z0-9_-]+).json\Z", file)
        if match_workout:
            with open(workouts_folder + "/" + file, "r") as file:
                temp_data = json.load(file)
                workouts.append(temp_data)

    # find the workout with matching nth_workout attribute
    for workout in workouts:
        if workout.get("nth_workout") == workout_number:
            return workout

    # if workout not found, return 404
    return 404


@app.get("/workouts/{workout_short_id}")
def get_workout_by_short_id(workout_short_id: int):
    # Make sure user is logged in, have their folder, and auth-token
    user_data = is_logged_in()
    if user_data[0] == False:
        return 403
    user_folder = user_data[1]

    # Workouts subfolder
    workouts_folder = user_folder + "/workouts"

    workouts = []
    for file in sorted(os.listdir(workouts_folder), reverse=True):
        match_workout = re.search("^workout_([A-Za-z0-9_-]+).json\Z", file)
        if match_workout:
            with open(workouts_folder + "/" + file, "r") as file:
                temp_data = json.load(file)
                workouts.append(temp_data)

    # find the workout with matching nth_workout attribute
    for workout in workouts:
        if workout.get("short_id") == workout_short_id:
            return workout

    # if workout not found, return 404
    return 404


@app.get("/workouts/{comment_count}")
def get_workouts_by_comment_count(comment_count: int):
    # Make sure user is logged in, have their folder, and auth-token
    user_data = is_logged_in()
    if user_data[0] == False:
        return 403
    user_folder = user_data[1]

    # Workouts subfolder
    workouts_folder = user_folder + "/workouts"

    workouts = []
    for file in sorted(os.listdir(workouts_folder), reverse=True):
        match_workout = re.search("^workout_([A-Za-z0-9_-]+).json\Z", file)
        if match_workout:
            with open(workouts_folder + "/" + file, "r") as file:
                temp_data = json.load(file)
                if temp_data["comment_count"] == comment_count:
                    workouts.append(temp_data)
    # if workout not found, return 404
    return 404


@app.get("/workouts/{like_count}")
def get_workouts_by_like_count(like_count: int):
    # Make sure user is logged in, have their folder, and auth-token
    user_data = is_logged_in()
    if user_data[0] == False:
        return 403
    user_folder = user_data[1]

    # Workouts subfolder
    workouts_folder = user_folder + "/workouts"

    workouts = []
    for file in sorted(os.listdir(workouts_folder), reverse=True):
        match_workout = re.search("^workout_([A-Za-z0-9_-]+).json\Z", file)
        if match_workout:
            with open(workouts_folder + "/" + file, "r") as file:
                temp_data = json.load(file)
                if temp_data["like_count"] == like_count:
                    workouts.append(temp_data)
    # if workout not found, return 404
    return 404

@app.get("/routine_folders")
def get_routine_folders():
    # Make sure user is logged in, have their folder, and auth-token
    user_data = is_logged_in()
    if user_data[0] == False:
        return 403
    user_folder = user_data[1]

    # Routines subfolder
    routines_folder = user_folder + "/routines"

    routines = []
    url = "https://api.hevyapp.com/routine_folders"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    else:
        return {"error": "Failed to get routine folders"}
    # for file in sorted(os.listdir(routines_folder), reverse=True):
    #     match_workout = re.search("^workout_([A-Za-z0-9_-]+).json\Z", file)
    #     if match_workout:
    #         with open(routines_folder + "/" + file, "r") as file:
    #             temp_data = json.load(file)
    #             routines.append(temp_data)
    # if workout not found, return 404
    return 404