from typing import Optional

from pydantic import BaseModel, Field

from tase.utils import get_timestamp
from ..vertices import BaseVertex


class BaseEdge(BaseModel):
    _collection_edge_name = 'base_edge_collection'

    _from_graph_db_mapping = {
        '_id': 'id',
        '_key': 'key',
        '_rev': 'rev',
    }
    _from_graph_db_mapping_rel = {
        '_from': 'from_node',
        '_to': 'to_node',
    }

    _to_graph_db_mapping = {
        'id': '_id',
        'key': '_key',
        'rev': '_rev',
    }
    _to_graph_db_mapping_rel = {
        'from_node': '_from',
        'to_node': '_to',
    }

    id: Optional[str]
    key: Optional[str]
    rev: Optional[str]
    from_node: 'BaseVertex'
    to_node: 'BaseVertex'
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

        for k, v in self._to_graph_db_mapping_rel.items():
            if temp_dict.get(k, None):
                temp_dict[v] = temp_dict[k]['id']
                del temp_dict[k]
            else:
                del temp_dict[k]
                temp_dict[v] = None

        return temp_dict

    @classmethod
    def _from_graph(cls, vertex: dict) -> Optional['dict']:
        if not len(vertex):
            return None

        for k, v in BaseEdge._from_graph_db_mapping.items():
            if vertex.get(k, None):
                vertex[v] = vertex[k]
                del vertex[k]
            else:
                vertex[v] = None

        for k, v in BaseEdge._from_graph_db_mapping_rel.items():
            if vertex.get(k, None):
                vertex[v] = BaseVertex.parse_from_graph({'_id': vertex.get(vertex[k], None)})
                del vertex[k]
            else:
                vertex[v] = None

        return vertex

    def parse_for_graph(self) -> dict:
        return self._to_graph()

    @classmethod
    def parse_from_graph(cls, vertex: dict):
        return cls(**cls._from_graph(vertex))

    def update_from_metadata(self, metadata: dict):
        for k, v in self._from_graph_db_mapping.items():
            setattr(self, v, metadata.get(k, None))
