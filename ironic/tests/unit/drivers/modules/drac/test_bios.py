# -*- coding: utf-8 -*-
#
# Copyright (c) 2015-2016 Dell Inc. or its subsidiaries.
# All Rights Reserved.
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

"""
Test class for DRAC BIOS configuration specific methods
"""

from dracclient import exceptions as drac_exceptions
import mock

from ironic.common import exception
from ironic.common import states
from ironic.conductor import task_manager
from ironic.drivers.modules.drac import bios as drac_bios
from ironic.drivers.modules.drac import common as drac_common
from ironic.drivers.modules.drac import job as drac_job
from ironic.tests.unit.db import utils as db_utils
from ironic.tests.unit.drivers.modules.drac import utils as test_utils
from ironic.tests.unit.objects import utils as obj_utils

INFO_DICT = test_utils.INFO_DICT


class DracBIOSConfigurationTestCase(test_utils.BaseDracTest):

    def setUp(self):
        super(DracBIOSConfigurationTestCase, self).setUp()
        self.node = obj_utils.create_test_node(self.context,
                                               driver='idrac',
                                               driver_info=INFO_DICT)

        patch_get_drac_client = mock.patch.object(
            drac_common, 'get_drac_client', spec_set=True, autospec=True)
        mock_get_drac_client = patch_get_drac_client.start()
        self.mock_client = mock.Mock()
        mock_get_drac_client.return_value = self.mock_client
        self.addCleanup(patch_get_drac_client.stop)

        proc_virt_attr = {
            'current_value': 'Enabled',
            'pending_value': None,
            'read_only': False,
            'possible_values': ['Enabled', 'Disabled']}
        mock_proc_virt_attr = mock.NonCallableMock(spec=[], **proc_virt_attr)
        mock_proc_virt_attr.name = 'ProcVirtualization'
        self.bios_attrs = {'ProcVirtualization': mock_proc_virt_attr}

    def test_get_config(self):
        self.mock_client.list_bios_settings.return_value = self.bios_attrs

        with task_manager.acquire(self.context, self.node.uuid,
                                  shared=True) as task:
            bios_config = task.driver.vendor.get_bios_config(task)

        self.mock_client.list_bios_settings.assert_called_once_with()
        self.assertIn('ProcVirtualization', bios_config)

    def test_get_config_fail(self):
        exc = drac_exceptions.BaseClientException('boom')
        self.mock_client.list_bios_settings.side_effect = exc

        with task_manager.acquire(self.context, self.node.uuid,
                                  shared=True) as task:
            self.assertRaises(exception.DracOperationError,
                              task.driver.vendor.get_bios_config, task)

        self.mock_client.list_bios_settings.assert_called_once_with()

    def test_set_config(self):
        self.mock_client.list_jobs.return_value = []

        with task_manager.acquire(self.context, self.node.uuid,
                                  shared=False) as task:
            task.driver.vendor.set_bios_config(task,
                                               ProcVirtualization='Enabled')

        self.mock_client.list_jobs.assert_called_once_with(
            only_unfinished=True)
        self.mock_client.set_bios_settings.assert_called_once_with(
            {'ProcVirtualization': 'Enabled'})

    def test_set_config_fail(self):
        self.mock_client.list_jobs.return_value = []
        exc = drac_exceptions.BaseClientException('boom')
        self.mock_client.set_bios_settings.side_effect = exc

        with task_manager.acquire(self.context, self.node.uuid,
                                  shared=False) as task:
            self.assertRaises(exception.DracOperationError,
                              task.driver.vendor.set_bios_config, task,
                              ProcVirtualization='Enabled')

        self.mock_client.set_bios_settings.assert_called_once_with(
            {'ProcVirtualization': 'Enabled'})

    def test_commit_config(self):
        self.mock_client.list_jobs.return_value = []

        with task_manager.acquire(self.context, self.node.uuid,
                                  shared=False) as task:
            task.driver.vendor.commit_bios_config(task)

        self.mock_client.list_jobs.assert_called_once_with(
            only_unfinished=True)
        self.mock_client.commit_pending_bios_changes.assert_called_once_with(
            False)

    def test_commit_config_with_reboot(self):
        self.mock_client.list_jobs.return_value = []

        with task_manager.acquire(self.context, self.node.uuid,
                                  shared=False) as task:
            task.driver.vendor.commit_bios_config(task, reboot=True)

        self.mock_client.list_jobs.assert_called_once_with(
            only_unfinished=True)
        self.mock_client.commit_pending_bios_changes.assert_called_once_with(
            True)

    def test_commit_config_fail(self):
        self.mock_client.list_jobs.return_value = []
        exc = drac_exceptions.BaseClientException('boom')
        self.mock_client.commit_pending_bios_changes.side_effect = exc

        with task_manager.acquire(self.context, self.node.uuid,
                                  shared=False) as task:
            self.assertRaises(exception.DracOperationError,
                              task.driver.vendor.commit_bios_config, task)

        self.mock_client.list_jobs.assert_called_once_with(
            only_unfinished=True)
        self.mock_client.commit_pending_bios_changes.assert_called_once_with(
            False)

    def test_abandon_config(self):
        with task_manager.acquire(self.context, self.node.uuid,
                                  shared=False) as task:
            task.driver.vendor.abandon_bios_config(task)

        self.mock_client.abandon_pending_bios_changes.assert_called_once_with()

    def test_abandon_config_fail(self):
        exc = drac_exceptions.BaseClientException('boom')
        self.mock_client.abandon_pending_bios_changes.side_effect = exc

        with task_manager.acquire(self.context, self.node.uuid,
                                  shared=False) as task:
            self.assertRaises(exception.DracOperationError,
                              task.driver.vendor.abandon_bios_config, task)

        self.mock_client.abandon_pending_bios_changes.assert_called_once_with()


class DracBIOSInterfaceTestCase(test_utils.BaseDracTest):

    def setUp(self):
        super(DracBIOSInterfaceTestCase, self).setUp()
        self.node = obj_utils.create_test_node(self.context,
                                               driver='idrac',
                                               driver_info=INFO_DICT)

        self.node.clean_step = {'foo': 'bar'}
        self.node.save()

        self.bios_attrs = {
            'ProcVirtualization': {
                'current_value': 'Enabled',
                'pending_value': None,
                'read_only': False,
                'possible_values': ['Enabled', 'Disabled']
            }
        }

    @mock.patch.object(drac_common, 'get_drac_client', spec_set=True,
                       autospec=True)
    @mock.patch.object(drac_job, 'validate_job_queue', spec_set=True,
                       autospec=True)
    @mock.patch.object(drac_bios, 'get_config', spec_set=True, autospec=True)
    @mock.patch.object(drac_bios, 'commit_config', spec_set=True,
                       autospec=True)
    def _test_apply_configuration(
            self, expected_state, mock_commit_config, mock_get_config,
            mock_validate_job_queue, mock_get_drac_client):
        mock_client = mock.Mock()
        mock_get_drac_client.return_value = mock_client
        mock_get_config.return_value = self.bios_attrs
        mock_commit_config.return_value = '42'

        settings = db_utils.get_test_bios_setting_setting_list()

        with task_manager.acquire(self.context, self.node.uuid,
                                  shared=False) as task:
            return_value = task.driver.bios.apply_configuration(
                task, settings)

            mock_client.set_bios_settings.assert_called_once_with(
                {s['name']: s['value'] for s in settings})
            mock_commit_config.assert_called_once_with(task.node, reboot=True)

        self.assertEqual(expected_state, return_value)
        self.node.refresh()
        self.assertEqual(['42'],
                         self.node.driver_internal_info['bios_config_job_ids'])

    def test_apply_configuration_in_clean(self):
        self._test_apply_configuration(states.CLEANWAIT)

    def test_apply_configuration_in_deploy(self):
        self.node.clean_step = None
        self.node.save()
        self._test_apply_configuration(states.DEPLOYWAIT)

#    @mock.patch.object(drac_common, 'get_drac_client', spec_set=True,
#                       autospec=True)
#    @mock.patch.object(drac_bios, 'list_physical_disks', autospec=True)
#    @mock.patch.object(drac_job, 'validate_job_queue', spec_set=True,
#                       autospec=True)
#    @mock.patch.object(drac_bios, 'commit_config', spec_set=True,
#                       autospec=True)
#    def test_create_configuration_no_change(
#            self, mock_commit_config, mock_validate_job_queue,
#            mock_list_physical_disks, mock_get_drac_client):
#        mock_client = mock.Mock()
#        mock_get_drac_client.return_value = mock_client
#        physical_disks = self._generate_physical_disks()
#        mock_list_physical_disks.return_value = physical_disks
#
#        with task_manager.acquire(self.context, self.node.uuid,
#                                  shared=False) as task:
#            return_value = task.driver.bios.create_configuration(
#                task, create_root_volume=False, create_nonroot_volumes=False)
#
#            self.assertEqual(0, mock_client.create_virtual_disk.call_count)
#            self.assertEqual(0, mock_commit_config.call_count)
#
#        self.assertIsNone(return_value)
#
#        self.node.refresh()
#        self.assertNotIn('bios_config_job_ids',
#        self.node.driver_internal_info)
#
#    @mock.patch.object(drac_common, 'get_drac_client', spec_set=True,
#                       autospec=True)
#    @mock.patch.object(drac_bios, 'list_physical_disks', autospec=True)
#    @mock.patch.object(drac_job, 'validate_job_queue', spec_set=True,
#                       autospec=True)
#    @mock.patch.object(drac_bios, 'commit_config', spec_set=True,
#                       autospec=True)
#    def test_create_configuration_with_nested_raid_level(
#            self, mock_commit_config, mock_validate_job_queue,
#            mock_list_physical_disks, mock_get_drac_client):
#        mock_client = mock.Mock()
#        mock_get_drac_client.return_value = mock_client
#
#        self.root_logical_disk = {
#            'size_gb': 100,
#            'raid_level': '5+0',
#            'is_root_volume': True
#        }
#        self.logical_disks = [self.root_logical_disk]
#        self.target_raid_configuration = {'logical_disks': self.logical_disks}
#        self.node.target_raid_config = self.target_raid_configuration
#        self.node.save()
#
#        physical_disks = self._generate_physical_disks()
#        mock_list_physical_disks.return_value = physical_disks
#
#        mock_commit_config.return_value = '42'
#
#        with task_manager.acquire(self.context, self.node.uuid,
#                                  shared=False) as task:
#            task.driver.bios.create_configuration(
#                task, create_root_volume=True, create_nonroot_volumes=True)
#
#            mock_client.create_virtual_disk.assert_called_once_with(
#                'RAID.Integrated.1-1',
#                ['Disk.Bay.0:Enclosure.Internal.0-1:RAID.Integrated.1-1',
#                 'Disk.Bay.1:Enclosure.Internal.0-1:RAID.Integrated.1-1',
#                 'Disk.Bay.2:Enclosure.Internal.0-1:RAID.Integrated.1-1',
#                 'Disk.Bay.3:Enclosure.Internal.0-1:RAID.Integrated.1-1',
#                 'Disk.Bay.4:Enclosure.Internal.0-1:RAID.Integrated.1-1',
#                 'Disk.Bay.5:Enclosure.Internal.0-1:RAID.Integrated.1-1'],
#                '5+0', 102400, None, 3, 2)
#
#            # Commits to the controller
#            mock_commit_config.assert_called_once_with(
#                mock.ANY, bios_controller='RAID.Integrated.1-1', reboot=True)
#
#        self.node.refresh()
#        self.assertEqual(['42'],
#                         self.node.driver_internal_info['bios_config_job_ids'])
#
#    @mock.patch.object(drac_common, 'get_drac_client', spec_set=True,
#                       autospec=True)
#    @mock.patch.object(drac_bios, 'list_physical_disks', autospec=True)
#    @mock.patch.object(drac_job, 'validate_job_queue', spec_set=True,
#                       autospec=True)
#    @mock.patch.object(drac_bios, 'commit_config', spec_set=True,
#                       autospec=True)
#    def test_create_configuration_with_nested_raid_10(
#            self, mock_commit_config, mock_validate_job_queue,
#            mock_list_physical_disks, mock_get_drac_client):
#        mock_client = mock.Mock()
#        mock_get_drac_client.return_value = mock_client
#
#        self.root_logical_disk = {
#            'size_gb': 100,
#            'raid_level': '1+0',
#            'is_root_volume': True
#        }
#        self.logical_disks = [self.root_logical_disk]
#        self.target_raid_configuration = {'logical_disks': self.logical_disks}
#        self.node.target_raid_config = self.target_raid_configuration
#        self.node.save()
#
#        physical_disks = self._generate_physical_disks()
#        mock_list_physical_disks.return_value = physical_disks
#
#        mock_commit_config.return_value = '42'
#
#        with task_manager.acquire(self.context, self.node.uuid,
#                                  shared=False) as task:
#            task.driver.bios.create_configuration(
#                task, create_root_volume=True, create_nonroot_volumes=True)
#
#            mock_client.create_virtual_disk.assert_called_once_with(
#                'RAID.Integrated.1-1',
#                ['Disk.Bay.0:Enclosure.Internal.0-1:RAID.Integrated.1-1',
#                 'Disk.Bay.1:Enclosure.Internal.0-1:RAID.Integrated.1-1',
#                 'Disk.Bay.2:Enclosure.Internal.0-1:RAID.Integrated.1-1',
#                 'Disk.Bay.3:Enclosure.Internal.0-1:RAID.Integrated.1-1'],
#                '1+0', 102400, None, None, None)
#
#            # Commits to the controller
#            mock_commit_config.assert_called_once_with(
#                mock.ANY, bios_controller='RAID.Integrated.1-1', reboot=True)
#
#        self.node.refresh()
#        self.assertEqual(['42'],
#                         self.node.driver_internal_info['bios_config_job_ids'])
#
#    @mock.patch.object(drac_common, 'get_drac_client', spec_set=True,
#                       autospec=True)
#    @mock.patch.object(drac_bios, 'list_physical_disks', autospec=True)
#    @mock.patch.object(drac_job, 'validate_job_queue', spec_set=True,
#                       autospec=True)
#    @mock.patch.object(drac_bios, 'commit_config', spec_set=True,
#                       autospec=True)
#    def test_create_configuration_with_multiple_controllers(
#            self, mock_commit_config, mock_validate_job_queue,
#            mock_list_physical_disks, mock_get_drac_client):
#        mock_client = mock.Mock()
#        mock_get_drac_client.return_value = mock_client
#
#        self.physical_disks[0]['controller'] = 'controller-2'
#        self.physical_disks[1]['controller'] = 'controller-2'
#        physical_disks = self._generate_physical_disks()
#        mock_list_physical_disks.return_value = physical_disks
#
#        mock_commit_config.side_effect = ['42', '12']
#
#        with task_manager.acquire(self.context, self.node.uuid,
#                                  shared=False) as task:
#            task.driver.bios.create_configuration(
#                task, create_root_volume=True, create_nonroot_volumes=True)
#
#            mock_client.create_virtual_disk.assert_has_calls(
#                [mock.call(
#                    'controller-2',
#                    ['Disk.Bay.0:Enclosure.Internal.0-1:RAID.Integrated.1-1',
#                     'Disk.Bay.1:Enclosure.Internal.0-1:RAID.Integrated.1-1'],
#                    '1', 51200, None, 2, 1),
#                 mock.call(
#                    'RAID.Integrated.1-1',
#                    ['Disk.Bay.2:Enclosure.Internal.0-1:RAID.Integrated.1-1',
#                     'Disk.Bay.3:Enclosure.Internal.0-1:RAID.Integrated.1-1',
#                     'Disk.Bay.4:Enclosure.Internal.0-1:RAID.Integrated.1-1'],
#                    '5', 102400, None, 3, 1),
#                 mock.call(
#                    'RAID.Integrated.1-1',
#                    ['Disk.Bay.5:Enclosure.Internal.0-1:RAID.Integrated.1-1',
#                     'Disk.Bay.6:Enclosure.Internal.0-1:RAID.Integrated.1-1',
#                     'Disk.Bay.7:Enclosure.Internal.0-1:RAID.Integrated.1-1'],
#                    '5', 102400, None, 3, 1)
#                 ],
#                any_order=True)
#            # Commits to both controller
#            mock_commit_config.assert_has_calls(
#                [mock.call(mock.ANY, raid_controller='controller-2',
#                           reboot=mock.ANY),
#                 mock.call(mock.ANY, raid_controller='RAID.Integrated.1-1',
#                           reboot=mock.ANY)],
#                any_order=True)
#            # One of the config jobs should issue a reboot
#            mock_commit_config.assert_has_calls(
#                [mock.call(mock.ANY, raid_controller=mock.ANY,
#                           reboot=False),
#                 mock.call(mock.ANY, raid_controller=mock.ANY,
#                           reboot=True)],
#                any_order=True)
#
#        self.node.refresh()
#        self.assertEqual(['42', '12'],
#                         self.node.driver_internal_info['bios_config_job_ids'])
#
#    @mock.patch.object(drac_common, 'get_drac_client', spec_set=True,
#                       autospec=True)
#    @mock.patch.object(drac_bios, 'list_physical_disks', autospec=True)
#    @mock.patch.object(drac_job, 'validate_job_queue', spec_set=True,
#                       autospec=True)
#    @mock.patch.object(drac_bios, 'commit_config', spec_set=True,
#                       autospec=True)
#    def test_create_configuration_with_backing_physical_disks(
#            self, mock_commit_config, mock_validate_job_queue,
#            mock_list_physical_disks, mock_get_drac_client):
#        mock_client = mock.Mock()
#        mock_get_drac_client.return_value = mock_client
#
#        self.root_logical_disk['physical_disks'] = [
#            'Disk.Bay.3:Enclosure.Internal.0-1:RAID.Integrated.1-1',
#            'Disk.Bay.4:Enclosure.Internal.0-1:RAID.Integrated.1-1']
#        self.logical_disks = (
#            [self.root_logical_disk] + self.nonroot_logical_disks)
#        self.target_raid_configuration = {'logical_disks': self.logical_disks}
#        self.node.target_raid_config = self.target_raid_configuration
#        self.node.save()
#
#        physical_disks = self._generate_physical_disks()
#        mock_list_physical_disks.return_value = physical_disks
#
#        mock_commit_config.return_value = '42'
#
#        with task_manager.acquire(self.context, self.node.uuid,
#                                  shared=False) as task:
#            task.driver.bios.create_configuration(
#                task, create_root_volume=True, create_nonroot_volumes=True)
#
#            mock_client.create_virtual_disk.assert_has_calls(
#                [mock.call(
#                    'RAID.Integrated.1-1',
#                    ['Disk.Bay.3:Enclosure.Internal.0-1:RAID.Integrated.1-1',
#                     'Disk.Bay.4:Enclosure.Internal.0-1:RAID.Integrated.1-1'],
#                    '1', 51200, None, 2, 1),
#                 mock.call(
#                    'RAID.Integrated.1-1',
#                    ['Disk.Bay.0:Enclosure.Internal.0-1:RAID.Integrated.1-1',
#                     'Disk.Bay.1:Enclosure.Internal.0-1:RAID.Integrated.1-1',
#                     'Disk.Bay.2:Enclosure.Internal.0-1:RAID.Integrated.1-1'],
#                    '5', 102400, None, 3, 1),
#                 mock.call(
#                    'RAID.Integrated.1-1',
#                    ['Disk.Bay.5:Enclosure.Internal.0-1:RAID.Integrated.1-1',
#                     'Disk.Bay.6:Enclosure.Internal.0-1:RAID.Integrated.1-1',
#                     'Disk.Bay.7:Enclosure.Internal.0-1:RAID.Integrated.1-1'],
#                    '5', 102400, None, 3, 1)],
#                any_order=True)
#
#            # Commits to the controller
#            mock_commit_config.assert_called_once_with(
#                mock.ANY, raid_controller='RAID.Integrated.1-1', reboot=True)
#
#        self.node.refresh()
#        self.assertEqual(['42'],
#                         self.node.driver_internal_info['bios_config_job_ids'])
#
#    @mock.patch.object(drac_common, 'get_drac_client', spec_set=True,
#                       autospec=True)
#    @mock.patch.object(drac_bios, 'list_physical_disks', autospec=True)
#    @mock.patch.object(drac_job, 'validate_job_queue', spec_set=True,
#                       autospec=True)
#    @mock.patch.object(drac_bios, 'commit_config', spec_set=True,
#                       autospec=True)
#    def test_create_configuration_with_predefined_number_of_phyisical_disks(
#            self, mock_commit_config, mock_validate_job_queue,
#            mock_list_physical_disks, mock_get_drac_client):
#        mock_client = mock.Mock()
#        mock_get_drac_client.return_value = mock_client
#
#        self.root_logical_disk['raid_level'] = '0'
#        self.root_logical_disk['number_of_physical_disks'] = 3
#        self.logical_disks = (
#            [self.root_logical_disk, self.nonroot_logical_disks[0]])
#        self.target_bios_configuration = {'logical_disks': self.logical_disks}
#        self.node.target_raid_config = self.target_raid_configuration
#        self.node.save()
#
#        physical_disks = self._generate_physical_disks()
#        mock_list_physical_disks.return_value = physical_disks
#
#        mock_commit_config.return_value = '42'
#
#        with task_manager.acquire(self.context, self.node.uuid,
#                                  shared=False) as task:
#            task.driver.bios.create_configuration(
#                task, create_root_volume=True, create_nonroot_volumes=True)
#
#            mock_client.create_virtual_disk.assert_has_calls(
#                [mock.call(
#                    'RAID.Integrated.1-1',
#                    ['Disk.Bay.0:Enclosure.Internal.0-1:RAID.Integrated.1-1',
#                     'Disk.Bay.1:Enclosure.Internal.0-1:RAID.Integrated.1-1',
#                     'Disk.Bay.2:Enclosure.Internal.0-1:RAID.Integrated.1-1'],
#                    '0', 51200, None, 3, 1),
#                 mock.call(
#                    'RAID.Integrated.1-1',
#                    ['Disk.Bay.3:Enclosure.Internal.0-1:RAID.Integrated.1-1',
#                     'Disk.Bay.4:Enclosure.Internal.0-1:RAID.Integrated.1-1',
#                     'Disk.Bay.5:Enclosure.Internal.0-1:RAID.Integrated.1-1'],
#                    '5', 102400, None, 3, 1)],
#                any_order=True)
#
#            # Commits to the controller
#            mock_commit_config.assert_called_once_with(
#                mock.ANY, raid_controller='RAID.Integrated.1-1', reboot=True)
#
#        self.node.refresh()
#        self.assertEqual(['42'],
#                         self.node.driver_internal_info['bios_config_job_ids'])
#
#    @mock.patch.object(drac_common, 'get_drac_client', spec_set=True,
#                       autospec=True)
#    @mock.patch.object(drac_bios, 'list_physical_disks', autospec=True)
#    @mock.patch.object(drac_job, 'validate_job_queue', spec_set=True,
#                       autospec=True)
#    @mock.patch.object(drac_bios, 'commit_config', spec_set=True,
#                       autospec=True)
#    def test_create_configuration_with_max_size(
#            self, mock_commit_config, mock_validate_job_queue,
#            mock_list_physical_disks, mock_get_drac_client):
#        mock_client = mock.Mock()
#        mock_get_drac_client.return_value = mock_client
#
#        self.root_logical_disk = {
#            'size_gb': 'MAX',
#            'raid_level': '1',
#            'physical_disks': [
#                'Disk.Bay.4:Enclosure.Internal.0-1:RAID.Integrated.1-1',
#                'Disk.Bay.5:Enclosure.Internal.0-1:RAID.Integrated.1-1'],
#            'is_root_volume': True
#        }
#        self.logical_disks = ([self.root_logical_disk]
#                              + self.nonroot_logical_disks)
#        self.target_raid_configuration = {'logical_disks': self.logical_disks}
#        self.node.target_raid_config = self.target_raid_configuration
#        self.node.save()
#
#        physical_disks = self._generate_physical_disks()
#        mock_list_physical_disks.return_value = physical_disks
#
#        mock_commit_config.return_value = '42'
#
#        with task_manager.acquire(self.context, self.node.uuid,
#                                  shared=False) as task:
#            task.driver.bios.create_configuration(
#                task, create_root_volume=True, create_nonroot_volumes=True)
#
#            mock_client.create_virtual_disk.assert_has_calls(
#                [mock.call(
#                    'RAID.Integrated.1-1',
#                    ['Disk.Bay.4:Enclosure.Internal.0-1:RAID.Integrated.1-1',
#                     'Disk.Bay.5:Enclosure.Internal.0-1:RAID.Integrated.1-1'],
#                    '1', 571776, None, 2, 1),
#                 mock.call(
#                    'RAID.Integrated.1-1',
#                    ['Disk.Bay.0:Enclosure.Internal.0-1:RAID.Integrated.1-1',
#                     'Disk.Bay.1:Enclosure.Internal.0-1:RAID.Integrated.1-1',
#                     'Disk.Bay.2:Enclosure.Internal.0-1:RAID.Integrated.1-1'],
#                    '5', 102400, None, 3, 1),
#                 mock.call(
#                    'RAID.Integrated.1-1',
#                    ['Disk.Bay.3:Enclosure.Internal.0-1:RAID.Integrated.1-1',
#                     'Disk.Bay.6:Enclosure.Internal.0-1:RAID.Integrated.1-1',
#                     'Disk.Bay.7:Enclosure.Internal.0-1:RAID.Integrated.1-1'],
#                    '5', 102400, None, 3, 1)],
#                any_order=True)
#
#            # Commits to the controller
#            mock_commit_config.assert_called_once_with(
#                mock.ANY, raid_controller='RAID.Integrated.1-1', reboot=True)
#
#        self.node.refresh()
#        self.assertEqual(['42'],
#                         self.node.driver_internal_info['bios_config_job_ids'])
#
#    @mock.patch.object(drac_common, 'get_drac_client', spec_set=True,
#                       autospec=True)
#    @mock.patch.object(drac_bios, 'list_physical_disks', autospec=True)
#    def test_create_configuration_with_max_size_without_backing_disks(
#            self, mock_list_physical_disks, mock_get_drac_client):
#        mock_client = mock.Mock()
#        mock_get_drac_client.return_value = mock_client
#
#        self.root_logical_disk = {
#            'size_gb': 'MAX',
#            'raid_level': '1',
#            'is_root_volume': True
#        }
#        self.logical_disks = [self.root_logical_disk]
#        self.target_raid_configuration = {'logical_disks': self.logical_disks}
#        self.node.target_raid_config = self.target_raid_configuration
#        self.node.save()
#
#        self.physical_disks = self.physical_disks[0:2]
#        physical_disks = self._generate_physical_disks()
#        mock_list_physical_disks.return_value = physical_disks
#
#        with task_manager.acquire(self.context, self.node.uuid,
#                                  shared=False) as task:
#            self.assertRaises(
#                exception.InvalidParameterValue,
#                task.driver.bios.create_configuration,
#                task)
#
#    @mock.patch.object(drac_common, 'get_drac_client', spec_set=True,
#                       autospec=True)
#    @mock.patch.object(drac_bios, 'list_physical_disks', autospec=True)
#    @mock.patch.object(drac_job, 'validate_job_queue', spec_set=True,
#                       autospec=True)
#    @mock.patch.object(drac_bios, 'commit_config', spec_set=True,
#                       autospec=True)
#    def test_create_configuration_with_share_physical_disks(
#            self, mock_commit_config, mock_validate_job_queue,
#            mock_list_physical_disks, mock_get_drac_client):
#        mock_client = mock.Mock()
#        mock_get_drac_client.return_value = mock_client
#
#        self.nonroot_logical_disks[0]['share_physical_disks'] = True
#        self.nonroot_logical_disks[1]['share_physical_disks'] = True
#        self.logical_disks = self.nonroot_logical_disks
#        self.target_raid_configuration = {'logical_disks': self.logical_disks}
#        self.node.target_raid_config = self.target_raid_configuration
#        self.node.save()
#
#        self.physical_disks = self.physical_disks[0:3]
#        physical_disks = self._generate_physical_disks()
#        mock_list_physical_disks.return_value = physical_disks
#
#        mock_commit_config.return_value = '42'
#
#        with task_manager.acquire(self.context, self.node.uuid,
#                                  shared=False) as task:
#            task.driver.bios.create_configuration(
#                task, create_root_volume=True, create_nonroot_volumes=True)
#
#            mock_client.create_virtual_disk.assert_has_calls(
#                [mock.call(
#                    'RAID.Integrated.1-1',
#                    ['Disk.Bay.0:Enclosure.Internal.0-1:RAID.Integrated.1-1',
#                     'Disk.Bay.1:Enclosure.Internal.0-1:RAID.Integrated.1-1',
#                     'Disk.Bay.2:Enclosure.Internal.0-1:RAID.Integrated.1-1'],
#                    '5', 102400, None, 3, 1),
#                 mock.call(
#                    'RAID.Integrated.1-1',
#                    ['Disk.Bay.0:Enclosure.Internal.0-1:RAID.Integrated.1-1',
#                     'Disk.Bay.1:Enclosure.Internal.0-1:RAID.Integrated.1-1',
#                     'Disk.Bay.2:Enclosure.Internal.0-1:RAID.Integrated.1-1'],
#                    '5', 102400, None, 3, 1)])
#
#            # Commits to the controller
#            mock_commit_config.assert_called_once_with(
#                mock.ANY, raid_controller='RAID.Integrated.1-1', reboot=True)
#
#        self.node.refresh()
#        self.assertEqual(['42'],
#                         self.node.driver_internal_info['raid_config_job_ids'])
#
#    @mock.patch.object(drac_common, 'get_drac_client', spec_set=True,
#                       autospec=True)
#    @mock.patch.object(drac_bios, 'list_physical_disks', autospec=True)
#    @mock.patch.object(drac_job, 'validate_job_queue', spec_set=True,
#                       autospec=True)
#    @mock.patch.object(drac_bios, 'commit_config', spec_set=True,
#                       autospec=True)
#    def test_create_configuration_fails_with_sharing_disabled(
#            self, mock_commit_config, mock_validate_job_queue,
#            mock_list_physical_disks, mock_get_drac_client):
#        mock_client = mock.Mock()
#        mock_get_drac_client.return_value = mock_client
#
#        self.nonroot_logical_disks[0]['share_physical_disks'] = False
#        self.nonroot_logical_disks[1]['share_physical_disks'] = False
#        self.logical_disks = self.nonroot_logical_disks
#        self.target_raid_configuration = {'logical_disks': self.logical_disks}
#        self.node.target_raid_config = self.target_raid_configuration
#        self.node.save()
#
#        self.physical_disks = self.physical_disks[0:3]
#        physical_disks = self._generate_physical_disks()
#        mock_list_physical_disks.return_value = physical_disks
#
#        mock_commit_config.return_value = '42'
#
#        with task_manager.acquire(self.context, self.node.uuid,
#                                  shared=False) as task:
#            self.assertRaises(
#                exception.DracOperationError,
#                task.driver.bios.create_configuration,
#                task, create_root_volume=True, create_nonroot_volumes=True)
#
#    @mock.patch.object(drac_common, 'get_drac_client', spec_set=True,
#                       autospec=True)
#    @mock.patch.object(drac_bios, 'list_physical_disks', autospec=True)
#    @mock.patch.object(drac_job, 'validate_job_queue', spec_set=True,
#                       autospec=True)
#    @mock.patch.object(drac_bios, 'commit_config', spec_set=True,
#                       autospec=True)
#    def test_create_configuration_with_max_size_and_share_physical_disks(
#            self, mock_commit_config, mock_validate_job_queue,
#            mock_list_physical_disks, mock_get_drac_client):
#        mock_client = mock.Mock()
#        mock_get_drac_client.return_value = mock_client
#
#        self.nonroot_logical_disks[0]['share_physical_disks'] = True
#        self.nonroot_logical_disks[0]['size_gb'] = 'MAX'
#        self.nonroot_logical_disks[0]['physical_disks'] = [
#            'Disk.Bay.0:Enclosure.Internal.0-1:RAID.Integrated.1-1',
#            'Disk.Bay.1:Enclosure.Internal.0-1:RAID.Integrated.1-1',
#            'Disk.Bay.2:Enclosure.Internal.0-1:RAID.Integrated.1-1']
#        self.nonroot_logical_disks[1]['share_physical_disks'] = True
#        self.logical_disks = self.nonroot_logical_disks
#        self.target_raid_configuration = {'logical_disks': self.logical_disks}
#        self.node.target_raid_config = self.target_raid_configuration
#        self.node.save()
#
#        self.physical_disks = self.physical_disks[0:3]
#        physical_disks = self._generate_physical_disks()
#        mock_list_physical_disks.return_value = physical_disks
#
#        mock_commit_config.return_value = '42'
#
#        with task_manager.acquire(self.context, self.node.uuid,
#                                  shared=False) as task:
#            task.driver.bios.create_configuration(
#                task, create_root_volume=True, create_nonroot_volumes=True)
#
#            mock_client.create_virtual_disk.assert_has_calls(
#                [mock.call(
#                    'RAID.Integrated.1-1',
#                    ['Disk.Bay.0:Enclosure.Internal.0-1:RAID.Integrated.1-1',
#                     'Disk.Bay.1:Enclosure.Internal.0-1:RAID.Integrated.1-1',
#                     'Disk.Bay.2:Enclosure.Internal.0-1:RAID.Integrated.1-1'],
#                    '5', 1041152, None, 3, 1),
#                 mock.call(
#                    'RAID.Integrated.1-1',
#                    ['Disk.Bay.0:Enclosure.Internal.0-1:RAID.Integrated.1-1',
#                     'Disk.Bay.1:Enclosure.Internal.0-1:RAID.Integrated.1-1',
#                     'Disk.Bay.2:Enclosure.Internal.0-1:RAID.Integrated.1-1'],
#                    '5', 102400, None, 3, 1)],
#                any_order=True)
#
#            # Commits to the controller
#            mock_commit_config.assert_called_once_with(
#                mock.ANY, bios_controller='RAID.Integrated.1-1', reboot=True)
#
#        self.node.refresh()
#        self.assertEqual(['42'],
#                         self.node.driver_internal_info['bios_config_job_ids'])
#
#    @mock.patch.object(drac_common, 'get_drac_client', spec_set=True,
#                       autospec=True)
#    @mock.patch.object(drac_bios, 'list_physical_disks', autospec=True)
#    @mock.patch.object(drac_job, 'validate_job_queue', spec_set=True,
#                       autospec=True)
#    @mock.patch.object(drac_bios, 'commit_config', spec_set=True,
#                       autospec=True)
#    def test_create_configuration_with_multiple_max_and_sharing_same_disks(
#            self, mock_commit_config, mock_validate_job_queue,
#            mock_list_physical_disks, mock_get_drac_client):
#        mock_client = mock.Mock()
#        mock_get_drac_client.return_value = mock_client
#
#        self.nonroot_logical_disks[0]['share_physical_disks'] = True
#        self.nonroot_logical_disks[0]['size_gb'] = 'MAX'
#        self.nonroot_logical_disks[0]['physical_disks'] = [
#            'Disk.Bay.0:Enclosure.Internal.0-1:RAID.Integrated.1-1',
#            'Disk.Bay.1:Enclosure.Internal.0-1:RAID.Integrated.1-1',
#            'Disk.Bay.2:Enclosure.Internal.0-1:RAID.Integrated.1-1']
#        self.nonroot_logical_disks[1]['share_physical_disks'] = True
#        self.nonroot_logical_disks[1]['size_gb'] = 'MAX'
#        self.nonroot_logical_disks[1]['physical_disks'] = [
#            'Disk.Bay.0:Enclosure.Internal.0-1:RAID.Integrated.1-1',
#            'Disk.Bay.1:Enclosure.Internal.0-1:RAID.Integrated.1-1',
#            'Disk.Bay.2:Enclosure.Internal.0-1:RAID.Integrated.1-1']
#        self.logical_disks = self.nonroot_logical_disks
#        self.target_raid_configuration = {'logical_disks': self.logical_disks}
#        self.node.target_raid_config = self.target_raid_configuration
#        self.node.save()
#
#        self.physical_disks = self.physical_disks[0:3]
#        physical_disks = self._generate_physical_disks()
#        mock_list_physical_disks.return_value = physical_disks
#
#        mock_commit_config.return_value = '42'
#
#        with task_manager.acquire(self.context, self.node.uuid,
#                                  shared=False) as task:
#            self.assertRaises(
#                exception.DracOperationError,
#                task.driver.bios.create_configuration,
#                task, create_root_volume=True, create_nonroot_volumes=True)
#
#    @mock.patch.object(drac_common, 'get_drac_client', spec_set=True,
#                       autospec=True)
#    @mock.patch.object(drac_bios, 'list_physical_disks', autospec=True)
#    @mock.patch.object(drac_job, 'validate_job_queue', spec_set=True,
#                       autospec=True)
#    @mock.patch.object(drac_bios, 'commit_config', spec_set=True,
#                       autospec=True)
#    def test_create_configuration_fails_if_not_enough_space(
#            self, mock_commit_config, mock_validate_job_queue,
#            mock_list_physical_disks, mock_get_drac_client):
#        mock_client = mock.Mock()
#        mock_get_drac_client.return_value = mock_client
#
#        self.logical_disk = {
#            'size_gb': 500,
#            'bios_level': '1'
#        }
#        self.logical_disks = [self.logical_disk, self.logical_disk]
#        self.target_bios_configuration = {'logical_disks': self.logical_disks}
#        self.node.target_bios_config = self.target_bios_configuration
#        self.node.save()
#
#        self.physical_disks = self.physical_disks[0:3]
#        physical_disks = self._generate_physical_disks()
#        mock_list_physical_disks.return_value = physical_disks
#
#        mock_commit_config.return_value = '42'
#
#        with task_manager.acquire(self.context, self.node.uuid,
#                                  shared=False) as task:
#            self.assertRaises(
#                exception.DracOperationError,
#                task.driver.bios.create_configuration,
#                task, create_root_volume=True, create_nonroot_volumes=True)
#
#    @mock.patch.object(drac_common, 'get_drac_client', spec_set=True,
#                       autospec=True)
#    @mock.patch.object(drac_bios, 'list_physical_disks', autospec=True)
#    @mock.patch.object(drac_job, 'validate_job_queue', spec_set=True,
#                       autospec=True)
#    @mock.patch.object(drac_bios, 'commit_config', spec_set=True,
#                       autospec=True)
#    def test_create_configuration_fails_if_disk_already_reserved(
#            self, mock_commit_config, mock_validate_job_queue,
#            mock_list_physical_disks, mock_get_drac_client):
#        mock_client = mock.Mock()
#        mock_get_drac_client.return_value = mock_client
#
#        self.logical_disk = {
#            'size_gb': 500,
#            'bios_level': '1',
#            'physical_disks': [
#                'Disk.Bay.4:Enclosure.Internal.0-1:RAID.Integrated.1-1',
#                'Disk.Bay.5:Enclosure.Internal.0-1:RAID.Integrated.1-1'],
#        }
#        self.logical_disks = [self.logical_disk, self.logical_disk.copy()]
#        self.target_bios_configuration = {'logical_disks': self.logical_disks}
#        self.node.target_bios_config = self.target_bios_configuration
#        self.node.save()
#
#        physical_disks = self._generate_physical_disks()
#        mock_list_physical_disks.return_value = physical_disks
#
#        mock_commit_config.return_value = '42'
#
#        with task_manager.acquire(self.context, self.node.uuid,
#                                  shared=False) as task:
#            self.assertRaises(
#                exception.DracOperationError,
#                task.driver.bios.create_configuration,
#                task, create_root_volume=True, create_nonroot_volumes=True)
#
#    @mock.patch.object(drac_common, 'get_drac_client', spec_set=True,
#                       autospec=True)
#    @mock.patch.object(drac_bios, 'list_virtual_disks', autospec=True)
#    @mock.patch.object(drac_job, 'validate_job_queue', spec_set=True,
#                       autospec=True)
#    @mock.patch.object(drac_bios, 'commit_config', spec_set=True,
#                       autospec=True)
#    def _test_delete_configuration(self, expected_state,
#                                   mock_commit_config,
#                                   mock_validate_job_queue,
#                                   mock_list_virtual_disks,
#                                   mock_get_drac_client):
#        mock_client = mock.Mock()
#        mock_get_drac_client.return_value = mock_client
#        virtual_disk_dict = {
#            'id': 'Disk.Virtual.0:RAID.Integrated.1-1',
#            'name': 'disk 0',
#            'description': 'Virtual Disk 0 on Integrated RAID Controller 1',
#            'controller': 'RAID.Integrated.1-1',
#            'bios_level': '1',
#            'size_mb': 571776,
#            'state': 'ok',
#            'bios_state': 'online',
#            'span_depth': 1,
#            'span_length': 2,
#            'pending_operations': None}
#        mock_list_virtual_disks.return_value = [
#            test_utils.dict_to_namedtuple(values=virtual_disk_dict)]
#        mock_commit_config.return_value = '42'
#
#        with task_manager.acquire(self.context, self.node.uuid,
#                                  shared=False) as task:
#            return_value = task.driver.bios.delete_configuration(task)
#
#            mock_client.delete_virtual_disk.assert_called_once_with(
#                'Disk.Virtual.0:RAID.Integrated.1-1')
#            mock_commit_config.assert_called_once_with(
#                task.node, bios_controller='RAID.Integrated.1-1', reboot=True)
#
#        self.assertEqual(expected_state, return_value)
#        self.node.refresh()
#        self.assertEqual(['42'],
#                         self.node.driver_internal_info['bios_config_job_ids'])
#
#    def test_delete_configuration_in_clean(self):
#        self._test_delete_configuration(states.CLEANWAIT)
#
#    def test_delete_configuration_in_deploy(self):
#        self.node.clean_step = None
#        self.node.save()
#        self._test_delete_configuration(states.DEPLOYWAIT)
#
#    @mock.patch.object(drac_common, 'get_drac_client', spec_set=True,
#                       autospec=True)
#    @mock.patch.object(drac_bios, 'list_virtual_disks', autospec=True)
#    @mock.patch.object(drac_job, 'validate_job_queue', spec_set=True,
#                       autospec=True)
#    @mock.patch.object(drac_bios, 'commit_config', spec_set=True,
#                       autospec=True)
#    def test_delete_configuration_no_change(self, mock_commit_config,
#                                            mock_validate_job_queue,
#                                            mock_list_virtual_disks,
#                                            mock_get_drac_client):
#        mock_client = mock.Mock()
#        mock_get_drac_client.return_value = mock_client
#        mock_list_virtual_disks.return_value = []
#
#        with task_manager.acquire(self.context, self.node.uuid,
#                                  shared=False) as task:
#            return_value = task.driver.bios.delete_configuration(task)
#
#            self.assertEqual(0, mock_client.delete_virtual_disk.call_count)
#            self.assertEqual(0, mock_commit_config.call_count)
#
#        self.assertIsNone(return_value)
#
#        self.node.refresh()
#        self.assertNotIn('bios_config_job_ids',
#        self.node.driver_internal_info)
