import collections
from typing import Sequence, Optional, Union, List, Deque

from aioarango.api import Endpoint
from aioarango.enums import MethodType
from aioarango.errors import (
    DocumentReplaceError,
    DocumentRevisionMisMatchError,
    DocumentInsertError,
    DocumentIllegalError,
    DocumentNotFoundError,
    DocumentIllegalKeyError,
    DocumentUniqueConstraintError,
)
from aioarango.errors.base import ArangoServerError
from aioarango.models import Request, Response
from aioarango.typings import Json, Params, Result
from aioarango.utils.document_utils import ensure_key_in_body


class ReplaceMultipleDocuments:
    async def replace_multiple_documents(
        self: Endpoint,
        collection_name: str,
        id_prefix: str,
        documents: Sequence[Json],
        check_for_revisions_match: bool = True,
        return_new: bool = False,
        return_old: bool = False,
        wait_for_sync: Optional[bool] = None,
        silent: bool = False,
    ) -> Result[Union[bool, List[Union[Json, ArangoServerError]]]]:
        """
        Replaces multiple documents in the specified collection with the
        ones in the body, the replaced documents are specified by the **_key**
        attributes in the body documents.

        Notes
        -----
        - The value of the **_key** attribute as well as attributes used as sharding keys may not be changed.

        - If **ignoreRevs** is `false` and there is a **_rev** attribute in a
          document in the body and its value does not match the revision of
          the corresponding document in the database, the precondition is
          violated.

        - Cluster only: The replacing documents may contain
          values for the collection's pre-defined shard keys. Values for the shard keys
          are treated as hints to improve performance. Should the shard keys
          values be incorrect ArangoDB may answer with a not found error.

        - Optionally, the query parameter **wait_for_sync** can be used to force
          synchronization of the document replacement operation to disk even in case
          that the **wait_for_sync** flag had been disabled for the entire collection.
          Thus, the **wait_for_sync** query parameter can be used to force synchronization
          of just specific operations. To use this, set the **wait_for_sync** parameter
          to true. If the **wait_for_sync** parameter is not specified or set to
          `false`, then the collection's `default` **wait_for_sync** behavior is
          applied. The **wait_for_sync** query parameter cannot be used to disable
          synchronization for collections that have a `default` **wait_for_sync** value
          of `true`.

        - The body of the response contains a JSON array of the same length
          as the input array with the information about the identifier and the
          revision of the replaced documents. In each entry, the attribute
          **_id** contains the known document-id of each updated document,
          **_key** contains the key which uniquely identifies a document in a
          given collection, and the attribute **_rev** contains the new document
          revision. In case of an error or violated precondition, an error
          object with the attribute error set to `true` and the attribute
          **error_code** set to the error code is built.

        - If the query parameter **return_old** is `true`, then, for each
          generated document, the complete previous revision of the document
          is returned under the **old** attribute in the result.

        - If the query parameter **return_new** is `true`, then, for each
          generated document, the complete new document is returned under
          the **new** attribute in the result.

        - Should an error have occurred with some documents
          the additional HTTP header **X-Arango-Error-Codes** is set, which
          contains a map of the error codes that occurred together with their
          multiplicities, as in: `1205:10`, `1210:17` which means that in 10
          cases the error 1205 "illegal document handle" and in 17 cases the
          error 1210 "unique constraint violated" has happened.




        Parameters
        ----------
        collection_name : str
            Collection name
        id_prefix : str
            ID prefix for this document.
        documents : list of Json
            New documents to replace the old ones with. They must
            contain the "_id" or "_key" fields. Edge documents must also have
            "_from" and "_to" fields.
        check_for_revisions_match : bool, default : True
            If set to `True`, revisions of **documents** (if given) are compared against the revisions of target documents.
        return_new : bool, default : True
            Include body of the new document in the returned metadata. Ignored if parameter **silent** is set to `True`.
        return_old : bool, default : True
            Include body of the old document in the returned metadata. Ignored if parameter **silent** is set to `True`.
        wait_for_sync : bool, optional
            Block until operation is synchronized to disk.
        silent : bool, default : False
            If set to `True`, no document metadata is returned. This can be used to save resources.

        Returns
        -------
        Result
            List of document metadata (e.g. document keys, revisions) and any exceptions, or `True` if parameter **silent** was set to `True`.

        """
        params: Params = {
            "returnNew": return_new,
            "returnOld": return_old,
            "ignoreRevs": not check_for_revisions_match,
            "silent": silent,
        }
        if wait_for_sync is not None:
            params["waitForSync"] = wait_for_sync

        documents = [ensure_key_in_body(doc, id_prefix) for doc in documents]

        request = Request(
            method_type=MethodType.PUT,
            endpoint=f"/_api/document/{collection_name}",
            params=params,
            data=documents,
            write=collection_name,
        )

        def response_handler(
            response: Response,
        ) -> Union[bool, List[Union[Json, ArangoServerError]]]:
            if not response.is_success:
                raise DocumentReplaceError(response, request)

            if silent is True:
                return True

            results: Deque[Union[Json, ArangoServerError]] = collections.deque()
            for body in response.body:
                if "_id" in body:
                    if "_oldRev" in body:
                        body["_old_rev"] = body.pop("_oldRev")
                    results.append(body)
                else:
                    sub_resp = self.connection.prep_bulk_err_response(response, body)

                    error: ArangoServerError
                    if sub_resp.error_code == 600:  # document format is illegal (status_code 400)
                        # the body does not contain a valid JSON representation of one document.
                        error = DocumentIllegalError(sub_resp, request)
                    elif sub_resp.error_code == 1202:  # document not found
                        error = DocumentNotFoundError(sub_resp, request)
                    elif sub_resp.error_code == 1221:  # illegal document key
                        error = DocumentIllegalKeyError(sub_resp, request)
                    elif sub_resp.error_code == 1210:  # status_code 409
                        error = DocumentUniqueConstraintError(response, request)
                    elif sub_resp.error_code == 1200:
                        error = DocumentRevisionMisMatchError(sub_resp, request)
                    else:
                        # This must not happen
                        error = DocumentInsertError(sub_resp, request)

                    results.append(error)

            # status_code 201 and 202
            # 201 : if waitForSync was true and operations were processed.
            # 202 : if waitForSync was false and operations were processed.
            return list(results)

        return await self.execute(request, response_handler)
