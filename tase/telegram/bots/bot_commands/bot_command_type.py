import pyrogram
from pydantic.types import Enum


class BotCommandType(Enum):
    UNKNOWN = "unknown"
    INVALID = "invalid"

    BASE = "base"

    START = "start"
    HOME = "home"
    HELP = "help"
    LANGUAGE = "lang"

    ADD_CHANNEL = "add_channel"

    @classmethod
    def get_from_message(
        cls,
        message: pyrogram.types.Message,
    ) -> "BotCommandType":
        if message is None or message.command is None or not len(message.command):
            return BotCommandType.INVALID

        command_string = message.command[0].lower()

        for bot_command_type in list(BotCommandType):
            if str(bot_command_type.value) == command_string:
                return bot_command_type

        return BotCommandType.INVALID