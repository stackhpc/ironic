# Copyright 2013 Hewlett-Packard Development Company, L.P.
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

from ironic_lib import disk_utils
from ironic_lib import metrics_utils
from ironic_lib import utils as il_utils
from oslo_log import log as logging
from oslo_utils import excutils
from six.moves.urllib import parse

from ironic.common import dhcp_factory
from ironic.common import exception
from ironic.common.i18n import _
from ironic.common import states
from ironic.conductor import task_manager
from ironic.conductor import utils as manager_utils
from ironic.conf import CONF
from ironic.drivers import base
from ironic.drivers.modules import agent_base_vendor
from ironic.drivers.modules import boot_mode_utils
from ironic.drivers.modules import deploy_utils

LOG = logging.getLogger(__name__)

METRICS = metrics_utils.get_metrics_logger(__name__)

DISK_LAYOUT_PARAMS = ('root_gb', 'swap_mb', 'ephemeral_gb')


def _save_disk_layout(node, i_info):
    """Saves the disk layout.

    The disk layout used for deployment of the node, is saved.

    :param node: the node of interest
    :param i_info: instance information (a dictionary) for the node, containing
                   disk layout information
    """
    driver_internal_info = node.driver_internal_info
    driver_internal_info['instance'] = {}

    for param in DISK_LAYOUT_PARAMS:
        driver_internal_info['instance'][param] = i_info[param]

    node.driver_internal_info = driver_internal_info
    node.save()


@METRICS.timer('check_image_size')
def check_image_size(task):
    """Check if the requested image is larger than the root partition size.

    Does nothing for whole-disk images.

    :param task: a TaskManager instance containing the node to act on.
    :raises: InstanceDeployFailure if size of the image is greater than root
        partition.
    """
    if task.node.driver_internal_info['is_whole_disk_image']:
        # The root partition is already created and populated, no use
        # validating its size
        return

    i_info = deploy_utils.parse_instance_info(task.node)
    image_path = deploy_utils._get_image_file_path(task.node.uuid)
    image_mb = disk_utils.get_image_mb(image_path)
    root_mb = 1024 * int(i_info['root_gb'])
    if image_mb > root_mb:
        msg = (_('Root partition is too small for requested image. Image '
                 'virtual size: %(image_mb)d MB, Root size: %(root_mb)d MB')
               % {'image_mb': image_mb, 'root_mb': root_mb})
        raise exception.InstanceDeployFailure(msg)


@METRICS.timer('get_deploy_info')
def get_deploy_info(node, address, iqn, port=None, lun='1', conv_flags=None):
    """Returns the information required for doing iSCSI deploy in a dictionary.

    :param node: ironic node object
    :param address: iSCSI address
    :param iqn: iSCSI iqn for the target disk
    :param port: iSCSI port, defaults to one specified in the configuration
    :param lun: iSCSI lun, defaults to '1'
    :param conv_flags: flag that will modify the behaviour of the image copy
        to disk.
    :raises: MissingParameterValue, if some required parameters were not
        passed.
    :raises: InvalidParameterValue, if any of the parameters have invalid
        value.
    """
    i_info = deploy_utils.parse_instance_info(node)

    params = {
        'address': address,
        'port': port or CONF.iscsi.portal_port,
        'iqn': iqn,
        'lun': lun,
        'image_path': deploy_utils._get_image_file_path(node.uuid),
        'node_uuid': node.uuid}

    is_whole_disk_image = node.driver_internal_info['is_whole_disk_image']
    if not is_whole_disk_image:
        params.update({'root_mb': i_info['root_mb'],
                       'swap_mb': i_info['swap_mb'],
                       'ephemeral_mb': i_info['ephemeral_mb'],
                       'preserve_ephemeral': i_info['preserve_ephemeral'],
                       'boot_option': deploy_utils.get_boot_option(node),
                       'boot_mode': boot_mode_utils.get_boot_mode(node)})

        cpu_arch = node.properties.get('cpu_arch')
        if cpu_arch is not None:
            params['cpu_arch'] = cpu_arch

        # Append disk label if specified
        disk_label = deploy_utils.get_disk_label(node)
        if disk_label is not None:
            params['disk_label'] = disk_label

    missing = [key for key in params if params[key] is None]
    if missing:
        raise exception.MissingParameterValue(
            _("Parameters %s were not passed to ironic"
              " for deploy.") % missing)

    # configdrive is nullable
    params['configdrive'] = i_info.get('configdrive')
    if is_whole_disk_image:
        return params

    if conv_flags:
        params['conv_flags'] = conv_flags

    # ephemeral_format is nullable
    params['ephemeral_format'] = i_info.get('ephemeral_format')

    return params


@METRICS.timer('continue_deploy')
def continue_deploy(task, **kwargs):
    """Resume a deployment upon getting POST data from deploy ramdisk.

    This method raises no exceptions because it is intended to be
    invoked asynchronously as a callback from the deploy ramdisk.

    :param task: a TaskManager instance containing the node to act on.
    :param kwargs: the kwargs to be passed to deploy.
    :raises: InvalidState if the event is not allowed by the associated
             state machine.
    :returns: a dictionary containing the following keys:

              For partition image:

              * 'root uuid': UUID of root partition
              * 'efi system partition uuid': UUID of the uefi system partition
                (if boot mode is uefi).

                .. note:: If key exists but value is None, it means partition
                          doesn't exist.

              For whole disk image:

              * 'disk identifier': ID of the disk to which image was deployed.
    """
    node = task.node

    params = get_deploy_info(node, **kwargs)

    def _fail_deploy(task, msg, raise_exception=True):
        """Fail the deploy after logging and setting error states."""
        if isinstance(msg, Exception):
            msg = (_('Deploy failed for instance %(instance)s. '
                     'Error: %(error)s') %
                   {'instance': node.instance_uuid, 'error': msg})
        deploy_utils.set_failed_state(task, msg)
        deploy_utils.destroy_images(task.node.uuid)
        if raise_exception:
            raise exception.InstanceDeployFailure(msg)

    # NOTE(lucasagomes): Let's make sure we don't log the full content
    # of the config drive here because it can be up to 64MB in size,
    # so instead let's log "***" in case config drive is enabled.
    if LOG.isEnabledFor(logging.logging.DEBUG):
        log_params = {
            k: params[k] if k != 'configdrive' else '***'
            for k in params
        }
        LOG.debug('Continuing deployment for node %(node)s, params %(params)s',
                  {'node': node.uuid, 'params': log_params})

    uuid_dict_returned = {}
    try:
        if node.driver_internal_info['is_whole_disk_image']:
            uuid_dict_returned = deploy_utils.deploy_disk_image(**params)
        else:
            uuid_dict_returned = deploy_utils.deploy_partition_image(**params)
    except exception.IronicException as e:
        with excutils.save_and_reraise_exception():
            LOG.error('Deploy of instance %(instance)s on node %(node)s '
                      'failed: %(error)s', {'instance': node.instance_uuid,
                                            'node': node.uuid, 'error': e})
            _fail_deploy(task, e, raise_exception=False)
    except Exception as e:
        LOG.exception('Deploy of instance %(instance)s on node %(node)s '
                      'failed with exception',
                      {'instance': node.instance_uuid, 'node': node.uuid})
        _fail_deploy(task, e)

    root_uuid_or_disk_id = uuid_dict_returned.get(
        'root uuid', uuid_dict_returned.get('disk identifier'))
    if not root_uuid_or_disk_id:
        msg = (_("Couldn't determine the UUID of the root "
                 "partition or the disk identifier after deploying "
                 "node %s") % node.uuid)
        LOG.error(msg)
        _fail_deploy(task, msg)

    if params.get('preserve_ephemeral', False):
        # Save disk layout information, to check that they are unchanged
        # for any future rebuilds
        _save_disk_layout(node, deploy_utils.parse_instance_info(node))

    deploy_utils.destroy_images(node.uuid)
    return uuid_dict_returned


@METRICS.timer('do_agent_iscsi_deploy')
def do_agent_iscsi_deploy(task, agent_client):
    """Method invoked when deployed with the agent ramdisk.

    This method is invoked by drivers for doing iSCSI deploy
    using agent ramdisk.  This method assumes that the agent
    is booted up on the node and is heartbeating.

    :param task: a TaskManager object containing the node.
    :param agent_client: an instance of agent_client.AgentClient
                         which will be used during iscsi deploy
                         (for exposing node's target disk via iSCSI,
                         for install boot loader, etc).
    :returns: a dictionary containing the following keys:

              For partition image:

              * 'root uuid': UUID of root partition
              * 'efi system partition uuid': UUID of the uefi system partition
                (if boot mode is uefi).

                .. note:: If key exists but value is None, it means partition
                          doesn't exist.

              For whole disk image:

              * 'disk identifier': ID of the disk to which image was deployed.
    :raises: InstanceDeployFailure if it encounters some error
             during the deploy.
    """
    node = task.node
    i_info = deploy_utils.parse_instance_info(node)
    wipe_disk_metadata = not i_info['preserve_ephemeral']

    iqn = 'iqn.2008-10.org.openstack:%s' % node.uuid
    portal_port = CONF.iscsi.portal_port
    conv_flags = CONF.iscsi.conv_flags
    result = agent_client.start_iscsi_target(
        node, iqn,
        portal_port,
        wipe_disk_metadata=wipe_disk_metadata)
    if result['command_status'] == 'FAILED':
        msg = (_("Failed to start the iSCSI target to deploy the "
                 "node %(node)s. Error: %(error)s") %
               {'node': node.uuid, 'error': result['command_error']})
        deploy_utils.set_failed_state(task, msg)
        raise exception.InstanceDeployFailure(reason=msg)

    address = parse.urlparse(node.driver_internal_info['agent_url'])
    address = address.hostname

    uuid_dict_returned = continue_deploy(task, iqn=iqn, address=address,
                                         conv_flags=conv_flags)
    root_uuid_or_disk_id = uuid_dict_returned.get(
        'root uuid', uuid_dict_returned.get('disk identifier'))

    # TODO(lucasagomes): Move this bit saving the root_uuid to
    # continue_deploy()
    driver_internal_info = node.driver_internal_info
    driver_internal_info['root_uuid_or_disk_id'] = root_uuid_or_disk_id
    node.driver_internal_info = driver_internal_info
    node.save()

    return uuid_dict_returned


@METRICS.timer('validate')
def validate(task):
    """Validates the pre-requisites for iSCSI deploy.

    Validates whether node in the task provided has some ports enrolled.
    This method validates whether conductor url is available either from CONF
    file or from keystone.

    :param task: a TaskManager instance containing the node to act on.
    :raises: InvalidParameterValue if the URL of the Ironic API service is not
             configured in config file and is not accessible via Keystone
             catalog.
    :raises: MissingParameterValue if no ports are enrolled for the given node.
    """
    # TODO(lucasagomes): Validate the format of the URL
    deploy_utils.get_ironic_api_url()
    # Validate the root device hints
    try:
        root_device = task.node.properties.get('root_device')
        il_utils.parse_root_device_hints(root_device)
    except ValueError as e:
        raise exception.InvalidParameterValue(
            _('Failed to validate the root device hints for node '
              '%(node)s. Error: %(error)s') % {'node': task.node.uuid,
                                               'error': e})
    deploy_utils.parse_instance_info(task.node)


class AgentDeployMixin(agent_base_vendor.AgentDeployMixin):

    @METRICS.timer('AgentDeployMixin.has_decomposed_deploy_steps')
    def has_decomposed_deploy_steps(self):
        """Return whether the driver supports decomposed deploy steps.

        Previously (since Rocky), drivers used a single 'deploy' deploy step on
        the deploy interface. Some additional steps were added for the 'direct'
        and 'iscsi' deploy interfaces in the Ussuri cycle, which means that
        more of the deployment flow is driven by deploy steps.
        """
        return True

    @METRICS.timer('AgentDeployMixin.continue_deploy')
    @base.deploy_step(priority=90)
    @task_manager.require_exclusive_lock
    def continue_deploy(self, task):
        """Method invoked when deployed using iSCSI.

        This method is invoked during a heartbeat from an agent when
        the node is in wait-call-back state. This deploys the image on
        the node and then configures the node to boot according to the
        desired boot option (netboot or localboot).

        :param task: a TaskManager object containing the node.
        :param kwargs: the kwargs passed from the heartbeat method.
        :raises: InstanceDeployFailure, if it encounters some error during
            the deploy.
        """
        node = task.node
        LOG.debug('Continuing the deployment on node %s', node.uuid)

        # FIXME(mgoddard): Do this better.
        uuid_dict_returned = do_agent_iscsi_deploy(task, self._client)
        driver_internal_info = node.driver_internal_info
        driver_internal_info['uuid_dict_returned'] = uuid_dict_returned
        node.driver_internal_info = driver_internal_info
        node.save()

    def _reboot_to_instance_no_image(self, task):
        # Boot to an Storage Volume

        # TODO(TheJulia): At some point, we should de-dupe this code
        # as it is nearly identical to the agent deploy interface.
        # This is not being done now as it is expected to be
        # refactored in the near future.
        manager_utils.node_power_action(task, states.POWER_OFF)
        power_state_to_restore = (
            manager_utils.power_on_node_if_needed(task))
        task.driver.network.remove_provisioning_network(task)
        task.driver.network.configure_tenant_networks(task)
        manager_utils.restore_power_state_if_needed(
            task, power_state_to_restore)
        task.driver.boot.prepare_instance(task)
        manager_utils.node_power_action(task, states.POWER_ON)

    @METRICS.timer('AgentDeployMixin.reboot_to_instance')
    @base.deploy_step(priority=80)
    def reboot_to_instance(self, task):
        if not task.driver.storage.should_write_image(task):
            self._reboot_to_instance_no_image(task)
            return

        # FIXME(mgoddard): do this better.
        node = task.node
        uuid_dict_returned = node.driver_internal_info['uuid_dict_returned']
        root_uuid = uuid_dict_returned.get('root uuid')
        efi_sys_uuid = uuid_dict_returned.get('efi system partition uuid')
        prep_boot_part_uuid = uuid_dict_returned.get(
            'PrEP Boot partition uuid')

        self.prepare_instance_to_boot(task, root_uuid, efi_sys_uuid,
                                      prep_boot_part_uuid=prep_boot_part_uuid)
        self.reboot_and_finish_deploy(task)


class ISCSIDeploy(AgentDeployMixin, base.DeployInterface):
    """iSCSI Deploy Interface for deploy-related actions."""

    def get_properties(self):
        return agent_base_vendor.VENDOR_PROPERTIES

    @METRICS.timer('ISCSIDeploy.validate')
    def validate(self, task):
        """Validate the deployment information for the task's node.

        :param task: a TaskManager instance containing the node to act on.
        :raises: InvalidParameterValue.
        :raises: MissingParameterValue
        """
        task.driver.boot.validate(task)
        node = task.node

        # Check the boot_mode, boot_option and disk_label capabilities values.
        deploy_utils.validate_capabilities(node)

        # Edit early if we are not writing a volume as the validate
        # tasks evaluate root device hints.
        if not task.driver.storage.should_write_image(task):
            LOG.debug('Skipping complete deployment interface validation '
                      'for node %s as it is set to boot from a remote '
                      'volume.', node.uuid)
            return

        # TODO(rameshg87): iscsi_ilo driver used to call this function. Remove
        # and copy-paste it's contents here.
        validate(task)

    @METRICS.timer('ISCSIDeploy.deploy')
    @base.deploy_step(priority=100)
    @task_manager.require_exclusive_lock
    def deploy(self, task):
        """Start deployment of the task's node.

        Fetches instance image, updates the DHCP port options for next boot,
        and issues a reboot request to the power driver.
        This causes the node to boot into the deployment ramdisk and triggers
        the next phase of PXE-based deployment via agent heartbeats.

        :param task: a TaskManager instance containing the node to act on.
        :returns: deploy state DEPLOYWAIT.
        """
        node = task.node
        if manager_utils.is_fast_track(task):
            # NOTE(mgoddard): For fast track we can mostly skip this step and
            # proceed to continue_deploy.
            LOG.debug('Performing a fast track deployment for %(node)s.',
                      {'node': task.node.uuid})
            deploy_utils.cache_instance_image(task.context, node)
            check_image_size(task)
        elif task.driver.storage.should_write_image(task):
            # Standard deploy process
            deploy_utils.cache_instance_image(task.context, node)
            check_image_size(task)
            # Check if the driver has already performed a reboot in a previous
            # deploy step.
            if not task.node.driver_internal_info.get('deployment_reboot',
                                                      False):
                manager_utils.node_power_action(task, states.REBOOT)
            info = task.node.driver_internal_info
            info.pop('deployment_reboot', None)
            task.node.driver_internal_info = info
            task.node.save()

            return states.DEPLOYWAIT

    @METRICS.timer('ISCSIDeploy.tear_down')
    @task_manager.require_exclusive_lock
    def tear_down(self, task):
        """Tear down a previous deployment on the task's node.

        Power off the node. All actual clean-up is done in the clean_up()
        method which should be called separately.

        :param task: a TaskManager instance containing the node to act on.
        :returns: deploy state DELETED.
        :raises: NetworkError if the cleaning ports cannot be removed.
        :raises: InvalidParameterValue when the wrong state is specified
             or the wrong driver info is specified.
        :raises: StorageError when volume detachment fails.
        :raises: other exceptions by the node's power driver if something
             wrong occurred during the power action.
        """
        manager_utils.node_power_action(task, states.POWER_OFF)
        task.driver.storage.detach_volumes(task)
        deploy_utils.tear_down_storage_configuration(task)
        power_state_to_restore = manager_utils.power_on_node_if_needed(task)
        task.driver.network.unconfigure_tenant_networks(task)
        # NOTE(mgoddard): If the deployment was unsuccessful the node may have
        # ports on the provisioning network which were not deleted.
        task.driver.network.remove_provisioning_network(task)
        manager_utils.restore_power_state_if_needed(
            task, power_state_to_restore)
        return states.DELETED

    @METRICS.timer('ISCSIDeploy.prepare')
    @task_manager.require_exclusive_lock
    def prepare(self, task):
        """Prepare the deployment environment for this task's node.

        Generates the TFTP configuration for PXE-booting both the deployment
        and user images, fetches the TFTP image from Glance and add it to the
        local cache.

        :param task: a TaskManager instance containing the node to act on.
        :raises: NetworkError: if the previous cleaning ports cannot be removed
            or if new cleaning ports cannot be created.
        :raises: InvalidParameterValue when the wrong power state is specified
            or the wrong driver info is specified for power management.
        :raises: StorageError If the storage driver is unable to attach the
            configured volumes.
        :raises: other exceptions by the node's power driver if something
            wrong occurred during the power action.
        :raises: any boot interface's prepare_ramdisk exceptions.
        """
        node = task.node
        deploy_utils.populate_storage_driver_internal_info(task)
        if node.provision_state in [states.ACTIVE, states.ADOPTING]:
            task.driver.boot.prepare_instance(task)
        else:
            if node.provision_state == states.DEPLOYING:
                fast_track_deploy = manager_utils.is_fast_track(task)
                if fast_track_deploy:
                    # The agent has already recently checked in and we are
                    # configured to take that as an indicator that we can
                    # skip ahead.
                    LOG.debug('The agent for node %(node)s has recently '
                              'checked in, and the node power will remain '
                              'unmodified.',
                              {'node': task.node.uuid})
                else:
                    # Adding the node to provisioning network so that the dhcp
                    # options get added for the provisioning port.
                    manager_utils.node_power_action(task, states.POWER_OFF)
                # NOTE(vdrok): in case of rebuild, we have tenant network
                # already configured, unbind tenant ports if present
                if task.driver.storage.should_write_image(task):
                    if not fast_track_deploy:
                        power_state_to_restore = (
                            manager_utils.power_on_node_if_needed(task))
                    task.driver.network.unconfigure_tenant_networks(task)
                    task.driver.network.add_provisioning_network(task)
                    if not fast_track_deploy:
                        manager_utils.restore_power_state_if_needed(
                            task, power_state_to_restore)
                task.driver.storage.attach_volumes(task)
                if (not task.driver.storage.should_write_image(task)
                    or fast_track_deploy):
                    # We have nothing else to do as this is handled in the
                    # backend storage system, and we can return to the caller
                    # as we do not need to boot the agent to deploy.
                    # Alternatively, we are in a fast track deployment
                    # and have nothing else to do.
                    return

            deploy_opts = deploy_utils.build_agent_options(node)
            task.driver.boot.prepare_ramdisk(task, deploy_opts)

    @METRICS.timer('ISCSIDeploy.clean_up')
    def clean_up(self, task):
        """Clean up the deployment environment for the task's node.

        Unlinks TFTP and instance images and triggers image cache cleanup.
        Removes the TFTP configuration files for this node.

        :param task: a TaskManager instance containing the node to act on.
        """
        deploy_utils.destroy_images(task.node.uuid)
        task.driver.boot.clean_up_ramdisk(task)
        task.driver.boot.clean_up_instance(task)
        provider = dhcp_factory.DHCPFactory()
        provider.clean_dhcp(task)

    def take_over(self, task):
        pass

    @METRICS.timer('ISCSIDeploy.get_clean_steps')
    def get_clean_steps(self, task):
        """Get the list of clean steps from the agent.

        :param task: a TaskManager object containing the node
        :raises NodeCleaningFailure: if the clean steps are not yet
            available (cached), for example, when a node has just been
            enrolled and has not been cleaned yet.
        :returns: A list of clean step dictionaries.
        """
        steps = deploy_utils.agent_get_clean_steps(
            task, interface='deploy',
            override_priorities={
                'erase_devices': CONF.deploy.erase_devices_priority,
                'erase_devices_metadata':
                    CONF.deploy.erase_devices_metadata_priority})
        return steps

    @METRICS.timer('ISCSIDeploy.execute_clean_step')
    def execute_clean_step(self, task, step):
        """Execute a clean step asynchronously on the agent.

        :param task: a TaskManager object containing the node
        :param step: a clean step dictionary to execute
        :raises: NodeCleaningFailure if the agent does not return a command
            status
        :returns: states.CLEANWAIT to signify the step will be completed
            asynchronously.
        """
        return deploy_utils.agent_execute_clean_step(task, step)

    @METRICS.timer('ISCSIDeploy.prepare_cleaning')
    def prepare_cleaning(self, task):
        """Boot into the agent to prepare for cleaning.

        :param task: a TaskManager object containing the node
        :raises NodeCleaningFailure: if the previous cleaning ports cannot
            be removed or if new cleaning ports cannot be created
        :returns: states.CLEANWAIT to signify an asynchronous prepare.
        """
        return deploy_utils.prepare_inband_cleaning(
            task, manage_boot=True)

    @METRICS.timer('ISCSIDeploy.tear_down_cleaning')
    def tear_down_cleaning(self, task):
        """Clean up the PXE and DHCP files after cleaning.

        :param task: a TaskManager object containing the node
        :raises NodeCleaningFailure: if the cleaning ports cannot be
            removed
        """
        deploy_utils.tear_down_inband_cleaning(
            task, manage_boot=True)
