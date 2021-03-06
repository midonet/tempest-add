
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
import pprint

from tempest import config
from tempest import test

from midokura.scenario import manager
from midokura.midotools import helper

CONF = config.CONF
LOG = manager.log.getLogger(__name__)
# path should be described in tempest.conf
SCPATH = "/network_scenarios/"


class TestNetworkBasicMultitenants(manager.AdvancedNetworkScenarioTest):
    """
        Description:
        Overlapping IP in different tenants

        Scenario:
        VMs with overlapping ip address in different
        tenants should not interfare each other

        Prerequisites:
        - 2 tenants
        - 1 network for each tenant
        - 1 subnet with same CIDR for each tenant

        Steps:
        This testing requires that an option
        "allow_overlapping_ips = True
        " is configured in neutron.conf file

        1. launch VMs with overlapping IP
        2. make sure they are not interfered
        3. curl http://169.254.169.254/latest/meta-data-instance-id
           and make sure it correctly identifies the VM

        Expected result:
        should succeed
    """

    @classmethod
    def resource_setup(cls):
        super(TestNetworkBasicMultitenants, cls).resource_setup()
        cls.builder = TestNetworkBasicMultitenants(builder=True)
        cls.scenarios = cls.builder.setup_topology(
            os.path.abspath(
                '{0}scenario_basic_multitenant.yaml'.format(SCPATH)))

    def _route_and_ip_test(self, ssh_client, remote_ip):
        LOG.info("Trying to get the list of ips")
        try:
            net_info = ssh_client.get_ip_list()
            LOG.debug(net_info)
            pattern = re.compile(
                '[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}')
            _list = pattern.findall(net_info)
            LOG.debug(_list)
            self.assertIn(remote_ip, _list)
            route_out = ssh_client.exec_command("sudo /sbin/route -n")
            self._check_default_gateway(route_out, remote_ip)
            LOG.info(route_out)
        except Exception as inst:
            LOG.info(inst)
            raise

    def _check_metadata(self, ssh_client, server):
        meta_out = ssh_client.exec_command(
            "curl http://169.254.169.254/latest/meta-data/instance-id")
        meta_instid = meta_out.split('-')[1]
        server_instid = server['OS-EXT-SRV-ATTR:instance_name'].split('-')[1]
        LOG.debug("metadata instance-id: " + meta_instid)
        LOG.debug("server instance-id: " + server_instid)
        self.assertTrue(meta_instid == server_instid)

    def _check_default_gateway(self, route_out, internal_ip):
        try:
            rtable = helper.Routetable.build_route_table(route_out)
            LOG.debug(rtable)
            self.assertTrue(any([r.is_default_route() for r in rtable]))
        except Exception as inst:
            LOG.info(inst.args)
            raise

    @test.attr(type='smoke')
    @test.services('compute', 'network')
    def test_network_basic_multitenant(self):
        for creds_and_scenario in self.scenarios:
            self._multitenant_test(creds_and_scenario)
        LOG.info("test finished, tearing down now ....")

    def _multitenant_test(self, creds_and_scenario):
        # the access_point server should be the last one in the list
        creds = creds_and_scenario['credentials']
        self.set_context(creds)
        servers_and_keys = creds_and_scenario['servers_and_keys']
        ap_details = servers_and_keys[-1]
        networks = ap_details['server']['addresses']
        hops = [(ap_details['FIP'].floating_ip_address,
                ap_details['keypair']['private_key'])]
        for element in servers_and_keys[:-1]:
            server = element['server']
            name = server['addresses'].keys()[0]
            LOG.debug("Server dict\n:" + pprint.pformat(server))
            if any(i in networks.keys() for i in server['addresses'].keys()):
                remote_ip = server['addresses'][name][0]['addr']
                privatekey = element['keypair']['private_key']
                hops.append((remote_ip, privatekey))
                ssh_client = self.setup_tunnel(hops)
                self._route_and_ip_test(ssh_client, hops[-1][0])
                self._check_metadata(ssh_client, server)
