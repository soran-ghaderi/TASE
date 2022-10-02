import collections
from typing import Match, Optional

import pyrogram
from pyrogram.enums import ParseMode
from pyrogram.types import InlineQueryResultArticle, InputTextMessageContent

from tase.common.utils import _trans, emoji
from tase.db.arangodb import graph as graph_models
from tase.db.arangodb.enums import ChatType, InteractionType
from tase.my_logger import logger
from tase.telegram.bots.inline import CustomInlineQueryResult
from tase.telegram.update_handlers.base import BaseHandler
from .base import InlineButton, InlineButtonType
from .common import populate_audio_items


class DownloadHistoryInlineButton(InlineButton):
    name = "download_history"
    type = InlineButtonType.DOWNLOAD_HISTORY

    s_my_downloads = _trans("My Downloads")
    text = f"{s_my_downloads} | {emoji._mobile_phone_with_arrow}"
    is_inline = True

    def on_inline_query(
        self,
        handler: BaseHandler,
        result: CustomInlineQueryResult,
        from_user: graph_models.vertices.User,
        client: pyrogram.Client,
        telegram_inline_query: pyrogram.types.InlineQuery,
        query_date: int,
        reg: Optional[Match] = None,
    ):
        audio_vertices = handler.db.graph.get_user_download_history(
            from_user,
            offset=result.from_,
        )

        audio_vertices = list(audio_vertices)

        results = collections.deque()

        populate_audio_items(
            results,
            audio_vertices,
            from_user,
            handler,
            query_date,
            result,
            telegram_inline_query,
        )

        if len(results):
            result.results = list(results)
        else:
            if result.from_ is None or result.from_ == 0:
                result.results = [
                    InlineQueryResultArticle(
                        title=_trans(
                            "No Results Were Found",
                            from_user.chosen_language_code,
                        ),
                        description=_trans(
                            "You haven't downloaded any audios yet",
                            from_user.chosen_language_code,
                        ),
                        input_message_content=InputTextMessageContent(
                            message_text=emoji.high_voltage,
                            parse_mode=ParseMode.HTML,
                        ),
                    )
                ]

    def on_chosen_inline_query(
        self,
        handler: BaseHandler,
        client: pyrogram.Client,
        from_user: graph_models.vertices.User,
        telegram_chosen_inline_result: pyrogram.types.ChosenInlineResult,
        reg: Match,
    ):

        result_id_list = telegram_chosen_inline_result.result_id.split("->")
        inline_query_id = result_id_list[0]
        hit_download_url = result_id_list[1]
        chat_type = ChatType(int(result_id_list[2]))

        if chat_type == ChatType.BOT:
            # fixme: only store audio inline messages for inline queries in the bot chat
            updated = handler.db.document.set_audio_inline_message_id(
                handler.telegram_client.telegram_id,
                from_user.user_id,
                inline_query_id,
                telegram_chosen_inline_result.inline_message_id,
            )
            if not updated:
                # could not update the inline message document, what now?
                pass

        interaction_vertex = handler.db.graph.create_interaction(
            hit_download_url,
            from_user,
            handler.telegram_client.telegram_id,
            InteractionType.SHARE,
            chat_type,
        )
        if not interaction_vertex:
            # could not create the download
            logger.error("Could not create the `interaction_vertex` vertex:")
            logger.error(telegram_chosen_inline_result)
