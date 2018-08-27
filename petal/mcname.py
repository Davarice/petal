import json
import requests

def idFromName(uname_raw):
    uname_low = uname_raw.lower()
    response = requests.get("https://api.mojang.com/users/profiles/minecraft/{}".format(uname_low))
    code = response.status_code
    if code == 200:
        return json.loads(response.text)
    else:
        return -1

def addToLocalDB(userdat, submission):
    uid = userdat["id"]
    uname = userdat["name"]
    print(uname + " has uuid " + uid)

def WLRequest(nameGiven):
    udat = idFromName(nameGiven)
    if udat == -1:
        return -1
    else:
        addToLocalDB(udat, nameGiven)

