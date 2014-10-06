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

import six

from tempest import config
from tempest import exceptions
from tempest.common.utils.linux import remote_client
from tempest.scenario import manager

import midokura.midotools.ssh as ssh


CONF = config.CONF
LOG = manager.log.getLogger(__name__)


class RemoteClient(remote_client.RemoteClient):
    """
    This remote client allows the creation of ssh tunnels.
    """

    def __init__(self, server, username, password=None, pkey=None, gws=None, keep_connection=True):
        LOG.info("Using our remote client...")
        ssh_timeout = CONF.compute.ssh_timeout
        network = CONF.compute.network_for_ssh
        ip_version = CONF.compute.ip_version_for_ssh
        ssh_channel_timeout = CONF.compute.ssh_channel_timeout
        if isinstance(server, six.string_types):
            ip_address = server
        else:
            addresses = server['addresses'][network]
            for address in addresses:
                if address['version'] == ip_version:
                    ip_address = address['addr']
                    break
            else:
                raise exceptions.ServerUnreachable()
        self.ssh_client = ssh.Client(ip_address, username, password,
                                     ssh_timeout, pkey=pkey,
                                     channel_timeout=ssh_channel_timeout,
                                     gws=gws, keep_connection=keep_connection)

    def exec_command(self, cmd, cmd_timeout=0):
        return self.ssh_client.exec_command(cmd, cmd_timeout)
