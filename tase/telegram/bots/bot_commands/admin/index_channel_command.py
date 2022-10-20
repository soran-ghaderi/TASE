import pyrogram
from pydantic import Field

from tase.common.utils import find_telegram_usernames
from tase.db.arangodb import graph as graph_models
from tase.db.arangodb.graph.vertices.user import UserRole
from tase.telegram.tasks import IndexAudiosTask, AddChannelTask
from tase.telegram.update_handlers.base import BaseHandler
from ..base_command import BaseCommand
from ..bot_command_type import BotCommandType


class IndexChannelCommand(BaseCommand):
    """
    Index a public channel based on its username.
    """

    command_type: BotCommandType = Field(default=BotCommandType.INDEX_CHANNEL)
    command_description = "Index a public channel by its `username`"
    required_role_level: UserRole = UserRole.ADMIN
    number_of_required_arguments = 1

    def command_function(
        self,
        client: pyrogram.Client,
        message: pyrogram.types.Message,
        handler: BaseHandler,
        from_user: graph_models.vertices.User,
        from_callback_query: bool,
    ) -> None:
        channel_username = message.command[1]

        username_list = find_telegram_usernames(channel_username)
        if len(username_list):
            channel_username = username_list[0][0]

        chat = handler.db.graph.get_chat_by_username(channel_username)
        if chat:
            if not chat.audio_indexer_metadata:
                AddChannelTask(kwargs={"channel_username": channel_username}).publish(handler.db)
            status, created = IndexAudiosTask(kwargs={"chat_key": chat.key}).publish(handler.db)
            if status is None:
                message.reply_text("internal error")
            else:
                if created:
                    if status.is_active():
                        message.reply_text(f"Started indexing `{chat.title}` channel")
                else:
                    if status.is_active():
                        message.reply_text(f"Task for indexing `{chat.title}` channel is already being processed")
                    else:
                        message.reply_text(f"The task for indexing `{chat.title}` channel is already finished")

        else:
            message.reply_text("This channel does not exist in the Database!")
            status, created = AddChannelTask(kwargs={"channel_username": channel_username}).publish(handler.db)
            if status is None:
                message.reply_text("internal error")
            else:
                if created:
                    if status.is_active():
                        message.reply_text(f"Added channel `{channel_username}` to the Database for indexing.")
                else:
                    if status.is_active():
                        message.reply_text(f"Channel with username `{channel_username}` is already being processed")
                    else:
                        message.reply_text(f"The task for adding channel with username `{channel_username}` is already finished")
