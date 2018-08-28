import json
import requests
"""
ERROR CODES:
 0: Success, user added to local database to be synced with whitelist
-1:
-2:
-9: Already whitelisted
"""
class Player:
    def __init__(self, discord_id, uuid, uname):
        self.discord_uuid = discord_id # discord uuid
        self.minecraft_uuid = uuid # minecraft/mojang uuid
        self.minecraft_name = uname # minecraft username (added to list of known aliases)
        self.approved = [] # list of discord uuids who approved the whitelisting

def addToLocalDB(userdat, submission): # Add UID and username to local whitelist database
    uid = userdat["id"]
    uname = userdat["name"]
    #print(uname + " has uuid " + uid)
    return 0

def idFromName(uname_raw):
    uname_low = uname_raw.lower()
    response = requests.get("https://api.mojang.com/users/profiles/minecraft/{}".format(uname_low))
    return {'code':response.status_code, 'udat':response.json() }
    #if code == 200:
        #return json.loads(response.text)
    #else:
        #return -1

def WLRequest(nameGiven, discord_id):
    udict = idFromName(nameGiven) # Get the id from the name, or an error
    if udict["code"] == 200: # If this is 200, the second part will contain json data; Try to add it
        verdict = addToLocalDB(udict["udat"], discord_id)
        return verdict
    #elif udict["code"] == 200: # Map response codes to function errors
        #return 
    else:
        return "Nondescript Error ({})".format(udict["code"])

