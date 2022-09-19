import pyrogram
from pydantic import Field
from pyrogram.enums import ParseMode
from pyrogram.types import InlineKeyboardMarkup

from tase.db.arangodb import graph as graph_models
from tase.telegram.bots.bot_commands.base_command import BaseCommand
from tase.telegram.bots.bot_commands.bot_command_type import BotCommandType
from tase.telegram.bots.ui.inline_buttons.base import InlineButton, InlineButtonType
from tase.telegram.bots.ui.templates import BaseTemplate, HomeData
from tase.telegram.update_handlers.base import BaseHandler


class HomeCommand(BaseCommand):
    """
    Shows the Home menu
    """

    command_type: BotCommandType = Field(default=BotCommandType.HOME)

    def command_function(
        self,
        client: pyrogram.Client,
        message: pyrogram.types.Message,
        handler: BaseHandler,
        from_user: graph_models.vertices.User,
        from_callback_query: bool,
    ) -> None:

        data = HomeData(
            support_channel_username="support_channel_username",
            url1="https://github.com/appheap/TASE",
            url2="https://github.com/appheap/TASE",
            lang_code=from_user.chosen_language_code,
        )

        markup = [
            [
                InlineButton.get_button(
                    InlineButtonType.DOWNLOAD_HISTORY
                ).get_inline_keyboard_button(from_user.chosen_language_code),
                InlineButton.get_button(
                    InlineButtonType.MY_PLAYLISTS
                ).get_inline_keyboard_button(from_user.chosen_language_code),
            ],
            [
                InlineButton.get_button(
                    InlineButtonType.SHOW_LANGUAGE_MENU
                ).get_inline_keyboard_button(from_user.chosen_language_code),
            ],
            [
                InlineButton.get_button(
                    InlineButtonType.ADVERTISEMENT
                ).get_inline_keyboard_button(from_user.chosen_language_code),
                InlineButton.get_button(
                    InlineButtonType.HELP_CATALOG
                ).get_inline_keyboard_button(from_user.chosen_language_code),
            ],
        ]
        markup = InlineKeyboardMarkup(markup)

        chat_id = None
        if message:
            if message.chat:
                chat_id = message.chat.id
            elif message.from_user:
                chat_id = message.from_user.id
        else:
            chat_id = from_user.user_id

        client.send_message(
            chat_id=chat_id,
            text=BaseTemplate.registry.home_template.render(data),
            parse_mode=ParseMode.HTML,
            reply_markup=markup,
        )
