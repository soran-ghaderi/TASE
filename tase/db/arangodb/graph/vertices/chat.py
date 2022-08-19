import pyrogram
from pydantic import Field
from pydantic.typing import Optional, List

from .base_vertex import BaseVertex
from ...enums import ChatType
from ...helpers import Restriction, AudioIndexerMetadata, AudioDocIndexerMetadata, UsernameExtractorMetadata


class Chat(BaseVertex):
    _collection_name = "chats"
    schema_version = 1

    _extra_do_not_update_fields = [
        "audio_indexer_metadata",
        "audio_doc_indexer_metadata",
        "username_extractor_metadata",
    ]

    chat_id: int
    is_public: bool
    chat_type: ChatType
    is_verified: Optional[bool]
    is_restricted: Optional[bool]
    # is_creator: creator => User
    is_scam: Optional[bool]
    is_fake: Optional[bool]
    is_support: Optional[bool]
    title: Optional[str]
    username: Optional[str]
    first_name: Optional[str]
    last_name: Optional[str]
    description: Optional[str]
    dc_id: Optional[int]
    has_protected_content: Optional[bool]
    invite_link: Optional[str]
    restrictions: Optional[List[Restriction]]
    # linked_chat: linked_chat => Chat
    available_reactions: Optional[List[str]]
    distance: Optional[int]
    members_count: Optional[int]

    audio_indexer_metadata: Optional[AudioIndexerMetadata] = Field(default=None)
    audio_doc_indexer_metadata: Optional[AudioDocIndexerMetadata] = Field(default=None)
    username_extractor_metadata: Optional[UsernameExtractorMetadata] = Field(default=None)

    @classmethod
    def parse_key(
        cls,
        telegram_chat: pyrogram.types.Chat,
    ) -> Optional[str]:
        if telegram_chat is None:
            return None
        return f"{telegram_chat.id}"

    @classmethod
    def parse(
        cls,
        telegram_chat: pyrogram.types.Chat,
    ) -> Optional["Chat"]:
        key = Chat.parse_key(telegram_chat)
        if key is None:
            return None

        chat_type = ChatType.parse_from_pyrogram(telegram_chat.type)

        description = telegram_chat.description if telegram_chat.description else telegram_chat.bio

        return Chat(
            key=key,
            chat_id=telegram_chat.id,
            is_public=Chat.get_is_public(telegram_chat, chat_type),
            chat_type=chat_type,
            is_verified=telegram_chat.is_verified,
            is_restricted=telegram_chat.is_restricted,
            is_scam=telegram_chat.is_scam,
            is_fake=telegram_chat.is_fake,
            is_support=telegram_chat.is_support,
            title=telegram_chat.title,
            username=telegram_chat.username.lower() if telegram_chat.username else None,
            # it's useful for searching by username
            first_name=telegram_chat.first_name,
            last_name=telegram_chat.last_name,
            description=description,
            dc_id=telegram_chat.dc_id,
            has_protected_content=telegram_chat.has_protected_content,
            invite_link=telegram_chat.invite_link,
            restrictions=Restriction.parse_from_restrictions(telegram_chat.restrictions),
            available_reactions=telegram_chat.available_reactions,
            distance=telegram_chat.distance,
            members_count=telegram_chat.members_count,
        )

    @staticmethod
    def get_is_public(
        telegram_chat: pyrogram.types.Chat,
        chat_type: ChatType,
    ) -> bool:
        """
        Check whether a chat is public or not

        Parameters
        ----------
        telegram_chat : pyrogram.types.Chat
            Chat object from pyrogram
        chat_type : ChatType
            Type of the chat

        Returns
        -------
        Whether the chat is public or not
        """
        is_public = False
        if chat_type in (ChatType.PRIVATE, ChatType.BOT):
            is_public = True
        elif chat_type == ChatType.GROUP:
            is_public = False
        elif chat_type in (ChatType.CHANNEL, ChatType.SUPERGROUP):
            if telegram_chat.username:
                is_public = True
            else:
                is_public = False

        return is_public


class ChatMethods:
    pass
