from typing import Optional, Tuple

from arango import DocumentInsertError, DocumentUpdateError, DocumentRevisionError
from arango.collection import VertexCollection
from pydantic import BaseModel, Field

from tase.my_logger import logger
from tase.utils import get_timestamp


class BaseVertex(BaseModel):
    _vertex_name = 'base_vertices'
    _from_graph_db_mapping = {
        '_id': 'id',
        '_key': 'key',
        '_rev': 'rev',
    }
    _to_graph_db_mapping = {
        'id': '_id',
        'key': '_key',
        'rev': '_rev',
    }

    id: Optional[str]
    key: Optional[str]
    rev: Optional[str]
    created_at: int = Field(default_factory=get_timestamp)
    modified_at: int = Field(default_factory=get_timestamp)

    def _to_graph(self) -> dict:
        temp_dict = self.dict()
        for k, v in self._to_graph_db_mapping.items():
            if temp_dict.get(k, None):
                temp_dict[v] = temp_dict[k]
                del temp_dict[k]
            else:
                del temp_dict[k]
                temp_dict[v] = None

        return temp_dict

    @classmethod
    def _from_graph(cls, vertex: dict) -> Optional['dict']:
        if not len(vertex):
            return None

        for k, v in BaseVertex._from_graph_db_mapping.items():
            if vertex.get(k, None):
                vertex[v] = vertex[k]
                del vertex[k]
            else:
                vertex[v] = None

        return vertex

    def parse_for_graph(self) -> dict:
        return self._to_graph()

    @classmethod
    def parse_from_graph(cls, vertex: dict):
        return cls(**cls._from_graph(vertex))

    def _update_from_metadata(self, metadata: dict):
        """
        Update the vertex's metadata from the `metadata`

        :param metadata: metadata returned from the database transaction
        """
        for k, v in self._from_graph_db_mapping.items():
            setattr(self, v, metadata.get(k, None))

    def _update_metadata_from_vertex(self, vertex: 'BaseVertex'):
        """
        Updates the metadata of this vertex from another vertex metadata
        :param vertex: The vertex to get the metadata from
        :return: self
        """
        for k in self._to_graph_db_mapping.keys():
            setattr(self, k, getattr(vertex, k, None))

        return self

    def create(self, db: 'VertexCollection') -> Tuple['BaseVertex', bool]:
        """
        Insert the object into the database

        :param db: The VertexCollection to use for inserting the object
        :return: self, successful
        """
        successful = True
        try:
            metadata = db.insert(self.parse_for_graph())
            self._update_from_metadata(metadata)
        except DocumentInsertError as e:
            # Failed to insert the document
            successful = False
            logger.exception(e)
        except Exception as e:
            successful = False
            logger.exception(e)
        return self, successful

    def update(self, db: 'VertexCollection', vertex: 'BaseVertex') -> Tuple['BaseVertex', bool]:
        """
        Update an object in the database

        :param vertex: The vertex used for updating the object
        :param db: The VertexCollection to use for updating the object
        :return: self, successful
        """
        if not isinstance(vertex, BaseVertex):
            raise Exception(f'`vertex` is not an instance of {BaseVertex.__class__.__name__} class')

        successful = True
        try:
            metadata = db.update(vertex._update_metadata_from_vertex(self).parse_for_graph())
            self._update_from_metadata(metadata)
        except DocumentUpdateError as e:
            # Failed to update document.
            successful = False
            logger.exception(e)
        except DocumentRevisionError as e:
            # The expected and actual document revisions mismatched.
            successful = False
            logger.exception(e)
        except Exception as e:
            successful = False
            logger.exception(e)
        return self, successful
