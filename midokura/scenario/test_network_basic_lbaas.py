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

import os

from tempest import config
from tempest import test

from midokura.scenario import manager
from midokura.scenario.test_network_helper_lbaas import TestLoadBalancerHelper

CONF = config.CONF
LOG = manager.log.getLogger(__name__)
SCPATH = "/network_scenarios/"


class TestLoadBalancerBasic(manager.AdvancedNetworkScenarioTest,
                            TestLoadBalancerHelper):
    """
        Scenario:
        A client access a VIP (load balancer) and access
        backends according to algorithm and session persistence
        from the outside world

        Pre-requisites:
        1 tenant
        1 private network
        2 VMs / backends

        Steps:
        1. Create private subnet A
        2. Launch two VMs listening on port 80 on subnet A
        3. Create pool with these two VMs
        4. Create LoadBalancer with RR algorithm
        5. Create a VIP on public subnet

        Accessing the public VIP should HIT both backends

        6. Update the VIP to session_persistence = SOURCE_IP

        Accessing the public VIP should HIT only 1 backend

        7. Check health monitoring by shutting down one VM
           Only one backend should answer without hitting the faulty one
    """

    @classmethod
    def resource_setup(cls):
        super(TestLoadBalancerBasic, cls).resource_setup()
        # With two backends and 25 requests, according to mdts
        # 1/((1/2)^(25-1)) -> 1/16m chance of not hitting all backends
        cls.init_setup()
        cls.builder = TestLoadBalancerBasic(builder=True)
        cls.servers_and_keys = \
            cls.builder.setup_topology(
                '{0}scenario_basic_lbaas.yaml'.format(SCPATH))
        cls.pool = dict()

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
                members = cls.pool.setdefault('members', [])
                members.append((ip_address, hostname, server_id))
        public_net = cls.builder._list_networks(id=CONF.network.public_network_id)[0]
        cls.pool['vip_subnet_id'] = public_net['subnets'][0]

    def _get_remote_client(self, server):
        host_ip = server['FIP'].floating_ip_address
        host_key = server['keypair']['private_key']
        hops = [(host_ip, host_key)]
        linux_client = self.setup_tunnel(hops)
        return linux_client

    def _make_client_request(self, command):
        return os.popen(command).read().rstrip()

    @test.attr(type='smoke')
    @test.services('compute', 'network')
    def test_network_lbaas_round_robin(self):
        super(TestLoadBalancerBasic, self).lbaas_round_robin()

    @test.attr(type='smoke')
    @test.services('compute', 'network')
    def test_network_lbaas_round_robin_with_session_persistence(self):
        super(TestLoadBalancerBasic, self).lbaas_round_robin_with_session_persistence()

    @test.attr(type='smoke')
    @test.services('compute', 'network')
    def test_network_lbaas_health_monitoring(self):
        super(TestLoadBalancerBasic, self).lbaas_health_monitoring()
