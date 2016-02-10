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


from openstack_dashboard.test.integration_tests import decorators
from openstack_dashboard.test.integration_tests import helpers
from openstack_dashboard.test.integration_tests.regions import messages

INSTANCE_NAME = helpers.gen_random_resource_name('instance',
                                                 timestamp=False)
ROUTER_NAME = helpers.gen_random_resource_name('router',
                                               timestamp=False)
NETWORK_NAME = helpers.gen_random_resource_name('network',
                                                timestamp=False)
SUBNET_NAME = helpers.gen_random_resource_name('subnet',
                                               timestamp=False)


@decorators.services_required("neutron")
class TestNetworkTopology(helpers.AdminTestCase):

    def test_create_delete_instance_from_network_topology(self):
        """This test checks create/delete instance from network topology page
            Steps:
            1) Login to Horizon Dashboard as reqular user
            2) Go to the Project -> Network -> Network Topology page
            3) Launch new instance from current page
            4) Check instance status (via popup window)
            5) Wait for SVG fully loading (wait for stable state)
            6) Get all instances, routers and networks
            7) Check that all instances are linked to internal network
            8) Check that there are no direct links between instances and
            external network
            9) Check that internal and external networks are linked
            through router
            10) Delete instance
        """
        network_topology_page = \
            self.home_pg.go_to_network_networktopologypage()
        network_topology_page.create_instance_ng(INSTANCE_NAME)
        self.assertFalse(
            network_topology_page.find_message_and_dismiss(messages.ERROR))

        network_topology_page.topology.wait_for_svg_loads()
        network_topology_page.show_labels()
        instances = network_topology_page.topology.get_instances()
        for instance in instances:
            self.assertTrue(
                network_topology_page.topology.is_status_active(instance))

        network_topology_page.topology.wait_for_svg_loads()
        instances = network_topology_page.topology.get_instances()
        int_net = network_topology_page.topology.get_internal_networks()[0]
        ext_net = network_topology_page.topology.get_external_networks()[0]
        router = network_topology_page.topology.get_routers()[0]

        for instance in instances:
            self.assertTrue(network_topology_page.topology.
                            is_link_between_nodes_available(instance, int_net))
            self.assertFalse(
                network_topology_page.topology.is_link_between_nodes_available
                (instance, ext_net))
        self.assertTrue(network_topology_page.topology.
                        is_link_between_nodes_available(int_net, router))
        self.assertTrue(network_topology_page.topology.
                        is_link_between_nodes_available(router, ext_net))
        self.assertFalse(network_topology_page.topology.
                         is_link_between_nodes_available(int_net, ext_net))

        for instance in instances:
            network_topology_page.topology.delete_instance(instance)
            self.assertTrue(network_topology_page.find_message_and_dismiss(
                messages.SUCCESS))

        network_topology_page.topology.wait_for_svg_loads()
        instances = network_topology_page.topology.get_instances()
        self.assertEqual(len(instances), 0)

    def test_toggle_network(self):
        """This test checks possibility to collapse/expand network
            Steps:
            1) Login to Horizon Dashboard as reqular user
            2) Go to the Project -> Network -> Network Topology page
            3) Launch 2 new instances from current page
            4) Wait for SVG fully loading (wait for stable state)
            6) Collapse network by click 'Toggle Network Collapse' button
            7) Check that no instances are shown
            8) Check that correct count of instances (2) is shown for private
            network
            9) Expand network by 'Toggle Network Collapse' button again
            10) Check that 2 instances are visible now, count of instances is
            not visible for private network
            11) Check that instances have link to private network
            12) Delete instances
        """
        count = 2
        network_topology_page = \
            self.home_pg.go_to_network_networktopologypage()
        network_topology_page.create_instance(INSTANCE_NAME,
                                              instance_count=count)
        self.assertTrue(
            network_topology_page.find_message_and_dismiss(messages.SUCCESS))
        self.assertFalse(
            network_topology_page.find_message_and_dismiss(messages.ERROR))
        network_topology_page.topology.wait_for_svg_loads()
        network_topology_page.collapse_network()

        instances = network_topology_page.topology.get_instances()
        int_net = network_topology_page.topology.get_internal_networks()[0]
        self.assertEqual(len(instances), 0)
        self.assertEqual(
            network_topology_page.topology.get_vm_count(int_net), count)

        network_topology_page.expand_network()
        network_topology_page.topology.wait_for_svg_loads()
        instances = network_topology_page.topology.get_instances()
        self.assertEqual(len(instances), count)
        self.assertEqual(
            network_topology_page.topology.get_vm_count(int_net), None)
        int_net = network_topology_page.topology.get_internal_networks()[0]
        for instance in instances:
            self.assertTrue(network_topology_page.topology.
                            is_link_between_nodes_available(instance, int_net))

        for instance in instances:
            network_topology_page.topology.delete_instance(instance)
            self.assertTrue(network_topology_page.find_message_and_dismiss(
                messages.SUCCESS))

    def test_create_delete_router_from_network_topology(self):
        """This test checks creation and deletion router from network topology
        page
        Steps:
        1) Login to Horizon Dashboard as regular user
        2) Go to Project > Network > Network Topology page
        3) Select 'Create Router' button
        4) From appeared form enter router name, select admin state 'UP' and
        'public' as external network > 'Create Router'
        5) Wait for SVG fully loading (wait for stable state)
        6) Check that router is visible, connected to the public network and is
        not connected to the private network
        7) Open router's balloon > 'Delete Router' button. Check that router
        is deleted.
        """
        network_topology_page = \
            self.home_pg.go_to_network_networktopologypage()
        network_topology_page.create_router(ROUTER_NAME)
        self.assertTrue(
            network_topology_page.find_message_and_dismiss(messages.SUCCESS))
        self.assertFalse(
            network_topology_page.find_message_and_dismiss(messages.ERROR))
        network_topology_page.topology.wait_for_svg_loads()
        network_topology_page.show_labels()

        ext_net = network_topology_page.topology.get_external_networks()[0]
        int_net = network_topology_page.topology.get_internal_networks()[0]
        routers = network_topology_page.topology.get_routers()
        router = [routers[i] for i in range(len(routers))
                  if routers[i][1][2] == ROUTER_NAME][0]
        self.assertTrue(network_topology_page.topology.
                        is_link_between_nodes_available(router, ext_net))
        self.assertFalse(network_topology_page.topology.
                         is_link_between_nodes_available(router, int_net))

        network_topology_page.topology.delete_router(router)
        self.assertTrue(
            network_topology_page.find_message_and_dismiss(messages.SUCCESS))
        network_topology_page.topology.wait_for_svg_loads()
        routers = network_topology_page.topology.get_routers()
        self.assertEqual(len(routers), 1)

    def test_connectors_sanity(self):
        """This test checks connection VM - Network - Router - public Network
        Steps:
        1) Login to Horizon Dashboard as regular user
        2) Go to Project > Network > Network Topology page
        3) Create private network, create router, connect created network to
        router by adding appropriate interface to router
        4) Create instance with network from step 3
        5) Wait for SVG fully loading (wait for stable state)
        6) Check connectivity: Instance - Network - Router - public Network
        7) Delete router, instance, network
        """
        network_topology_page = \
            self.home_pg.go_to_network_networktopologypage()
        network_topology_page.create_network(NETWORK_NAME, SUBNET_NAME)
        self.assertTrue(
            network_topology_page.find_message_and_dismiss(messages.SUCCESS))
        self.assertFalse(
            network_topology_page.find_message_and_dismiss(messages.ERROR))

        network_topology_page.create_router(ROUTER_NAME)
        self.assertTrue(
            network_topology_page.find_message_and_dismiss(messages.SUCCESS))
        self.assertFalse(
            network_topology_page.find_message_and_dismiss(messages.ERROR))
        network_topology_page.topology.wait_for_svg_loads()
        network_topology_page.show_labels()

        routers = network_topology_page.topology.get_routers()
        router = [routers[i] for i in range(len(routers))
                  if routers[i][1][2] == ROUTER_NAME][0]
        network_topology_page.topology.add_interface_to_router(router,
                                                               SUBNET_NAME)
        network_topology_page.topology.wait_for_svg_loads()

        network_topology_page.create_instance(INSTANCE_NAME, networks=True,
                                              net=NETWORK_NAME)
        self.assertTrue(
            network_topology_page.find_message_and_dismiss(messages.SUCCESS))
        self.assertFalse(
            network_topology_page.find_message_and_dismiss(messages.ERROR))
        instances = network_topology_page.topology.get_instances()
        for instance in instances:
            self.assertTrue(
                network_topology_page.topology.is_status_active(instance))
        network_topology_page.topology.wait_for_svg_loads()
        network_topology_page.show_labels()

        ext_net = network_topology_page.topology.get_external_networks()[0]
        routers = network_topology_page.topology.get_routers()
        router = [routers[i] for i in range(len(routers))
                  if routers[i][1][2] == ROUTER_NAME][0]
        networks = network_topology_page.topology.get_internal_networks()
        network = [networks[i] for i in range(len(networks))
                   if networks[i][1][2] == NETWORK_NAME][0]
        instances = network_topology_page.topology.get_instances()
        instance = [instances[i] for i in range(len(instances))
                    if instances[i][1][2] == INSTANCE_NAME][0]
        self.assertTrue(network_topology_page.topology.
                        is_link_between_nodes_available(ext_net, router))
        self.assertTrue(network_topology_page.topology.
                        is_link_between_nodes_available(router, network))
        self.assertTrue(network_topology_page.topology.
                        is_link_between_nodes_available(network, instance))

        network_topology_page.topology.delete_router(router)
        self.assertTrue(
            network_topology_page.find_message_and_dismiss(messages.SUCCESS))
        network_topology_page.topology.wait_for_svg_loads()
        routers = network_topology_page.topology.get_routers()
        self.assertEqual(len(routers), 1)

        network_topology_page.topology.delete_instance(instance)
        self.assertTrue(
            network_topology_page.find_message_and_dismiss(messages.SUCCESS))
        network_topology_page.topology.wait_for_svg_loads()
        instances = network_topology_page.topology.get_instances()
        self.assertEqual(len(instances), 0)

        network_topology_page.topology.delete_network(network)
        self.assertTrue(
            network_topology_page.find_message_and_dismiss(messages.SUCCESS))
        network_topology_page.topology.wait_for_svg_loads()
        networks = network_topology_page.topology.get_internal_networks()
        self.assertEqual(len(networks), 1)
