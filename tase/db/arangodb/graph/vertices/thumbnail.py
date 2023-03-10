from __future__ import annotations

import collections
from typing import Optional, Deque, Tuple, TYPE_CHECKING

import pyrogram.types

from aioarango.models import PersistentIndex
from tase.common.utils import datetime_to_timestamp
from tase.errors import EdgeCreationFailed
from tase.my_logger import logger
from .base_vertex import BaseVertex

if TYPE_CHECKING:
    from . import Audio
    from .. import ArangoGraphMethods
    from ..edges import Has


class Thumbnail(BaseVertex):
    """
    Represents the information about the thumbnail of an audio file.

    Attributes
    ----------
    photo_file_unique_id : str
        File unique ID of the uploaded photo.
    thumbnail_file_unique_id : str
        File unique ID of the original thumbnail.
    width : int
        Width of the original thumbnail and the uploaded photo.
    height : int
        Height of the original thumbnail and the uploaded photo.
    file_size : int
        Size of the original thumbnail file or the uploaded photo.
    date : int
        Timestamp in which the photo was uploaded. (in nanoseconds)
    archive_chat_id : int
        ID of the chat where the photo was uploaded.
    archive_message_id : int
        ID of the message which the photo belongs to.
    """

    schema_version = 1
    __collection_name__ = "thumbnails"
    __indexes__ = [
        PersistentIndex(
            custom_version=1,
            name="photo_file_unique_id",
            fields=[
                "photo_file_unique_id",
            ],
        ),
        PersistentIndex(
            custom_version=1,
            name="thumbnail_file_unique_id",
            fields=[
                "thumbnail_file_unique_id",
            ],
        ),
        PersistentIndex(
            custom_version=1,
            name="archive_chat_id",
            fields=[
                "archive_chat_id",
            ],
        ),
        PersistentIndex(
            custom_version=1,
            name="archive_message_id",
            fields=[
                "archive_message_id",
            ],
        ),
    ]
    __non_updatable_fields__ = []

    photo_file_unique_id: str
    thumbnail_file_unique_id: str

    # These attributes are the same for both the thumbnail and the uploaded photo.
    width: int
    height: int
    file_size: int

    # This attribute is for the uploaded photo
    date: int

    # These attributes show the uploaded photo message information.
    archive_chat_id: int
    archive_message_id: int

    @classmethod
    def parse_key(
        cls,
        telegram_thumbnail: pyrogram.types.Thumbnail,
    ) -> Optional[str]:
        if not telegram_thumbnail:
            return None

        return telegram_thumbnail.file_unique_id

    @classmethod
    def parse(
        cls,
        telegram_thumbnail: pyrogram.types.Thumbnail,
        telegram_uploaded_photo_message: pyrogram.types.Message,
    ) -> Optional[Thumbnail]:
        if not telegram_thumbnail or not telegram_uploaded_photo_message or not telegram_uploaded_photo_message.photo:
            return None

        photo = telegram_uploaded_photo_message.photo

        key = cls.parse_key(telegram_thumbnail)
        if not key:
            return None

        return Thumbnail(
            key=key,
            photo_file_unique_id=photo.file_unique_id,
            thumbnail_file_unique_id=telegram_thumbnail.file_unique_id,
            width=photo.width,
            height=photo.height,
            file_size=photo.file_size,
            date=datetime_to_timestamp(photo.date),
            archive_chat_id=telegram_uploaded_photo_message.chat.id,
            archive_message_id=telegram_uploaded_photo_message.id,
        )


class ThumbnailMethods:
    _get_audio_vertex_thumbnails_with_edge_query = (
        "for v, e in 1..1 outbound @vertex_id graph @graph_name options {order: 'dfs', edgeCollections: [@has], vertexCollections: [@thumbnails]}"
        "   sort e.created_at asc"
        "   return {vertex: v, edge: e}"
    )

    async def get_thumbnail(self, telegram_thumbnail: pyrogram.types.Thumbnail) -> Optional[Thumbnail]:
        return await Thumbnail.get(Thumbnail.parse_key(telegram_thumbnail))

    async def get_thumbnail_by_archive_message_info(
        self,
        archive_chat_id: int,
        archive_message_id: int,
    ) -> Optional[Thumbnail]:
        return await Thumbnail.find_one(
            filters={
                "archive_chat_id": archive_chat_id,
                "archive_message_id": archive_message_id,
            }
        )

    async def create_thumbnail(
        self,
        telegram_thumbnail: pyrogram.types.Thumbnail,
        telegram_uploaded_photo_message: pyrogram.types.Message,
    ) -> Optional[Thumbnail]:
        try:
            thumbnail, successful = await Thumbnail.insert(
                Thumbnail.parse(
                    telegram_thumbnail=telegram_thumbnail,
                    telegram_uploaded_photo_message=telegram_uploaded_photo_message,
                )
            )
        except Exception as e:
            logger.exception(e)
        else:
            if thumbnail and successful:
                return thumbnail

        return None

    async def get_or_create_thumbnail(
        self,
        telegram_thumbnail: pyrogram.types.Thumbnail,
        telegram_uploaded_photo_message: pyrogram.types.Message,
    ) -> Optional[Thumbnail]:
        thumbnail = await Thumbnail.get(Thumbnail.parse_key(telegram_thumbnail))
        if not thumbnail:
            thumbnail = await self.create_thumbnail(
                telegram_thumbnail=telegram_thumbnail,
                telegram_uploaded_photo_message=telegram_uploaded_photo_message,
            )

        return thumbnail

    async def update_connected_thumbnails(
        self: ArangoGraphMethods,
        source_vertex: Audio,
        thumbnails: Deque[Thumbnail],
    ) -> None:
        """
        Update connected `Thumbnail` vertices and edges connected to an `Audio` vertex after being updated.

        Parameters
        ----------
        source_vertex : Audio
            Audio vertex to update its `Thumbnail` vertices.
        thumbnails : List
            The new thumbnail vertices to update the edges by.

        Raises
        ------
        EdgeCreationFailed
            If creation of the related edges was unsuccessful.
        """
        from tase.db.arangodb.graph.edges import Has

        # get the current thumbnail vertices and edges connected to this vertex
        current_thumbnails_and_edges = await self.get_audio_thumbnails_with_edges(audio_vertex_id=source_vertex.id)
        current_vertices = {thumbnail.key for thumbnail, _ in current_thumbnails_and_edges}
        current_edges = {edge.key for _, edge, in current_vertices}

        current_vertices_mapping = {thumbnail.key: thumbnail for thumbnail, _ in current_thumbnails_and_edges}
        current_edges_mapping = {edge.key: edge for _, edge, in current_thumbnails_and_edges}

        # find the new thumbnail vertices and edges' keys
        new_vertices = set()
        new_edges = set()

        new_vertices_mapping = dict()
        new_edges_mapping = dict()

        for new_thumbnail in thumbnails:
            thumbnail_key = new_thumbnail.key
            edge_key = Has.parse_key(source_vertex, new_thumbnail)

            new_vertices.add(thumbnail_key)
            new_edges.add(edge_key)

            new_vertices_mapping[thumbnail_key] = new_thumbnail
            new_edges_mapping[edge_key] = new_thumbnail

        # find the difference between the current and the new state of the given vertices and edges
        removed_vertices = current_vertices - new_vertices
        removed_edges = current_edges - new_edges

        to_create_vertices = new_vertices - current_vertices
        to_create_edges = new_edges - current_edges

        # delete the removed edges
        for edge_key in removed_edges:
            to_be_removed_edge: Has = current_edges_mapping[edge_key]
            if not await to_be_removed_edge.delete():
                logger.error(f"Error in deleting `Has` edge with key `{edge_key}`")

        # create new thumbnail vertices:
        # since the thumbnail vertices are already stored in the database, there is no need for this part

        # create the new edges
        for edge_key in to_create_edges:
            thumbnail_v = new_edges_mapping[edge_key]
            if thumbnail_v:
                if not await Has.get_or_create_edge(source_vertex, thumbnail_v):
                    raise EdgeCreationFailed(Has.__class__.__name__)

    async def get_audio_thumbnails_with_edges(self, audio_vertex_id: str) -> Deque[Tuple[Thumbnail, Has]]:
        if not audio_vertex_id:
            return collections.deque()

        from ..edges import Has

        res = collections.deque()
        async with await Thumbnail.execute_query(
            self._get_audio_vertex_thumbnails_with_edge_query,
            bind_vars={
                "vertex_id": audio_vertex_id,
                "has": Has.__collection_name__,
                "thumbnails": Thumbnail.__collection_name__,
            },
        ) as cursor:
            async for d in cursor:
                if "vertex" in d and "edge" in d:
                    res.append(
                        (
                            Thumbnail.from_collection(d["vertex"]),
                            Has.from_collection(d["edge"]),
                        )
                    )

        return res
