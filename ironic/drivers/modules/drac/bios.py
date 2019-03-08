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
DRAC BIOS configuration specific methods
"""

from futurist import periodics
from ironic_lib import metrics_utils
from oslo_log import log as logging
from oslo_utils import importutils

from ironic.common import exception
from ironic.common import states
from ironic.conductor import task_manager
from ironic.conductor import utils as manager_utils
from ironic.conf import CONF
from ironic.drivers import base
from ironic.drivers.modules.drac import common as drac_common
from ironic.drivers.modules.drac import job as drac_job
from ironic import objects

drac_exceptions = importutils.try_import('dracclient.exceptions')

LOG = logging.getLogger(__name__)

METRICS = metrics_utils.get_metrics_logger(__name__)


def get_config(node):
    """Get the BIOS configuration.

    The BIOS settings look like::

        {'EnumAttrib': {'name': 'EnumAttrib',
                        'current_value': 'Value',
                        'pending_value': 'New Value', # could also be None
                        'read_only': False,
                        'possible_values': ['Value', 'New Value', 'None']},
         'StringAttrib': {'name': 'StringAttrib',
                          'current_value': 'Information',
                          'pending_value': None,
                          'read_only': False,
                          'min_length': 0,
                          'max_length': 255,
                          'pcre_regex': '^[0-9A-Za-z]{0,255}$'},
         'IntegerAttrib': {'name': 'IntegerAttrib',
                           'current_value': 0,
                           'pending_value': None,
                           'read_only': True,
                           'lower_bound': 0,
                           'upper_bound': 65535}}

    :param node: an ironic node object.
    :raises: DracOperationError on an error from python-dracclient.
    :returns: a dictionary containing BIOS settings

    The above values are only examples, of course.  BIOS attributes exposed via
    this API will always be either an enumerated attribute, a string attribute,
    or an integer attribute.  All attributes have the following parameters:

    :param name: is the name of the BIOS attribute.
    :param current_value: is the current value of the attribute.
                          It will always be either an integer or a string.
    :param pending_value: is the new value that we want the attribute to have.
                          None means that there is no pending value.
    :param read_only: indicates whether this attribute can be changed.
                      Trying to change a read-only value will result in
                      an error. The read-only flag can change depending
                      on other attributes.
                      A future version of this call may expose the
                      dependencies that indicate when that may happen.

    Enumerable attributes also have the following parameters:

    :param possible_values: is an array of values it is permissible to set
                            the attribute to.

    String attributes also have the following parameters:

    :param min_length: is the minimum length of the string.
    :param max_length: is the maximum length of the string.
    :param pcre_regex: is a PCRE compatible regular expression that the string
                       must match.  It may be None if the string is read only
                       or if the string does not have to match any particular
                       regular expression.

    Integer attributes also have the following parameters:

    :param lower_bound: is the minimum value the attribute can have.
    :param upper_bound: is the maximum value the attribute can have.
    """

    client = drac_common.get_drac_client(node)

    try:
        return client.list_bios_settings()
    except drac_exceptions.BaseClientException as exc:
        LOG.error('DRAC driver failed to get the BIOS settings for node '
                  '%(node_uuid)s. Reason: %(error)s.',
                  {'node_uuid': node.uuid,
                   'error': exc})
        raise exception.DracOperationError(error=exc)


def set_config(task, **kwargs):
    """Sets the pending_value parameter for each of the values passed in.

    :param task: a TaskManager instance containing the node to act on.
    :param kwargs: a dictionary of {'AttributeName': 'NewValue'}
    :raises: DracOperationError on an error from python-dracclient.
    :returns: A dictionary containing the 'is_commit_required' key with a
              boolean value indicating whether commit_config() needs to be
              called to make the changes, and the 'is_reboot_required' key
              which has a value of 'true' or 'false'.  This key is used to
              indicate to the commit_config() call if a reboot should be
              performed.
    """
    node = task.node
    drac_job.validate_job_queue(node)

    client = drac_common.get_drac_client(node)
    if 'http_method' in kwargs:
        del kwargs['http_method']

    try:
        return client.set_bios_settings(kwargs)
    except drac_exceptions.BaseClientException as exc:
        LOG.error('DRAC driver failed to set the BIOS settings for node '
                  '%(node_uuid)s. Reason: %(error)s.',
                  {'node_uuid': node.uuid,
                   'error': exc})
        raise exception.DracOperationError(error=exc)


def commit_config(task, reboot=False):
    """Commits pending changes added by set_config

    :param task: a TaskManager instance containing the node to act on.
    :param reboot: indicates whether a reboot job should be automatically
                   created with the config job.
    :raises: DracOperationError on an error from python-dracclient.
    :returns: the job_id key with the id of the newly created config job.
    """
    node = task.node
    drac_job.validate_job_queue(node)

    client = drac_common.get_drac_client(node)

    try:
        return client.commit_pending_bios_changes(reboot)
    except drac_exceptions.BaseClientException as exc:
        LOG.error('DRAC driver failed to commit the pending BIOS changes '
                  'for node %(node_uuid)s. Reason: %(error)s.',
                  {'node_uuid': node.uuid,
                   'error': exc})
        raise exception.DracOperationError(error=exc)


def abandon_config(task):
    """Abandons uncommitted changes added by set_config

    :param task: a TaskManager instance containing the node to act on.
    :raises: DracOperationError on an error from python-dracclient.
    """
    node = task.node
    client = drac_common.get_drac_client(node)

    try:
        client.abandon_pending_bios_changes()
    except drac_exceptions.BaseClientException as exc:
        LOG.error('DRAC driver failed to delete the pending BIOS '
                  'settings for node %(node_uuid)s. Reason: %(error)s.',
                  {'node_uuid': node.uuid,
                   'error': exc})
        raise exception.DracOperationError(error=exc)


def _commit(node):
    """Commit changes to BIOS on the node."""

    driver_internal_info = node.driver_internal_info
    if 'bios_config_job_ids' not in driver_internal_info:
        driver_internal_info['bios_config_job_ids'] = []

        job_id = commit_config(node, reboot=True)

        LOG.info('Change has been committed to BIOS settings '
                 'on node %(node)s. DRAC job id: %(job_id)s',
                 {'node': node.uuid, 'job_id': job_id})

        driver_internal_info['bios_config_job_ids'].append(job_id)

    node.driver_internal_info = driver_internal_info
    node.save()

    if node.clean_step:
        return states.CLEANWAIT
    else:
        return states.DEPLOYWAIT


class DracBIOS(base.BIOSInterface):

    _APPLY_CONFIGURATION_ARGSINFO = {
        'settings': {
            'description': (
                'A list of BIOS settings to be applied'
            ),
            'required': True
        }
    }

    def validate(self, task):
        """Validates the driver information needed by the idrac driver.

        :param task: a TaskManager instance containing the node to act on.
        :raises: InvalidParameterValue on malformed parameter(s)
        :raises: MissingParameterValue on missing parameter(s)
        """
        drac_common.parse_driver_info(task.node)

    def get_properties(self):
        """Return the properties of the interface."""
        return drac_common.COMMON_PROPERTIES

    def cache_bios_settings(self, task):
        """Store or update the current BIOS settings for the node.

        Get the current BIOS settings and store them in the bios_settings
        database table.

        :param task: a TaskManager instance containing the node to act on.
        :raises: DracOperationError on an error from python-dracclient.
        """

        node_id = task.node.id
        attributes = get_config(task)
        settings = []
        # Convert Redfish BIOS attributes to Ironic BIOS settings
        if attributes:
            settings = [{'name': k, 'value': v['current_value']}
                        for k, v in attributes.items()]

        LOG.debug('Cache BIOS settings for node %(node_uuid)s',
                  {'node_uuid': task.node.uuid})

        create_list, update_list, delete_list, nochange_list = (
            objects.BIOSSettingList.sync_node_setting(
                task.context, node_id, settings))

        if create_list:
            objects.BIOSSettingList.create(
                task.context, node_id, create_list)
        if update_list:
            objects.BIOSSettingList.save(
                task.context, node_id, update_list)
        if delete_list:
            delete_names = [d['name'] for d in delete_list]
            objects.BIOSSettingList.delete(
                task.context, node_id, delete_names)

    @base.clean_step(priority=0)
    @base.deploy_step(priority=0)
    @base.cache_bios_settings
    def factory_reset(self, task):
        """Reset the BIOS settings of the node to the factory default.

        :param task: a TaskManager instance containing the node to act on.
        :raises: DracOperationError on an error from python-dracclient.
        """
        raise NotImplementedError()

    @base.clean_step(priority=0, argsinfo=_APPLY_CONFIGURATION_ARGSINFO)
    @base.deploy_step(priority=0, argsinfo=_APPLY_CONFIGURATION_ARGSINFO)
    @base.cache_bios_settings
    def apply_configuration(self, task, settings):
        """Apply the BIOS settings to the node.

        :param task: a TaskManager instance containing the node to act on.
        :param settings: a list of BIOS settings to be updated.
        :raises: DracOperationError on an error from python-dracclient.
        """
        # Convert Ironic BIOS settings to DRAC BIOS attributes
        attributes = {s['name']: s['value'] for s in settings}

        LOG.debug('Apply BIOS configuration for node %(node_uuid)s: '
                  '%(settings)r', {'node_uuid': task.node.uuid,
                                   'settings': settings})
        set_config(task, **attributes)
        return _commit(task.node)

    @METRICS.timer('DracBIOS._query_bios_config_job_status')
    @periodics.periodic(
        spacing=CONF.drac.query_bios_config_job_status_interval)
    def _query_bios_config_job_status(self, manager, context):
        """Periodic task to check the progress of running BIOS config jobs."""

        filters = {'reserved': False, 'maintenance': False}
        fields = ['driver_internal_info']

        node_list = manager.iter_nodes(fields=fields, filters=filters)
        for (node_uuid, driver, conductor_group,
             driver_internal_info) in node_list:
            try:
                lock_purpose = 'checking async bios configuration jobs'
                with task_manager.acquire(context, node_uuid,
                                          purpose=lock_purpose,
                                          shared=True) as task:
                    if not isinstance(task.driver.bios, DracBIOS):
                        continue

                    job_ids = driver_internal_info.get('bios_config_job_ids')
                    if not job_ids:
                        continue

                    self._check_node_bios_jobs(task)

            except exception.NodeNotFound:
                LOG.info("During query_bios_config_job_status, node "
                         "%(node)s was not found and presumed deleted by "
                         "another process.", {'node': node_uuid})
            except exception.NodeLocked:
                LOG.info("During query_bios_config_job_status, node "
                         "%(node)s was already locked by another process. "
                         "Skip.", {'node': node_uuid})

    @METRICS.timer('DracBIOS._check_node_bios_jobs')
    def _check_node_bios_jobs(self, task):
        """Check the progress of running BIOS config jobs of a node."""

        node = task.node
        bios_config_job_ids = node.driver_internal_info['bios_config_job_ids']
        finished_job_ids = []

        for config_job_id in bios_config_job_ids:
            config_job = drac_job.get_job(node, job_id=config_job_id)

            if config_job.status == 'Completed':
                finished_job_ids.append(config_job_id)
            elif config_job.status == 'Failed':
                finished_job_ids.append(config_job_id)
                self._set_bios_config_job_failure(node)

        if not finished_job_ids:
            return

        task.upgrade_lock()
        self._delete_cached_config_job_id(node, finished_job_ids)

        if not node.driver_internal_info['bios_config_job_ids']:
            if not node.driver_internal_info.get('bios_config_job_failure',
                                                 False):
                self._resume(task)
            else:
                self._clear_bios_config_job_failure(node)
                self._set_failed(task, config_job)

    def _set_bios_config_job_failure(self, node):
        driver_internal_info = node.driver_internal_info
        driver_internal_info['bios_config_job_failure'] = True
        node.driver_internal_info = driver_internal_info
        node.save()

    def _clear_bios_config_job_failure(self, node):
        driver_internal_info = node.driver_internal_info
        del driver_internal_info['bios_config_job_failure']
        node.driver_internal_info = driver_internal_info
        node.save()

    def _delete_cached_config_job_id(self, node, finished_config_job_ids=None):
        if finished_config_job_ids is None:
            finished_config_job_ids = []
        driver_internal_info = node.driver_internal_info
        unfinished_job_ids = [job_id for job_id
                              in driver_internal_info['bios_config_job_ids']
                              if job_id not in finished_config_job_ids]
        driver_internal_info['bios_config_job_ids'] = unfinished_job_ids
        node.driver_internal_info = driver_internal_info
        node.save()

    def _set_failed(self, task, config_job):
        LOG.error("BIOS configuration job failed for node %(node)s. "
                  "Failed config job: %(config_job_id)s. "
                  "Message: '%(message)s'.",
                  {'node': task.node.uuid, 'config_job_id': config_job.id,
                   'message': config_job.message})
        task.node.last_error = config_job.message
        task.process_event('fail')

    def _resume(self, task):
        # Signal that the node has been rebooted.
        flag_name = ('cleaning_reboot' if task.node.clean_step
                     else 'deployment_reboot')
        driver_internal_info = task.node.driver_internal_info
        driver_internal_info[flag_name] = True
        task.node.driver_internal_info = driver_internal_info
        task.node.save()
        if task.node.clean_step:
            manager_utils.notify_conductor_resume_clean(task)
        else:
            manager_utils.notify_conductor_resume_deploy(task)
