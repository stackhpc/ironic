# -*- encoding: utf-8 -*-
#
# Copyright 2013 Hewlett-Packard Development Company, L.P.
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
Fake driver interfaces used in testing.

This is also an example of some kinds of things which can be done within
drivers.  For instance, the MultipleVendorInterface class demonstrates how to
load more than one interface and wrap them in some logic to route incoming
vendor_passthru requests appropriately. This can be useful eg. when mixing
functionality between a power interface and a deploy interface, when both rely
on separate vendor_passthru methods.
"""

from oslo_log import log

from ironic.common import boot_devices
from ironic.common import exception
from ironic.common.i18n import _
from ironic.common import states
from ironic.drivers import base
from ironic import objects


LOG = log.getLogger(__name__)


class FakePower(base.PowerInterface):
    """Example implementation of a simple power interface."""

    def get_properties(self):
        return {}

    def validate(self, task):
        pass

    def get_power_state(self, task):
        return task.node.power_state

    def reboot(self, task, timeout=None):
        pass

    def set_power_state(self, task, power_state, timeout=None):
        if power_state not in [states.POWER_ON, states.POWER_OFF,
                               states.SOFT_REBOOT, states.SOFT_POWER_OFF]:
            raise exception.InvalidParameterValue(
                _("set_power_state called with an invalid power "
                  "state: %s.") % power_state)
        task.node.power_state = power_state

    def get_supported_power_states(self, task):
        return [states.POWER_ON, states.POWER_OFF, states.REBOOT,
                states.SOFT_REBOOT, states.SOFT_POWER_OFF]

    @base.deploy_step(priority=0,
                      argsinfo={'arg1': {'description': 'desc1',
                                         'required': True},
                                'arg2': {'description': 'desc2',
                                         'required': False}})
    def power_step(self, task, arg1, arg2='default'):
        LOG.error("Power step called with %s and %s", arg1, arg2)

    @base.deploy_step(priority=1,
                      argsinfo={'arg1': {'description': 'desc1',
                                         'required': False},
                                'arg2': {'description': 'desc2',
                                         'required': False}})
    def default_power_step(self, task, arg1='default', arg2='default'):
        LOG.error("Default power step called with %s and %s", arg1, arg2)


class FakeBoot(base.BootInterface):
    """Example implementation of a simple boot interface."""

    # NOTE(TheJulia): default capabilities to make unit tests
    # happy with the fake boot interface.
    capabilities = ['ipxe_boot', 'pxe_boot']

    def get_properties(self):
        return {}

    def validate(self, task):
        pass

    def prepare_ramdisk(self, task, ramdisk_params, mode='deploy'):
        pass

    def clean_up_ramdisk(self, task, mode='deploy'):
        pass

    def prepare_instance(self, task):
        pass

    def clean_up_instance(self, task):
        pass


class FakeDeploy(base.DeployInterface):
    """Class for a fake deployment driver.

    Example implementation of a deploy interface that uses a
    separate power interface.
    """

    def get_properties(self):
        return {}

    def validate(self, task):
        pass

    @base.deploy_step(priority=100)
    def deploy(self, task):
        return None

    def tear_down(self, task):
        return states.DELETED

    def prepare(self, task):
        pass

    def clean_up(self, task):
        pass

    def take_over(self, task):
        pass

    @base.deploy_step(priority=0,
                      argsinfo={'arg1': {'description': 'desc1',
                                         'required': True},
                                'arg2': {'description': 'desc2',
                                         'required': False}})
    def deploy_step(self, task, arg1, arg2='default'):
        LOG.error("Deploy step called with %s and %s", arg1, arg2)


class FakeVendorA(base.VendorInterface):
    """Example implementation of a vendor passthru interface."""

    def get_properties(self):
        return {'A1': 'A1 description. Required.',
                'A2': 'A2 description. Optional.'}

    def validate(self, task, method, **kwargs):
        if method == 'first_method':
            bar = kwargs.get('bar')
            if not bar:
                raise exception.MissingParameterValue(_(
                    "Parameter 'bar' not passed to method 'first_method'."))

    @base.passthru(['POST'],
                   description=_("Test if the value of bar is baz"))
    def first_method(self, task, http_method, bar):
        return True if bar == 'baz' else False


class FakeVendorB(base.VendorInterface):
    """Example implementation of a secondary vendor passthru."""

    def get_properties(self):
        return {'B1': 'B1 description. Required.',
                'B2': 'B2 description. Required.'}

    def validate(self, task, method, **kwargs):
        if method in ('second_method', 'third_method_sync',
                      'fourth_method_shared_lock'):
            bar = kwargs.get('bar')
            if not bar:
                raise exception.MissingParameterValue(_(
                    "Parameter 'bar' not passed to method '%s'.") % method)

    @base.passthru(['POST'],
                   description=_("Test if the value of bar is kazoo"))
    def second_method(self, task, http_method, bar):
        return True if bar == 'kazoo' else False

    @base.passthru(['POST'], async_call=False,
                   description=_("Test if the value of bar is meow"))
    def third_method_sync(self, task, http_method, bar):
        return True if bar == 'meow' else False

    @base.passthru(['POST'], require_exclusive_lock=False,
                   description=_("Test if the value of bar is woof"))
    def fourth_method_shared_lock(self, task, http_method, bar):
        return True if bar == 'woof' else False


class FakeConsole(base.ConsoleInterface):
    """Example implementation of a simple console interface."""

    def get_properties(self):
        return {}

    def validate(self, task):
        pass

    def start_console(self, task):
        pass

    def stop_console(self, task):
        pass

    def get_console(self, task):
        return {}


class FakeManagement(base.ManagementInterface):
    """Example implementation of a simple management interface."""

    def get_properties(self):
        return {}

    def validate(self, task):
        # TODO(dtantsur): remove when snmp hardware type no longer supports the
        # fake management.
        if task.node.driver == 'snmp':
            LOG.warning('Using "fake" management with "snmp" hardware type '
                        'is deprecated, use "noop" instead for node %s',
                        task.node.uuid)

    def get_supported_boot_devices(self, task):
        return [boot_devices.PXE]

    def set_boot_device(self, task, device, persistent=False):
        if device not in self.get_supported_boot_devices(task):
            raise exception.InvalidParameterValue(_(
                "Invalid boot device %s specified.") % device)

    def get_boot_device(self, task):
        return {'boot_device': boot_devices.PXE, 'persistent': False}

    def get_sensors_data(self, task):
        return {}

    @base.deploy_step(priority=0,
                      argsinfo={'arg1': {'description': 'desc1',
                                         'required': True},
                                'arg2': {'description': 'desc2',
                                         'required': False}})
    def management_step(self, task, arg1, arg2='default'):
        LOG.error("Management step called with %s and %s", arg1, arg2)

    @base.deploy_step(priority=200,
                      argsinfo={'arg1': {'description': 'desc1',
                                         'required': False},
                                'arg2': {'description': 'desc2',
                                         'required': False}})
    def default_management_step(self, task, arg1='default', arg2='default'):
        LOG.error("Default management step called with %s and %s", arg1, arg2)


class FakeInspect(base.InspectInterface):

    """Example implementation of a simple inspect interface."""

    def get_properties(self):
        return {}

    def validate(self, task):
        pass

    def inspect_hardware(self, task):
        return states.MANAGEABLE


class FakeRAID(base.RAIDInterface):
    """Example implementation of simple RAIDInterface."""

    def get_properties(self):
        return {}

    def create_configuration(self, task, create_root_volume=True,
                             create_nonroot_volumes=True):
        pass

    def delete_configuration(self, task):
        pass

    @base.deploy_step(priority=0,
                      argsinfo={'arg1': {'description': 'desc1',
                                'required': True},
                                'arg2': {'description': 'desc2',
                                         'required': False}})
    def raid_step(self, task, arg1, arg2='default'):
        LOG.error("RAID step called with %s and %s", arg1, arg2)


class FakeBIOS(base.BIOSInterface):
    """Fake implementation of simple BIOSInterface."""

    def get_properties(self):
        return {}

    def validate(self, task):
        pass

    @base.clean_step(priority=0, argsinfo={
        'settings': {'description': ('List of BIOS settings, each item needs '
                     'to contain a dictionary with name/value pairs'),
                     'required': True}})
    def apply_configuration(self, task, settings):
        # Note: the implementation of apply_configuration in fake interface
        # is just for testing purpose, for real driver implementation, please
        # refer to develop doc at https://docs.openstack.org/ironic/latest/
        # contributor/bios_develop.html.
        node_id = task.node.id
        create_list, update_list, delete_list, nochange_list = (
            objects.BIOSSettingList.sync_node_setting(task.context, node_id,
                                                      settings))

        if len(create_list) > 0:
            objects.BIOSSettingList.create(task.context, node_id, create_list)
        if len(update_list) > 0:
            objects.BIOSSettingList.save(task.context, node_id, update_list)
        if len(delete_list) > 0:
            delete_names = [setting['name'] for setting in delete_list]
            objects.BIOSSettingList.delete(task.context, node_id,
                                           delete_names)

        # nochange_list is part of return of sync_node_setting and it might be
        # useful to the drivers to give a message if no change is required
        # during application of settings.
        if len(nochange_list) > 0:
            pass

    @base.clean_step(priority=0)
    def factory_reset(self, task):
        # Note: the implementation of factory_reset in fake interface is
        # just for testing purpose, for real driver implementation, please
        # refer to develop doc at https://docs.openstack.org/ironic/latest/
        # contributor/bios_develop.html.
        node_id = task.node.id
        setting_objs = objects.BIOSSettingList.get_by_node_id(
            task.context, node_id)
        for setting in setting_objs:
            objects.BIOSSetting.delete(task.context, node_id, setting.name)

    @base.clean_step(priority=0)
    def cache_bios_settings(self, task):
        # Note: the implementation of cache_bios_settings in fake interface
        # is just for testing purpose, for real driver implementation, please
        # refer to develop doc at https://docs.openstack.org/ironic/latest/
        # contributor/bios_develop.html.
        pass

    @base.deploy_step(priority=0,
                      argsinfo={'arg1': {'description': 'desc1',
                                'required': True},
                                'arg2': {'description': 'desc2',
                                         'required': False}})
    def bios_step(self, task, arg1, arg2='default'):
        LOG.error("BIOS step called with %s and %s", arg1, arg2)


class FakeStorage(base.StorageInterface):
    """Example implementation of simple storage Interface."""

    def validate(self, task):
        pass

    def get_properties(self):
        return {}

    def attach_volumes(self, task):
        pass

    def detach_volumes(self, task):
        pass

    def should_write_image(self, task):
        return True


class FakeRescue(base.RescueInterface):
    """Example implementation of a simple rescue interface."""

    def get_properties(self):
        return {}

    def validate(self, task):
        pass

    def rescue(self, task):
        return states.RESCUE

    def unrescue(self, task):
        return states.ACTIVE
