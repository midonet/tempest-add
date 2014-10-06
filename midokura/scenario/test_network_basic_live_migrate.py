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

import re
import os
import testtools

from tempest import test
from tempest import config

from midokura.scenario import manager

LOG = manager.log.getLogger(__name__)
SCPATH = "/network_scenarios/"
CONF = config.CONF

class TestNetworkBasicLiveMigrate(manager.AdvancedNetworkScenarioTest):
    """
        Scenario:
            Live migration
        Prerequisite:
            1 tenant
            1 network
            1 vm
        Steps:
            1) spawn the VM
            2) do an ssh to the VM's FIP
            3) SSH to the VM using the FIP from the exterior
            4) Keep SSH session open
            5) Live migrate the VM
        Expected result:
            SSH connection remains open after migration
    """

    @classmethod
    def resource_setup(cls):
        super(TestNetworkBasicLiveMigrate, cls).resource_setup()
        cls.builder = TestNetworkBasicLiveMigrate(builder=True)
        cls.servers_and_keys = cls.builder.setup_topology(
            os.path.abspath(
                '{0}scenario_basic_live_migrate.yaml'.format(SCPATH)))

    def _get_compute_other_than(self, current_host):
        ## Get all hostnames
        all_hosts = self._get_compute_hostnames()
        ## Get hostname other than current hostname
        for host in all_hosts:
            if host != current_host:
                return host

    @testtools.skipUnless(CONF.compute_feature_enabled.live_migration,
                          'Live migration not available')
    @test.attr(type='smoke')
    @test.services('compute', 'network')
    def test_network_basic_live_migrate(self):
        if len(self._get_compute_hostnames()) < 2:
            raise self.skipTest(
                "Less than 2 compute nodes, skipping migration test.")

        for server_def in self.servers_and_keys:
            server = server_def['server']
            hops = [(server_def['FIP'].floating_ip_address,
                     server_def['keypair']['private_key'])]
            client = self.setup_tunnel(hops, keep_connection=True)

            # Before migrate, take the hostname
            vm_host1 = client.exec_command("hostname")
            # Pick a target host different than current host
            current_host = self._get_host_for_server(server['id'])
            target_host = self._get_compute_other_than(current_host)
            # Migrate server with block migration and wait for server status active
            body = self.admin_manager.servers_client.live_migrate_server(
                server['id'],
                target_host,
                True) # True for block live migration
            self.admin_manager.servers_client.wait_for_server_status(server['id'], 'ACTIVE')
            self.assertEqual(target_host, self._get_host_for_server(server['id']))
            # Check that the ssh connection is still open
            vm_host2 = client.exec_command("hostname")
            self.assertTrue(vm_host1 == vm_host2)

        LOG.info("test finished, tearing down now ....")
