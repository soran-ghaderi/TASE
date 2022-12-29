from typing import Optional, List

import pyrogram

from tase.common.utils import _trans, emoji
from tase.db.arangodb import graph as graph_models
from tase.telegram.bots.inline import CustomInlineQueryResult
from tase.telegram.update_handlers.base import BaseHandler
from ..base import InlineButton, InlineButtonType, ButtonActionType, InlineItemType, InlineButtonData
from ..inline_items.item_info import PlaylistItemInfo


class SharePlaylistButtonData(InlineButtonData):
    __button_type__ = InlineButtonType.SHARE_PLAYLIST

    playlist_key: str

    @classmethod
    def generate_data(cls, playlist_key: str) -> Optional[str]:
        return f"#{cls.get_type_value()}|{playlist_key}"

    @classmethod
    def __parse__(
        cls,
        data_split_lst: List[str],
    ) -> Optional[InlineButtonData]:
        if len(data_split_lst) != 2:
            return None

        return SharePlaylistButtonData(playlist_key=data_split_lst[1])


class SharePlaylistInlineButton(InlineButton):
    __type__ = InlineButtonType.SHARE_PLAYLIST
    action = ButtonActionType.OTHER_CHAT_INLINE
    __switch_inline_query__ = "share_pl"

    __valid_inline_items__ = [InlineItemType.PLAYLIST]

    s_share = _trans("Share")
    text = f"{s_share} | {emoji._link}"

    @classmethod
    def get_keyboard(
        cls,
        *,
        playlist_key: str,
        lang_code: Optional[str] = "en",
    ) -> pyrogram.types.InlineKeyboardButton:
        return cls.get_button(cls.__type__).__parse_keyboard_button__(
            switch_inline_query_other_chat=SharePlaylistButtonData.generate_data(playlist_key),
            lang_code=lang_code,
        )

    async def on_inline_query(
        self,
        handler: BaseHandler,
        result: CustomInlineQueryResult,
        from_user: graph_models.vertices.User,
        client: pyrogram.Client,
        telegram_inline_query: pyrogram.types.InlineQuery,
        query_date: int,
        inline_button_data: Optional[SharePlaylistButtonData] = None,
    ):
        playlist = await handler.db.graph.get_playlist_by_key(inline_button_data.playlist_key)

        if result.is_first_page() and playlist and not playlist.is_soft_deleted and playlist.is_public:
            from tase.telegram.bots.ui.inline_items import PlaylistItem

            result.add_item(
                PlaylistItem.get_item(
                    playlist,
                    from_user,
                    telegram_inline_query,
                    view_playlist=True,
                ),
                count=False,
            )

        await result.answer_query()

    async def on_chosen_inline_query(
        self,
        handler: BaseHandler,
        client: pyrogram.Client,
        from_user: graph_models.vertices.User,
        telegram_chosen_inline_result: pyrogram.types.ChosenInlineResult,
        inline_button_data: SharePlaylistButtonData,
        inline_item_info: PlaylistItemInfo,
    ):
        pass
