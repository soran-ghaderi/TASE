from __future__ import annotations

import collections
import copy
from typing import Optional, List, Generator, TYPE_CHECKING, Deque, Tuple

import pyrogram
from decouple import config

from aioarango.models import PersistentIndex
from tase.common.preprocessing import clean_text, empty_to_null
from tase.common.utils import (
    datetime_to_timestamp,
    get_now_timestamp,
    find_hashtags_in_text,
)
from tase.db.db_utils import (
    get_telegram_message_media_type,
    parse_audio_key,
    is_audio_valid_for_inline,
    parse_audio_document_key,
)
from tase.errors import (
    TelegramMessageWithNoAudio,
    InvalidToVertex,
    InvalidFromVertex,
    EdgeCreationFailed,
)
from tase.my_logger import logger
from .base_vertex import BaseVertex
from .hashtag import Hashtag
from .hit import Hit
from .interaction import Interaction
from .user import User
from ...helpers import BitRateType

if TYPE_CHECKING:
    from .. import ArangoGraphMethods
from ...enums import TelegramAudioType, MentionSource, InteractionType, AudioType


class Audio(BaseVertex):
    _collection_name = "audios"
    schema_version = 1
    _extra_indexes = [
        PersistentIndex(
            custom_version=1,
            name="chat_id",
            fields=[
                "chat_id",
            ],
        ),
        PersistentIndex(
            custom_version=1,
            name="message_id",
            fields=[
                "message_id",
            ],
        ),
        PersistentIndex(
            custom_version=1,
            name="message_date",
            fields=[
                "message_date",
            ],
        ),
        PersistentIndex(
            custom_version=1,
            name="message_edit_date",
            fields=[
                "message_edit_date",
            ],
        ),
        PersistentIndex(
            custom_version=1,
            name="views",
            fields=[
                "views",
            ],
        ),
        PersistentIndex(
            custom_version=1,
            name="forward_date",
            fields=[
                "forward_date",
            ],
        ),
        PersistentIndex(
            custom_version=1,
            name="via_bot",
            fields=[
                "via_bot",
            ],
        ),
        PersistentIndex(
            custom_version=1,
            name="has_protected_content",
            fields=[
                "has_protected_content",
            ],
        ),
        PersistentIndex(
            custom_version=1,
            name="file_unique_id",
            fields=[
                "file_unique_id",
            ],
        ),
        PersistentIndex(
            custom_version=1,
            name="date",
            fields=[
                "date",
            ],
        ),
        PersistentIndex(
            custom_version=1,
            name="audio_type",
            fields=[
                "audio_type",
            ],
        ),
        PersistentIndex(
            custom_version=1,
            name="valid_for_inline_search",
            fields=[
                "valid_for_inline_search",
            ],
        ),
        PersistentIndex(
            custom_version=1,
            name="estimated_bit_rate_type",
            fields=[
                "estimated_bit_rate_type",
            ],
        ),
        PersistentIndex(
            custom_version=1,
            name="has_checked_forwarded_message",
            fields=[
                "has_checked_forwarded_message",
            ],
        ),
        PersistentIndex(
            custom_version=1,
            name="has_checked_forwarded_message_at",
            fields=[
                "has_checked_forwarded_message_at",
            ],
        ),
        PersistentIndex(
            custom_version=1,
            name="is_forwarded",
            fields=[
                "is_forwarded",
            ],
        ),
        PersistentIndex(
            custom_version=1,
            name="is_deleted",
            fields=[
                "is_deleted",
            ],
        ),
        PersistentIndex(
            custom_version=1,
            name="deleted_at",
            fields=[
                "deleted_at",
            ],
        ),
        PersistentIndex(
            custom_version=1,
            name="is_edited",
            fields=[
                "is_edited",
            ],
        ),
    ]

    _extra_do_not_update_fields = [
        "has_checked_forwarded_message_at",
        "deleted_at",
    ]

    chat_id: int
    message_id: int
    message_caption: Optional[str]
    raw_message_caption: Optional[str]
    message_date: Optional[int]
    message_edit_date: Optional[int]
    views: Optional[int]
    forward_date: Optional[int]
    forward_from_user_id: Optional[int]
    forward_from_chat_id: Optional[int]
    forward_from_message_id: Optional[int]
    forward_signature: Optional[str]
    forward_sender_name: Optional[str]
    via_bot: bool
    has_protected_content: Optional[bool]
    # forward_from_chat : forward_from => Chat
    # forward_from : forward_from => Chat
    # via_bot : via_bot => User

    # file_id: str # todo: is it necessary?
    file_unique_id: Optional[str]
    duration: Optional[int]
    performer: Optional[str]
    raw_performer: Optional[str]
    title: Optional[str]
    raw_title: Optional[str]
    file_name: Optional[str]
    raw_file_name: Optional[str]
    mime_type: Optional[str]
    file_size: Optional[int]
    date: Optional[int]

    ####################################################
    audio_type: TelegramAudioType  # whether the audio file is shown in the `audios` or `files/documents` section of telegram app
    valid_for_inline_search: bool
    """
     when an audio's title is None or the audio is shown in document section of
     telegram, then that audio could not be shown in telegram inline mode. Moreover, it should not have keyboard
     markups like `add_to_playlist`, etc... . On top of that, if any audio of this kind gets downloaded through
     query search, then, it cannot be shown in `download_history` section or any other sections that work in inline
     mode.
    """

    estimated_bit_rate_type: BitRateType
    has_checked_forwarded_message: Optional[bool]
    has_checked_forwarded_message_at: Optional[int]

    type: AudioType
    archive_message_id: Optional[int]

    is_forwarded: bool
    is_deleted: bool
    deleted_at: Optional[int]  # this is not always accurate
    is_edited: bool

    @classmethod
    def parse_key(
        cls,
        telegram_message: pyrogram.types.Message,
        chat_id: int,
    ) -> Optional[str]:
        """
        Parse the `key` from the given `telegram_message` argument

        Parameters
        ----------
        telegram_message : pyrogram.types.Message
            Telegram message to parse the key from
        chat_id : int
            Chat ID this message belongs to.

        Returns
        -------
        str, optional
            Parsed key if the parsing was successful, otherwise return `None` if the `telegram_message` is `None`.

        """
        return parse_audio_key(telegram_message, chat_id)

    @classmethod
    def parse(
        cls,
        telegram_message: pyrogram.types.Message,
        chat_id: int,
        audio_type: AudioType,
    ) -> Optional[Audio]:
        """
        Parse an `Audio` from the given `telegram_message` argument.

        Parameters
        ----------
        telegram_message : pyrogram.types.Message
            Telegram message to parse the `Audio` from
        chat_id : int
            Chat ID this message belongs to.
        audio_type : AudioType
            Type of the audio.

        Returns
        -------
        Audio, optional
            Parsed `Audio` if parsing was successful, otherwise, return `None`.

        Raises
        ------
        TelegramMessageWithNoAudio
            If `telegram_message` argument does not contain any valid audio file.
        """
        if telegram_message is None:
            return None

        key = Audio.parse_key(telegram_message, chat_id)

        audio, telegram_audio_type = get_telegram_message_media_type(telegram_message)
        if audio is None or telegram_audio_type == TelegramAudioType.NON_AUDIO:
            raise TelegramMessageWithNoAudio(telegram_message.id, chat_id)

        title = getattr(audio, "title", None)

        valid_for_inline = is_audio_valid_for_inline(audio, telegram_audio_type)

        is_forwarded = True if telegram_message.forward_date else False

        if telegram_message.forward_from_chat:
            forwarded_from_chat_id = telegram_message.forward_from_chat.id
        else:
            forwarded_from_chat_id = None

        if telegram_message.forward_from:
            forwarded_from_user_id = telegram_message.forward_from.id
        else:
            forwarded_from_user_id = None

        if is_forwarded and forwarded_from_chat_id is not None:
            has_checked_forwarded_message = False
        else:
            has_checked_forwarded_message = None

        raw_title = copy.copy(title)
        raw_caption = copy.copy(telegram_message.caption if telegram_message.caption else telegram_message.text)
        raw_performer = copy.copy(getattr(audio, "performer", None))
        raw_file_name = copy.copy(audio.file_name)

        title = clean_text(title)
        caption = clean_text(telegram_message.caption if telegram_message.caption else telegram_message.text)
        performer = clean_text(getattr(audio, "performer", None))
        file_name = clean_text(audio.file_name)

        duration = getattr(audio, "duration", None)

        return Audio(
            key=key,
            chat_id=telegram_message.chat.id,
            message_id=telegram_message.id,
            message_caption=caption,
            raw_message_caption=raw_caption,
            message_date=datetime_to_timestamp(telegram_message.date),
            message_edit_date=datetime_to_timestamp(telegram_message.edit_date),
            views=telegram_message.views,
            forward_date=datetime_to_timestamp(telegram_message.forward_date),
            forward_from_user_id=forwarded_from_user_id,
            forward_from_chat_id=forwarded_from_chat_id,
            forward_from_message_id=telegram_message.forward_from_message_id,
            forward_signature=telegram_message.forward_signature,
            forward_sender_name=telegram_message.forward_sender_name,
            via_bot=True if telegram_message.via_bot else False,
            has_protected_content=telegram_message.has_protected_content,
            ################################
            file_unique_id=audio.file_unique_id,
            duration=duration,
            performer=performer,
            raw_performer=empty_to_null(raw_performer),
            title=title,
            raw_title=empty_to_null(raw_title),
            file_name=file_name,
            raw_file_name=empty_to_null(raw_file_name),
            mime_type=audio.mime_type,
            file_size=audio.file_size,
            date=datetime_to_timestamp(audio.date),
            ################################
            valid_for_inline_search=valid_for_inline,
            estimated_bit_rate_type=BitRateType.estimate(
                audio.file_size,
                duration,
            ),
            audio_type=telegram_audio_type,
            has_checked_forwarded_message=has_checked_forwarded_message,
            type=audio_type,
            is_forwarded=is_forwarded,
            is_deleted=True if telegram_message.empty else False,
            is_edited=True if telegram_message.edit_date else False,
        )

    async def mark_as_deleted(self) -> bool:
        """
        Mark the Audio the as deleted. This happens when the message is deleted in telegram.

        Returns
        -------
        bool
            Whether the operation was successful or not.

        """
        self_copy = self.copy(deep=True)
        self_copy.is_deleted = True
        self_copy.deleted_at = get_now_timestamp()
        return await self.update(
            self_copy,
            reserve_non_updatable_fields=False,
            check_for_revisions_match=False,
        )

    async def mark_as_non_audio(self) -> bool:
        """
        Mark the audio as invalid since it has been edited in telegram and changed to non-audio file.


        Returns
        -------
        bool
            Whether the update was successful or not.

        """
        self_copy = self.copy(deep=True)
        self_copy.audio_type = TelegramAudioType.NON_AUDIO
        return await self.update(
            self_copy,
            reserve_non_updatable_fields=True,
            check_for_revisions_match=False,
        )

    async def mark_as_archived(
        self,
        archive_message_id: int,
    ) -> bool:
        """
        Mark the audio as archived after it has been archived.

        Parameters
        ----------
        archive_message_id : int
            ID of the message in the archive channel.


        Returns
        -------
        bool
            Whether the update was successful or not.
        """
        if archive_message_id is None:
            return False

        self_copy: Audio = self.copy(deep=True)
        self_copy.type = AudioType.ARCHIVED
        self_copy.archive_message_id = archive_message_id

        return await self.update(
            self_copy,
            reserve_non_updatable_fields=True,
            check_for_revisions_match=False,
        )

    @property
    def is_archived(self) -> bool:
        """
        Check if this audio is archived or not.

        Returns
        -------
        bool
            Whether this audio is archived or not.

        """
        return self.type == AudioType.ARCHIVED

    def get_doc_cache_key(
        self,
        telegram_client_id: int,
    ) -> Optional[str]:
        if not telegram_client_id:
            return None

        if self.type == AudioType.NOT_ARCHIVED:
            return parse_audio_document_key(telegram_client_id, self.chat_id, self.message_id)
        else:
            # fixme : a better way to get the archive channel id ?
            return parse_audio_document_key(telegram_client_id, config("ARCHIVE_CHANNEL_ID"), self.archive_message_id)

    def find_hashtags(self) -> List[Tuple[str, int, MentionSource]]:
        """
        Find hashtags in text attributes of this audio vertex.

        Returns
        -------
        list
            A list containing a tuple of the `hashtag` string, its starting index, and its mention source.

        Raises
        ------
        ValueError
            If input data is invalid.
        """
        return find_hashtags_in_text(
            [
                self.raw_message_caption,
                self.raw_title,
                self.raw_performer,
                self.raw_file_name,
            ],
            [
                MentionSource.MESSAGE_TEXT,
                MentionSource.AUDIO_TITLE,
                MentionSource.AUDIO_PERFORMER,
                MentionSource.AUDIO_FILE_NAME if self.audio_type == TelegramAudioType.AUDIO_FILE else MentionSource.DOCUMENT_FILE_NAME,
            ],
        )


######################################################################


class AudioMethods:
    _get_audio_from_hit_query = (
        "for v,e in 1..1 outbound @start_vertex graph @graph_name options {order:'dfs', edgeCollections:[@has], vertexCollections:[@audios]}"
        "   limit 1"
        "   return v"
    )

    _check_audio_validity_for_inline_mode_by_hit_download_url = (
        "for hit in @@hits"
        "   filter hit.download_url == @hit_download_url"
        "   for v,e in 1..1 outbound hit graph @graph_name options {order:'dfs', edgeCollections:[@has], vertexCollections:[@audios]}"
        "       limit 1"
        "       return v.valid_for_inline_search"
    )

    _get_audio_by_hit_download_url = (
        "for hit in @@hits"
        "   filter hit.download_url == @hit_download_url"
        "   for v,e in 1..1 outbound hit graph @graph_name options {order:'dfs', edgeCollections:[@has], vertexCollections:[@audios]}"
        "       limit 1"
        "       return v"
    )

    _get_user_download_history_query = (
        "for dl_v,dl_e in 1..1 outbound @start_vertex graph @graph_name options {order:'dfs', edgeCollections:[@has], vertexCollections:[@interactions]}"
        "   filter dl_v.type == @interaction_type"
        "   sort dl_e.created_at DESC"
        "   for aud_v,has_e in 1..1 outbound dl_v graph @graph_name options {order:'dfs', edgeCollections:[@has], vertexCollections:[@audios]}"
        "       limit @offset, @limit"
        "       return aud_v"
    )

    _get_user_download_history_inline_query = (
        "for dl_v,dl_e in 1..1 outbound @start_vertex graph @graph_name options {order:'dfs', edgeCollections:[@has], vertexCollections:[@interactions]}"
        "   filter dl_v.type == @interaction_type"
        "   sort dl_e.created_at DESC"
        "   for aud_v,has_e in 1..1 outbound dl_v graph @graph_name options {order:'dfs', edgeCollections:[@has], vertexCollections:[@audios]}"
        "       filter aud_v.valid_for_inline_search == true"
        "       limit @offset, @limit"
        "       return aud_v"
    )

    _get_audios_by_keys = "return document(@@audios, @audio_keys)"

    _iter_audios_query = "for audio in @@audios" "   filter audio.modified_at <= @now" "   sort audio.created_at asc" "   return audio"

    _get_new_indexed_audios_count_query = (
        "for audio in @@audios"
        "   filter audio.created_at >= @checkpoint"
        "   collect with count into new_indexed_audios_count"
        "   return new_indexed_audios_count"
    )

    _get_total_indexed_audios_count_query = (
        "for audio in @@audios" "   collect with count into total_indexed_audios_count" "   return total_indexed_audios_count"
    )

    # fixme: this query returns duplicate items in the same group
    _get_not_archived_downloaded_audios = (
        "for interaction in @@interactions"
        "   filter interaction.type == @interaction_type and interaction.created_at < @now"
        "   sort interaction.created_at desc"
        "   for v_audio in 1..1 outbound interaction graph @graph_name options {order: 'dfs', edgeCollections: [@has], vertexCollections: [@audios]}"
        "       filter not has(v_audio, 'type') or v_audio.type == @not_archived_type"
        "       collect temp = v_audio.chat_id into chat_audios = v_audio"
        "       return chat_audios"
    )

    async def create_audio(
        self: ArangoGraphMethods,
        telegram_message: pyrogram.types.Message,
        chat_id: int,
        audio_type: AudioType,
    ) -> Optional[Audio]:
        """
        Create Audio alongside necessary vertices and edges in the ArangoDB.

        Parameters
        ----------
        telegram_message : pyrogram.types.Message
            Telegram message to create the Audio from
        chat_id : int
            Chat ID this message belongs to.
        audio_type : AudioType
            Type of the Audio.

        Returns
        -------
        Audio, optional
            Audio if the creation was successful, otherwise, return None

        Raises
        ------
        EdgeCreationFailed
            If creation of the related edges was unsuccessful.
        """
        if telegram_message is None:
            return None

        try:
            audio, successful = await Audio.insert(Audio.parse(telegram_message, chat_id, audio_type))
        except TelegramMessageWithNoAudio as e:
            # this message doesn't contain any valid audio file
            pass
        except Exception as e:
            logger.exception(e)
        else:
            if audio and successful:
                from tase.db.arangodb.graph.edges import HasHashtag

                audio: Audio = audio
                try:
                    hashtags = audio.find_hashtags()
                except ValueError:
                    pass
                else:
                    for hashtag, start_index, mention_source in hashtags:
                        hashtag_vertex = await self.get_or_create_hashtag(hashtag)

                        if hashtag_vertex:
                            has_hashtag = await HasHashtag.get_or_create_edge(
                                audio,
                                hashtag_vertex,
                                mention_source,
                                start_index,
                            )
                            if has_hashtag is None:
                                raise EdgeCreationFailed(HasHashtag.__class__.__name__)
                        else:
                            pass

                chat = await self.get_or_create_chat(telegram_message.chat)
                try:
                    from tase.db.arangodb.graph.edges import SentBy

                    sent_by_edge = await SentBy.get_or_create_edge(audio, chat)
                    if sent_by_edge is None:
                        raise EdgeCreationFailed(SentBy.__class__.__name__)
                except (InvalidFromVertex, InvalidToVertex):
                    pass

                # since checking for audio file validation is done above, there is no need to it again.
                file = await self.get_or_create_file(telegram_message)
                try:
                    from tase.db.arangodb.graph.edges import FileRef

                    file_ref_edge = await FileRef.get_or_create_edge(audio, file)
                    if file_ref_edge is None:
                        raise EdgeCreationFailed(FileRef.__class__.__name__)
                except (InvalidFromVertex, InvalidToVertex):
                    pass

                if audio.is_forwarded:
                    if telegram_message.forward_from:
                        forwarded_from = await self.get_or_create_user(telegram_message.forward_from)
                    elif telegram_message.forward_from_chat:
                        forwarded_from = await self.get_or_create_chat(telegram_message.forward_from_chat)
                    else:
                        forwarded_from = None

                    if forwarded_from is not None:
                        try:
                            from tase.db.arangodb.graph.edges import ForwardedFrom

                            forwarded_from_edge = await ForwardedFrom.get_or_create_edge(audio, forwarded_from)
                            if forwarded_from_edge is None:
                                raise EdgeCreationFailed(ForwardedFrom.__class__.__name__)
                        except (InvalidFromVertex, InvalidToVertex):
                            pass

                    # todo: the `forwarded_from` edge from `audio` to the `original audio` must be checked later

                if audio.via_bot:
                    bot = await self.get_or_create_user(telegram_message.via_bot)
                    try:
                        from tase.db.arangodb.graph.edges import ViaBot

                        via_bot_edge = await ViaBot.get_or_create_edge(audio, bot)
                        if via_bot_edge is None:
                            raise EdgeCreationFailed(ViaBot.__class__.__name__)
                    except (InvalidFromVertex, InvalidToVertex):
                        pass

                return audio

        return None

    async def get_or_create_audio(
        self,
        telegram_message: pyrogram.types.Message,
        chat_id: int,
        audio_type: AudioType,
    ) -> Optional[Audio]:
        """
        Get Audio if it exists in ArangoDB, otherwise, create Audio alongside necessary vertices and edges in the
        ArangoDB.

        Parameters
        ----------
        telegram_message : pyrogram.types.Message
            Telegram message to create the Audio from
        chat_id : int
            Chat ID this message belongs to.
        audio_type : AudioType
            Type of the audio.

        Returns
        -------
        Audio, optional
            Audio if the operation was successful, otherwise, return None

        Raises
        ------
        EdgeCreationFailed
            If creation of the related edges was unsuccessful.
        """
        if telegram_message is None:
            return None

        audio = await Audio.get(Audio.parse_key(telegram_message, chat_id))
        if audio is None:
            audio = await self.create_audio(telegram_message, chat_id, audio_type)

        return audio

    async def update_or_create_audio(
        self: ArangoGraphMethods,
        telegram_message: pyrogram.types.Message,
        chat_id: int,
        audio_type: AudioType,
    ) -> Optional[Audio]:
        """
        Update Audio alongside necessary vertices and edges in the ArangoDB if it exists, otherwise, create it.

        Parameters
        ----------
        telegram_message : pyrogram.types.Message
            Telegram message to create the Audio from.
        chat_id : int
            Chat ID this message belongs to.
        audio_type : AudioType
            Type of the audio.

        Returns
        -------
        Audio, optional
            Audio if the creation was successful, otherwise, return None

        Raises
        ------
        EdgeCreationFailed
            If creation of the related edges was unsuccessful.
        """
        if telegram_message is None:
            return None

        audio: Optional[Audio] = await Audio.get(Audio.parse_key(telegram_message, chat_id))

        if audio is not None:
            telegram_audio, telegram_audio_type = get_telegram_message_media_type(telegram_message)
            if telegram_audio is None or telegram_audio_type == TelegramAudioType.NON_AUDIO:
                # this message doesn't contain any valid audio file, check if there is a previous audio in the database
                # and check it as invalid audio.
                successful = await audio.mark_as_non_audio()
                if not successful:
                    # fixme: could not mark the audio as invalid, why?
                    pass
            else:
                # update the audio and its edges
                if telegram_message.empty:
                    # the message has been deleted, mark the audio as deleted in the database
                    deleted = await audio.mark_as_deleted()
                    if not deleted:
                        # fixme: could not mark the audio as deleted, why?
                        pass
                else:
                    # the message has not been `deleted`, update remaining attributes
                    from tase.db.arangodb.graph.edges import FileRef

                    try:
                        # the type of the audio after update is not changed. So, the previous type is used for updating the current one.
                        new_audio = Audio.parse(telegram_message, chat_id, audio.type)

                        if new_audio.file_unique_id == audio.file_unique_id:
                            updated = await audio.update(new_audio)
                            if updated:
                                await self._update_connected_hashtags(audio)
                        else:
                            # audio file has been changed, the connected hashtag and file vertices must be updated.
                            updated = await audio.update(new_audio)
                            if updated:
                                # todo: remove the audio from playlists, etc.

                                # update connected hashtag vertices and edges
                                await self._update_connected_hashtags(audio)

                                current_file, current_file_ref = await self.get_audio_file_with_file_ref_edge(audio.id)
                                if current_file and current_file_ref:
                                    current_file_ref: FileRef

                                    if await current_file_ref.delete():
                                        # since checking for audio file validation is done above, there is no need to it again.
                                        await self._create_file_with_file_ref_edge(telegram_message, audio)
                                    else:
                                        logger.error(
                                            f"Error in deleting `FileRef` edge with key `{current_file_ref.key}` connected to `Audio` vertex with key `"
                                            f"{audio.key}`"
                                        )
                                else:
                                    # since checking for audio file validation is done above, there is no need to it again.
                                    await self._create_file_with_file_ref_edge(telegram_message, audio)

                    except ValueError:
                        updated = False
                    except TelegramMessageWithNoAudio:
                        await audio.mark_as_non_audio()
                        updated = False

        else:
            audio = await self.create_audio(telegram_message, chat_id, audio_type)

        return audio

    async def _create_file_with_file_ref_edge(
        self: ArangoGraphMethods,
        telegram_message: pyrogram.types.Message,
        audio: Audio,
    ) -> None:
        """
        Create a `File` vertex and connect it to the given `Audio` vertex with a `FileRef` edge.

        Parameters
        ----------
        telegram_message : pyrogram.types.Message
            Telegram message to use for creating the file vertex and file_ref edge.
        audio : Audio
            `Audio` vertex to create the file and file_ref for.

        Raises
        ------
        EdgeCreationFailed
            If creation of the related edges was unsuccessful.
        """
        file = await self.get_or_create_file(telegram_message)
        try:
            from tase.db.arangodb.graph.edges import FileRef

            file_ref_edge = await FileRef.get_or_create_edge(audio, file)
            if file_ref_edge is None:
                raise EdgeCreationFailed(FileRef.__class__.__name__)

        except (InvalidFromVertex, InvalidToVertex):
            pass

    async def _update_connected_hashtags(
        self: ArangoGraphMethods,
        audio: Audio,
    ) -> None:
        """
        Update connected `hashtag` vertices and edges connected to and `Audio` vertex after being updated.

        Parameters
        ----------
        audio : Audio
            Updated audio vertex.

        Raises
        ------
        EdgeCreationFailed
            If creation of the related edges was unsuccessful.
        """
        from tase.db.arangodb.graph.edges import HasHashtag

        try:
            hashtags = audio.find_hashtags()
        except ValueError:
            pass
        else:
            # get the current hashtag vertices and edges connected to this audio vertex
            current_hashtags_and_edges_list = await self.get_audio_hashtags_with_edges(audio.id)
            current_vertices = {hashtag.key for hashtag, _ in current_hashtags_and_edges_list}
            current_edges = {edge.key for _, edge, in current_hashtags_and_edges_list}

            current_vertices_mapping = {hashtag.key: hashtag for hashtag, _ in current_hashtags_and_edges_list}
            current_edges_mapping = {edge.key: edge for _, edge, in current_hashtags_and_edges_list}

            # find the new hashtag vertices and edges keys
            new_vertices = set()
            new_edges = set()

            new_vertices_mapping = dict()
            new_edges_mapping = dict()

            for hashtag_string, start_index, mention_source in hashtags:
                hashtag_key = Hashtag.parse_key(hashtag_string)
                edge_key = HasHashtag.parse_has_hashtag_key(audio.key, hashtag_key, mention_source, start_index)

                new_vertices.add(hashtag_key)
                new_edges.add(edge_key)

                new_vertices_mapping[hashtag_key] = hashtag_string
                new_edges_mapping[edge_key] = (hashtag_key, start_index, mention_source)

            # find the difference between the current and new state of vertices and edges
            removed_vertices = current_vertices - new_vertices  # since a hashtag vertex might be connected to other audio vertices, it's best not to delete it.
            removed_edges = current_edges - new_edges

            to_create_vertices = new_vertices - current_vertices
            to_create_edges = new_edges - current_edges

            # delete the removed edges
            for edge_key in removed_edges:
                to_be_removed_edge: HasHashtag = current_edges_mapping[edge_key]
                if not await to_be_removed_edge.delete():
                    logger.error(f"Error in deleting `HasHashtag` edge with key `{to_be_removed_edge.key}`")

            # create new hashtag vertices
            for hashtag_key in to_create_vertices:
                hashtag_string: str = new_vertices_mapping.get(hashtag_key, None)
                if hashtag_string:
                    _vertex = await self.get_or_create_hashtag(hashtag_string)
                    if _vertex:
                        current_vertices_mapping[hashtag_key] = _vertex

            # create the new edges
            for edge_key in to_create_edges:
                hashtag_key, start_index, mention_source = new_edges_mapping[edge_key]
                hashtag_vertex = current_vertices_mapping.get(hashtag_key, None)
                if hashtag_vertex:
                    has_hashtag = await HasHashtag.get_or_create_edge(
                        audio,
                        hashtag_vertex,
                        mention_source,
                        start_index,
                    )
                    if has_hashtag is None:
                        raise EdgeCreationFailed(HasHashtag.__class__.__name__)

    async def find_audio_by_download_url(
        self,
        download_url: str,
    ) -> Optional[Audio]:
        """
        Get Audio by `download_url` in the ArangoDB

        Parameters
        ----------
        download_url : str
            Download URL to get the Audio from

        Returns
        -------
        Audio, optional
            Audio if it exists with the given `download_url` parameter, otherwise, return None

        """
        if download_url is None:
            return None

        return await Audio.find_one({"download_url": download_url})

    async def get_audio_from_hit(
        self,
        hit: Hit,
    ) -> Optional[Audio]:
        """
        Get an `Audio` vertex from the given `Hit` vertex

        Parameters
        ----------
        hit : Hit
            Hit to get the audio from.

        Returns
        -------
        Audio, optional
            Audio if operation was successful, otherwise, return None

        Raises
        ------
        ValueError
            If the given `Hit` vertex has more than one linked `Audio` vertices.
        """
        if hit is None:
            return

        from tase.db.arangodb.graph.edges import Has

        res = collections.deque()
        async with await Audio.execute_query(
            self._get_audio_from_hit_query,
            bind_vars={
                "start_vertex": hit.id,
                "audios": Audio._collection_name,
                "has": Has._collection_name,
            },
        ) as cursor:
            async for doc in cursor:
                res.append(Audio.from_collection(doc))

        if len(res) > 1:
            raise ValueError(f"Hit with id `{hit.id}` have more than one linked audios.")

        if res:
            return res[0]

        return None

    async def is_audio_valid_for_inline_mode(
        self,
        *,
        hit_download_url: str = None,
        audio_vertex_key: str = None,
    ) -> Optional[bool]:
        """
        Check for inline validity of an `Audio` vertex from a `Hit` vertex `download_url`

        Parameters
        ----------
        hit_download_url : str
            Download URL of a hit vertex connected to the audio vertex
        audio_vertex_key : str
            Audio vertex key

        Returns
        -------
        bool, optional
            Whether the audio vertex is valid for inline search if it exists in the database, otherwise return None

        """
        if audio_vertex_key is None and (hit_download_url is None or not len(hit_download_url)):
            return False

        from tase.db.arangodb.graph.edges import Has

        if hit_download_url is not None:
            async with await Audio.execute_query(
                self._check_audio_validity_for_inline_mode_by_hit_download_url,
                bind_vars={
                    "@hits": Hit._collection_name,
                    "hit_download_url": hit_download_url,
                    "audios": Audio._collection_name,
                    "has": Has._collection_name,
                },
            ) as cursor:
                async for doc in cursor:
                    return doc

        else:
            audio: Audio = await Audio.get(audio_vertex_key)
            return audio.valid_for_inline_search if audio is not None else False

        return False

    async def get_audio_from_hit_download_url(
        self,
        hit_download_url: str = None,
    ) -> Optional[Audio]:
        """
        Get the audio vertex connected to a hit vertex with the given download URL.

        Parameters
        ----------
        hit_download_url : str
            Download URL of a hit vertex connected to the audio vertex

        Returns
        -------
        Audio, optional
            Audio vertex connected to the hit vertex with the given download URL.

        """
        if not hit_download_url:
            return None

        from tase.db.arangodb.graph.edges import Has

        async with await Audio.execute_query(
            self._get_audio_by_hit_download_url,
            bind_vars={
                "@hits": Hit._collection_name,
                "hit_download_url": hit_download_url,
                "audios": Audio._collection_name,
                "has": Has._collection_name,
            },
        ) as cursor:
            async for doc in cursor:
                return Audio.from_collection(doc)

        return None

    async def get_user_download_history(
        self,
        user: User,
        filter_by_valid_for_inline_search: bool = True,
        offset: int = 0,
        limit: int = 15,
    ) -> Deque[Audio]:
        """
        Get `User` download history.

        Parameters
        ----------
        user : User
            User to get the download history
        filter_by_valid_for_inline_search : bool, default : True
            Whether to only get audio files that are valid to be shown in inline mode
        offset : int, default : 0
            Offset to get the download history query after
        limit : int, default : 15
            Number of `Audio`s to query

        Returns
        -------
        deque
            Audios that the given user has downloaded

        """
        if user is None:
            return collections.deque()

        from tase.db.arangodb.graph.edges import Has

        res = collections.deque()
        async with await Audio.execute_query(
            self._get_user_download_history_inline_query if filter_by_valid_for_inline_search else self._get_user_download_history_query,
            bind_vars={
                "start_vertex": user.id,
                "has": Has._collection_name,
                "audios": Audio._collection_name,
                "interactions": Interaction._collection_name,
                "interaction_type": InteractionType.DOWNLOAD.value,
                "offset": offset,
                "limit": limit,
            },
        ) as cursor:
            async for doc in cursor:
                res.append(Audio.from_collection(doc))

        return res

    async def get_audios_from_keys(
        self,
        keys: List[str],
    ) -> Deque[Audio]:
        """
        Get a list of Audios from a list of keys.

        Parameters
        ----------
        keys : List[str]
            List of keys to get the audios from.

        Returns
        -------
        Deque
            List of Audios if operation was successful, otherwise, return None

        """
        if keys is None or not len(keys):
            return collections.deque()

        res = collections.deque()
        async with await Audio.execute_query(
            self._get_audios_by_keys,
            bind_vars={
                "@audios": Audio._collection_name,
                "audio_keys": list(keys),
            },
        ) as cursor:
            async for audios_lst in cursor:
                for doc in audios_lst:
                    res.append(Audio.from_collection(doc))

        return res

    async def iter_audios(
        self,
        now: int,
    ) -> Generator[Audio, None, None]:
        if now is None:
            return

        async with await Audio.execute_query(
            self._iter_audios_query,
            bind_vars={
                "@audios": Audio._collection_name,
                "now": now,
            },
        ) as cursor:
            async for doc in cursor:
                yield Audio.from_collection(doc)

    async def get_audio_by_key(
        self,
        key: str,
    ) -> Optional[Audio]:
        return await Audio.get(key)

    async def get_new_indexed_audio_files_count(self) -> int:
        """
        Get the total number of indexed audio files in the last 24 hours

        Returns
        -------
        int
            Total number of indexed audio files in the last 24 hours

        """
        checkpoint = get_now_timestamp() - 86400000

        async with await Audio.execute_query(
            self._get_new_indexed_audios_count_query,
            bind_vars={
                "@audios": Audio._collection_name,
                "checkpoint": checkpoint,
            },
        ) as cursor:
            async for doc in cursor:
                return int(doc)

        return 0

    async def get_total_indexed_audio_files_count(self) -> int:
        """
        Get the total number of indexed audio files

        Returns
        -------
        int
            Total number of indexed audio files

        """
        async with await Audio.execute_query(
            self._get_total_indexed_audios_count_query,
            bind_vars={
                "@audios": Audio._collection_name,
            },
        ) as cursor:
            async for doc in cursor:
                return int(doc)

        return 0

    async def get_not_archived_downloaded_audios(self) -> Deque[Deque[Audio]]:
        """
        Get the downloaded audio vertices that have not been archived yet.

        Returns
        -------
        deque
            A nested deque containing the results grouped by `chat_id` attribute.

        """
        from tase.db.arangodb.graph.edges import Has

        res = collections.deque()
        async with await Audio.execute_query(
            self._get_not_archived_downloaded_audios,
            bind_vars={
                "@interactions": Interaction._collection_name,
                "audios": Audio._collection_name,
                "has": Has._collection_name,
                "now": get_now_timestamp(),
                "interaction_type": InteractionType.DOWNLOAD.value,
                "not_archived_type": AudioType.NOT_ARCHIVED.value,
            },
        ) as cursor:
            async for audio_doc_lst in cursor:
                group = collections.deque()
                group_keys = set()
                for audio_doc in audio_doc_lst:
                    if audio_doc["_key"] not in group_keys:
                        _audio = Audio.from_collection(audio_doc)
                        group.append(_audio)
                        group_keys.add(_audio.key)

                if group:
                    res.append(group)

        return res
