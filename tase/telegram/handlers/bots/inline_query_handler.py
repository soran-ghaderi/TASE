from __future__ import annotations

from typing import List

import pyrogram
from pyrogram import filters
from pyrogram import handlers
from pyrogram.enums import ChatType
from pyrogram.types import InlineQueryResultCachedAudio, InlineQueryResultArticle, InputTextMessageContent, \
    InlineKeyboardMarkup

from tase.db import elasticsearch_models
from tase.my_logger import logger
from tase.telegram import template_globals
from tase.telegram.handlers import BaseHandler, HandlerMetadata, exception_handler
from tase.telegram.inline_buton_globals import buttons
from tase.telegram.templates import AudioCaptionData
from tase.utils import get_timestamp, emoji, _trans


class InlineQueryHandler(BaseHandler):

    def init_handlers(self) -> List[HandlerMetadata]:
        return [
            HandlerMetadata(
                cls=handlers.InlineQueryHandler,
                callback=self.custom_commands_handler,
                filters=filters.regex("^#[a-zA-Z0-9_]+"),
                group=0,
            ),
            HandlerMetadata(
                cls=handlers.InlineQueryHandler,
                callback=self.on_inline_query,
                group=0
            )
        ]

    @exception_handler
    def on_inline_query(self, client: 'pyrogram.Client', inline_query: 'pyrogram.types.InlineQuery'):
        logger.debug(f"on_inline_query: {inline_query}")
        query_date = get_timestamp()

        # todo: fix this
        db_from_user = self.db.get_user_by_user_id(inline_query.from_user.id)
        if not db_from_user:
            # update the user
            db_from_user = self.db.update_or_create_user(inline_query.from_user)

        found_any = True
        from_ = 0
        results = []
        next_offset = None

        if inline_query.query is None or not len(inline_query.query):
            # todo: query is empty
            found_any = False
        else:
            if inline_query.offset is not None and len(inline_query.offset):
                from_ = int(inline_query.offset)

            db_audio_docs, query_metadata = self.db.search_audio(inline_query.query, from_, size=15)

            if not db_audio_docs or not len(db_audio_docs) or not len(query_metadata):
                found_any = False

            db_audio_docs: List['elasticsearch_models.Audio'] = db_audio_docs

            chats_dict = self.update_audio_cache(db_audio_docs)

            for db_audio_doc in db_audio_docs:
                db_audio_file_cache = self.db.get_audio_file_from_cache(db_audio_doc, self.telegram_client.telegram_id)

                #  todo: Some audios have null titles, solution?
                if not db_audio_file_cache or not db_audio_doc.title:
                    continue

                results.append(
                    InlineQueryResultCachedAudio(
                        audio_file_id=db_audio_file_cache.file_id,
                        id=f'{inline_query.id}->{db_audio_doc.id}',
                        caption=template_globals.audio_caption_template.render(
                            AudioCaptionData.parse_from_audio_doc(
                                db_audio_doc,
                                db_from_user,
                                chats_dict[db_audio_doc.chat_id],
                                bot_url='https://t.me/bot?start',
                                include_source=True,
                            )
                        ),
                    )
                )

            # todo: `2` works, but why?
            plus = 2 if inline_query.offset is None or not len(inline_query.offset) else 0
            next_offset = str(from_ + len(results) + plus) if len(results) else None
            db_inline_query, db_hits = self.db.get_or_create_inline_query(
                self.telegram_client.telegram_id,
                inline_query,
                query_date=query_date,
                query_metadata=query_metadata,
                audio_docs=db_audio_docs,
                next_offset=next_offset
            )

            if db_inline_query and db_hits:
                for res, db_hit in zip(results, db_hits):
                    markup = [
                        [
                            buttons['add_to_playlist'].get_inline_keyboard_button(
                                db_from_user.chosen_language_code,
                                db_hit.download_url
                            ),
                        ],

                    ]
                    if inline_query.chat_type == ChatType.BOT:
                        markup.append(
                            [
                                buttons['home'].get_inline_keyboard_button(db_from_user.chosen_language_code),
                            ]
                        )

                    res.reply_markup = InlineKeyboardMarkup(markup)

            # ids = [result.audio_file_id for result in results]
            logger.info(
                f"{inline_query.id} : {inline_query.query} ({len(results)}) => {inline_query.offset} : {next_offset}")
            # logger.info(ids)

        if found_any:
            try:
                inline_query.answer(results, cache_time=1, next_offset=next_offset)
            except Exception as e:
                logger.exception(e)
        else:
            # todo: No results matching the query found, what now?
            if from_ is None or from_ == 0:
                inline_query.answer(
                    [
                        InlineQueryResultArticle(
                            title=_trans("No Results Were Found", db_from_user.chosen_language_code),
                            description=_trans("No results were found", db_from_user.chosen_language_code),
                            input_message_content=InputTextMessageContent(
                                message_text=emoji.high_voltage,
                            )
                        )
                    ],
                    cache_time=1,
                )

    @exception_handler
    def custom_commands_handler(self, client: 'pyrogram.Client', inline_query: 'pyrogram.types.InlineQuery'):
        logger.debug(f"custom_commands_handler: {inline_query}")
        query_date = get_timestamp()

        # todo: fix this
        db_from_user = self.db.get_user_by_user_id(inline_query.from_user.id)
        if not db_from_user:
            # update the user
            db_from_user = self.db.update_or_create_user(inline_query.from_user)

        command = inline_query.query.split('#')[1]

        if command in buttons.keys():
            button = buttons[command]
            button.on_inline_query(
                client,
                inline_query,
                self,
                self.db,
                self.telegram_client,
                db_from_user,
            )
        else:
            pass