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

import shlex

from ironic.common import utils
from ironic.conf import CONF
from ironic.console.container import container

# The VNC port the console container app listens on. With host
# networking the container's port is the host's port.
VNC_PORT = 5900


class ContainerKollaConsoleContainer(container.ContainerConsoleContainer):
    """Console container provider where port publication is not possible.

    The console container is run with host networking instead of a
    published port, so the VNC server listens on port 5900 of the
    conductor host and no port discovery through the engine is needed.
    The engine must run on the conductor host, as the container joins
    the host network.
    """

    provider_name = 'container-kolla'

    def _render_template(self, uuid='', app_name=None):
        """Render the run command template to an argument vector.

        As in the container provider, but renders
        [vnc]container_kolla_command_template, whose default template
        replaces the published port with --network host. app_info is
        deliberately not a template variable, as in the container
        provider: it contains BMC credentials which must not appear on
        a command line, so it is passed via the CLI process environment
        instead.

        :param uuid: Unique identifier for the node.
        :param app_name: Name of the application to run in the container.
        :returns: A list of arguments for the container CLI.
        """
        params = {
            'uuid': uuid,
            'image': CONF.vnc.console_image,
            'app': app_name or 'fake',
            'read_only': CONF.vnc.read_only,
            'conductor': CONF.host,
            'my_ip': CONF.my_ip,
        }
        rendered = utils.render_template(
            CONF.vnc.container_kolla_command_template, params=params)
        return shlex.split(rendered, comments=True)

    def _host_port(self, container):
        """Return the VNC host and port for a container.

        With host networking the container has no published ports: the
        VNC server listens on port 5900 of the conductor host, so the
        endpoint is known without querying the engine.

        :param container: container name (unused)
        :returns: Tuple of host IP address and port
        """
        return CONF.my_ip, VNC_PORT
