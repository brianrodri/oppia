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

from google.cloud.ndb import exceptions
from google.cloud.ndb import model
from google.cloud.ndb import key as key_module

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
        print(self, '\n')
        return _DICT_OF_MODELS.get(self)



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


def put_multi(entities):
    return [entity.put_async() for entity in entities]


def get_multi(keys):
    return [key.get_async() for key in keys]