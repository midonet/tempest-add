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

from tempest import config
from tempest import test

from midokura.scenario import manager
from midokura.scenario.test_network_helper_lbaas import TestLoadBalancerHelper

CONF = config.CONF
LOG = manager.log.getLogger(__name__)
SCPATH = "/network_scenarios/"


class TestLoadBalancerAdvanced(manager.AdvancedNetworkScenarioTest,
                               TestLoadBalancerHelper):
    """
        Scenario:
        A client access a VIP (load balancer) and access
        backends according to algorithm and session persistence

        Pre-requisites:
        1 tenant
        2 private networks
        1 client
        2 VMs / backends

        Steps:
        1. Create private subnetA and subnetB
        2. Launch two VMs on subnetB
        3. Launch a VM (client) on subnetA
        4. Create pool with these two VMs
        5. Create LoadBalancer with RR algorithm
        6. Create a VIP on subnet A

        Accessing the VIP from client should HIT both backends

        7. Update the VIP to session_persistence = SOURCE_IP

        Accessing the VIP from client should HIT only 1 backend

        Note: health monitoring for private nets doesn't work
    """

    @classmethod
    def resource_setup(cls):
        super(TestLoadBalancerAdvanced, cls).resource_setup()
        # With two backends and 25 requests, according to mdts
        # 1/((1/2)^(25-1)) -> 1/16m chance of not hitting all backends
        cls.init_setup()
        cls.builder = TestLoadBalancerAdvanced(builder=True)
        cls.servers_and_keys = \
            cls.builder.setup_topology(
                '{0}scenario_advanced_lbaas.yaml'.format(SCPATH))
        cls.pool = dict()
        # Get the server acting as the gateway
        cls.accesspoint = cls.servers_and_keys[-1]

        # Get the server acting as the client
        client_and_key = next(server
                              for server in cls.servers_and_keys
                              if 'client' in server['server']['name'])
        net_name = client_and_key['server']['addresses'].keys()[0]
        net = cls.builder._get_network_by_name(net_name)[0]
        cls.pool['vip_subnet_id'] = net['subnets'][0]
        # Get an ssh connection to the client
        cls.request_client = cls.builder._get_remote_client(client_and_key)

        # Get members
        cls.members_and_keys = [server
                                 for server in cls.servers_and_keys
                                 if 'backend' in server['server']['name']]
        for server in cls.members_and_keys:
            for net_name, net_host in server['server']['addresses'].items():
                net = cls.builder._get_network_by_name(net_name)[0]
                subnet = cls.builder._list_subnets(id=net['subnets'][0])[0]
                ip_address = net_host[0]['addr']
                hostname = server['server']['name']
                server_id = server['server']['id']
                cls.pool.setdefault('subnet', subnet)
                cls.pool['vip_subnet_id'] = subnet['id']
                members = cls.pool.setdefault('members', [])
                members.append((ip_address, hostname, server_id))

    def _get_remote_client(self, server):
        ap_ip = self.accesspoint['FIP'].floating_ip_address
        ap_key = self.accesspoint['keypair']['private_key']
        net_name = server['server']['addresses'].keys()[0]
        host_ip = server['server']['addresses'][net_name][0]['addr']
        host_key = server['keypair']['private_key']
        hops = [(ap_ip, ap_key), (host_ip, host_key)]
        linux_client = self.setup_tunnel(hops)
        return linux_client

    def _make_client_request(self, command):
        return self.request_client.exec_command(command, 5).rstrip()

    @test.attr(type='smoke')
    @test.services('compute', 'network')
    def test_network_lbaas_round_robin(self):
        super(TestLoadBalancerAdvanced, self).lbaas_round_robin()

    @test.attr(type='smoke')
    @test.services('compute', 'network')
    def test_network_lbaas_round_robin_with_session_persistence(self):
        super(TestLoadBalancerAdvanced, self).lbaas_round_robin_with_session_persistence()
