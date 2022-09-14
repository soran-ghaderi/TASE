from __future__ import annotations

from typing import Optional

import pyrogram
from elastic_transport import ObjectApiResponse
from pydantic import Field

from tase.my_logger import logger
from tase.utils import datetime_to_timestamp
from .base_document import BaseDocument
from ...arangodb.enums import TelegramAudioType
from ...db_utils import get_telegram_message_media_type, parse_audio_key


class Audio(BaseDocument):
    schema_version = 1

    _index_name = "audios_index"
    _mappings = {
        "properties": {
            "schema_version": {"type": "integer"},
            "created_at": {"type": "long"},
            "modified_at": {"type": "long"},
            "chat_id": {"type": "long"},
            "message_id": {"type": "long"},
            "message_caption": {"type": "text"},
            "message_date": {"type": "date"},
            "file_unique_id": {"type": "keyword"},
            "duration": {"type": "integer"},
            "performer": {"type": "text"},
            "title": {"type": "text"},
            "file_name": {"type": "text"},
            "mime_type": {"type": "keyword"},
            "file_size": {"type": "integer"},
            "date": {"type": "date"},
            "views": {"type": "long"},
            "downloads": {"type": "long"},
            "shares": {"type": "long"},
            "search_hits": {"type": "long"},
            "non_search_hits": {"type": "long"},
            "likes": {"type": "long"},
            "dislikes": {"type": "long"},
            "audio_type": {"type": "integer"},
            "valid_for_inline_search": {"type": "boolean"},
        }
    }

    _extra_do_not_update_fields = (
        "views",
        "downloads",
        "shares",
        "search_hits",
        "non_search_hits",
        "likes",
        "dislikes",
    )
    _search_fields = [
        "performer",
        "title",
        "file_name",
        "message_caption",
    ]

    chat_id: int
    message_id: int
    message_caption: Optional[str]
    message_date: int

    file_unique_id: str
    duration: Optional[int]
    performer: Optional[str]
    title: Optional[str]
    file_name: Optional[str]
    mime_type: Optional[str]
    file_size: int
    date: int

    views: int = Field(default=0)
    downloads: int = Field(default=0)
    shares: int = Field(default=0)
    search_hits: int = Field(default=0)
    non_search_hits: int = Field(default=0)
    likes: int = Field(default=0)
    dislikes: int = Field(default=0)
    audio_type: TelegramAudioType  # whether the audio file is shown in the `audios` or `files/documents` section of telegram app
    valid_for_inline_search: bool
    """
     when an audio's title is None or the audio is shown in document section of
     telegram, then that audio could not be shown in telegram inline mode. Moreover, it should not have keyboard
     markups like `add_to_playlist`, etc... . On top of that, if any audio of this kind gets downloaded through
     query search, then, it cannot be shown in `download_history` section or any other sections that work in inline
     mode.
    """

    @classmethod
    def parse_id(
        cls,
        telegram_message: pyrogram.types.Message,
    ) -> Optional[str]:
        """
        Parse the `ID` from the given `telegram_message` argument if it contains a valid audio file, otherwise raise
        an `ValueError` exception.

        Parameters
        ----------
        telegram_message : pyrogram.types.Message
            Telegram message to parse the ID from

        Returns
        -------
        str, optional
            Parsed ID if the parsing was successful, otherwise return `None` if the `telegram_message` is `None`.

        """
        return parse_audio_key(telegram_message)

    @classmethod
    def parse(
        cls,
        telegram_message: pyrogram.types.Message,
    ) -> Optional[Audio]:
        """
        Parse an `Audio` from the given `telegram_message` argument.

        Parameters
        ----------
        telegram_message : pyrogram.types.Message
            Telegram message to parse the `Audio` from

        Returns
        -------
        Audio, optional
            Parsed `Audio` if parsing was successful, otherwise, return `None`.

        Raises
        ------
        ValueError
            If `telegram_message` argument does not contain any valid audio file.
        """
        if telegram_message is None:
            return None

        _id = cls.parse_id(telegram_message)
        if _id is None:
            return None

        audio, audio_type = get_telegram_message_media_type(telegram_message)
        if audio_type == TelegramAudioType.NON_AUDIO:
            raise ValueError("Unexpected value for `message`: nor audio nor document")

        title = getattr(audio, "title", None)

        # todo: check if the following statement is actually true
        valid_for_inline = True if title is not None and audio_type == TelegramAudioType.AUDIO_FILE else False

        caption = telegram_message.caption if telegram_message.caption else telegram_message.text

        return Audio(
            id=_id,
            chat_id=telegram_message.chat.id,
            message_id=telegram_message.id,
            message_caption=caption,
            message_date=datetime_to_timestamp(telegram_message.date),
            file_unique_id=audio.file_unique_id,
            duration=getattr(audio, "duration", None),
            performer=getattr(audio, "performer", None),
            title=title,
            file_name=audio.file_name,
            mime_type=audio.mime_type,
            file_size=audio.file_size,
            date=datetime_to_timestamp(audio.date),
            ########################################
            views=telegram_message.views or 0,
            valid_for_inline_search=valid_for_inline,
            audio_type=audio_type,
        )

    @classmethod
    def search_by_download_url(
        cls,
        download_url: str,
    ) -> Optional[Audio]:
        if download_url is None:
            return None
        db_docs = []

        try:
            res: ObjectApiResponse = cls._es.search(
                index=cls._index_name,
                query={
                    "match": {
                        "download_url": download_url,
                    },
                },
            )

            hits = res.body["hits"]["hits"]

            for index, hit in enumerate(hits, start=1):
                db_doc = cls.from_index(hit=hit, rank=len(hits) - index + 1)
                db_docs.append(db_doc)

        except Exception as e:
            logger.exception(e)

        return db_docs[0] if len(db_docs) else None

    @classmethod
    def get_query(
        cls,
        query: Optional[str],
        valid_for_inline_search: Optional[bool] = True,
    ) -> Optional[dict]:
        if valid_for_inline_search:
            return {
                "bool": {
                    "must": {
                        "multi_match": {
                            "query": query,
                            "fuzziness": "AUTO",
                            "type": "best_fields",
                            "minimum_should_match": "65%",
                            "fields": cls._search_fields,
                        }
                    },
                    "filter": {"exists": {"field": "title"}},
                }
            }
        else:
            return {
                "bool": {
                    "must": {
                        "multi_match": {
                            "query": query,
                            "fuzziness": "AUTO",
                            "type": "best_fields",
                            "minimum_should_match": "65%",
                            "fields": cls._search_fields,
                        }
                    },
                    "filter": {"exists": {"field": "title"}},
                }
            }

    @classmethod
    def get_sort(
        cls,
    ) -> Optional[dict]:
        return {
            "_score": {"order": "desc"},
            "download_count": {"order": "desc"},
            "date": {"order": "desc"},
        }


class AudioMethods:
    def create_audio(
        self,
        telegram_message: pyrogram.types.Message,
    ) -> Optional[Audio]:
        """
        Create Audio document in the ElasticSearch.

        Parameters
        ----------
        telegram_message : pyrogram.types.Message
            Telegram message to create the Audio from

        Returns
        -------
        Audio, optional
            Audio if the creation was successful, otherwise, return None

        """
        try:
            audio, successful = Audio.create(Audio.parse(telegram_message))
        except ValueError:
            # this message doesn't contain any valid audio file
            pass
        else:
            if audio and successful:
                return audio

        return None

    def get_or_create_audio(
        self,
        telegram_message: pyrogram.types.Message,
    ) -> Optional[Audio]:
        """
        Get Audio if it exists in ElasticSearch, otherwise, create Audio document.

        Parameters
        ----------
        telegram_message : pyrogram.types.Message
            Telegram message to create the Audio from

        Returns
        -------
        Audio, optional
            Audio if the operation was successful, otherwise, return None

        """
        if telegram_message is None:
            return None

        audio = Audio.get(Audio.parse_id(telegram_message))
        if audio is None:
            # audio does not exist in the index, create it
            audio = self.create_audio(telegram_message)

        return audio

    def update_or_create_audio(
        self,
        telegram_message: pyrogram.types.Message,
    ) -> Optional[Audio]:
        """
        Update Audio document in the ElasticSearch if it exists, otherwise, create it.

        Parameters
        ----------
        telegram_message : pyrogram.types.Message
            Telegram message to create the Audio from

        Returns
        -------
        Audio, optional
            Audio if the creation was successful, otherwise, return None

        """
        if telegram_message is None:
            return None

        audio = Audio.get(Audio.parse_id(telegram_message))
        if audio is None:
            # audio does not exist in the index, create it
            audio = self.create_audio(telegram_message)
        else:
            # audio exists in the index, update it
            try:
                updated = audio.update(Audio.parse(telegram_message))
            except ValueError:
                updated = False
        return audio

    def get_audio_by_id(
        self,
        id: str,
    ) -> Optional[Audio]:
        """
        Get `Audio` by its `ID`

        Parameters
        ----------
        id : str
            ID of the `Audio` to get

        Returns
        -------
        Audio, optional
            Audio if it exists in ElasticSearch, otherwise, return None

        """
        return Audio.get(id)
