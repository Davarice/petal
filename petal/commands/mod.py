"""Commands module for MODERATION UTILITIES.
Access: Role-based"""

from . import core


class CommandsMod(core.Commands):
    def authenticate(self, *_):
        return False


# Keep the actual classname unique from this common identifier
# Might make debugging nicer
CommandModule = CommandsMod
