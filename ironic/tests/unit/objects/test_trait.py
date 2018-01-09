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

import mock

from ironic.common import context
from ironic import objects
from ironic.tests.unit.db import base as db_base
from ironic.tests.unit.db import utils as db_utils
from ironic.tests.unit.objects import utils as obj_utils


class TestTraitObject(db_base.DbTestCase, obj_utils.SchemasTestMixIn):

    def setUp(self):
        super(TestTraitObject, self).setUp()
        self.ctxt = context.get_admin_context()
        self.fake_trait = db_utils.get_test_node_trait()
        self.node_id = self.fake_trait['node_id']

    def test_get_by_id(self):
        with mock.patch.object(self.dbapi, 'get_node_traits_by_node_id',
                               autospec=True) as mock_get_traits:
            mock_get_traits.return_value = [self.fake_trait]

            traits = objects.TraitList.get_by_node_id(self.context,
                                                      self.node_id)

            mock_get_traits.assert_called_once_with(self.node_id)
            self.assertEqual(self.context, traits._context)
            self.assertEqual(1, len(traits))
            self.assertEqual(self.fake_trait['trait'], traits[0].trait)
            self.assertEqual(self.fake_trait['node_id'], traits[0].node_id)

    def test_create_list(self):
        traits = [self.fake_trait['trait']]

        with mock.patch.object(self.dbapi, 'set_node_traits',
                               autospec=True) as mock_set_traits:
            mock_set_traits.return_value = [self.fake_trait, self.fake_trait]

            result = objects.TraitList.create(self.context, self.node_id,
                                              traits)

            mock_set_traits.assert_called_once_with(self.node_id, traits)
            self.assertEqual(self.context, result._context)
            self.assertEqual(2, len(result))
            self.assertEqual(self.fake_trait['node_id'], result[0].node_id)

    def test_destroy_list(self):
        with mock.patch.object(self.dbapi, 'set_node_traits',
                               autospec=True) as mock_set_traits:
            objects.TraitList.destroy(self.context, self.node_id)

            mock_set_traits.assert_called_once_with(self.node_id, [])

    def test_create(self):
        trait = objects.Trait(context=self.context,
                              node_id=self.node_id, trait="fake")

        with mock.patch.object(self.dbapi, 'add_node_trait',
                               autospec=True) as mock_add_trait:
            mock_add_trait.return_value = self.fake_trait

            trait.create()

            mock_add_trait.assert_called_once_with(self.node_id, "fake")

            self.assertEqual(self.fake_trait['trait'], trait.trait)
            self.assertEqual(self.fake_trait['node_id'], trait.node_id)

    def test_destroy(self):
        with mock.patch.object(self.dbapi, 'delete_node_trait',
                               autospec=True) as mock_delete_trait:

            objects.Trait.destroy(self.context, self.node_id, "trait")

            mock_delete_trait.assert_called_once_with(self.node_id, "trait")

    def test_exists(self):
        with mock.patch.object(self.dbapi, 'node_trait_exists',
                               autospec=True) as mock_trait_exists:
            mock_trait_exists.return_value = True

            result = objects.Trait.exists(self.context, self.node_id, "trait")

            self.assertTrue(result)
            mock_trait_exists.assert_called_once_with(self.node_id, "trait")
