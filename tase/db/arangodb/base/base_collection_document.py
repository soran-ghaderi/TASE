from arango import DocumentInsertError, DocumentRevisionError, DocumentUpdateError
from arango.collection import VertexCollection, EdgeCollection
from pydantic import BaseModel, Field, ValidationError
from pydantic.types import Enum
from pydantic.typing import Dict, List, Optional, Any, Type, Union, Tuple

from tase.my_logger import logger
from tase.utils import get_timestamp


class ToGraphBaseProcessor(BaseModel):
    @classmethod
    def process(
        cls,
        document: "BaseCollectionDocument",
        attr_value_dict: Dict[str, Any],
    ) -> None:
        """
        Executes some operations on the attribute value dictionary.

        Parameters
        ----------
        document : BaseCollectionDocument
            Document this processing is done for
        attr_value_dict : Dict[str, Any]
            Attribute value mapping dictionary to be processed
        """
        raise NotImplementedError


class FromGraphBaseProcessor(BaseModel):
    @classmethod
    def process(
        cls,
        document_class: Type["BaseCollectionDocument"],
        graph_doc: Dict[str, Any],
    ) -> None:
        """
        Executes some operations on the attribute value dictionary.

        Parameters
        ----------
        document_class : BaseCollectionDocument
            Class of this document. (It's not an instance of the class)
        graph_doc : Dict[str, Any]
            Attribute value mapping dictionary to be processed
        """
        raise NotImplementedError


##############################################################################


class ToGraphAttributeMapper(ToGraphBaseProcessor):
    """
    Prepares the attribute value mapping to be saved into the database.
    """

    @classmethod
    def process(
        cls,
        document: "BaseCollectionDocument",
        attr_value_dict: Dict[str, Any],
    ) -> None:
        for obj_attr, graph_doc_attr in document._to_graph_db_mapping.items():
            attr_value = attr_value_dict.get(obj_attr, None)
            if attr_value is not None:
                attr_value_dict[graph_doc_attr] = attr_value
                del attr_value_dict[obj_attr]
            else:
                del attr_value_dict[obj_attr]
                attr_value_dict[graph_doc_attr] = None


class ToGraphEnumConverter(ToGraphBaseProcessor):
    """
    Converts enum types to their values because `Enum` types cannot be directly saved into ArangoDB.

    """

    @classmethod
    def process(
        cls,
        document: "BaseCollectionDocument",
        attr_value_dict: Dict[str, Any],
    ) -> None:
        for attr_name, attr_value in attr_value_dict.copy().items():
            attr_value = getattr(document, attr_name, None)
            if attr_value:
                if isinstance(attr_value, Enum):
                    attr_value_dict[attr_name] = attr_value.value


class FromGraphAttributeMapper(FromGraphBaseProcessor):
    """
    Prepare the attribute value mapping from graph to be converted into a python object.
    """

    @classmethod
    def process(
        cls,
        document_class: Type["BaseCollectionDocument"],
        graph_doc: Dict[str, Any],
    ) -> None:
        for graph_doc_attr, obj_attr in document_class._from_graph_db_mapping.items():
            attr_value = graph_doc.get(graph_doc_attr, None)
            if attr_value is not None:
                graph_doc[obj_attr] = attr_value
                del graph_doc[graph_doc_attr]
            else:
                graph_doc[obj_attr] = None


################################################################################


class BaseCollectionDocument(BaseModel):
    schema_version: int = Field(default=1)

    _collection_name = "base_documents"
    _collection: Optional[Union[VertexCollection, EdgeCollection]]

    _from_graph_db_mapping = {
        "_id": "id",
        "_key": "key",
        "_rev": "rev",
    }

    _to_graph_db_mapping = {
        "id": "_id",
        "key": "_key",
        "rev": "_rev",
    }

    _to_graph_db_base_processors: Optional[List[ToGraphBaseProcessor]] = (
        ToGraphEnumConverter,
        ToGraphAttributeMapper,
    )
    _to_graph_db_extra_processors: Optional[List[ToGraphBaseProcessor]] = None

    _from_graph_db_base_processors: Optional[List[FromGraphBaseProcessor]] = (FromGraphAttributeMapper,)
    _from_graph_db_extra_processors: Optional[List[FromGraphBaseProcessor]] = None

    _base_do_not_update_fields: Optional[List[str]] = ["created_at"]
    _extra_do_not_update_fields = None

    id: Optional[str]
    key: Optional[str]
    rev: Optional[str]

    created_at: int = Field(default_factory=get_timestamp)
    modified_at: int = Field(default_factory=get_timestamp)

    class Config:
        arbitrary_types_allowed = True

    def to_graph(self) -> Dict[str, Any]:
        """
        Converts the object to a dictionary to be saved into the ArangoDB.

        Returns
        -------
        Dict[str, Any]
            Dictionary mapping attribute names to attribute values

        """
        attr_value_dict = self.dict()

        for attrib_processor in self._to_graph_db_base_processors:
            attrib_processor.process(self, attr_value_dict)

        if self._to_graph_db_extra_processors is not None:
            for doc_processor in self._to_graph_db_extra_processors:
                doc_processor.process(self, attr_value_dict)

        return attr_value_dict

    @classmethod
    def from_graph(
        cls,
        doc: Dict[str, Any],
    ) -> Optional["BaseCollectionDocument"]:
        """
        Converts a database document dictionary to be converted into a python object.

        Parameters
        ----------
        doc : Dict[str, Any]
            Dictionary mapping attribute names to attribute values

        Returns
        -------
        BaseCollectionDocument
            Python object converted from the database document dictionary

        """
        if doc is None or not len(doc):
            return None

        for doc_processor in cls._from_graph_db_base_processors:
            doc_processor.process(cls, doc)

        if cls._from_graph_db_extra_processors is not None:
            for doc_processor in cls._from_graph_db_extra_processors:
                doc_processor.process(cls, doc)

        try:
            obj = cls(**doc)
        except ValidationError as e:
            # Attribute value mapping cannot be validated, and it cannot be converted to a python object
            logger.debug(e)
        except Exception as e:
            # todo: check if this happens
            logger.exception(e)
        else:
            return obj

        return None

    @classmethod
    def create(
        cls,
        doc: "BaseCollectionDocument",
    ) -> Tuple[Optional["BaseCollectionDocument"], bool]:
        """
        Insert an object into the ArangoDB

        Parameters
        ----------
        doc : BaseCollectionDocument
            Object to inserted into the ArangoDB

        Returns
        -------
        Tuple[Optional[BaseCollectionDocument], bool]
            Updated object with returned metadata from ArangoDB and `True` if the operation was successful,
            old object and `False` otherwise
        """

        if doc is None:
            return None, False

        successful = False
        try:
            metadata = cls._collection.insert(doc.to_graph())
            doc._update_metadata(metadata)
            successful = True
        except DocumentInsertError as e:
            # Failed to insert the document
            logger.exception(f"{cls.__name__} : {e}")
        except Exception as e:
            logger.exception(f"{cls.__name__} : {e}")
        return doc, successful

    @classmethod
    def update(
        cls,
        old_doc: "BaseCollectionDocument",
        doc: "BaseCollectionDocument",
    ) -> Tuple[Optional["BaseCollectionDocument"], bool]:
        """
        Update an object in the database

        Parameters
        ----------
        old_doc : BaseCollectionDocument
            Document that is already in the database
        doc: BaseCollectionDocument
            Document used for updating the object in the database

        """
        if not isinstance(doc, BaseCollectionDocument):
            raise Exception(
                f"{doc.__class__.__name__} is not an instance of {BaseCollectionDocument.__class__.__name__} class"
            )

        if old_doc is None or doc is None:
            return None, False

        successful = False
        try:
            metadata = cls._collection.update(
                doc._update_metadata_from_old_document(old_doc)._update_non_updatable_fields(old_doc).to_graph()
            )
            doc._update_metadata(metadata)
            successful = True
        except DocumentUpdateError as e:
            # Failed to update document.
            logger.exception(f"{cls.__name__} : {e}")
        except DocumentRevisionError as e:
            # The expected and actual document revisions mismatched.
            logger.exception(f"{cls.__name__} : {e}")
        except Exception as e:
            logger.exception(f"{cls.__name__} : {e}")
        return doc, successful

    def _update_metadata(
        self,
        metadata: Dict[str, str],
    ) -> None:
        """
        Update a document's metadata from the `metadata` parameter

        Parameters
        ----------
        metadata : Dict[str, str]
            Metadata returned from the database query

        """
        for k, v in self._from_graph_db_mapping.items():
            setattr(self, v, metadata.get(k, None))

    def _update_metadata_from_old_document(
        self,
        old_doc: "BaseCollectionDocument",
    ) -> "BaseCollectionDocument":
        """
        Update the metadata of this document from an old document metadata

        Parameters
        ----------
        old_doc : The document to get the metadata from

        Returns
        -------
        BaseCollectionDocument
            Updated document
        """
        for field_name in self._to_graph_db_mapping.keys():
            setattr(self, field_name, getattr(old_doc, field_name, None))

        return self

    def _update_non_updatable_fields(
        self,
        old_doc: "BaseCollectionDocument",
    ) -> "BaseCollectionDocument":
        """
        Update the non-updatable field values of a document from an old document

        Parameters
        ----------
        old_doc : BaseCollectionDocument
            Document to update the fields from

        Returns
        -------
        BaseCollectionDocument
            Updated document

        """
        for field_name in self._base_do_not_update_fields:
            setattr(self, field_name, getattr(old_doc, field_name, None))

        if self._extra_do_not_update_fields is not None:
            for field_name in self._extra_do_not_update_fields:
                setattr(self, field_name, getattr(old_doc, field_name, None))

        return self

    @classmethod
    def find_by_key(cls, key: str) -> Optional["BaseCollectionDocument"]:
        """
        Find a document in a collection by its `key`

        Parameters
        ----------
        key : str
            Key of the document in the collection

        Returns
        -------
        Optional[BaseCollectionDocument]
            Document matching the specified key if it exists in the collection, otherwise return `None`

        """
        if key is None:
            return None

        cursor = cls._collection.find({"_key": key})
        if cursor is not None and len(cursor):
            return cls.from_graph(cursor.pop())
        else:
            return None
