#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

"""
Test class for DRAC RAID interface
"""

from dracclient import constants
from dracclient import exceptions as drac_exceptions
import mock

from ironic.common import exception
from ironic.common import states
from ironic.conductor import task_manager
from ironic.conductor import utils as conductor_utils
from ironic.drivers.modules.drac import common as drac_common
from ironic.drivers.modules.drac import job as drac_job
from ironic.drivers.modules.drac import raid as drac_raid
from ironic.tests.unit.drivers.modules.drac import utils as test_utils
from ironic.tests.unit.objects import utils as obj_utils

INFO_DICT = test_utils.INFO_DICT


@mock.patch.object(drac_common, 'get_drac_client', spec_set=True,
                   autospec=True)
class DracQueryRaidConfigurationTestCase(test_utils.BaseDracTest):

    def setUp(self):
        super(DracQueryRaidConfigurationTestCase, self).setUp()
        self.node = obj_utils.create_test_node(self.context,
                                               driver='idrac',
                                               driver_info=INFO_DICT)

        raid_controller_dict = {
            'id': 'RAID.Integrated.1-1',
            'description': 'Integrated RAID Controller 1',
            'manufacturer': 'DELL',
            'model': 'PERC H710 Mini',
            'primary_status': 'ok',
            'firmware_version': '21.3.0-0009',
            'bus': '1',
            'supports_realtime': True}
        self.raid_controller = test_utils.make_raid_controller(
            raid_controller_dict)

        virtual_disk_dict = {
            'id': 'Disk.Virtual.0:RAID.Integrated.1-1',
            'name': 'disk 0',
            'description': 'Virtual Disk 0 on Integrated RAID Controller 1',
            'controller': 'RAID.Integrated.1-1',
            'raid_level': '1',
            'size_mb': 571776,
            'status': 'ok',
            'raid_status': 'online',
            'span_depth': 1,
            'span_length': 2,
            'pending_operations': None,
            'physical_disks': []}
        self.virtual_disk = test_utils.make_virtual_disk(virtual_disk_dict)

        physical_disk_dict = {
            'id': 'Disk.Bay.1:Enclosure.Internal.0-1:RAID.Integrated.1-1',
            'description': ('Disk 1 in Backplane 1 of '
                            'Integrated RAID Controller 1'),
            'controller': 'RAID.Integrated.1-1',
            'manufacturer': 'SEAGATE',
            'model': 'ST600MM0006',
            'media_type': 'hdd',
            'interface_type': 'sas',
            'size_mb': 571776,
            'free_size_mb': 571776,
            'serial_number': 'S0M3EY2Z',
            'firmware_version': 'LS0A',
            'status': 'ok',
            'raid_status': 'ready',
            'sas_address': '500056B37789ABE3',
            'device_protocol': None}
        self.physical_disk = test_utils.make_physical_disk(physical_disk_dict)

    def test_list_raid_controllers(self, mock_get_drac_client):
        mock_client = mock.Mock()
        mock_get_drac_client.return_value = mock_client
        mock_client.list_raid_controllers.return_value = [self.raid_controller]

        raid_controllers = drac_raid.list_raid_controllers(self.node)

        mock_client.list_raid_controllers.assert_called_once_with()
        self.assertEqual(self.raid_controller, raid_controllers[0])

    def test_list_raid_controllers_fail(self, mock_get_drac_client):
        mock_client = mock.Mock()
        mock_get_drac_client.return_value = mock_client
        exc = exception.DracOperationError('boom')
        mock_client.list_raid_controllers.side_effect = exc

        self.assertRaises(exception.DracOperationError,
                          drac_raid.list_raid_controllers, self.node)

    def test_list_virtual_disks(self, mock_get_drac_client):
        mock_client = mock.Mock()
        mock_get_drac_client.return_value = mock_client
        mock_client.list_virtual_disks.return_value = [self.virtual_disk]

        virtual_disks = drac_raid.list_virtual_disks(self.node)

        mock_client.list_virtual_disks.assert_called_once_with()
        self.assertEqual(self.virtual_disk, virtual_disks[0])

    def test_list_virtual_disks_fail(self, mock_get_drac_client):
        mock_client = mock.Mock()
        mock_get_drac_client.return_value = mock_client
        exc = exception.DracOperationError('boom')
        mock_client.list_virtual_disks.side_effect = exc

        self.assertRaises(exception.DracOperationError,
                          drac_raid.list_virtual_disks, self.node)

    def test_list_physical_disks(self, mock_get_drac_client):
        mock_client = mock.Mock()
        mock_get_drac_client.return_value = mock_client
        mock_client.list_physical_disks.return_value = [self.physical_disk]

        physical_disks = drac_raid.list_physical_disks(self.node)

        mock_client.list_physical_disks.assert_called_once_with()
        self.assertEqual(self.physical_disk, physical_disks[0])

    def test_list_physical_disks_fail(self, mock_get_drac_client):
        mock_client = mock.Mock()
        mock_get_drac_client.return_value = mock_client
        exc = exception.DracOperationError('boom')
        mock_client.list_physical_disks.side_effect = exc

        self.assertRaises(exception.DracOperationError,
                          drac_raid.list_physical_disks, self.node)


@mock.patch.object(drac_common, 'get_drac_client', spec_set=True,
                   autospec=True)
class DracManageVirtualDisksTestCase(test_utils.BaseDracTest):

    def setUp(self):
        super(DracManageVirtualDisksTestCase, self).setUp()
        self.node = obj_utils.create_test_node(self.context,
                                               driver='idrac',
                                               driver_info=INFO_DICT)

    @mock.patch.object(drac_job, 'validate_job_queue', spec_set=True,
                       autospec=True)
    def test_create_virtual_disk(self, mock_validate_job_queue,
                                 mock_get_drac_client):
        mock_client = mock.Mock()
        mock_get_drac_client.return_value = mock_client

        drac_raid.create_virtual_disk(
            self.node, 'controller', ['disk1', 'disk2'], '1+0', 43008)

        mock_validate_job_queue.assert_called_once_with(
            self.node, name_prefix='Config:RAID:controller')
        mock_client.create_virtual_disk.assert_called_once_with(
            'controller', ['disk1', 'disk2'], '1+0', 43008, None, None, None)

    @mock.patch.object(drac_job, 'validate_job_queue', spec_set=True,
                       autospec=True)
    def test_create_virtual_disk_with_optional_attrs(self,
                                                     mock_validate_job_queue,
                                                     mock_get_drac_client):
        mock_client = mock.Mock()
        mock_get_drac_client.return_value = mock_client

        drac_raid.create_virtual_disk(
            self.node, 'controller', ['disk1', 'disk2'], '1+0', 43008,
            disk_name='name', span_length=3, span_depth=2)

        mock_validate_job_queue.assert_called_once_with(
            self.node, name_prefix='Config:RAID:controller')
        mock_client.create_virtual_disk.assert_called_once_with(
            'controller', ['disk1', 'disk2'], '1+0', 43008, 'name', 3, 2)

    @mock.patch.object(drac_job, 'validate_job_queue', spec_set=True,
                       autospec=True)
    def test_create_virtual_disk_fail(self, mock_validate_job_queue,
                                      mock_get_drac_client):
        mock_client = mock.Mock()
        mock_get_drac_client.return_value = mock_client
        exc = drac_exceptions.BaseClientException('boom')
        mock_client.create_virtual_disk.side_effect = exc

        self.assertRaises(
            exception.DracOperationError, drac_raid.create_virtual_disk,
            self.node, 'controller', ['disk1', 'disk2'], '1+0', 42)

    @mock.patch.object(drac_job, 'validate_job_queue', spec_set=True,
                       autospec=True)
    def test_delete_virtual_disk(self, mock_validate_job_queue,
                                 mock_get_drac_client):
        mock_client = mock.Mock()
        mock_get_drac_client.return_value = mock_client

        drac_raid.delete_virtual_disk(self.node, 'disk1')

        mock_validate_job_queue.assert_called_once_with(self.node)
        mock_client.delete_virtual_disk.assert_called_once_with('disk1')

    @mock.patch.object(drac_job, 'validate_job_queue', spec_set=True,
                       autospec=True)
    def test_delete_virtual_disk_fail(self, mock_validate_job_queue,
                                      mock_get_drac_client):
        mock_client = mock.Mock()
        mock_get_drac_client.return_value = mock_client
        exc = drac_exceptions.BaseClientException('boom')
        mock_client.delete_virtual_disk.side_effect = exc

        self.assertRaises(
            exception.DracOperationError, drac_raid.delete_virtual_disk,
            self.node, 'disk1')

    @mock.patch.object(drac_job, 'validate_job_queue', spec_set=True,
                       autospec=True)
    def test__reset_raid_config(self, mock_validate_job_queue,
                                mock_get_drac_client):
        mock_client = mock.Mock()
        mock_get_drac_client.return_value = mock_client

        drac_raid._reset_raid_config(
            self.node, 'controller')

        mock_validate_job_queue.assert_called_once_with(
            self.node, name_prefix='Config:RAID:controller')
        mock_client.reset_raid_config.assert_called_once_with(
            'controller')

    @mock.patch.object(drac_job, 'validate_job_queue', spec_set=True,
                       autospec=True)
    def test__reset_raid_config_fail(self, mock_validate_job_queue,
                                     mock_get_drac_client):
        mock_client = mock.Mock()
        mock_get_drac_client.return_value = mock_client

        exc = drac_exceptions.BaseClientException('boom')
        mock_client.reset_raid_config.side_effect = exc

        self.assertRaises(
            exception.DracOperationError, drac_raid._reset_raid_config,
            self.node, 'RAID.Integrated.1-1')

    @mock.patch.object(drac_job, 'validate_job_queue', spec_set=True,
                       autospec=True)
    def test_clear_foreign_config(self, mock_validate_job_queue,
                                  mock_get_drac_client):
        mock_client = mock.Mock()
        mock_get_drac_client.return_value = mock_client

        drac_raid.clear_foreign_config(
            self.node, 'RAID.Integrated.1-1')

        mock_validate_job_queue.assert_called_once_with(
            self.node, 'Config:RAID:RAID.Integrated.1-1')
        mock_client.clear_foreign_config.assert_called_once_with(
            'RAID.Integrated.1-1')

    @mock.patch.object(drac_job, 'validate_job_queue', spec_set=True,
                       autospec=True)
    def test_clear_foreign_config_fail(self, mock_validate_job_queue,
                                       mock_get_drac_client):
        mock_client = mock.Mock()
        mock_get_drac_client.return_value = mock_client

        exc = drac_exceptions.BaseClientException('boom')
        mock_client.clear_foreign_config.side_effect = exc

        self.assertRaises(
            exception.DracOperationError, drac_raid.clear_foreign_config,
            self.node, 'RAID.Integrated.1-1')

    def test_commit_config(self, mock_get_drac_client):
        mock_client = mock.Mock()
        mock_get_drac_client.return_value = mock_client

        drac_raid.commit_config(self.node, 'controller1')

        mock_client.commit_pending_raid_changes.assert_called_once_with(
            raid_controller='controller1', reboot=False, realtime=False)

    def test_commit_config_with_reboot(self, mock_get_drac_client):
        mock_client = mock.Mock()
        mock_get_drac_client.return_value = mock_client

        drac_raid.commit_config(self.node, 'controller1', reboot=True,
                                realtime=False)

        mock_client.commit_pending_raid_changes.assert_called_once_with(
            raid_controller='controller1', reboot=True, realtime=False)

    def test_commit_config_with_realtime(self, mock_get_drac_client):
        mock_client = mock.Mock()
        mock_get_drac_client.return_value = mock_client

        drac_raid.commit_config(self.node, 'RAID.Integrated.1-1', reboot=False,
                                realtime=True)

        mock_client.commit_pending_raid_changes.assert_called_once_with(
            raid_controller='RAID.Integrated.1-1', reboot=False, realtime=True)

    def test_commit_config_fail(self, mock_get_drac_client):
        mock_client = mock.Mock()
        mock_get_drac_client.return_value = mock_client
        exc = drac_exceptions.BaseClientException('boom')
        mock_client.commit_pending_raid_changes.side_effect = exc

        self.assertRaises(
            exception.DracOperationError, drac_raid.commit_config, self.node,
            'controller1')

    def test_abandon_config(self, mock_get_drac_client):
        mock_client = mock.Mock()
        mock_get_drac_client.return_value = mock_client

        drac_raid.abandon_config(self.node, 'controller1')

        mock_client.abandon_pending_raid_changes.assert_called_once_with(
            'controller1')

    def test_abandon_config_fail(self, mock_get_drac_client):
        mock_client = mock.Mock()
        mock_get_drac_client.return_value = mock_client
        exc = drac_exceptions.BaseClientException('boom')
        mock_client.abandon_pending_raid_changes.side_effect = exc

        self.assertRaises(
            exception.DracOperationError, drac_raid.abandon_config, self.node,
            'controller1')


class DracCreateRaidConfigurationHelpersTestCase(test_utils.BaseDracTest):

    def setUp(self):
        super(DracCreateRaidConfigurationHelpersTestCase, self).setUp()
        self.node = obj_utils.create_test_node(self.context,
                                               driver='idrac',
                                               driver_info=INFO_DICT)

        self.physical_disk = {
            'id': 'Disk.Bay.1:Enclosure.Internal.0-1:RAID.Integrated.1-1',
            'description': ('Disk 1 in Backplane 1 of '
                            'Integrated RAID Controller 1'),
            'controller': 'RAID.Integrated.1-1',
            'manufacturer': 'SEAGATE',
            'model': 'ST600MM0006',
            'media_type': 'hdd',
            'interface_type': 'sas',
            'size_mb': 571776,
            'free_size_mb': 571776,
            'serial_number': 'S0M3EY2Z',
            'firmware_version': 'LS0A',
            'status': 'ok',
            'raid_status': 'ready',
            'sas_address': '500056B37789ABE3',
            'device_protocol': None}

        self.physical_disks = []
        for i in range(8):
            disk = self.physical_disk.copy()
            disk['id'] = ('Disk.Bay.%s:Enclosure.Internal.0-1:'
                          'RAID.Integrated.1-1' % i)
            disk['serial_number'] = 'serial%s' % i

            self.physical_disks.append(disk)

        self.root_logical_disk = {
            'size_gb': 50,
            'raid_level': '1',
            'disk_type': 'hdd',
            'interface_type': 'sas',
            'volume_name': 'root_volume',
            'is_root_volume': True
        }
        self.nonroot_logical_disks = [
            {'size_gb': 100,
             'raid_level': '5',
             'disk_type': 'hdd',
             'interface_type': 'sas',
             'volume_name': 'data_volume1'},
            {'size_gb': 100,
             'raid_level': '5',
             'disk_type': 'hdd',
             'interface_type': 'sas',
             'volume_name': 'data_volume2'}
        ]

        self.logical_disks = (
            [self.root_logical_disk] + self.nonroot_logical_disks)
        self.target_raid_configuration = {'logical_disks': self.logical_disks}
        self.node.target_raid_config = self.target_raid_configuration
        self.node.save()

    def _generate_physical_disks(self):
        physical_disks = []

        for disk in self.physical_disks:
            physical_disks.append(test_utils.make_physical_disk(disk))

        return physical_disks

    def test__filter_logical_disks_root_only(self):
        logical_disks = drac_raid._filter_logical_disks(
            self.target_raid_configuration['logical_disks'], True, False)

        self.assertEqual(1, len(logical_disks))
        self.assertEqual('root_volume', logical_disks[0]['volume_name'])

    def test__filter_logical_disks_nonroot_only(self):
        logical_disks = drac_raid._filter_logical_disks(
            self.target_raid_configuration['logical_disks'], False, True)

        self.assertEqual(2, len(logical_disks))
        self.assertEqual('data_volume1', logical_disks[0]['volume_name'])
        self.assertEqual('data_volume2', logical_disks[1]['volume_name'])

    def test__filter_logical_disks_excelude_all(self):
        logical_disks = drac_raid._filter_logical_disks(
            self.target_raid_configuration['logical_disks'], False, False)

        self.assertEqual(0, len(logical_disks))

    def test__calculate_spans_for_2_disk_and_raid_level_1(self):
        raid_level = '1'
        disks_count = 2

        spans_count = drac_raid._calculate_spans(raid_level, disks_count)
        self.assertEqual(1, spans_count)

    def test__calculate_spans_for_7_disk_and_raid_level_50(self):
        raid_level = '5+0'
        disks_count = 7

        spans_count = drac_raid._calculate_spans(raid_level, disks_count)

        self.assertEqual(2, spans_count)

    def test__calculate_spans_for_7_disk_and_raid_level_10(self):
        raid_level = '1+0'
        disks_count = 7

        spans_count = drac_raid._calculate_spans(raid_level, disks_count)
        self.assertEqual(3, spans_count)

    def test__calculate_spans_for_invalid_raid_level(self):
        raid_level = 'foo'
        disks_count = 7

        self.assertRaises(exception.DracOperationError,
                          drac_raid._calculate_spans, raid_level, disks_count)

    def test__max_volume_size_mb(self):
        physical_disks = self._generate_physical_disks()
        physical_disk_free_space_mb = {}
        for disk in physical_disks:
            physical_disk_free_space_mb[disk] = disk.free_size_mb

        max_size = drac_raid._max_volume_size_mb(
            '5', physical_disks[0:3], physical_disk_free_space_mb)

        self.assertEqual(1143552, max_size)

    def test__volume_usage_per_disk_mb(self):
        logical_disk = {
            'size_mb': 102400,
            'raid_level': '5',
            'disk_type': 'hdd',
            'interface_type': 'sas',
            'volume_name': 'data_volume1'}
        physical_disks = self._generate_physical_disks()

        usage_per_disk = drac_raid._volume_usage_per_disk_mb(logical_disk,
                                                             physical_disks)

        self.assertEqual(14656, usage_per_disk)

    def test__find_configuration(self):
        logical_disks = [
            {'size_mb': 102400,
             'raid_level': '5',
             'is_root_volume': True,
             'disk_type': 'hdd'}
        ]
        physical_disks = self._generate_physical_disks()
        expected_contoller = 'RAID.Integrated.1-1'
        expected_physical_disk_ids = [
            'Disk.Bay.0:Enclosure.Internal.0-1:RAID.Integrated.1-1',
            'Disk.Bay.1:Enclosure.Internal.0-1:RAID.Integrated.1-1',
            'Disk.Bay.2:Enclosure.Internal.0-1:RAID.Integrated.1-1']

        logical_disks = drac_raid._find_configuration(logical_disks,
                                                      physical_disks,
                                                      False)

        self.assertEqual(expected_contoller,
                         logical_disks[0]['controller'])
        self.assertEqual(expected_physical_disk_ids,
                         logical_disks[0]['physical_disks'])

    def test__find_configuration_with_more_than_min_disks_for_raid_level(self):
        logical_disks = [
            {'size_mb': 3072000,
             'raid_level': '5',
             'is_root_volume': True,
             'disk_type': 'hdd'}
        ]
        physical_disks = self._generate_physical_disks()
        expected_contoller = 'RAID.Integrated.1-1'
        expected_physical_disk_ids = [
            'Disk.Bay.0:Enclosure.Internal.0-1:RAID.Integrated.1-1',
            'Disk.Bay.1:Enclosure.Internal.0-1:RAID.Integrated.1-1',
            'Disk.Bay.2:Enclosure.Internal.0-1:RAID.Integrated.1-1',
            'Disk.Bay.3:Enclosure.Internal.0-1:RAID.Integrated.1-1',
            'Disk.Bay.4:Enclosure.Internal.0-1:RAID.Integrated.1-1',
            'Disk.Bay.5:Enclosure.Internal.0-1:RAID.Integrated.1-1',
            'Disk.Bay.6:Enclosure.Internal.0-1:RAID.Integrated.1-1']

        logical_disks = drac_raid._find_configuration(logical_disks,
                                                      physical_disks,
                                                      False)

        self.assertEqual(expected_contoller,
                         logical_disks[0]['controller'])
        self.assertEqual(expected_physical_disk_ids,
                         logical_disks[0]['physical_disks'])

    def test__find_configuration_all_steps(self):
        logical_disks = [
            # step 1
            {'size_mb': 102400,
             'raid_level': '1',
             'physical_disks': [
                 'Disk.Bay.0:Enclosure.Internal.0-1:RAID.Integrated.1-1',
                 'Disk.Bay.1:Enclosure.Internal.0-1:RAID.Integrated.1-1']},
            # step 2
            {'size_mb': 51200,
             'raid_level': '5'},
            # step 3
            {'size_mb': 'MAX',
             'raid_level': '0',
             'physical_disks': [
                 'Disk.Bay.2:Enclosure.Internal.0-1:RAID.Integrated.1-1',
                 'Disk.Bay.3:Enclosure.Internal.0-1:RAID.Integrated.1-1']},
        ]
        physical_disks = self._generate_physical_disks()

        logical_disks = drac_raid._find_configuration(logical_disks,
                                                      physical_disks,
                                                      False)

        self.assertEqual(3, len(logical_disks))
        # step 1
        self.assertIn(
            {'raid_level': '1',
             'size_mb': 102400,
             'controller': 'RAID.Integrated.1-1',
             'span_depth': 1,
             'span_length': 2,
             'physical_disks': [
                 'Disk.Bay.0:Enclosure.Internal.0-1:RAID.Integrated.1-1',
                 'Disk.Bay.1:Enclosure.Internal.0-1:RAID.Integrated.1-1']},
            logical_disks)
        # step 2
        self.assertIn(
            {'raid_level': '5',
             'size_mb': 51200,
             'controller': 'RAID.Integrated.1-1',
             'span_depth': 1,
             'span_length': 3,
             'physical_disks': [
                 'Disk.Bay.4:Enclosure.Internal.0-1:RAID.Integrated.1-1',
                 'Disk.Bay.5:Enclosure.Internal.0-1:RAID.Integrated.1-1',
                 'Disk.Bay.6:Enclosure.Internal.0-1:RAID.Integrated.1-1']},
            logical_disks)
        # step 3
        self.assertIn(
            {'raid_level': '0',
             'size_mb': 1143552,
             'controller': 'RAID.Integrated.1-1',
             'span_depth': 1,
             'span_length': 2,
             'physical_disks': [
                 'Disk.Bay.2:Enclosure.Internal.0-1:RAID.Integrated.1-1',
                 'Disk.Bay.3:Enclosure.Internal.0-1:RAID.Integrated.1-1']},
            logical_disks)

    def test__find_configuration_pending_delete(self):
        logical_disks = [
            {'size_mb': 102400,
             'raid_level': '5',
             'is_root_volume': True,
             'disk_type': 'hdd'}
        ]
        physical_disks = self._generate_physical_disks()
        # No free space, but deletion pending means they're still usable.
        physical_disks = [disk._replace(free_size_mb=0)
                          for disk in physical_disks]

        expected_contoller = 'RAID.Integrated.1-1'
        expected_physical_disk_ids = [
            'Disk.Bay.0:Enclosure.Internal.0-1:RAID.Integrated.1-1',
            'Disk.Bay.1:Enclosure.Internal.0-1:RAID.Integrated.1-1',
            'Disk.Bay.2:Enclosure.Internal.0-1:RAID.Integrated.1-1']

        logical_disks = drac_raid._find_configuration(logical_disks,
                                                      physical_disks,
                                                      True)

        self.assertEqual(expected_contoller,
                         logical_disks[0]['controller'])
        self.assertEqual(expected_physical_disk_ids,
                         logical_disks[0]['physical_disks'])


class DracRaidInterfaceTestCase(test_utils.BaseDracTest):

    def setUp(self):
        super(DracRaidInterfaceTestCase, self).setUp()
        self.node = obj_utils.create_test_node(self.context,
                                               driver='idrac',
                                               driver_info=INFO_DICT)

        self.physical_disk = {
            'id': 'Disk.Bay.1:Enclosure.Internal.0-1:RAID.Integrated.1-1',
            'description': ('Disk 1 in Backplane 1 of '
                            'Integrated RAID Controller 1'),
            'controller': 'RAID.Integrated.1-1',
            'manufacturer': 'SEAGATE',
            'model': 'ST600MM0006',
            'media_type': 'hdd',
            'interface_type': 'sas',
            'size_mb': 571776,
            'free_size_mb': 571776,
            'serial_number': 'S0M3EY2Z',
            'firmware_version': 'LS0A',
            'status': 'ok',
            'raid_status': 'ready',
            'sas_address': '500056B37789ABE3',
            'device_protocol': None}

        self.physical_disks = []
        for i in range(8):
            disk = self.physical_disk.copy()
            disk['id'] = ('Disk.Bay.%s:Enclosure.Internal.0-1:'
                          'RAID.Integrated.1-1' % i)
            disk['serial_number'] = 'serial%s' % i

            self.physical_disks.append(disk)

        self.root_logical_disk = {
            'size_gb': 50,
            'raid_level': '1',
            'disk_type': 'hdd',
            'interface_type': 'sas',
            'volume_name': 'root_volume',
            'is_root_volume': True
        }
        self.nonroot_logical_disks = [
            {'size_gb': 100,
             'raid_level': '5',
             'disk_type': 'hdd',
             'interface_type': 'sas',
             'volume_name': 'data_volume1'},
            {'size_gb': 100,
             'raid_level': '5',
             'disk_type': 'hdd',
             'interface_type': 'sas',
             'volume_name': 'data_volume2'}
        ]

        self.logical_disks = (
            [self.root_logical_disk] + self.nonroot_logical_disks)
        self.target_raid_configuration = {'logical_disks': self.logical_disks}
        self.node.target_raid_config = self.target_raid_configuration
        self.node.clean_step = {'foo': 'bar'}
        self.node.save()

    def _generate_physical_disks(self):
        physical_disks = []

        for disk in self.physical_disks:
            physical_disks.append(test_utils.make_physical_disk(disk))

        return physical_disks

    @mock.patch.object(drac_common, 'get_drac_client', spec_set=True,
                       autospec=True)
    @mock.patch.object(drac_raid, '_reset_raid_config', autospec=True)
    @mock.patch.object(drac_raid, 'list_physical_disks', autospec=True)
    @mock.patch.object(drac_job, 'validate_job_queue', spec_set=True,
                       autospec=True)
    @mock.patch.object(drac_raid, 'commit_config', spec_set=True,
                       autospec=True)
    def _test_create_configuration(
            self, expected_state, mock_commit_config, mock_validate_job_queue,
            mock_list_physical_disks, mock__reset_raid_config,
            mock_get_drac_client):
        mock_client = mock.Mock()
        mock_get_drac_client.return_value = mock_client
        physical_disks = self._generate_physical_disks()
        mock_list_physical_disks.return_value = physical_disks
        mock_commit_config.return_value = '42'
        raid_controller_dict = {
            'id': 'RAID.Integrated.1-1',
            'description': 'Integrated RAID Controller 1',
            'manufacturer': 'DELL',
            'model': 'PERC H710 Mini',
            'primary_status': 'ok',
            'firmware_version': '21.3.0-0009',
            'bus': '1',
            'supports_realtime': True}
        raid_controller = test_utils.make_raid_controller(
            raid_controller_dict)
        mock_client.list_raid_controllers.return_value = [raid_controller]
        mock__reset_raid_config.return_value = {
            'is_reboot_required': constants.RebootRequired.optional,
            'is_commit_required': True}
        mock_client.create_virtual_disk.return_value = {
            'is_reboot_required': constants.RebootRequired.optional,
            'is_commit_required': True}

        with task_manager.acquire(self.context, self.node.uuid,
                                  shared=False) as task:
            return_value = task.driver.raid.create_configuration(
                task, create_root_volume=True, create_nonroot_volumes=False)

            mock_client.create_virtual_disk.assert_called_once_with(
                'RAID.Integrated.1-1',
                ['Disk.Bay.0:Enclosure.Internal.0-1:RAID.Integrated.1-1',
                 'Disk.Bay.1:Enclosure.Internal.0-1:RAID.Integrated.1-1'],
                '1', 51200, None, 2, 1)

            mock_commit_config.assert_called_once_with(
                task.node, raid_controller='RAID.Integrated.1-1', reboot=False,
                realtime=True)

        self.assertEqual(expected_state, return_value)
        self.node.refresh()
        self.assertEqual(['42'],
                         self.node.driver_internal_info['raid_config_job_ids'])

    def test_create_configuration_in_clean(self):
        self._test_create_configuration(states.CLEANWAIT)

    def test_create_configuration_in_deploy(self):
        self.node.clean_step = None
        self.node.save()
        self._test_create_configuration(states.DEPLOYWAIT)

    @mock.patch.object(drac_common, 'get_drac_client', spec_set=True,
                       autospec=True)
    @mock.patch.object(drac_raid, 'list_physical_disks', autospec=True)
    @mock.patch.object(drac_job, 'validate_job_queue', spec_set=True,
                       autospec=True)
    @mock.patch.object(drac_raid, 'commit_config', spec_set=True,
                       autospec=True)
    def test_create_configuration_no_change(
            self, mock_commit_config, mock_validate_job_queue,
            mock_list_physical_disks,
            mock_get_drac_client):
        mock_client = mock.Mock()
        mock_get_drac_client.return_value = mock_client
        physical_disks = self._generate_physical_disks()
        mock_list_physical_disks.return_value = physical_disks
        mock_client.create_virtual_disk.return_value = {
            'is_reboot_required': constants.RebootRequired.optional,
            'is_commit_required': True}

        with task_manager.acquire(self.context, self.node.uuid,
                                  shared=False) as task:
            return_value = task.driver.raid.create_configuration(
                task, create_root_volume=False, create_nonroot_volumes=False,
                delete_existing=False)

            self.assertEqual(0, mock_client.create_virtual_disk.call_count)
            self.assertEqual(0, mock_commit_config.call_count)

        self.assertIsNone(return_value)

        self.node.refresh()
        self.assertNotIn('raid_config_job_ids', self.node.driver_internal_info)

    @mock.patch.object(drac_common, 'get_drac_client', spec_set=True,
                       autospec=True)
    @mock.patch.object(drac_raid, '_reset_raid_config', autospec=True)
    @mock.patch.object(drac_raid, 'list_virtual_disks', autospec=True)
    @mock.patch.object(drac_raid, 'list_physical_disks', autospec=True)
    @mock.patch.object(drac_job, 'validate_job_queue', spec_set=True,
                       autospec=True)
    @mock.patch.object(drac_raid, 'commit_config', spec_set=True,
                       autospec=True)
    def test_create_configuration_delete_existing(
            self, mock_commit_config,
            mock_validate_job_queue,
            mock_list_physical_disks,
            mock_list_virtual_disks,
            mock__reset_raid_config,
            mock_get_drac_client):
        self.node.clean_step = None
        self.node.save()
        mock_client = mock.Mock()
        mock_get_drac_client.return_value = mock_client

        physical_disks = self._generate_physical_disks()
        raid_controller_dict = {
            'id': 'RAID.Integrated.1-1',
            'description': 'Integrated RAID Controller 1',
            'manufacturer': 'DELL',
            'model': 'PERC H710 Mini',
            'primary_status': 'ok',
            'firmware_version': '21.3.0-0009',
            'bus': '1',
            'supports_realtime': True}
        raid_controller = test_utils.make_raid_controller(
            raid_controller_dict)
        mock_list_physical_disks.return_value = physical_disks
        mock_commit_config.return_value = '42'
        mock_client.list_raid_controllers.return_value = [raid_controller]
        mock__reset_raid_config.return_value = {
            'is_reboot_required': constants.RebootRequired.optional,
            'is_commit_required': True}

        mock_client.create_virtual_disk.return_value = {
            'is_reboot_required': constants.RebootRequired.optional,
            'is_commit_required': True
        }

        with task_manager.acquire(self.context, self.node.uuid,
                                  shared=False) as task:
            return_value = task.driver.raid.create_configuration(
                task, create_root_volume=True, create_nonroot_volumes=False,
                delete_existing=True)
            mock_client.create_virtual_disk.assert_called_once_with(
                'RAID.Integrated.1-1',
                ['Disk.Bay.0:Enclosure.Internal.0-1:RAID.Integrated.1-1',
                 'Disk.Bay.1:Enclosure.Internal.0-1:RAID.Integrated.1-1'],
                '1', 51200, None, 2, 1)
            mock_commit_config.assert_called_once_with(
                task.node, raid_controller='RAID.Integrated.1-1',
                realtime=True, reboot=False)

            self.assertEqual(1, mock_commit_config.call_count)

        self.assertEqual(states.DEPLOYWAIT, return_value)
        self.node.refresh()
        self.assertEqual(['42'],
                         self.node.driver_internal_info['raid_config_job_ids'])

    @mock.patch.object(drac_common, 'get_drac_client', spec_set=True,
                       autospec=True)
    @mock.patch.object(drac_raid, 'list_physical_disks', autospec=True)
    @mock.patch.object(drac_job, 'validate_job_queue', spec_set=True,
                       autospec=True)
    @mock.patch.object(drac_raid, 'commit_config', spec_set=True,
                       autospec=True)
    def test_create_configuration_with_nested_raid_level(
            self, mock_commit_config, mock_validate_job_queue,
            mock_list_physical_disks, mock_get_drac_client):
        mock_client = mock.Mock()
        mock_get_drac_client.return_value = mock_client

        self.root_logical_disk = {
            'size_gb': 100,
            'raid_level': '5+0',
            'is_root_volume': True
        }

        self.logical_disks = [self.root_logical_disk]
        self.target_raid_configuration = {'logical_disks': self.logical_disks}
        self.node.target_raid_config = self.target_raid_configuration
        self.node.save()

        physical_disks = self._generate_physical_disks()
        mock_list_physical_disks.return_value = physical_disks
        mock_commit_config.return_value = '42'
        mock_client.create_virtual_disk.return_value = {
            'is_reboot_required': constants.RebootRequired.optional,
            'is_commit_required': True}

        with task_manager.acquire(self.context, self.node.uuid,
                                  shared=False) as task:
            task.driver.raid.create_configuration(
                task, create_root_volume=True, create_nonroot_volumes=True,
                delete_existing=False)

            mock_client.create_virtual_disk.assert_called_once_with(
                'RAID.Integrated.1-1',
                ['Disk.Bay.0:Enclosure.Internal.0-1:RAID.Integrated.1-1',
                 'Disk.Bay.1:Enclosure.Internal.0-1:RAID.Integrated.1-1',
                 'Disk.Bay.2:Enclosure.Internal.0-1:RAID.Integrated.1-1',
                 'Disk.Bay.3:Enclosure.Internal.0-1:RAID.Integrated.1-1',
                 'Disk.Bay.4:Enclosure.Internal.0-1:RAID.Integrated.1-1',
                 'Disk.Bay.5:Enclosure.Internal.0-1:RAID.Integrated.1-1'],
                '5+0', 102400, None, 3, 2)

            # Commits to the controller
            mock_commit_config.assert_called_once_with(
                mock.ANY, raid_controller='RAID.Integrated.1-1', reboot=False,
                realtime=True)

        self.node.refresh()
        self.assertEqual(['42'],
                         self.node.driver_internal_info['raid_config_job_ids'])

    @mock.patch.object(drac_common, 'get_drac_client', spec_set=True,
                       autospec=True)
    @mock.patch.object(drac_raid, 'list_physical_disks', autospec=True)
    @mock.patch.object(drac_job, 'validate_job_queue', spec_set=True,
                       autospec=True)
    @mock.patch.object(drac_raid, 'commit_config', spec_set=True,
                       autospec=True)
    def test_create_configuration_with_nested_raid_10(
            self, mock_commit_config,
            mock_validate_job_queue, mock_list_physical_disks,
            mock_get_drac_client):
        mock_client = mock.Mock()
        mock_get_drac_client.return_value = mock_client

        self.root_logical_disk = {
            'size_gb': 100,
            'raid_level': '1+0',
            'is_root_volume': True
        }
        self.logical_disks = [self.root_logical_disk]
        self.target_raid_configuration = {'logical_disks': self.logical_disks}
        self.node.target_raid_config = self.target_raid_configuration
        self.node.save()

        physical_disks = self._generate_physical_disks()
        mock_list_physical_disks.return_value = physical_disks

        mock_commit_config.return_value = '42'
        mock_client.create_virtual_disk.return_value = {
            'is_reboot_required': constants.RebootRequired.optional,
            'is_commit_required': True}

        with task_manager.acquire(self.context, self.node.uuid,
                                  shared=False) as task:
            task.driver.raid.create_configuration(
                task, create_root_volume=True, create_nonroot_volumes=True,
                delete_existing=False)

            mock_client.create_virtual_disk.assert_called_once_with(
                'RAID.Integrated.1-1',
                ['Disk.Bay.0:Enclosure.Internal.0-1:RAID.Integrated.1-1',
                 'Disk.Bay.1:Enclosure.Internal.0-1:RAID.Integrated.1-1',
                 'Disk.Bay.2:Enclosure.Internal.0-1:RAID.Integrated.1-1',
                 'Disk.Bay.3:Enclosure.Internal.0-1:RAID.Integrated.1-1'],
                '1+0', 102400, None, None, None)

            # Commits to the controller
            mock_commit_config.assert_called_once_with(
                mock.ANY, raid_controller='RAID.Integrated.1-1', reboot=False,
                realtime=True)

        self.node.refresh()
        self.assertEqual(['42'],
                         self.node.driver_internal_info['raid_config_job_ids'])

    @mock.patch.object(drac_common, 'get_drac_client', spec_set=True,
                       autospec=True)
    @mock.patch.object(drac_raid, 'list_physical_disks', autospec=True)
    @mock.patch.object(drac_job, 'validate_job_queue', spec_set=True,
                       autospec=True)
    @mock.patch.object(drac_raid, 'commit_config', spec_set=True,
                       autospec=True)
    def test_create_configuration_with_multiple_controllers(
            self, mock_commit_config, mock_validate_job_queue,
            mock_list_physical_disks, mock_get_drac_client):
        mock_client = mock.Mock()
        mock_get_drac_client.return_value = mock_client

        self.physical_disks[0]['controller'] = 'controller-2'
        self.physical_disks[1]['controller'] = 'controller-2'
        physical_disks = self._generate_physical_disks()
        mock_list_physical_disks.return_value = physical_disks

        mock_commit_config.side_effect = ['42', '12', '13']
        mock_client.create_virtual_disk.side_effect = [{
            'is_reboot_required': constants.RebootRequired.true,
            'is_commit_required': True
        }, {
            'is_reboot_required': constants.RebootRequired.optional,
            'is_commit_required': True
        }, {
            'is_reboot_required': constants.RebootRequired.optional,
            'is_commit_required': True
        }]

        with task_manager.acquire(self.context, self.node.uuid,
                                  shared=False) as task:
            task.driver.raid.create_configuration(
                task, create_root_volume=True, create_nonroot_volumes=True,
                delete_existing=False)
            mock_client.create_virtual_disk.assert_has_calls(
                [mock.call(
                    'controller-2',
                    ['Disk.Bay.0:Enclosure.Internal.0-1:RAID.Integrated.1-1',
                     'Disk.Bay.1:Enclosure.Internal.0-1:RAID.Integrated.1-1'],
                    '1', 51200, None, 2, 1),
                 mock.call(
                    'RAID.Integrated.1-1',
                    ['Disk.Bay.2:Enclosure.Internal.0-1:RAID.Integrated.1-1',
                     'Disk.Bay.3:Enclosure.Internal.0-1:RAID.Integrated.1-1',
                     'Disk.Bay.4:Enclosure.Internal.0-1:RAID.Integrated.1-1'],
                    '5', 102400, None, 3, 1),
                 mock.call(
                    'RAID.Integrated.1-1',
                    ['Disk.Bay.5:Enclosure.Internal.0-1:RAID.Integrated.1-1',
                     'Disk.Bay.6:Enclosure.Internal.0-1:RAID.Integrated.1-1',
                     'Disk.Bay.7:Enclosure.Internal.0-1:RAID.Integrated.1-1'],
                    '5', 102400, None, 3, 1)
                 ],
                any_order=True)

            # Commits to both controller
            mock_commit_config.assert_has_calls(
                [mock.call(mock.ANY, raid_controller='controller-2',
                           reboot=mock.ANY, realtime=mock.ANY),
                 mock.call(mock.ANY, raid_controller='RAID.Integrated.1-1',
                           reboot=mock.ANY, realtime=mock.ANY)],
                any_order=True)

        self.node.refresh()
        self.assertEqual(['42', '12', '13'],
                         self.node.driver_internal_info['raid_config_job_ids'])

    @mock.patch.object(drac_common, 'get_drac_client', spec_set=True,
                       autospec=True)
    @mock.patch.object(drac_raid, 'list_physical_disks', autospec=True)
    @mock.patch.object(drac_job, 'validate_job_queue', spec_set=True,
                       autospec=True)
    @mock.patch.object(drac_raid, 'commit_config', spec_set=True,
                       autospec=True)
    def test_create_configuration_with_backing_physical_disks(
            self, mock_commit_config, mock_validate_job_queue,
            mock_list_physical_disks, mock_get_drac_client):
        mock_client = mock.Mock()
        mock_get_drac_client.return_value = mock_client

        self.root_logical_disk['physical_disks'] = [
            'Disk.Bay.3:Enclosure.Internal.0-1:RAID.Integrated.1-1',
            'Disk.Bay.4:Enclosure.Internal.0-1:RAID.Integrated.1-1']
        self.logical_disks = (
            [self.root_logical_disk] + self.nonroot_logical_disks)
        self.target_raid_configuration = {'logical_disks': self.logical_disks}
        self.node.target_raid_config = self.target_raid_configuration
        self.node.save()

        physical_disks = self._generate_physical_disks()
        mock_list_physical_disks.return_value = physical_disks

        mock_commit_config.side_effect = ['42', '12', '13']
        mock_client.create_virtual_disk.return_value = {
            'is_reboot_required': constants.RebootRequired.optional,
            'is_commit_required': True
        }

        with task_manager.acquire(self.context, self.node.uuid,
                                  shared=False) as task:
            task.driver.raid.create_configuration(
                task, create_root_volume=True, create_nonroot_volumes=True,
                delete_existing=False)
            mock_client.create_virtual_disk.assert_has_calls(
                [mock.call(
                    'RAID.Integrated.1-1',
                    ['Disk.Bay.3:Enclosure.Internal.0-1:RAID.Integrated.1-1',
                     'Disk.Bay.4:Enclosure.Internal.0-1:RAID.Integrated.1-1'],
                    '1', 51200, None, 2, 1),
                 mock.call(
                    'RAID.Integrated.1-1',
                    ['Disk.Bay.0:Enclosure.Internal.0-1:RAID.Integrated.1-1',
                     'Disk.Bay.1:Enclosure.Internal.0-1:RAID.Integrated.1-1',
                     'Disk.Bay.2:Enclosure.Internal.0-1:RAID.Integrated.1-1'],
                    '5', 102400, None, 3, 1),
                 mock.call(
                    'RAID.Integrated.1-1',
                    ['Disk.Bay.5:Enclosure.Internal.0-1:RAID.Integrated.1-1',
                     'Disk.Bay.6:Enclosure.Internal.0-1:RAID.Integrated.1-1',
                     'Disk.Bay.7:Enclosure.Internal.0-1:RAID.Integrated.1-1'],
                    '5', 102400, None, 3, 1)],
                any_order=True)

            # Commits to the controller
            mock_commit_config.assert_called_with(
                mock.ANY, raid_controller='RAID.Integrated.1-1',
                reboot=False, realtime=True)

        self.node.refresh()
        self.assertEqual(['42'],
                         self.node.driver_internal_info['raid_config_job_ids'])

    @mock.patch.object(drac_common, 'get_drac_client', spec_set=True,
                       autospec=True)
    @mock.patch.object(drac_raid, 'list_physical_disks', autospec=True)
    @mock.patch.object(drac_job, 'validate_job_queue', spec_set=True,
                       autospec=True)
    @mock.patch.object(drac_raid, 'commit_config', spec_set=True,
                       autospec=True)
    def test_create_configuration_with_predefined_number_of_phyisical_disks(
            self, mock_commit_config, mock_validate_job_queue,
            mock_list_physical_disks, mock_get_drac_client):

        mock_client = mock.Mock()
        mock_get_drac_client.return_value = mock_client

        self.root_logical_disk['raid_level'] = '0'
        self.root_logical_disk['number_of_physical_disks'] = 3
        self.logical_disks = (
            [self.root_logical_disk, self.nonroot_logical_disks[0]])
        self.target_raid_configuration = {'logical_disks': self.logical_disks}
        self.node.target_raid_config = self.target_raid_configuration
        self.node.save()

        physical_disks = self._generate_physical_disks()
        mock_list_physical_disks.return_value = physical_disks
        mock_commit_config.side_effect = ['42', '12']
        mock_client.create_virtual_disk.return_value = {
            'is_reboot_required': constants.RebootRequired.optional,
            'is_commit_required': True
        }

        with task_manager.acquire(self.context, self.node.uuid,
                                  shared=False) as task:
            task.driver.raid.create_configuration(
                task, create_root_volume=True, create_nonroot_volumes=True,
                delete_existing=False)

            mock_client.create_virtual_disk.assert_has_calls(
                [mock.call(
                    'RAID.Integrated.1-1',
                    ['Disk.Bay.0:Enclosure.Internal.0-1:RAID.Integrated.1-1',
                     'Disk.Bay.1:Enclosure.Internal.0-1:RAID.Integrated.1-1',
                     'Disk.Bay.2:Enclosure.Internal.0-1:RAID.Integrated.1-1'],
                    '0', 51200, None, 3, 1),
                 mock.call(
                    'RAID.Integrated.1-1',
                    ['Disk.Bay.3:Enclosure.Internal.0-1:RAID.Integrated.1-1',
                     'Disk.Bay.4:Enclosure.Internal.0-1:RAID.Integrated.1-1',
                     'Disk.Bay.5:Enclosure.Internal.0-1:RAID.Integrated.1-1'],
                    '5', 102400, None, 3, 1)],
                any_order=True)

            # Commits to the controller
            mock_commit_config.assert_called_with(
                mock.ANY, raid_controller='RAID.Integrated.1-1',
                reboot=False, realtime=True)

        self.node.refresh()
        self.assertEqual(['42'],
                         self.node.driver_internal_info['raid_config_job_ids'])

    @mock.patch.object(drac_common, 'get_drac_client', spec_set=True,
                       autospec=True)
    @mock.patch.object(drac_raid, 'list_physical_disks', autospec=True)
    @mock.patch.object(drac_job, 'validate_job_queue', spec_set=True,
                       autospec=True)
    @mock.patch.object(drac_raid, 'commit_config', spec_set=True,
                       autospec=True)
    def test_create_configuration_with_max_size(
            self, mock_commit_config, mock_validate_job_queue,
            mock_list_physical_disks, mock_get_drac_client):
        mock_client = mock.Mock()
        mock_get_drac_client.return_value = mock_client

        self.root_logical_disk = {
            'size_gb': 'MAX',
            'raid_level': '1',
            'physical_disks': [
                'Disk.Bay.4:Enclosure.Internal.0-1:RAID.Integrated.1-1',
                'Disk.Bay.5:Enclosure.Internal.0-1:RAID.Integrated.1-1'],
            'is_root_volume': True
        }
        self.logical_disks = ([self.root_logical_disk]
                              + self.nonroot_logical_disks)
        self.target_raid_configuration = {'logical_disks': self.logical_disks}
        self.node.target_raid_config = self.target_raid_configuration
        self.node.save()

        physical_disks = self._generate_physical_disks()
        mock_list_physical_disks.return_value = physical_disks

        mock_commit_config.side_effect = ['42', '12', '13']
        mock_client.create_virtual_disk.return_value = {
            'is_reboot_required': constants.RebootRequired.optional,
            'is_commit_required': True
        }

        with task_manager.acquire(self.context, self.node.uuid,
                                  shared=False) as task:
            task.driver.raid.create_configuration(
                task, create_root_volume=True, create_nonroot_volumes=True,
                delete_existing=False)

            mock_client.create_virtual_disk.assert_has_calls(
                [mock.call(
                    'RAID.Integrated.1-1',
                    ['Disk.Bay.4:Enclosure.Internal.0-1:RAID.Integrated.1-1',
                     'Disk.Bay.5:Enclosure.Internal.0-1:RAID.Integrated.1-1'],
                    '1', 571776, None, 2, 1),
                 mock.call(
                    'RAID.Integrated.1-1',
                    ['Disk.Bay.0:Enclosure.Internal.0-1:RAID.Integrated.1-1',
                     'Disk.Bay.1:Enclosure.Internal.0-1:RAID.Integrated.1-1',
                     'Disk.Bay.2:Enclosure.Internal.0-1:RAID.Integrated.1-1'],
                    '5', 102400, None, 3, 1),
                 mock.call(
                    'RAID.Integrated.1-1',
                    ['Disk.Bay.3:Enclosure.Internal.0-1:RAID.Integrated.1-1',
                     'Disk.Bay.6:Enclosure.Internal.0-1:RAID.Integrated.1-1',
                     'Disk.Bay.7:Enclosure.Internal.0-1:RAID.Integrated.1-1'],
                    '5', 102400, None, 3, 1)],
                any_order=True)

            # Commits to the controller
            mock_commit_config.assert_called_with(
                mock.ANY, raid_controller='RAID.Integrated.1-1', reboot=False,
                realtime=True)

        self.node.refresh()
        self.assertEqual(['42'],
                         self.node.driver_internal_info['raid_config_job_ids'])

    @mock.patch.object(drac_common, 'get_drac_client', spec_set=True,
                       autospec=True)
    @mock.patch.object(drac_raid, 'list_physical_disks', autospec=True)
    def test_create_configuration_with_max_size_without_backing_disks(
            self, mock_list_physical_disks, mock_get_drac_client):
        mock_client = mock.Mock()
        mock_get_drac_client.return_value = mock_client

        self.root_logical_disk = {
            'size_gb': 'MAX',
            'raid_level': '1',
            'is_root_volume': True
        }
        self.logical_disks = [self.root_logical_disk]
        self.target_raid_configuration = {'logical_disks': self.logical_disks}
        self.node.target_raid_config = self.target_raid_configuration
        self.node.save()

        self.physical_disks = self.physical_disks[0:2]
        physical_disks = self._generate_physical_disks()
        mock_list_physical_disks.return_value = physical_disks

        with task_manager.acquire(self.context, self.node.uuid,
                                  shared=False) as task:
            self.assertRaises(
                exception.InvalidParameterValue,
                task.driver.raid.create_configuration,
                task)

    @mock.patch.object(drac_common, 'get_drac_client', spec_set=True,
                       autospec=True)
    @mock.patch.object(drac_raid, 'list_physical_disks', autospec=True)
    @mock.patch.object(drac_job, 'validate_job_queue', spec_set=True,
                       autospec=True)
    @mock.patch.object(drac_raid, 'commit_config', spec_set=True,
                       autospec=True)
    def test_create_configuration_with_share_physical_disks(
            self, mock_commit_config, mock_validate_job_queue,
            mock_list_physical_disks, mock_get_drac_client):
        mock_client = mock.Mock()
        mock_get_drac_client.return_value = mock_client

        self.nonroot_logical_disks[0]['share_physical_disks'] = True
        self.nonroot_logical_disks[1]['share_physical_disks'] = True
        self.logical_disks = self.nonroot_logical_disks
        self.target_raid_configuration = {'logical_disks': self.logical_disks}
        self.node.target_raid_config = self.target_raid_configuration
        self.node.save()

        self.physical_disks = self.physical_disks[0:3]
        physical_disks = self._generate_physical_disks()
        mock_list_physical_disks.return_value = physical_disks

        mock_commit_config.side_effect = ['42', '12']
        mock_client.create_virtual_disk.return_value = {
            'is_reboot_required': constants.RebootRequired.optional,
            'is_commit_required': True
        }

        with task_manager.acquire(self.context, self.node.uuid,
                                  shared=False) as task:
            task.driver.raid.create_configuration(
                task, create_root_volume=True, create_nonroot_volumes=True,
                delete_existing=False)

            mock_client.create_virtual_disk.assert_has_calls(
                [mock.call(
                    'RAID.Integrated.1-1',
                    ['Disk.Bay.0:Enclosure.Internal.0-1:RAID.Integrated.1-1',
                     'Disk.Bay.1:Enclosure.Internal.0-1:RAID.Integrated.1-1',
                     'Disk.Bay.2:Enclosure.Internal.0-1:RAID.Integrated.1-1'],
                    '5', 102400, None, 3, 1),
                 mock.call(
                    'RAID.Integrated.1-1',
                    ['Disk.Bay.0:Enclosure.Internal.0-1:RAID.Integrated.1-1',
                     'Disk.Bay.1:Enclosure.Internal.0-1:RAID.Integrated.1-1',
                     'Disk.Bay.2:Enclosure.Internal.0-1:RAID.Integrated.1-1'],
                    '5', 102400, None, 3, 1)])

            # Commits to the controller
            mock_commit_config.assert_called_with(
                mock.ANY, raid_controller='RAID.Integrated.1-1', reboot=False,
                realtime=True)

        self.node.refresh()
        self.assertEqual(['42'],
                         self.node.driver_internal_info['raid_config_job_ids'])

    @mock.patch.object(drac_common, 'get_drac_client', spec_set=True,
                       autospec=True)
    @mock.patch.object(drac_raid, '_reset_raid_config', autospec=True)
    @mock.patch.object(drac_raid, 'list_physical_disks', autospec=True)
    @mock.patch.object(drac_job, 'validate_job_queue', spec_set=True,
                       autospec=True)
    @mock.patch.object(drac_raid, 'commit_config', spec_set=True,
                       autospec=True)
    def test_create_configuration_fails_with_sharing_disabled(
            self, mock_commit_config, mock_validate_job_queue,
            mock_list_physical_disks, mock__reset_raid_config,
            mock_get_drac_client):
        mock_client = mock.Mock()
        mock_get_drac_client.return_value = mock_client

        self.nonroot_logical_disks[0]['share_physical_disks'] = False
        self.nonroot_logical_disks[1]['share_physical_disks'] = False
        self.logical_disks = self.nonroot_logical_disks
        self.target_raid_configuration = {'logical_disks': self.logical_disks}
        self.node.target_raid_config = self.target_raid_configuration
        self.node.save()

        self.physical_disks = self.physical_disks[0:3]
        physical_disks = self._generate_physical_disks()
        mock_list_physical_disks.return_value = physical_disks
        raid_controller_dict = {
            'id': 'RAID.Integrated.1-1',
            'description': 'Integrated RAID Controller 1',
            'manufacturer': 'DELL',
            'model': 'PERC H710 Mini',
            'primary_status': 'ok',
            'firmware_version': '21.3.0-0009',
            'bus': '1',
            'supports_realtime': True}
        raid_controller = test_utils.make_raid_controller(
            raid_controller_dict)
        mock_client.list_raid_controllers.return_value = [raid_controller]
        mock_commit_config.return_value = '42'
        mock_client.create_virtual_disk.return_value = {
            'is_reboot_required': constants.RebootRequired.optional,
            'is_commit_required': True}

        with task_manager.acquire(self.context, self.node.uuid,
                                  shared=False) as task:
            self.assertRaises(
                exception.DracOperationError,
                task.driver.raid.create_configuration,
                task, create_root_volume=True, create_nonroot_volumes=True)

    @mock.patch.object(drac_common, 'get_drac_client', spec_set=True,
                       autospec=True)
    @mock.patch.object(drac_raid, 'list_physical_disks', autospec=True)
    @mock.patch.object(drac_job, 'validate_job_queue', spec_set=True,
                       autospec=True)
    @mock.patch.object(drac_raid, 'commit_config', spec_set=True,
                       autospec=True)
    def test_create_configuration_with_max_size_and_share_physical_disks(
            self, mock_commit_config, mock_validate_job_queue,
            mock_list_physical_disks,
            mock_get_drac_client):
        mock_client = mock.Mock()
        mock_get_drac_client.return_value = mock_client

        self.nonroot_logical_disks[0]['share_physical_disks'] = True
        self.nonroot_logical_disks[0]['size_gb'] = 'MAX'
        self.nonroot_logical_disks[0]['physical_disks'] = [
            'Disk.Bay.0:Enclosure.Internal.0-1:RAID.Integrated.1-1',
            'Disk.Bay.1:Enclosure.Internal.0-1:RAID.Integrated.1-1',
            'Disk.Bay.2:Enclosure.Internal.0-1:RAID.Integrated.1-1']
        self.nonroot_logical_disks[1]['share_physical_disks'] = True
        self.logical_disks = self.nonroot_logical_disks
        self.target_raid_configuration = {'logical_disks': self.logical_disks}
        self.node.target_raid_config = self.target_raid_configuration
        self.node.save()

        self.physical_disks = self.physical_disks[0:3]
        physical_disks = self._generate_physical_disks()
        mock_list_physical_disks.return_value = physical_disks

        mock_commit_config.return_value = '42'
        mock_client.create_virtual_disk.return_value = {
            'is_reboot_required': constants.RebootRequired.optional,
            'is_commit_required': True
        }

        with task_manager.acquire(self.context, self.node.uuid,
                                  shared=False) as task:
            task.driver.raid.create_configuration(
                task, create_root_volume=True, create_nonroot_volumes=True,
                delete_existing=False)

            mock_client.create_virtual_disk.assert_has_calls(
                [mock.call(
                    'RAID.Integrated.1-1',
                    ['Disk.Bay.0:Enclosure.Internal.0-1:RAID.Integrated.1-1',
                     'Disk.Bay.1:Enclosure.Internal.0-1:RAID.Integrated.1-1',
                     'Disk.Bay.2:Enclosure.Internal.0-1:RAID.Integrated.1-1'],
                    '5', 1041152, None, 3, 1),
                 mock.call(
                    'RAID.Integrated.1-1',
                    ['Disk.Bay.0:Enclosure.Internal.0-1:RAID.Integrated.1-1',
                     'Disk.Bay.1:Enclosure.Internal.0-1:RAID.Integrated.1-1',
                     'Disk.Bay.2:Enclosure.Internal.0-1:RAID.Integrated.1-1'],
                    '5', 102400, None, 3, 1)],
                any_order=True)

            # Commits to the controller
            mock_commit_config.assert_called_with(
                mock.ANY, raid_controller='RAID.Integrated.1-1', reboot=False,
                realtime=True)

        self.node.refresh()
        self.assertEqual(['42'],
                         self.node.driver_internal_info['raid_config_job_ids'])

    @mock.patch.object(drac_common, 'get_drac_client', spec_set=True,
                       autospec=True)
    @mock.patch.object(drac_raid, 'list_physical_disks', autospec=True)
    @mock.patch.object(drac_job, 'validate_job_queue', spec_set=True,
                       autospec=True)
    @mock.patch.object(drac_raid, 'commit_config', spec_set=True,
                       autospec=True)
    def test_create_configuration_with_multiple_max_and_sharing_same_disks(
            self, mock_commit_config, mock_validate_job_queue,
            mock_list_physical_disks, mock_get_drac_client):
        mock_client = mock.Mock()
        mock_get_drac_client.return_value = mock_client

        self.nonroot_logical_disks[0]['share_physical_disks'] = True
        self.nonroot_logical_disks[0]['size_gb'] = 'MAX'
        self.nonroot_logical_disks[0]['physical_disks'] = [
            'Disk.Bay.0:Enclosure.Internal.0-1:RAID.Integrated.1-1',
            'Disk.Bay.1:Enclosure.Internal.0-1:RAID.Integrated.1-1',
            'Disk.Bay.2:Enclosure.Internal.0-1:RAID.Integrated.1-1']
        self.nonroot_logical_disks[1]['share_physical_disks'] = True
        self.nonroot_logical_disks[1]['size_gb'] = 'MAX'
        self.nonroot_logical_disks[1]['physical_disks'] = [
            'Disk.Bay.0:Enclosure.Internal.0-1:RAID.Integrated.1-1',
            'Disk.Bay.1:Enclosure.Internal.0-1:RAID.Integrated.1-1',
            'Disk.Bay.2:Enclosure.Internal.0-1:RAID.Integrated.1-1']
        self.logical_disks = self.nonroot_logical_disks
        self.target_raid_configuration = {'logical_disks': self.logical_disks}
        self.node.target_raid_config = self.target_raid_configuration
        self.node.save()

        self.physical_disks = self.physical_disks[0:3]
        physical_disks = self._generate_physical_disks()
        mock_list_physical_disks.return_value = physical_disks

        mock_commit_config.return_value = '42'
        mock_client.create_virtual_disk.return_value = {
            'is_reboot_required': constants.RebootRequired.optional,
            'is_commit_required': True}

        with task_manager.acquire(self.context, self.node.uuid,
                                  shared=False) as task:
            self.assertRaises(
                exception.DracOperationError,
                task.driver.raid.create_configuration,
                task, create_root_volume=True, create_nonroot_volumes=True,
                delete_existing=False)

    @mock.patch.object(drac_common, 'get_drac_client', spec_set=True,
                       autospec=True)
    @mock.patch.object(drac_raid, '_reset_raid_config', autospec=True)
    @mock.patch.object(drac_raid, 'list_physical_disks', autospec=True)
    @mock.patch.object(drac_job, 'validate_job_queue', spec_set=True,
                       autospec=True)
    @mock.patch.object(drac_raid, 'commit_config', spec_set=True,
                       autospec=True)
    @mock.patch.object(drac_raid, 'create_virtual_disk', spec_set=True,
                       autospec=True)
    def test_create_configuration_fails_if_not_enough_space(
            self, mock_create_virtual_disk, mock_commit_config,
            mock_validate_job_queue, mock_list_physical_disks,
            mock__reset_raid_config, mock_get_drac_client):
        mock_client = mock.Mock()
        mock_get_drac_client.return_value = mock_client

        self.logical_disk = {
            'size_gb': 500,
            'raid_level': '1'
        }
        self.logical_disks = [self.logical_disk, self.logical_disk]
        self.target_raid_configuration = {'logical_disks': self.logical_disks}
        self.node.target_raid_config = self.target_raid_configuration
        self.node.save()

        self.physical_disks = self.physical_disks[0:3]
        physical_disks = self._generate_physical_disks()
        mock_list_physical_disks.return_value = physical_disks
        raid_controller_dict = {
            'id': 'RAID.Integrated.1-1',
            'description': 'Integrated RAID Controller 1',
            'manufacturer': 'DELL',
            'model': 'PERC H710 Mini',
            'primary_status': 'ok',
            'firmware_version': '21.3.0-0009',
            'bus': '1',
            'supports_realtime': True}
        raid_controller = test_utils.make_raid_controller(
            raid_controller_dict)
        mock_client.list_raid_controllers.return_value = [raid_controller]
        mock__reset_raid_config.return_value = {
            'is_reboot_required': constants.RebootRequired.optional,
            'is_commit_required': True}

        mock_commit_config.return_value = '42'
        mock_create_virtual_disk.return_value = {
            'is_reboot_required': constants.RebootRequired.optional,
            'is_commit_required': True}

        with task_manager.acquire(self.context, self.node.uuid,
                                  shared=False) as task:
            self.assertRaises(
                exception.DracOperationError,
                task.driver.raid.create_configuration,
                task, create_root_volume=True, create_nonroot_volumes=True)

    @mock.patch.object(drac_common, 'get_drac_client', spec_set=True,
                       autospec=True)
    @mock.patch.object(drac_raid, '_reset_raid_config', spec_set=True,
                       autospec=True)
    @mock.patch.object(drac_raid, 'list_physical_disks', autospec=True)
    @mock.patch.object(drac_job, 'validate_job_queue', spec_set=True,
                       autospec=True)
    @mock.patch.object(drac_raid, 'commit_config', spec_set=True,
                       autospec=True)
    @mock.patch.object(drac_raid, 'create_virtual_disk', spec_set=True,
                       autospec=True)
    def test_create_configuration_fails_if_disk_already_reserved(
            self, mock_create_virtual_disk, mock_commit_config,
            mock_validate_job_queue, mock_list_physical_disks,
            mock__reset_raid_config, mock_get_drac_client):
        mock_client = mock.Mock()
        mock_get_drac_client.return_value = mock_client

        self.logical_disk = {
            'size_gb': 500,
            'raid_level': '1',
            'physical_disks': [
                'Disk.Bay.4:Enclosure.Internal.0-1:RAID.Integrated.1-1',
                'Disk.Bay.5:Enclosure.Internal.0-1:RAID.Integrated.1-1'],
        }
        self.logical_disks = [self.logical_disk, self.logical_disk.copy()]
        self.target_raid_configuration = {'logical_disks': self.logical_disks}
        self.node.target_raid_config = self.target_raid_configuration
        self.node.save()

        physical_disks = self._generate_physical_disks()
        mock_list_physical_disks.return_value = physical_disks

        raid_controller_dict = {
            'id': 'RAID.Integrated.1-1',
            'description': 'Integrated RAID Controller 1',
            'manufacturer': 'DELL',
            'model': 'PERC H710 Mini',
            'primary_status': 'ok',
            'firmware_version': '21.3.0-0009',
            'bus': '1',
            'supports_realtime': True}
        raid_controller = test_utils.make_raid_controller(
            raid_controller_dict)
        mock_client.list_raid_controllers.return_value = [raid_controller]

        mock_commit_config.return_value = '42'
        mock__reset_raid_config.return_value = {
            'is_reboot_required': constants.RebootRequired.optional,
            'is_commit_required': True}

        mock_create_virtual_disk.return_value = {
            'is_reboot_required': constants.RebootRequired.optional,
            'is_commit_required': True}

        with task_manager.acquire(self.context, self.node.uuid,
                                  shared=False) as task:
            self.assertRaises(
                exception.DracOperationError,
                task.driver.raid.create_configuration,
                task, create_root_volume=True, create_nonroot_volumes=True)

    @mock.patch.object(drac_common, 'get_drac_client', spec_set=True,
                       autospec=True)
    @mock.patch.object(drac_raid, '_reset_raid_config', autospec=True)
    @mock.patch.object(drac_raid, 'list_raid_controllers', autospec=True)
    @mock.patch.object(drac_job, 'validate_job_queue', spec_set=True,
                       autospec=True)
    @mock.patch.object(drac_raid, 'commit_config', spec_set=True,
                       autospec=True)
    def _test_delete_configuration(self, expected_state,
                                   mock_commit_config,
                                   mock_validate_job_queue,
                                   mock_list_raid_controllers,
                                   mock__reset_raid_config,
                                   mock_get_drac_client):
        mock_client = mock.Mock()
        mock_get_drac_client.return_value = mock_client
        raid_controller_dict = {
            'id': 'RAID.Integrated.1-1',
            'description': 'Integrated RAID Controller 1',
            'manufacturer': 'DELL',
            'model': 'PERC H710 Mini',
            'primary_status': 'ok',
            'firmware_version': '21.3.0-0009',
            'bus': '1',
            'supports_realtime': True}

        mock_list_raid_controllers.return_value = [
            test_utils.make_raid_controller(raid_controller_dict)]
        mock_commit_config.return_value = '42'
        mock__reset_raid_config.return_value = {
            'is_reboot_required': constants.RebootRequired.optional,
            'is_commit_required': True}

        with task_manager.acquire(self.context, self.node.uuid,
                                  shared=False) as task:
            return_value = task.driver.raid.delete_configuration(task)

            mock_commit_config.assert_called_once_with(
                task.node, raid_controller='RAID.Integrated.1-1', reboot=False,
                realtime=True)

        self.assertEqual(expected_state, return_value)
        self.node.refresh()
        self.assertEqual(['42'],
                         self.node.driver_internal_info['raid_config_job_ids'])

    def test_delete_configuration_in_clean(self):
        self._test_delete_configuration(states.CLEANWAIT)

    def test_delete_configuration_in_deploy(self):
        self.node.clean_step = None
        self.node.save()
        self._test_delete_configuration(states.DEPLOYWAIT)

    @mock.patch.object(drac_common, 'get_drac_client', spec_set=True,
                       autospec=True)
    @mock.patch.object(drac_raid, 'list_raid_controllers', autospec=True)
    @mock.patch.object(drac_job, 'validate_job_queue', spec_set=True,
                       autospec=True)
    @mock.patch.object(drac_raid, 'commit_config', spec_set=True,
                       autospec=True)
    def test_delete_configuration_no_change(self, mock_commit_config,
                                            mock_validate_job_queue,
                                            mock_list_raid_controllers,
                                            mock_get_drac_client):
        mock_client = mock.Mock()
        mock_get_drac_client.return_value = mock_client
        mock_list_raid_controllers.return_value = []

        with task_manager.acquire(self.context, self.node.uuid,
                                  shared=False) as task:
            return_value = task.driver.raid.delete_configuration(task)

            self.assertEqual(0, mock_client._reset_raid_config.call_count)
            self.assertEqual(0, mock_commit_config.call_count)

        self.assertIsNone(return_value)

        self.node.refresh()
        self.assertNotIn('raid_config_job_ids', self.node.driver_internal_info)

    @mock.patch.object(drac_raid, 'list_virtual_disks', autospec=True)
    def test_get_logical_disks(self, mock_list_virtual_disks):
        virtual_disk_dict = {
            'id': 'Disk.Virtual.0:RAID.Integrated.1-1',
            'name': 'disk 0',
            'description': 'Virtual Disk 0 on Integrated RAID Controller 1',
            'controller': 'RAID.Integrated.1-1',
            'raid_level': '1',
            'size_mb': 571776,
            'status': 'ok',
            'raid_status': 'online',
            'span_depth': 1,
            'span_length': 2,
            'pending_operations': None,
            'physical_disks': []}
        mock_list_virtual_disks.return_value = [
            test_utils.make_virtual_disk(virtual_disk_dict)]
        expected_logical_disk = {'id': 'Disk.Virtual.0:RAID.Integrated.1-1',
                                 'size_gb': 558,
                                 'raid_level': '1',
                                 'name': 'disk 0',
                                 'controller': 'RAID.Integrated.1-1'}

        with task_manager.acquire(self.context, self.node.uuid,
                                  shared=False) as task:
            props = task.driver.raid.get_logical_disks(task)

        self.assertEqual({'logical_disks': [expected_logical_disk]},
                         props)

    @mock.patch.object(drac_common, 'get_drac_client', spec_set=True,
                       autospec=True)
    @mock.patch.object(conductor_utils, '_notify_conductor_resume_operation',
                       autospec=True)
    @mock.patch.object(drac_raid, 'clear_foreign_config', spec_set=True,
                       autospec=True)
    @mock.patch.object(drac_raid, 'list_virtual_disks', autospec=True)
    @mock.patch.object(drac_job, 'validate_job_queue', spec_set=True,
                       autospec=True)
    def test__execute_cleaning_foreign_drives(self,
                                              mock_validate_job_queue,
                                              mock_list_virtual_disks,
                                              mock_clear_foreign_config,
                                              mock_resume,
                                              mock_get_drac_client):
        mock_client = mock.Mock()
        mock_get_drac_client.return_value = mock_client
        virtual_disk_dict = {
            'id': 'Disk.Virtual.0:RAID.Integrated.1-1',
            'name': 'disk 0',
            'description': 'Virtual Disk 0 on Integrated RAID Controller 1',
            'controller': 'RAID.Integrated.1-1',
            'raid_level': '1',
            'size_mb': 571776,
            'status': 'ok',
            'raid_status': 'online',
            'span_depth': 1,
            'span_length': 2,
            'pending_operations': None,
            'physical_disks': []}
        mock_list_virtual_disks.return_value = [
            test_utils.make_virtual_disk(virtual_disk_dict)]

        raid_config_params = ['RAID.Integrated.1-1']
        raid_config_substep = ['completed']
        driver_internal_info = self.node.driver_internal_info
        driver_internal_info['raid_config_parameters'] = raid_config_params
        driver_internal_info['raid_config_substep'] = raid_config_substep
        self.node.driver_internal_info = driver_internal_info
        self.node.save()
        mock_clear_foreign_config.return_value = {
            'is_reboot_required': constants.RebootRequired.false,
            'is_commit_required': False
        }

        with task_manager.acquire(self.context, self.node.uuid,
                                  shared=False) as task:
            return_value = task.driver.raid._execute_foreign_drives(
                task, self.node)
            mock_resume.assert_called_once_with(
                task, 'cleaning', 'continue_node_clean')

        self.assertIsNone(return_value)
        self.assertNotIn('raid_config_parameters',
                         self.node.driver_internal_info)
        self.assertNotIn('raid_config_substep',
                         self.node.driver_internal_info)
