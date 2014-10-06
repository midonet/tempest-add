
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


class TestNetworkBasicDNAT(manager.AdvancedNetworkScenarioTest):

    """
        Scenario:
        A launched VM should get an ip address and
        routing table entries from DHCP. And
        it should be able to metadata service.

        Pre-requisites:
        1 tenant
        1 Public router with FIP
        1 network
        1 VM without FIP

        Steps:
        1. create a network
        2. launch a VM
        3. Create a HTTP server on tempesthost
        4. Navigate the HTTP server from the VM
        5. assert that the vm can reach it without FIP
            or any other extra routes and get the response.
        6. Same with ICMP
        7. Same with UDP

        Expected results:
        Reads the web page
        Pings the tempest host
        Gets a response from udp nc server
    """

    @classmethod
    def resource_setup(cls):
        super(TestNetworkBasicDNAT, cls).resource_setup()
        cls.builder = TestNetworkBasicDNAT(builder=True)
        cls.servers_and_keys = cls.builder.setup_topology(
            os.path.abspath(
                '{0}scenario_basic_dnat.yaml'.format(SCPATH)))

    @test.attr(type='smoke')
    @test.services('compute', 'network')
    def test_network_basic_dnat(self):
        ap_details = self.servers_and_keys[-1]
        access_point = ap_details['server']
        networks = access_point['addresses']
        hops = [(ap_details['FIP'].floating_ip_address,
                 ap_details['keypair']['private_key'])]
        # the access_point server should be the last one in the list
        ap_client = self.setup_tunnel(hops)
        get_ip = ap_client.exec_command(
            "netstat | grep ssh | awk '{print $5}'").split(':')[0]
        http_server = http.myHTTPServer(port=8089, ip=get_ip)
        p = Process(target=http_server.start)
        p.daemon = True
        p.start()
        process = self.netcat_local(get_ip, '50000')
        element = self.servers_and_keys[0]
        server = element['server']
        name = server['addresses'].keys()[0]
        if any(i in networks.keys() for i in server['addresses'].keys()):
            remote_ip = server['addresses'][name][0]['addr']
            keypair = element['keypair']
            privatekey = keypair['private_key']
            hops.append((remote_ip, privatekey))
            ssh_client = self.setup_tunnel(hops)
            resp = ssh_client.exec_command(
                'curl http://{0}:8089/'.format(get_ip))
            self.assertEqual('Hello world!', resp)
            self._ping_through_gateway(hops, [get_ip])
            resp = ssh_client.exec_command("echo ping | nc -u -w 2 %s 50000" %
                                           get_ip).rstrip()
            self.kill_me('nc')
            process.kill()
            self.assertEqual('pong', resp)
            self._clean_netcat_local()
        else:
            LOG.info("FAIL - No ip connectivity to the server ip: %s"
                     % server.networks[name][0])
            raise Exception("FAIL - No ip for this network : %s"
                            % server.networks)
        LOG.info("test finished, tearing down now ....")
