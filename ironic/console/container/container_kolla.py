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
Console container provider for containerised deployments such as Kolla
where the container engine cannot publish container ports to the host.
"""

import json
import shlex
import threading

from oslo_concurrency import processutils
from oslo_log import log as logging

from ironic.common import exception
from ironic.common import utils
from ironic.conf import CONF
from ironic.console.container import container

LOG = logging.getLogger(__name__)

# Label carrying the VNC port allocated to a console container. It is
# read back to determine a container's endpoint and to find which ports
# of [vnc]container_kolla_vnc_port_range are already taken.
VNC_PORT_LABEL = f'{container.LABEL_PREFIX}.vnc-port'

# Offset of the container's loopback-only shutdown signalling HTTP port
# from its VNC port. Any constant offset works: it only needs to be
# injective so that two containers on the same host never share a
# signalling port. The configured VNC port range must therefore not
# overlap the same range shifted by this offset.
SHUTDOWN_HTTP_PORT_OFFSET = 1000

# The VNC port the console container app listens on when VNC_PORT is
# not set.
DEFAULT_VNC_PORT = 5900


class ContainerKollaConsoleContainer(container.ContainerConsoleContainer):
    """Console container provider where port publication is not possible.

    The console containers are run with host networking instead of a
    published port: each container's VNC server listens on its own
    allocated port on the conductor host, so multiple consoles can be
    running on one conductor at once. The engine must run on the
    conductor host, as the containers join the host network.
    """

    provider_name = 'container-kolla'

    template_option = 'container_kolla_command_template'

    def __init__(self):
        super().__init__()
        # Serialise port allocation with the container run so that two
        # concurrent console starts cannot be given the same VNC port.
        self._port_lock = threading.Lock()

    def _render_template(self, uuid='', app_name=None, vnc_port=None):
        """Render the run command template to an argument vector.

        As in the container provider, but renders
        [vnc]container_kolla_command_template, whose default template
        replaces the published port with --network host and passes the
        allocated VNC port to the container as environment. app_info is
        deliberately not a template variable, as in the container
        provider: it contains BMC credentials which must not appear on
        a command line, so it is passed via the CLI process environment
        instead.

        :param uuid: Unique identifier for the node.
        :param app_name: Name of the application to run in the container.
        :param vnc_port: VNC port the container will listen on on the
                         conductor host. Unset during the template
                         validity check in the constructor.
        :returns: A list of arguments for the container CLI.
        """
        vnc_port = vnc_port or DEFAULT_VNC_PORT
        params = {
            'uuid': uuid,
            'image': CONF.vnc.console_image,
            'app': app_name or 'fake',
            'read_only': CONF.vnc.read_only,
            'conductor': CONF.host,
            'my_ip': CONF.my_ip,
            'vnc_port': vnc_port,
            'shutdown_http_port': vnc_port + SHUTDOWN_HTTP_PORT_OFFSET,
        }
        rendered = utils.render_template(
            CONF.vnc.container_kolla_command_template, params=params)
        return shlex.split(rendered, comments=True)

    def _allocated_vnc_ports(self):
        """Return the VNC ports in use by this conductor's containers.

        The ports are read from the vnc-port label of the running
        console containers the engine reports for this conductor, so
        containers left over from a previous conductor run are
        accounted for as well.

        :returns: Set of VNC ports in use
        """
        out, _ = self._execute(
            'ps', '--format', f'{{{{.Label "{VNC_PORT_LABEL}"}}}}',
            '--filter',
            f'label={container.LABEL_PREFIX}.conductor={CONF.host}')
        ports = set()
        for line in out.split():
            try:
                ports.add(int(line))
            except ValueError:
                # '<no value>' for containers without the label
                continue
        return ports

    def _allocate_vnc_port(self):
        """Allocate the lowest free VNC port for a new console container.

        The ports of this conductor's running console containers are
        excluded, whatever the origin of the containers.

        :returns: An allocated VNC port
        :raises: ConsoleContainerError when no port of
                 [vnc]container_kolla_vnc_port_range is free
        """
        in_use = self._allocated_vnc_ports()
        for port_range in CONF.vnc.container_kolla_vnc_port_range:
            for port in port_range:
                if port not in in_use:
                    return port
        raise exception.ConsoleContainerError(
            provider=self.provider_name,
            reason='No free VNC port: all ports of '
                   '[vnc]container_kolla_vnc_port_range are in use by '
                   'console containers of this conductor.')

    def _host_port(self, container):
        """Return the VNC host and port for a container.

        With host networking the container has no published ports: the
        VNC server listens on the port the provider allocated for the
        container, which is recorded in its vnc-port label, so the
        endpoint is read from the engine and no port discovery is
        needed.

        :param container: container name
        :returns: Tuple of host IP address and VNC port
        :raises: ConsoleContainerError
        """
        try:
            out, _ = self._execute(
                'inspect', '--format',
                f'{{{{.Config.Labels."{VNC_PORT_LABEL}"}}}}', container)
        except processutils.ProcessExecutionError as e:
            LOG.exception('Problem calling %s inspect %s',
                          CONF.vnc.container_executable, container)
            raise exception.ConsoleContainerError(
                provider=self.provider_name, reason=e)

        try:
            port = int(out.strip())
        except ValueError:
            raise exception.ConsoleContainerError(
                provider=self.provider_name,
                reason=f'Could not read the {VNC_PORT_LABEL} label of '
                       f'container {container}: {out.strip()}')
        return CONF.my_ip, port

    def start_container(self, task, app_name, app_info):
        """Start a console container for a node.

        As in the container provider, but the container's VNC port is
        allocated from [vnc]container_kolla_vnc_port_range and passed
        to the container, because with host networking there is no
        published port to discover: the VNC server listens on the
        allocated port of the conductor host.

        :param task: A TaskManager instance.
        :param app_name: Sets container environment APP value
        :param app_info: Sets container environment APP_INFO value
        :returns: Tuple of host IP address and VNC port
        :raises: ConsoleContainerError
        """
        uuid = task.node.uuid
        LOG.debug('Starting console container for node %s', uuid)

        container_name = self._container_name(uuid)
        # NOTE: remove any stale container so a retried start, or a
        # node which has moved between conductors, cannot collide with
        # a leftover name, as in the container provider.
        self._remove_container(container_name)

        try:
            # NOTE: the allocation and the run are serialised so two
            # concurrent starts cannot be given the same VNC port.
            with self._port_lock:
                vnc_port = self._allocate_vnc_port()
                run_args = self._render_template(uuid, app_name, vnc_port)
                # NOTE: app_info contains BMC credentials, so it is
                # supplied through the CLI process environment for the
                # value-less '--env APP_INFO' entry, never on a command
                # line.
                self._execute(*run_args, env={'APP_INFO': json.dumps(
                    app_info)})
            host, port = self._host_port(container_name)
            self._wait_for_listen(host, port)
        except exception.ConsoleContainerError:
            self._handle_failed_start(container_name, uuid)
            raise
        except Exception as e:
            self._handle_failed_start(container_name, uuid)
            raise exception.ConsoleContainerError(
                provider=self.provider_name, reason=e)
        return host, port
