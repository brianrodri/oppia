#!/usr/bin/env python
#
# Copyright 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

"""
In-memory persistent stub for the Python datastore API. Gets, queries,
and searches are implemented as in-memory scans over all entities.

Stores entities across sessions as pickled proto bufs in a single file. On
startup, all entities are read from the file and loaded into memory. On
every Put(), the file is wiped and all entities are written from scratch.
Clients can also manually Read() and Write() the file themselves.

Transactions are serialized through __tx_lock. Each transaction acquires it
when it begins and releases it when it commits or rolls back. This is
important, since there are other member variables like __tx_snapshot that are
per-transaction, so they should only be used by one tx at a time.
"""

import functools

from google.cloud.ndb import _datastore_query
from google.cloud.ndb import exceptions
from google.cloud.ndb import query as query_module
from google.cloud.ndb import model
import six

_DICT_OF_MODELS = {}


def _validate_key(value, entity=None):
    """Validate a key.

    Args:
        value (.Key): The key to be validated.
        entity (Optional[Model]): The entity that the key is being validated
            for.

    Returns:
        .Key: The passed in ``value``.

    Raises:
        .BadValueError: If ``value`` is not a :class:`.Key`.
        KindError: If ``entity`` is specified, but the kind of the entity
            doesn't match the kind of ``value``.
    """
    if not isinstance(value, Key):
        raise exceptions.BadValueError("Expected Key, got {!r}".format(value))

    if entity and type(entity) != Model:
        if value.kind() != entity._get_kind():
            raise model.KindError(
                "Expected Key kind to be {}; received "
                "{}".format(entity._get_kind(), value.kind())
            )

    return value


class Key:

    def __new__(cls, model_class, id):
        instance = super().__new__(cls)
        if isinstance(model_class, str):
            instance._kind = model_class
        else:
            instance._kind = model_class.__name__
        instance._id = id
        return instance

    def id(self):
        return self._id

    def kind(self):
        return self._kind

    def __eq__(self, another):
        return (
            self.kind() == another.kind() and self.id() == another.id())

    def __hash__(self):
        return hash(self.id())

    def __repr__(self):
        return 'Key(%s, %s)' % (self._kind, self._id)

    def get_async(self):
        return _DICT_OF_MODELS.get(self)

    def delete_async(self):
        del _DICT_OF_MODELS[self]



class ModelKey(model.ModelKey):
    """Special property to store a special "key" for a :class:`Model`.

    This is intended to be used as a pseudo-:class:`Property` on each
    :class:`Model` subclass. It is **not** intended for other usage in
    application code.

    It allows key-only queries to be done for a given kind.

    .. automethod:: _validate
    """

    def _validate(self, value):
        """Validate a ``value`` before setting it.

        Args:
            value (.Key): The value to check.

        Returns:
            .Key: The passed-in ``value``.
        """
        return _validate_key(value)

    @staticmethod
    def _set_value(entity, value):
        """Set the entity key on an entity.

        Args:
            entity (Model): An entity to set the entity key on.
            value (.Key): The key to be set on the entity.
        """
        if value is not None:
            value = _validate_key(value, entity=entity)
            value = entity._validate_key(value)

        entity._entity_key = value


class Model(model.Model):

    _key = ModelKey()
    key = _key

    def __init__(self, **kwargs):
        id_ = self._get_arg(kwargs, "id")

        if not id_ is None:
            self._key = Key(self._get_kind(), id_)

        self._values = {}
        self._set_attributes(kwargs)

    @classmethod
    def get_by_id(cls, model_id):
        return Key(cls._get_kind(), model_id).get_async()

    @classmethod
    def get_multi(cls, keys):
        return [key.get_async() for key in keys]

    def put_async(self):
        """We use this method because the multi library methods call this
        instead of put.
        """
        self._pre_put_hook()
        _DICT_OF_MODELS[self.key] = self
        self._post_put_hook(None)
        return self.key

    def put(self):
        return self.put_async()

    @classmethod
    def query(cls, *filters, **kwargs):
        """Generate a query for this class.

        Args:
            *filters (query.FilterNode): Filters to apply to this query.
            distinct (Optional[bool]): Setting this to :data:`True` is
                shorthand for setting `distinct_on` to `projection`.
            ancestor (key.Key): Entities returned will be descendants of
                `ancestor`.
            order_by (list[Union[str, google.cloud.ndb.model.Property]]):
                The model properties used to order query results.
            orders (list[Union[str, google.cloud.ndb.model.Property]]):
                Deprecated. Synonym for `order_by`.
            project (str): The project to perform the query in. Also known as
                the app, in Google App Engine. If not passed, uses the
                client's value.
            app (str): Deprecated. Synonym for `project`.
            namespace (str): The namespace to which to restrict results.
                If not passed, uses the client's value.
            projection (list[str]): The fields to return as part of the
                query results.
            distinct_on (list[str]): The field names used to group query
                results.
            group_by (list[str]): Deprecated. Synonym for distinct_on.
            default_options (QueryOptions): QueryOptions object.
        """
        query = Query(
            kind=cls._get_kind(),
            ancestor=kwargs.get("ancestor"),
            order_by=kwargs.get("order_by"),
            orders=kwargs.get("orders"),
            project=kwargs.get("project"),
            app=kwargs.get("app"),
            namespace=kwargs.get("namespace"),
            projection=kwargs.get("projection"),
            distinct_on=kwargs.get("distinct_on"),
            group_by=kwargs.get("group_by"),
            default_options=kwargs.get("default_options"),
        )
        query = query.filter(*cls._default_filters())
        query = query.filter(*filters)
        return query


def _to_property_names(properties):
    fixed = []
    for prop in properties:
        if isinstance(prop, six.string_types):
            fixed.append(prop)
        elif isinstance(prop, model.Property):
            fixed.append(prop._name)
        else:
            raise TypeError(
                "Unexpected property {}; " "should be string or Property".format(prop)
            )
    return fixed


def _check_properties(kind, fixed, **kwargs):
    modelclass = Model._kind_map.get(kind)
    if modelclass is not None:
        modelclass._check_properties(fixed, **kwargs)


def _query_options(wrapped):
    """A decorator for functions with query arguments for arguments.

    Many methods of :class:`Query` all take more or less the same arguments
    from which they need to create a :class:`QueryOptions` instance following
    the same somewhat complicated rules.

    This decorator wraps these methods with a function that does this
    processing for them and passes in a :class:`QueryOptions` instance using
    the ``_options`` argument to those functions, bypassing all of the
    other arguments.
    """
    # If there are any positional arguments, get their names.
    # inspect.signature is not available in Python 2.7, so we use the
    # arguments obtained with inspect.getarspec, which come from the
    # positional decorator used with all query_options decorated methods.
    arg_names = getattr(wrapped, "_positional_names", [])
    positional = [arg for arg in arg_names if arg != "self"]

    # Provide dummy values for positional args to avoid TypeError
    dummy_args = [None for _ in positional]

    @functools.wraps(wrapped)
    def wrapper(self, *args, **kwargs):
        # Maybe we already did this (in the case of X calling X_async)
        if "_options" in kwargs:
            return wrapped(self, *dummy_args, _options=kwargs["_options"])

        # Transfer any positional args to keyword args, so they're all in the
        # same structure.
        for name, value in zip(positional, args):
            if name in kwargs:
                raise TypeError(
                    "{}() got multiple values for argument '{}'".format(
                        wrapped.__name__, name
                    )
                )
            kwargs[name] = value

        options = kwargs.pop("options", None)

        projection = kwargs.get("projection")
        if projection:
            projection = _to_property_names(projection)
            _check_properties(self.kind, projection)
            kwargs["projection"] = projection

        if kwargs.get("keys_only"):
            if kwargs.get("projection"):
                raise TypeError("Cannot specify 'projection' with 'keys_only=True'")
            kwargs["projection"] = ["__key__"]
            del kwargs["keys_only"]

        if kwargs.get("transaction"):
            kwargs.pop(
                "read_consistency", kwargs.pop("read_policy", None)
            )

        # The 'page_size' arg for 'fetch_page' can just be translated to
        # 'limit'
        page_size = kwargs.pop("page_size", None)
        if page_size:
            kwargs["limit"] = page_size

        # Get arguments for QueryOptions attributes
        query_arguments = {
            name: self._option(name, kwargs.pop(name, None), options)
            for name in query_module.QueryOptions.slots()
        }

        # Any left over kwargs don't actually correspond to slots in
        # QueryOptions, but should be left to the QueryOptions constructor to
        # sort out. Some might be synonyms or shorthand for other options.
        query_arguments.update(kwargs)

        query_options = query_module.QueryOptions(**query_arguments)

        return wrapped(self, *dummy_args, _options=query_options)

    return wrapper


class Query(query_module.Query):

    @_query_options
    def get(self, **kwargs):
        options = kwargs["_options"].copy(limit=1)
        print(options)
        return None

    @_query_options
    def iter(self, **kwargs):
        return None


def query_everything():
    return Query()


def get_multi(keys):
    return [key.get_async() for key in keys]


def put_multi(entities):
    return [entity.put_async() for entity in entities]


def delete_multi(keys):
    return [key.delete_async() for key in keys]