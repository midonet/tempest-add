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

import time

from tempest import config
from tempest import exceptions

from midokura.scenario import manager

CONF = config.CONF
LOG = manager.log.getLogger(__name__)


class TestLoadBalancerHelper():
    """
        Scenario:
        Helper class to factor common code between basic
        and advanced lbaas scenarios. The description should
        be found on the implementation test class.
    """

    @classmethod
    def init_setup(cls):
        ''' Should be called inside setUp method of test class'''
        cls.num_requests = 25
        cls.max_failures = 4
        cls.protocol_port = 8080

    def _start_servers(self):
        for server in self.members_and_keys:
            self._start_server(server)

    def _start_server(self, server):
        # Start netcat command
        server_name = server['server']['name']
        start_server = 'while true; do ' \
                       'nc -l -p %d -e echo %s; ' \
                       'done &' % (self.protocol_port, server_name)
        linux_client = self._get_remote_client(server)
        linux_client.exec_command(start_server)
        self.addCleanup(self._stop_server, server, linux_client)

    def _stop_server(self, server, linux_client):
        # Stop netcat command
        while_pid = linux_client.exec_command("ps aux|grep while|head -n 1").split()[0]
        stop_server = 'kill -9 %s && killall -9 nc' % while_pid
        linux_client.exec_command(stop_server)

    def __create_pool(self, pool_dict, lb_method, health_monitor):
        pool = self._create_pool(
            lb_method=lb_method,
            protocol='TCP',
            subnet_id=pool_dict['subnet']['id'])
        if health_monitor:
            create_kwargs = {
                "type": "TCP",
                "delay": 1,
                "timeout": 1,
                "max_retries": 3}
            self._create_health_monitor(pool.id, create_kwargs)
        self.assertTrue(pool)
        pool_dict['pool'] = pool

    def _create_members(self, pool_dict):
        for ip_address, hostname, server_id in pool_dict['members']:
            member = self._create_member(address=ip_address,
                                         protocol_port=self.protocol_port,
                                         pool_id=pool_dict['pool'].id)
            self.assertTrue(member)

    def _create_load_balancer(self, pool_dict, lb_method,
                              health_monitor=False):
        self.__create_pool(pool_dict, lb_method, health_monitor)
        self._create_members(pool_dict)
        # Creates a VIP from the pub subnet
        vip = self._create_vip(protocol='TCP',
                               protocol_port=self.protocol_port,
                               subnet_id=pool_dict['vip_subnet_id'],
                               pool_id=pool_dict['pool'].id)
        pool_dict['vip'] = vip
        self.assertTrue(vip)

    def _connect_to_server(self, ip):
        nc_command = "nc %s %d" % (ip, self.protocol_port)
        server = self._make_client_request(nc_command)
        if 'backend' in server:
            LOG.info("Connection successfull to %s [%s]" % (ip, server))
            return server
        else:
            LOG.info("ERROR connecting to %s" % ip)
            return None

    def _check_connection(self, vip):
        timeout = CONF.compute.ping_timeout
        start = time.time()
        while not self._connect_to_server(vip.address):
            # Allow some time for busybox nc to be alive
            time.sleep(1)
            if (time.time() - start) > timeout:
                message = "Timeout out trying to connecto to %s" % vip.address
                raise exceptions.TimeoutException(message)

    def _send_requests(self, vip, members):
        hostnames = [hostname for _, hostname, _ in members]
        counters = dict.fromkeys(hostnames, 0)
        counters.setdefault('failures', 0)
        for i in range(self.num_requests):
            server_response = self._connect_to_server(vip.address)
            if not server_response:
                LOG.info(server_response)
                counters['failures'] += 1
                LOG.info("LOAD_BALANCER: Error connecting to VIP")
            else:
                counters[server_response] += 1
                LOG.info("LOAD_BALANCER: Hit %s" % server_response)
            # Workarround to allow nc (busybox) to respawn, quite flacky
            time.sleep(1)
        return counters

    def _check_balancing_method(self, counters, persistence):
        unique_members = [member
                          for member, counter in counters.items()
                          if counter > 0 and 'backend' in member]
        all_members = [member
                       for member, counter in counters.items()
                       if 'backend' in member]
        LOG.info("DEBUG ROUND ROBIN")
        LOG.info("Failures %d" % counters['failures'])
        LOG.info(unique_members)
        LOG.info(all_members)
        if not persistence:
            self.assertTrue(len(unique_members) == len(all_members),
                            "Not all members were balanced (ROUND_ROBIN)")
        else:
            LOG.info("WITH SOURCE_IP PERSISTENCE")
            self.assertTrue(len(unique_members) == 1,
                            "More than one backend was balanced (SOURCE_IP)")
        # nc is quite flaky, support a minimum number of failures but report an
        # error when this number is high enough
        self.assertTrue(counters['failures'] < self.max_failures,
                        "Some requests failed to hit the backends")

    def lbaas_round_robin(self):
        self._start_servers()
        self._create_load_balancer(self.pool, 'ROUND_ROBIN')
        # Check without session persistence (default)
        self._check_connection(self.pool['vip'])
        counters = self._send_requests(self.pool['vip'],
                                       self.pool['members'])
        self._check_balancing_method(counters, persistence=False)
        LOG.info("test finished, tearing down now ....")

    def lbaas_round_robin_with_session_persistence(self):
        self._start_servers()
        self._create_load_balancer(self.pool, 'ROUND_ROBIN')
        # Check with session persistence
        self.network_client.update_vip(
            self.pool['vip'].id,
            session_persistence={'type': 'SOURCE_IP'})
        counters = self._send_requests(self.pool['vip'],
                                       self.pool['members'])
        self._check_balancing_method(counters, persistence=True)
        LOG.info("test finished, tearing down now ....")

    def lbaas_health_monitoring(self):
        self._start_servers()
        self._create_load_balancer(self.pool, 'ROUND_ROBIN',
                                   health_monitor=True)
        counters = self._send_requests(self.pool['vip'],
                                       self.pool['members'])
        self._check_balancing_method(counters, persistence=False)

        # Get the port to update up/down from the device_id
        server_id = self.pool['members'][0][2]
        server_port = self._list_ports(device_id=server_id)[0]
        self.network_client.update_port(server_port['id'],
                                        admin_state_up=False)
        # Bring up the port again to adminstateup True
        # at the end of the test
        self.addCleanup(self.network_client.update_port,
                        server_port['id'],
                        admin_state_up=True)
        # Wait for the health monitor to detect the wakeup member
        time.sleep(10)
        counters = self._send_requests(self.pool['vip'],
                                       self.pool['members'])
        self._check_balancing_method(counters, persistence=True)
        LOG.info("test finished, tearing down now ....")
