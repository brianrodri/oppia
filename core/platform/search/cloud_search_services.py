# coding: utf-8
#
# Copyright 2014 The Oppia Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the 'License');
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an 'AS-IS' BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Provides search services."""

from __future__ import absolute_import  # pylint: disable=import-only-modules
from __future__ import unicode_literals  # pylint: disable=import-only-modules

import datetime
import numbers

import feconf
import python_utils

DEFAULT_NUM_RETRIES = 3


class SearchFailureError(Exception):
    """This error is raised when a search operation fails.
       The original_exception will point to what went wrong inside the gae sdk.
       Other platform implementations should have a similar way of revealing
       platform specific errors.
    """

    def __init__(self, original_exception=None):
        super(SearchFailureError, self).__init__(
            '%s: %s' % (type(original_exception), original_exception.message))
        self.original_exception = original_exception


def add_documents_to_index(documents, index, retries=DEFAULT_NUM_RETRIES):
    """Adds a document to an index.

    Args:
        documents: list(dict). Each document should be a dictionary.
            Every key in the document is a field name, and the corresponding
            value will be the field's value.
            If there is a key named 'id', its value will be used as the
            document's id.
            If there is a key named 'rank', its value will be used as
            the document's rank.
            By default, search results are returned ordered by descending rank.
            If there is a key named 'language_code', its value will be used as
            the document's language. Otherwise, constants.DEFAULT_LANGUAGE_CODE
            is used.
        index: str. The name of the index to insert the document into.
        retries: int. The number of times to retry inserting the documents.

    Returns:
        list(str). Returns a list of document ids of the documents that were
        added.

    Raises:
        SearchFailureError. Raised when the indexing fails. If it fails for any
            document, none will be inserted.
        ValueError. Raised when invalid values are given.
    """
    del documents, index, retries
    raise NotImplementedError


def _dict_to_search_document(d):
    """Returns and converts the document dict into objects.

    Args:
        d: dict. A dict containing field names as keys and
            corresponding field values as values.

    Returns:
        Document. The document containing fields.

    Raises:
        ValueError. The given document is not in the dict format.
    """
    del d
    raise NotImplementedError()


def _make_fields(key, value):
    """Returns the fields corresponding to the key value pair according to the
    type of value.

    Args:
        key: str. The name of the field.
        value: *. The field value.

    Returns:
        list(*). A list of fields.

    Raises:
        ValueError. The type of field value is not list, str, Number or
            datetime.
    """
    del key, value
    raise NotImplementedError()


def _validate_list(key, value):
    """Validates a list to be included as document fields. The key is just
    passed in to make better error messages.

    Args:
        key: str. A string that represents the descriptor of this
            particular list.
        value: list(*). The list to be validated. Each element of a valid list
            must be either a python_utils.BASESTRING, datetime.date,
            datetime.datetime, numbers.Number.
    """

    for ind, element in enumerate(value):
        if not isinstance(element, (
                python_utils.BASESTRING, datetime.date, datetime.datetime,
                numbers.Number)):
            raise ValueError(
                'All values of a multi-valued field must be numbers, strings, '
                'date or datetime instances, The %dth value for field %s has'
                ' type %s.' % (ind, key, type(element)))


def delete_documents_from_index(
        doc_ids, index, retries=DEFAULT_NUM_RETRIES):
    """Deletes documents from an index.

    Args:
        doc_ids: list(str). A list of document ids of documents to be deleted
            from the index.
        index: str. The name of the index to delete the document from.
        retries: int. The number of times to retry deleting the documents.

    Raises:
        SearchFailureError. Raised when the deletion fails. If it fails for any
            document, none will be deleted.
    """
    del doc_ids, index, retries
    raise NotImplementedError()


def clear_index(index_name):
    """Clears an index completely.

    WARNING: This does all the clearing in-request, and may therefore fail if
    there are too many entries in the index.

    Args:
        index_name: str. The name of the index to delete the document from.
    """
    del index_name
    raise NotImplementedError()


def search(
        query_string, index, cursor=None, limit=feconf.SEARCH_RESULTS_PAGE_SIZE,
        sort='', ids_only=False, retries=DEFAULT_NUM_RETRIES):
    """Searches for documents in an index.

    Args:
        query_string: str. The search query.
            The syntax used is described here:
            https://developers.google.com/appengine/docs/python/search/query_strings
        index: str. The name of the index to search.
        cursor: str. A cursor string, as returned by this function. Pass this in
            to get the next 'page' of results. Leave as None to start at the
            beginning.
        limit: int. The maximum number of documents to return.
        sort: str. A string indicating how to sort results. This should be a
            string of space separated values. Each value should start with a '+'
            or a '-' character indicating whether to sort in ascending or
            descending order respectively. This character should be followed by
            a field name to sort on.
        ids_only: bool. Whether to only return document ids.
        retries: int. The number of times to retry searching the index.

    Returns:
        2-tuple of (result_docs, result_cursor_str). Where:
            result_docs: list(dict). Represents search documents. If ids_only is
                True, this will be a list of strings, doc_ids.
            result_cursor_str: str. a cursor that you can pass back in to get
                the next page of results. This wil be a web safe string that you
                can use in urls. It will be None if there is no next page.
    """
    del query_string, index, cursor, limit, sort, ids_only, retries
    raise NotImplementedError()


def _string_to_sort_expressions(input_string):
    """Returns the sorted expression of the input string.

    Args:
        input_string: str. The input string to be sorted.

    Returns:
        list(SortExpression). A list of sorted expressions.

    Raises:
        ValueError. Fields in the sort expression do not start with '+' or '-'
            to indicate sort direction.
    """
    del input_string
    raise NotImplementedError()


def get_document_from_index(doc_id, index):
    """Returns a document with a give doc_id(s) from the index.

    Args:
        doc_id: str. A doc_id as a string.
        index: str. The name of an index.

    Returns:
        dict. The requested document as a dict.
    """
    del doc_id, index
    raise NotImplementedError()


def _search_document_to_dict(doc):
    """Converts and returns the search document into a dict format.

    Args:
        doc: Document. The document to be converted into dict format.

    Returns:
        dict(str, str). The document in dict format.
    """
    d = {'id': doc.doc_id, 'language_code': doc.language, 'rank': doc.rank}

    for field in doc.fields:
        d[field.name] = field.value

    return d
