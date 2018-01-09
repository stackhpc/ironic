#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from oslo_versionedobjects import base as object_base

from ironic.db import api as db_api
from ironic.objects import base
from ironic.objects import fields as object_fields

MAX_TAG_LENGTH = 60


@base.IronicObjectRegistry.register
class Trait(base.IronicObject):
    # Version 1.0: Initial version
    VERSION = '1.0'

    dbapi = db_api.get_instance()

    fields = {
        'node_id': object_fields.StringField(),
        'trait': object_fields.StringField(),
    }

    @object_base.remotable
    def create(self):
        db_trait = self.dbapi.add_node_trait(self.node_id, self.trait)
        self._from_db_object(self._context, self, db_trait)

    @object_base.remotable_classmethod
    def destroy(cls, context, node_id, trait):
        cls.dbapi.delete_node_trait(node_id, trait)

    @object_base.remotable_classmethod
    def exists(cls, context, node_id, trait):
        return cls.dbapi.node_trait_exists(node_id, trait)


@base.IronicObjectRegistry.register
class TraitList(object_base.ObjectListBase, base.IronicObject):
    # Version 1.0: Initial version
    VERSION = '1.0'

    dbapi = db_api.get_instance()

    fields = {
        'objects': object_fields.ListOfObjectsField('Trait'),
    }

    @object_base.remotable_classmethod
    def get_by_node_id(cls, context, node_id):
        db_traits = cls.dbapi.get_node_traits_by_node_id(node_id)
        return object_base.obj_make_list(context, cls(), Trait, db_traits)

    @object_base.remotable_classmethod
    def create(cls, context, node_id, traits):
        """Replaces all existing traits with the specified list."""
        db_traits = cls.dbapi.set_node_traits(node_id, traits)
        return object_base.obj_make_list(context, cls(), Trait, db_traits)

    @object_base.remotable_classmethod
    def destroy(cls, context, node_id):
        cls.dbapi.set_node_traits(node_id, [])
