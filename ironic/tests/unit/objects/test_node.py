# coding=utf-8
#
#
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

import datetime
import json

import mock
from oslo_utils import uuidutils
from testtools import matchers

from ironic.common import context
from ironic.common import exception
from ironic import objects
from ironic.tests.unit.db import base as db_base
from ironic.tests.unit.db import utils as db_utils
from ironic.tests.unit.objects import utils as obj_utils


class TestNodeObject(db_base.DbTestCase, obj_utils.SchemasTestMixIn):

    def setUp(self):
        super(TestNodeObject, self).setUp()
        self.ctxt = context.get_admin_context()
        self.fake_node = db_utils.get_test_node()
        self.node = obj_utils.get_test_node(self.ctxt, **self.fake_node)

    def test_as_dict_insecure(self):
        self.node.driver_info['ipmi_password'] = 'fake'
        self.node.instance_info['configdrive'] = 'data'
        d = self.node.as_dict()
        self.assertEqual('fake', d['driver_info']['ipmi_password'])
        self.assertEqual('data', d['instance_info']['configdrive'])
        # Ensure the node can be serialised.
        json.dumps(d)

    def test_as_dict_secure(self):
        self.node.driver_info['ipmi_password'] = 'fake'
        self.node.instance_info['configdrive'] = 'data'
        d = self.node.as_dict(secure=True)
        self.assertEqual('******', d['driver_info']['ipmi_password'])
        self.assertEqual('******', d['instance_info']['configdrive'])
        # Ensure the node can be serialised.
        json.dumps(d)

    def test_get_by_id(self):
        node_id = self.fake_node['id']
        with mock.patch.object(self.dbapi, 'get_node_by_id',
                               autospec=True) as mock_get_node:
            mock_get_node.return_value = self.fake_node

            node = objects.Node.get(self.context, node_id)

            mock_get_node.assert_called_once_with(node_id)
            self.assertEqual(self.context, node._context)

    def test_get_by_uuid(self):
        uuid = self.fake_node['uuid']
        with mock.patch.object(self.dbapi, 'get_node_by_uuid',
                               autospec=True) as mock_get_node:
            mock_get_node.return_value = self.fake_node

            node = objects.Node.get(self.context, uuid)

            mock_get_node.assert_called_once_with(uuid)
            self.assertEqual(self.context, node._context)

    def test_get_bad_id_and_uuid(self):
        self.assertRaises(exception.InvalidIdentity,
                          objects.Node.get, self.context, 'not-a-uuid')

    def test_get_by_name(self):
        node_name = 'test'
        fake_node = db_utils.get_test_node(name=node_name)
        with mock.patch.object(self.dbapi, 'get_node_by_name',
                               autospec=True) as mock_get_node:
            mock_get_node.return_value = fake_node

            node = objects.Node.get_by_name(self.context, node_name)

            mock_get_node.assert_called_once_with(node_name)
            self.assertEqual(self.context, node._context)

    def test_get_by_name_node_not_found(self):
        with mock.patch.object(self.dbapi, 'get_node_by_name',
                               autospec=True) as mock_get_node:
            node_name = 'non-existent'
            mock_get_node.side_effect = exception.NodeNotFound(node=node_name)
            self.assertRaises(exception.NodeNotFound,
                              objects.Node.get_by_name, self.context,
                              node_name)

    def test_get_by_instance_uuid(self):
        uuid = self.fake_node['instance_uuid']
        with mock.patch.object(self.dbapi, 'get_node_by_instance',
                               autospec=True) as mock_get_node:
            mock_get_node.return_value = self.fake_node

            node = objects.Node.get_by_instance_uuid(self.context, uuid)

            mock_get_node.assert_called_once_with(uuid)
            self.assertEqual(self.context, node._context)

    def test_get_by_instance_not_found(self):
        with mock.patch.object(self.dbapi, 'get_node_by_instance',
                               autospec=True) as mock_get_node:
            instance = 'non-existent'
            mock_get_node.side_effect = \
                exception.InstanceNotFound(instance=instance)
            self.assertRaises(exception.InstanceNotFound,
                              objects.Node.get_by_instance_uuid, self.context,
                              instance)

    def test_get_by_port_addresses(self):
        with mock.patch.object(self.dbapi, 'get_node_by_port_addresses',
                               autospec=True) as mock_get_node:
            mock_get_node.return_value = self.fake_node

            node = objects.Node.get_by_port_addresses(self.context,
                                                      ['aa:bb:cc:dd:ee:ff'])

            mock_get_node.assert_called_once_with(['aa:bb:cc:dd:ee:ff'])
            self.assertEqual(self.context, node._context)

    def test_save(self):
        uuid = self.fake_node['uuid']
        test_time = datetime.datetime(2000, 1, 1, 0, 0)
        with mock.patch.object(self.dbapi, 'get_node_by_uuid',
                               autospec=True) as mock_get_node:
            mock_get_node.return_value = self.fake_node
            with mock.patch.object(self.dbapi, 'update_node',
                                   autospec=True) as mock_update_node:
                mock_update_node.return_value = db_utils.get_test_node(
                    properties={"fake": "property"}, driver='fake-driver',
                    driver_internal_info={}, updated_at=test_time)
                n = objects.Node.get(self.context, uuid)
                self.assertEqual({"private_state": "secret value"},
                                 n.driver_internal_info)
                n.properties = {"fake": "property"}
                n.driver = "fake-driver"
                n.save()

                mock_get_node.assert_called_once_with(uuid)
                mock_update_node.assert_called_once_with(
                    uuid, {'properties': {"fake": "property"},
                           'driver': 'fake-driver',
                           'driver_internal_info': {},
                           'version': objects.Node.VERSION})
                self.assertEqual(self.context, n._context)
                res_updated_at = (n.updated_at).replace(tzinfo=None)
                self.assertEqual(test_time, res_updated_at)
                self.assertEqual({}, n.driver_internal_info)

    def test_save_updated_at_field(self):
        uuid = self.fake_node['uuid']
        extra = {"test": 123}
        test_time = datetime.datetime(2000, 1, 1, 0, 0)
        with mock.patch.object(self.dbapi, 'get_node_by_uuid',
                               autospec=True) as mock_get_node:
            mock_get_node.return_value = self.fake_node
            with mock.patch.object(self.dbapi, 'update_node',
                                   autospec=True) as mock_update_node:
                mock_update_node.return_value = (
                    db_utils.get_test_node(extra=extra, updated_at=test_time))
                n = objects.Node.get(self.context, uuid)
                self.assertEqual({"private_state": "secret value"},
                                 n.driver_internal_info)
                n.properties = {"fake": "property"}
                n.extra = extra
                n.driver = "fake-driver"
                n.driver_internal_info = {}
                n.save()

                mock_get_node.assert_called_once_with(uuid)
                mock_update_node.assert_called_once_with(
                    uuid, {'properties': {"fake": "property"},
                           'driver': 'fake-driver',
                           'driver_internal_info': {},
                           'extra': {'test': 123},
                           'version': objects.Node.VERSION})
                self.assertEqual(self.context, n._context)
                res_updated_at = n.updated_at.replace(tzinfo=None)
                self.assertEqual(test_time, res_updated_at)

    def test_save_with_traits(self):
        uuid = self.fake_node['uuid']
        with mock.patch.object(self.dbapi, 'get_node_by_uuid',
                               autospec=True) as mock_get_node:
            mock_get_node.return_value = self.fake_node
            with mock.patch.object(self.dbapi, 'update_node',
                                   autospec=True) as mock_update_node:
                n = objects.Node.get(self.context, uuid)
                trait = objects.Trait(self.context, node_id=n.id,
                                      trait='CUSTOM_1')
                n.traits = objects.TraitList(self.context, objects=[trait])
                self.assertRaises(exception.BadRequest, n.save)
                self.assertFalse(mock_update_node.called)

    def test_refresh(self):
        uuid = self.fake_node['uuid']
        returns = [dict(self.fake_node, properties={"fake": "first"}),
                   dict(self.fake_node, properties={"fake": "second"})]
        expected = [mock.call(uuid), mock.call(uuid)]
        with mock.patch.object(self.dbapi, 'get_node_by_uuid',
                               side_effect=returns,
                               autospec=True) as mock_get_node:
            n = objects.Node.get(self.context, uuid)
            self.assertEqual({"fake": "first"}, n.properties)
            n.refresh()
            self.assertEqual({"fake": "second"}, n.properties)
            self.assertEqual(expected, mock_get_node.call_args_list)
            self.assertEqual(self.context, n._context)

    def test_save_after_refresh(self):
        # Ensure that it's possible to do object.save() after object.refresh()
        db_node = db_utils.create_test_node()
        n = objects.Node.get_by_uuid(self.context, db_node.uuid)
        n_copy = objects.Node.get_by_uuid(self.context, db_node.uuid)
        n.name = 'b240'
        n.save()
        n_copy.refresh()
        n_copy.name = 'aaff'
        # Ensure this passes and an exception is not generated
        n_copy.save()

    def test_list(self):
        with mock.patch.object(self.dbapi, 'get_node_list',
                               autospec=True) as mock_get_list:
            mock_get_list.return_value = [self.fake_node]
            nodes = objects.Node.list(self.context)
            self.assertThat(nodes, matchers.HasLength(1))
            self.assertIsInstance(nodes[0], objects.Node)
            self.assertEqual(self.context, nodes[0]._context)

    def test_reserve(self):
        with mock.patch.object(self.dbapi, 'reserve_node',
                               autospec=True) as mock_reserve:
            mock_reserve.return_value = self.fake_node
            node_id = self.fake_node['id']
            fake_tag = 'fake-tag'
            node = objects.Node.reserve(self.context, fake_tag, node_id)
            self.assertIsInstance(node, objects.Node)
            mock_reserve.assert_called_once_with(fake_tag, node_id)
            self.assertEqual(self.context, node._context)

    def test_reserve_node_not_found(self):
        with mock.patch.object(self.dbapi, 'reserve_node',
                               autospec=True) as mock_reserve:
            node_id = 'non-existent'
            mock_reserve.side_effect = exception.NodeNotFound(node=node_id)
            self.assertRaises(exception.NodeNotFound,
                              objects.Node.reserve, self.context, 'fake-tag',
                              node_id)

    def test_release(self):
        with mock.patch.object(self.dbapi, 'release_node',
                               autospec=True) as mock_release:
            node_id = self.fake_node['id']
            fake_tag = 'fake-tag'
            objects.Node.release(self.context, fake_tag, node_id)
            mock_release.assert_called_once_with(fake_tag, node_id)

    def test_release_node_not_found(self):
        with mock.patch.object(self.dbapi, 'release_node',
                               autospec=True) as mock_release:
            node_id = 'non-existent'
            mock_release.side_effect = exception.NodeNotFound(node=node_id)
            self.assertRaises(exception.NodeNotFound,
                              objects.Node.release, self.context,
                              'fake-tag', node_id)

    def test_touch_provisioning(self):
        with mock.patch.object(self.dbapi, 'get_node_by_uuid',
                               autospec=True) as mock_get_node:
            mock_get_node.return_value = self.fake_node
            with mock.patch.object(self.dbapi, 'touch_node_provisioning',
                                   autospec=True) as mock_touch:
                node = objects.Node.get(self.context, self.fake_node['uuid'])
                node.touch_provisioning()
                mock_touch.assert_called_once_with(node.id)

    def test_create(self):
        node = obj_utils.get_test_node(self.ctxt, **self.fake_node)
        with mock.patch.object(self.dbapi, 'create_node',
                               autospec=True) as mock_create_node:
            mock_create_node.return_value = db_utils.get_test_node()

            node.create()

            args, _kwargs = mock_create_node.call_args
            self.assertEqual(objects.Node.VERSION, args[0]['version'])
            self.assertEqual(1, mock_create_node.call_count)

    def test_create_with_invalid_properties(self):
        node = obj_utils.get_test_node(self.ctxt, **self.fake_node)
        node.properties = {"local_gb": "5G"}
        self.assertRaises(exception.InvalidParameterValue, node.create)

    def test_create_with_traits(self):
        node = obj_utils.get_test_node(self.ctxt, **self.fake_node)
        trait = objects.Trait(self.context, node_id=node.id, trait='CUSTOM_1')
        node.traits = objects.TraitList(self.context, objects=[trait])
        self.assertRaises(exception.BadRequest, node.create)

    def test_update_with_invalid_properties(self):
        uuid = self.fake_node['uuid']
        with mock.patch.object(self.dbapi, 'get_node_by_uuid',
                               autospec=True) as mock_get_node:
            mock_get_node.return_value = self.fake_node
            node = objects.Node.get(self.context, uuid)
            node.properties = {"local_gb": "5G", "memory_mb": "5",
                               'cpus': '-1', 'cpu_arch': 'x86_64'}
            self.assertRaisesRegex(exception.InvalidParameterValue,
                                   ".*local_gb=5G, cpus=-1$", node.save)
            mock_get_node.assert_called_once_with(uuid)

    def test__validate_property_values_success(self):
        uuid = self.fake_node['uuid']
        with mock.patch.object(self.dbapi, 'get_node_by_uuid',
                               autospec=True) as mock_get_node:
            mock_get_node.return_value = self.fake_node
            node = objects.Node.get(self.context, uuid)
            values = self.fake_node
            expect = {
                'cpu_arch': 'x86_64',
                "cpus": '8',
                "local_gb": '10',
                "memory_mb": '4096',
            }
            node._validate_property_values(values['properties'])
            self.assertEqual(expect, values['properties'])

    def test_payload_schemas(self):
        self._check_payload_schemas(objects.node, objects.Node.fields)


class TestConvertToVersion(db_base.DbTestCase):

    def setUp(self):
        super(TestConvertToVersion, self).setUp()
        self.ctxt = context.get_admin_context()
        self.fake_node = db_utils.get_test_node(driver='fake-hardware')

    def test_rescue_supported_missing(self):
        # rescue_interface not set, should be set to default.
        node = obj_utils.get_test_node(self.ctxt, **self.fake_node)
        delattr(node, 'rescue_interface')
        node.obj_reset_changes()

        node._convert_to_version("1.22")

        self.assertIsNone(node.rescue_interface)
        self.assertEqual({'rescue_interface': None},
                         node.obj_get_changes())

    def test_rescue_supported_set(self):
        # rescue_interface set, no change required.
        node = obj_utils.get_test_node(self.ctxt, **self.fake_node)

        node.rescue_interface = 'fake'
        node.obj_reset_changes()
        node._convert_to_version("1.22")
        self.assertEqual('fake', node.rescue_interface)
        self.assertEqual({}, node.obj_get_changes())

    def test_rescue_unsupported_missing(self):
        # rescue_interface not set, no change required.
        node = obj_utils.get_test_node(self.ctxt, **self.fake_node)

        delattr(node, 'rescue_interface')
        node.obj_reset_changes()
        node._convert_to_version("1.21")
        self.assertNotIn('rescue_interface', node)
        self.assertEqual({}, node.obj_get_changes())

    def test_rescue_unsupported_set_remove(self):
        # rescue_interface set, should be removed.
        node = obj_utils.get_test_node(self.ctxt, **self.fake_node)

        node.rescue_interface = 'fake'
        node.obj_reset_changes()
        node._convert_to_version("1.21")
        self.assertNotIn('rescue_interface', node)
        self.assertEqual({}, node.obj_get_changes())

    def test_rescue_unsupported_set_no_remove_non_default(self):
        # rescue_interface set, should be set to default.
        node = obj_utils.get_test_node(self.ctxt, **self.fake_node)

        node.rescue_interface = 'fake'
        node.obj_reset_changes()
        node._convert_to_version("1.21", False)
        self.assertIsNone(node.rescue_interface)
        self.assertEqual({'rescue_interface': None, 'traits': None},
                         node.obj_get_changes())

    def test_rescue_unsupported_set_no_remove_default(self):
        # rescue_interface set, no change required.
        node = obj_utils.get_test_node(self.ctxt, **self.fake_node)

        node.rescue_interface = None
        node.traits = None
        node.obj_reset_changes()
        node._convert_to_version("1.21", False)
        self.assertIsNone(node.rescue_interface)
        self.assertEqual({}, node.obj_get_changes())

    def test_traits_supported_missing(self):
        # traits not set, should be set to default.
        node = obj_utils.get_test_node(self.ctxt, **self.fake_node)
        delattr(node, 'traits')
        node.obj_reset_changes()

        node._convert_to_version("1.23")

        self.assertIsNone(node.traits)
        self.assertEqual({'traits': None},
                         node.obj_get_changes())

    def test_traits_supported_set(self):
        # traits set, no change required.
        node = obj_utils.get_test_node(self.ctxt, **self.fake_node)
        traits = objects.TraitList(
            objects=[objects.Trait('CUSTOM_TRAIT')])
        traits.obj_reset_changes()
        node.traits = traits
        node.obj_reset_changes()

        node._convert_to_version("1.23")

        self.assertEqual(traits, node.traits)
        self.assertEqual({}, node.obj_get_changes())

    def test_traits_unsupported_missing_remove(self):
        # traits not set, no change required.
        node = obj_utils.get_test_node(self.ctxt, **self.fake_node)
        delattr(node, 'traits')
        node.obj_reset_changes()

        node._convert_to_version("1.22")

        self.assertNotIn('traits', node)
        self.assertEqual({}, node.obj_get_changes())

    def test_traits_unsupported_missing(self):
        # traits not set, should be set to default.
        node = obj_utils.get_test_node(self.ctxt, **self.fake_node)
        delattr(node, 'traits')
        node.obj_reset_changes()

        node._convert_to_version("1.22", False)

        self.assertNotIn('traits', node)
        self.assertEqual({}, node.obj_get_changes())

    def test_trait_unsupported_set_no_remove_non_default(self):
        # traits set, should be set to default.
        node = obj_utils.get_test_node(self.ctxt, **self.fake_node)
        node.traits = objects.TraitList(self.ctxt)
        node.traits.obj_reset_changes()
        node.obj_reset_changes()

        node._convert_to_version("1.22", False)

        self.assertIsNone(node.traits)
        self.assertEqual({'traits': None},
                         node.obj_get_changes())

    def test_trait_unsupported_set_no_remove_default(self):
        # traits set, no change required.
        node = obj_utils.get_test_node(self.ctxt, **self.fake_node)
        node.traits = None
        node.obj_reset_changes()

        node._convert_to_version("1.22", False)

        self.assertIsNone(node.traits)
        self.assertEqual({}, node.obj_get_changes())


class TestNodePayloads(db_base.DbTestCase):

    def setUp(self):
        super(TestNodePayloads, self).setUp()
        self.ctxt = context.get_admin_context()
        self.fake_node = db_utils.get_test_node()
        self.node = obj_utils.get_test_node(self.ctxt, **self.fake_node)

    def _test_node_payload(self, payload):
        self.assertEqual(self.node.clean_step, payload.clean_step)
        self.assertEqual(self.node.console_enabled,
                         payload.console_enabled)
        self.assertEqual(self.node.created_at, payload.created_at)
        self.assertEqual(self.node.driver, payload.driver)
        self.assertEqual(self.node.extra, payload.extra)
        self.assertEqual(self.node.inspection_finished_at,
                         payload.inspection_finished_at)
        self.assertEqual(self.node.inspection_started_at,
                         payload.inspection_started_at)
        self.assertEqual(self.node.instance_uuid, payload.instance_uuid)
        self.assertEqual(self.node.last_error, payload.last_error)
        self.assertEqual(self.node.maintenance, payload.maintenance)
        self.assertEqual(self.node.maintenance_reason,
                         payload.maintenance_reason)
        self.assertEqual(self.node.boot_interface, payload.boot_interface)
        self.assertEqual(self.node.console_interface,
                         payload.console_interface)
        self.assertEqual(self.node.deploy_interface, payload.deploy_interface)
        self.assertEqual(self.node.inspect_interface,
                         payload.inspect_interface)
        self.assertEqual(self.node.management_interface,
                         payload.management_interface)
        self.assertEqual(self.node.network_interface,
                         payload.network_interface)
        self.assertEqual(self.node.power_interface, payload.power_interface)
        self.assertEqual(self.node.raid_interface, payload.raid_interface)
        self.assertEqual(self.node.storage_interface,
                         payload.storage_interface)
        self.assertEqual(self.node.vendor_interface,
                         payload.vendor_interface)
        self.assertEqual(self.node.name, payload.name)
        self.assertEqual(self.node.power_state, payload.power_state)
        self.assertEqual(self.node.properties, payload.properties)
        self.assertEqual(self.node.provision_state, payload.provision_state)
        self.assertEqual(self.node.provision_updated_at,
                         payload.provision_updated_at)
        self.assertEqual(self.node.resource_class, payload.resource_class)
        self.assertEqual(self.node.target_power_state,
                         payload.target_power_state)
        self.assertEqual(self.node.target_provision_state,
                         payload.target_provision_state)
        self.assertEqual(self.node.traits.get_trait_names(), payload.traits)
        self.assertEqual(self.node.updated_at, payload.updated_at)
        self.assertEqual(self.node.uuid, payload.uuid)

    def test_node_payload(self):
        payload = objects.NodePayload(self.node)
        self._test_node_payload(payload)

    def test_node_payload_no_traits(self):
        delattr(self.node, 'traits')
        payload = objects.NodePayload(self.node)
        self.assertEqual([], payload.traits)

    def test_node_payload_traits_is_none(self):
        self.node.traits = None
        payload = objects.NodePayload(self.node)
        self.assertEqual([], payload.traits)

    def test_node_set_power_state_payload(self):
        payload = objects.NodeSetPowerStatePayload(self.node, 'POWER_ON')
        self._test_node_payload(payload)
        self.assertEqual('POWER_ON', payload.to_power)

    def test_node_corrected_power_state_payload(self):
        payload = objects.NodeCorrectedPowerStatePayload(self.node, 'POWER_ON')
        self._test_node_payload(payload)
        self.assertEqual('POWER_ON', payload.from_power)

    def test_node_set_provision_state_payload(self):
        payload = objects.NodeSetProvisionStatePayload(self.node, 'AVAILABLE',
                                                       'DEPLOYING', 'DEPLOY')
        self._test_node_payload(payload)
        self.assertEqual(self.node.instance_info, payload.instance_info)
        self.assertEqual('DEPLOY', payload.event)
        self.assertEqual('AVAILABLE', payload.previous_provision_state)
        self.assertEqual('DEPLOYING', payload.previous_target_provision_state)

    def test_node_crud_payload(self):
        chassis_uuid = uuidutils.generate_uuid()
        payload = objects.NodeCRUDPayload(self.node, chassis_uuid)
        self._test_node_payload(payload)
        self.assertEqual(chassis_uuid, payload.chassis_uuid)
        self.assertEqual(self.node.instance_info, payload.instance_info)
        self.assertEqual(self.node.driver_info, payload.driver_info)
