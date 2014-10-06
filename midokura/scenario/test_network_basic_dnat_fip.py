
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

from tempest import test

from multiprocessing import Process
from midokura.midotools import http
from midokura.scenario import manager


LOG = manager.log.getLogger(__name__)
# path should be described in tempest.conf
SCPATH = "/network_scenarios/"


class TestNetworkBasicDNATFIP(manager.AdvancedNetworkScenarioTest):

    """
        Scenario:
        A launched VM should get an ip address and
        routing table entries from DHCP. And
        it should be able to metadata service.

        Pre-requisites:
        1 tenant
        1 Public router
        1 network
        1 VM with FIP

        Steps:
        1. create a network
        2. launch a VM
        3. Create a HTTP server on tempesthost
        4. Navigate the HTTP server from the VM
        5. assert that the vm can reach it without FIP
            or any other extra routes and gets server response
        6. Same with ICMP
        7. Same with UDP

        Expected results:
        Reads teh http web page
        Pings the tempest host machine
        Gets a response from udp server
    """

    @classmethod
    def resource_setup(cls):
        super(TestNetworkBasicDNATFIP, cls).resource_setup()
        cls.builder = TestNetworkBasicDNATFIP(builder=True)
        cls.servers_and_keys = cls.builder.setup_topology(
            os.path.abspath(
                '{0}scenario_basic_dnat_fip.yaml'.format(SCPATH)))

    @test.attr(type='smoke')
    @test.services('compute', 'network')
    def test_network_basic_dnat_fip(self):
        server_details = self.servers_and_keys[0]
        hops = [(server_details['FIP'].floating_ip_address,
                 server_details['keypair']['private_key'])]
        # the access_point server should be the last one in the list
        client = self.setup_tunnel(hops)
        get_ip = client.exec_command(
            "netstat | grep ssh | awk '{print $5}'").split(':')[0]
        http_server = http.myHTTPServer(port=8098, ip=get_ip)
        p = Process(target=http_server.start)
        p.daemon = True
        p.start()
        process = self.netcat_local(get_ip, '6666')
        resp = client.exec_command(
            'curl http://{0}:8098/'.format(get_ip))
        self.assertEqual('Hello world!', resp)
        self.assertTrue(self._check_remote_connectivity(client,
                                                        get_ip,
                                                        True))
        resp = client.exec_command("echo ping | nc -u -w 2 %s 6666" %
                                   get_ip).rstrip()
        process.kill()
        self.kill_me('nc')
        self.assertEqual('pong', resp)
        self._clean_netcat_local()
        LOG.info("test finished, tearing down now ....")
