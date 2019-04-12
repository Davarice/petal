from datetime import datetime as dt
import importlib
import shlex
import sys
from typing import get_type_hints

import discord
import facebook
import praw
import pytumblr
import twitter

from petal.grasslands import Giraffe, Octopus, Peacock


# List of modules to load; All Command-providing modules should be included (NOT "core").
# Order of this list is the order in which commands will be searched. First occurrence
#     the user is permitted to access will be run.
LoadModules = [
    "sudo",
    "dev",
    "admin",
    "manager",
    "mod",
    "listener",
    "social",
    "event",
    "minecraft",
    "util",
    "public",
    "custom",
]

for module in LoadModules:
    # Import everything in the list above.
    importlib.import_module("." + module, package=__name__)


def split(line: str) -> (list, str):
    """Break an input line into a list of tokens, and a "regular" message."""
    # Split the full command line into a list of tokens, each its own arg.
    tokens = shlex.shlex(line, posix=True)
    tokens.quotes += "`"
    # Split the string only on whitespace.
    tokens.whitespace_split = True
    # However, consider a comma to be whitespace so it splits on them too.
    tokens.whitespace += ","
    # Consider a semicolon to denote a comment; Everything after a semicolon
    #   will then be ignored.
    tokens.commenters = ";"

    # Now, find the original string, but only up until the point of a semicolon.
    # Therefore, the following command:
    #   `help commands -v; @person, this is where to see the list`
    # will return a list, ["help", "commands", "-v"], and a string, "help commands -v".
    # This will allow commands to consider "the rest of the line" without going
    #   beyond a semicolon, and without having to reconstruct the line from the
    #   list of arguments, which may or may not have been separated by spaces.
    original = shlex.shlex(line, posix=True)
    original.quotes += "`"
    original.whitespace_split = True
    original.whitespace = ""
    original.commenters = ";"

    # Return a list of all the tokens, and the first part of the "original".
    return list(tokens), original.read_token()


class CommandRouter:
    version = ""

    def __init__(self, client, *a, **kw):
        self.client = client
        self.config = client.config
        self.engines = []

        self.log = Peacock()
        self.log.info("Loading Command modules...")
        self.startup = dt.utcnow()

        # Load all command engines.
        for MODULE in LoadModules:
            # Get the module.
            self.log.info("Loading {} commands...".format(MODULE.capitalize()))
            mod = sys.modules.get(__name__ + "." + MODULE, None)
            if mod:
                # Instantiate its command engine.
                cmod = mod.CommandModule(client, self, *a, **kw)
                self.engines.append(cmod)
                setattr(self, MODULE, cmod)
                self.log.ready("{} commands loaded.".format(MODULE.capitalize()))
            else:
                self.log.warn("FAILED to load {} commands.".format(MODULE.capitalize()))

        # Execute legacy initialization.
        # TODO: Move this elsewhere

        key_osu = self.config.get("osu")
        if key_osu:
            self.osu = Octopus(key_osu)
        else:
            self.osu = None
            self.log.warn("No OSU! key found.")

        key_imgur = self.config.get("imgur")
        if key_imgur:
            self.imgur = Giraffe(key_imgur)
        else:
            self.imgur = None
            self.log.warn("No imgur key found.")

        reddit = self.config.get("reddit")
        if reddit:
            self.reddit = praw.Reddit(
                client_id=reddit["clientID"],
                client_secret=reddit["clientSecret"],
                user_agent=reddit["userAgent"],
                username=reddit["username"],
                password=reddit["password"],
            )
            if self.reddit.read_only:
                self.log.warn(
                    "This account is in read only mode. "
                    + "You may have done something wrong. "
                    + "This will disable reddit functionality."
                )
                self.reddit = None
                return
            else:
                self.log.ready("Reddit support enabled!")
        else:
            self.reddit = None
            self.log.warn("No Reddit keys found")

        tweet = self.config.get("twitter")
        # Twittwr support disabled till api fix
        if tweet and False:
            self.twit = twitter.Api(
                consumer_key=tweet["consumerKey"],
                consumer_secret=tweet["consumerSecret"],
                access_token_key=tweet["accessToken"],
                access_token_secret=tweet["accessTokenSecret"],
                tweet_mode="extended",
            )
            if "id" not in str(self.twit.VerifyCredentials()):
                self.log.warn(
                    "Your Twitter authentication is invalid, "
                    + " Twitter posting will not work"
                )
                self.twit = None
                return
        else:
            self.twit = None
            self.log.warn("No Twitter keys found.")

        fb = self.config.get("facebook")
        if fb:
            self.fb = facebook.GraphAPI(
                access_token=fb["graphAPIAccessToken"], version=fb["version"]
            )
        else:
            self.fb = None
            self.log.warn("No Facebook keys found.")

        tumblr = self.config.get("tumblr")
        if tumblr:
            self.tumblr = pytumblr.TumblrRestClient(
                tumblr["consumerKey"],
                tumblr["consumerSecret"],
                tumblr["oauthToken"],
                tumblr["oauthTokenSecret"],
            )
            self.log.ready("Tumblr support Enabled!")
        else:
            self.tumblr = None
            self.log.warn("No Tumblr keys found.")

        self.log.ready("Command Module Loaded!")

    def find_command(self, kword, src=None, recursive=True):
        """
        Find and return a class method whose name matches kword.
        """
        denied = ""
        for mod in self.engines:
            func, submod = mod.get_command(kword)
            if not func:
                continue
            else:
                mod_src = submod or mod
                permitted, reason = mod_src.authenticate(src)
                if not src or permitted:
                    return mod_src, func, False
                else:
                    if reason == "bad user":
                        denied = "Could not find you on the main server."
                    elif reason == "bad role":
                        denied = "Could not find the correct role on the main server."
                    elif reason == "bad op":
                        denied = "Command wants MC Operator but is not integrated."
                    elif reason == "private":
                        denied = "Command cannot be used in DM."
                    elif reason == "denied":
                        denied = mod_src.auth_fail.format(
                            op=mod_src.op,
                            role=(
                                self.config.get(mod_src.role)
                                if mod_src.role
                                else "!! ERROR !!"
                            ),
                            user=src.author.name,
                        )
                    else:
                        denied = "`{}`.".format(reason)

        # This command is not "real". Check whether it is an alias.
        alias = dict(self.config.get("aliases")) or {}
        if recursive and kword in alias:
            return self.find_command(alias[kword], src, False)

        return None, None, denied

    def get_all(self):
        full = []
        for mod in self.engines:
            full += mod.get_all()
        return full

    def parse(self, cline: list) -> (list, dict):
        """$cline is a list of strings. Figure out which strings, if any, are
            meant to be options/flags. If an option has a related value, add it
            to the options dict with the value as its value. Otherwise, do the
            same but with True instead. Return what args remain with the options
            dict.
        """
        args = []
        opts = {}

        # Loop through given arguments.
        for i, arg in enumerate(cline):
            # Find args that begin with a dash.
            if arg.startswith("-") and not arg.lstrip("-").isnumeric():
                # This arg is an option key.
                key = arg.lstrip("-")

                if "=" in key:
                    # A specific value was given.
                    key, val = key.split("=", 1)
                else:
                    # Unspecified value defaults to generic True.
                    val = True

                if arg.startswith("--"):
                    # This arg is a long opt; The whole word is one key.
                    opts["_" + key.strip("_")] = val
                else:
                    # This is a short opt cluster; Each letter is a key.
                    for char in key[:-1]:
                        opts["_" + char] = True
                    opts["_" + key[-1]] = val
            else:
                args.append(arg)

        return args, opts

    async def route(self, command: str, src: discord.Message):
        """Route a command (and the source message) to the correct method of the
            correct module. By this point, the prefix should have been stripped
            away already, leaving a plaintext command.
        """
        cline, msg = split(command)
        cword = cline.pop(0)

        # Find the method, if one exists.
        engine, func, denied = self.find_command(cword, src)
        if denied:
            # User is not permitted to use this.
            return "Authentication failure: " + denied

        elif not func and src.id not in self.client.potential_typoed_commands:
            # This is not a command. However, might it have been a typo? Add the
            #   message ID to a deque.
            self.client.potential_typoed_commands.append(src.id)
            return ""

        elif func:
            if src.id in self.client.potential_typoed_commands:
                self.client.potential_typoed_commands.remove(src.id)

            # Extract option flags from the argument list.
            args, opts = self.parse(cline)

            # Check to make sure that all options are correctly typed.
            hints = get_type_hints(func)
            for opt, val in opts.items():
                if opt in hints:
                    wanted = hints[opt]
                    opt_name = ("-" * min(len(opt[1:]), 2)) + opt[1:]

                    # Check for any invalid typing.
                    if wanted == bool and type(val) != bool:
                        # Command wants bool, but value has been specified. Fail.
                        return "Flag `{}` does not take a value.".format(opt_name)
                    elif wanted != bool and type(val) == bool:
                        # Command wants value, but value was left boolean. Fail.
                        return "Option `{}` requires a value of type {}.".format(
                            opt_name, wanted.__name__
                        )

                    elif wanted == int:
                        # Command wants int.
                        if type(val) == str:
                            if val.isdigit():
                                # Value is str, but is a str of an int. Change it.
                                opts[opt] = int(val)
                            else:
                                # Value is str, but is not a integer str. Invalid.
                                return "Option `{}` must be integer.".format(opt_name)
                        elif type(val) != wanted:
                            # Value is neither str nor int and cannot be made valid. Fail.
                            return "Option `{}` wanted `{}` but got `{}`.".format(
                                opt_name, wanted.__name__, type(val).__name__
                            )
                    elif wanted == float:
                        # Command wants float.
                        if type(val) == str:
                            if val.isnumeric():
                                # Value is str, but is a str of a float. Change it.
                                opts[opt] = float(val)
                            else:
                                # Value is str, but is not a numeric str. Invalid.
                                return "Option `{}` must be numeric.".format(opt_name)
                        elif type(val) != wanted:
                            # Value is neither str nor float and cannot be made valid. Fail.
                            return "Option `{}` wanted `{}` but got `{}`.".format(
                                opt_name, wanted.__name__, type(val).__name__
                            )

                    elif wanted != str and type(val) == str:
                        # "Else:" Command wants non-str, but value is str.
                        return "Option `{}` is `{}` but should be `{}`.".format(
                            opt_name, type(val).__name__, wanted.__name__
                        )

            # Execute the method, passing the arguments as a list and the options
            #     as keyword arguments.
            try:
                if "|" in args:
                    await self.client.send_message(
                        channel=src.channel,
                        message="It looks like you might have tried to separate arguments with a pipe (`|`). I will still try to run that command, but just so you know, arguments are now *space-separated*, and grouped by quotes. Check out the `argtest` command for more info.",
                    )
                return (await func(args=args, **opts, msg=msg, src=src)) or ""
            except Exception as e:
                return "Sorry, an exception was raised: `{}` (`{}`)".format(
                    type(e).__name__, e
                )

    async def run(self, src: discord.Message):
        """Given a message, determine whether it is a command;
        If it is, route it accordingly.
        """
        if src.author == self.client.user:
            return
        prefix = self.config.prefix
        if src.content.startswith(prefix):
            # Message begins with the invocation prefix
            command = src.content[len(prefix) :]
            return await self.route(command, src)
            # Remove the prefix and route the command

    @property
    def uptime(self):
        delta = dt.utcnow() - self.startup
        delta = delta.total_seconds()

        d = divmod(delta, 86400)  # days
        h = divmod(d[1], 3600)  # hours
        m = divmod(h[1], 60)  # minutes
        s = m[1]  # seconds

        return "%d days, %d hours, %d minutes, %d seconds" % (d[0], h[0], m[0], s)

    @staticmethod
    def get_member_name(server, member):
        try:
            m = server.get_member(member).name
            if m is None:
                m = member
        except AttributeError:
            m = member

        return m

    async def check_pa_updates(self, force=False):
        if force:
            self.config.doc["lastRun"] = dt.utcnow()
            self.config.save()

        else:
            last_run = self.config.get("lastRun")
            self.log.f("pa", "Last run at: " + str(last_run))
            if last_run is None:
                last_run = dt.utcnow()
                self.config.doc["lastRun"] = last_run
                self.config.save()
            else:
                difference = (
                    dt.utcnow() - dt.strptime(str(last_run), "%Y-%m-%d %H:%M:%S.%f")
                ).total_seconds()
                self.log.f("pa", "Difference: " + str(difference))
                if difference < 86400:
                    return
                else:
                    self.config.doc["lastRun"] = dt.utcnow()
                    self.config.save()

        self.log.f("pa", "Searching for entries...")
        response = self.client.db.get_motd_entry(update=True)

        if response is None:
            if force:
                return "Could not find suitable entry, make sure you have added questions to the DB"

            self.log.f("pa", "Could not find suitable entry")

        else:
            try:
                em = discord.Embed(
                    title="Patch Asks",
                    description="Today Patch asks: \n " + response["content"],
                    colour=0x0ACDFF,
                )

                msg = await self.client.embed(
                    self.client.get_channel(self.config.get("motdChannel")), em
                )

                await self.client.send_message(
                    msg.author,
                    msg.channel,
                    "*today's question was "
                    + "written by "
                    + self.get_member_name(msg.server, response["author"])
                    + "*",
                )
                self.log.f(
                    "pa",
                    "Going with entry: "
                    + str(response["num"])
                    + " by "
                    + self.get_member_name(msg.server, response["author"]),
                )

            except KeyError:
                self.log.f("pa", "Malformed entry, dumping: " + str(response))
