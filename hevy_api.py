import requests
import json
import os
import getpass
import re
import time
import datetime
import shutil

from pathlib import Path
from fastapi import FastAPI

app = FastAPI()

# Basic headers to use throughout
BASIC_HEADERS = {
    "x-api-key": "with_great_power",
    "Content-Type": "application/json",
    "accept-encoding": "gzip",
}

#
# Simple method to provide a login prompt on command line, which is then just passed to login below
#
def login_cli():
    user = input("Please input a username: ")
    password = getpass.getpass()

    return login(user, password)


#
# Login method taking a username and password
# Logs in and then downloads account.json, the profile pic, and the workout_count
# Returns 200 if all successful
#
@app.post("/login")
def login(user: str, password: str):
    home_folder = str(Path.home())
    utb_folder = home_folder + "/.underthebar"

    if not os.path.exists(utb_folder):
        os.makedirs(utb_folder)
        os.makedirs(utb_folder + "/temp")

    headers = BASIC_HEADERS.copy()

    # Post username and password to Hevy
    s = requests.Session()

    r = s.post(
        "https://api.hevyapp.com/login",
        data=json.dumps({"emailOrUsername": user, "password": password}),
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
            # print(json.dumps(r.json(), indent=4, sort_keys=True))

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
                    # print(json.dumps(r.json(), indent=4, sort_keys=True))

                    with open(user_folder + "/workout_count.json", "w") as f:
                        json.dump(workout_count, f)

                    return {"status_code": 200}
                return {"status_code": r.status_code}
        else:
            return {"status_code": r.status_code}
    else:
        return {"status_code": r.status_code}


#
# Simple method to log out. We'll delete the user id and auth-token from the sessions file
#
@app.post("/logout")
async def logout(request: Request, session: dict = Depends(get_session)):
    # Remove the user's session data from the session store
    session.clear()

    # Redirect the user to the login page
    return RedirectResponse(url="/login")



# POST request to create a new workout
# We'll make a new workout folder, copy over the template json, and then add some new info from the form provided.
# Lastly, we'll upload this new json file to Hevy
def create_workout(name, sets, reps, weight):
	# Make sure user is logged in, have their folder, and auth-token
	user_data = is_logged_in()
	if user_data[0] == False:
		return 403
	user_folder = user_data[1]
	auth_token = user_data[2]
	
	workout_template = {
		"workout_name": "",
		"workout_sets": [
			{
				"workout_set_name": "",
				"workout_set_reps": 0,
				"workout_set_weight": 0.0,
				"workout_set_index": 0
			}
		]
	}

	workout_path = user_folder + "/workouts/"+name+".json"
	if os.path.exists(workout_path):
		return 409
	shutil.copyfile(user_folder + "/workouts/workout_template.json", workout_path)

	with open(workout_path, 'r') as f:
		data = json.load(f)
	
	data["workout_name"] = name
	
	for i in range(len(data["workout_sets"])):
		data["workout_sets"][i]["workout_set_name"] = "Set "+str(i+1)
		data["workout_sets"][i]["workout_set_reps"] = int(reps)
		data["workout_sets"][i]["workout_set_weight"] = float(weight)
		data["workout_sets"][i]["workout_set_index"] = i

	with open(workout_path, 'w') as f:
		json.dump(data, f)

	headers = BASIC_HEADERS.copy()
	headers.update({'auth-token': auth_token})

	with open(workout_path, 'rb') as f:
		r = requests.post("https://api.hevyapp.com/workout", headers=headers, data=f)
	
	if r.status_code == 200:
		# We'll save the new etag value to our local workout_count.json file for quicker updating
		data = r.json()
		with open(user_folder+"/workout_count.json", 'r') as f:
			workout_count = json.load(f)
		workout_count["Etag"] = r.headers['Etag']
		with open(user_folder+"/workout_count.json", 'w') as f:
			json.dump(workout_count, f)
		
		return r.status_code
	return r.status_code

# GET request to obtain a list of all our saved workouts
# API returns the JSON file containing workout data and an etag value
def get_workout_list():
	# Make sure user is logged in, have their folder, and auth-token
	user_data = is_logged_in()
	if user_data[0] == False:
		return 403
	user_folder = user_data[1]
	auth_token = user_data[2]
	
	headers = BASIC_HEADERS.copy()
	headers.update({'auth-token': auth_token})
	
	r = requests.get("https://api.hevyapp.com/workouts", headers=headers)
	if r.status_code == 200:
		data = r.json()
		with open(user_folder+"/workout_list.json", 'w') as f:
			json.dump({"data":data, "Etag":r.headers['Etag']}, f)
		return r.json()
	return r.status_code

# GET request to obtain a specific workout by ID
# API returns the JSON file containing workout data and an etag value
def
