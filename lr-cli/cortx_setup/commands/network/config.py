#
# Copyright (c) 2020 Seagate Technology LLC and/or its Affiliates
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.
# For any questions about this software or licensing,
# please email opensource@seagate.com or cortx-questions@seagate.com.
#

# Cortx Setup API for configuring network

from cortx_setup.commands.command import Command
from cortx_setup.config import CONFSTORE_CLUSTER_FILE
from cortx_setup.commands.common_utils import get_machine_id
from cortx.utils.conf_store import Conf
from provisioner.commands import PillarSet
from provisioner.salt import local_minion_id


class NetworkConfig(Command):
    _args = {
        'transport_type': {
            'type': str,
            'default': None,
            'optional': True,
            'help': 'Transport type for network e.g {lnet|libfabric}'
        },
        'interface_type': {
            'type': str,
            'default': None,
            'optional': True,
            'help': 'Interface type for network e.g {tcp|o2ib}'
        },
        'type': {
            'type': str,
            'default': None,
            'optional': True,
            'dest': 'network_type',
            'choices': ['data', 'mgmt'],
            'help': 'Network type for provided interfaces'
        },
        'interfaces': {
            'type': str,
            'nargs': '+',
            'optional': True,
            'help': 'List of interfaces for provided type '
                    'e.g eth1 eth2'
        },
        'private': {
            'default': False,
            'optional': True,
            'action': 'store_true',
            'help': 'Use provided interfaces for private network'
        }
    }

    def run(self, transport_type=None, interface_type=None, network_type=None,
                interfaces=None, private=False
    ):

        """Network config execution method.

        Execution:
        `cortx_setup network config --transport-type lent`
        `cortx_setup network config --interface-type tcp`
        `cortx_setup network config --type mgmt --interfaces eth0`
        `cortx_setup network config --type data --interfaces eth1 eth2`
        `cortx_setup network config --type data --interfaces eth3 eth4 --mode private`

        """

        node_id = local_minion_id()
        machine_id = get_machine_id(node_id)
        Conf.load(
            'node_config_index',
            f'json://{CONFSTORE_CLUSTER_FILE}'
        )

        if transport_type is not None:
            self.logger.debug(
                f"Updating transport type to {transport_type} in confstore"
            )
            PillarSet().run(
                f'cluster/{node_id}/network/data/transport_type',
                f'{transport_type}',
                targets=node_id,
                local=True
            )
            Conf.set(
                'node_config_index',
                f'server_node>{machine_id}>network>data>transport_type',
                transport_type
            )

        if interface_type is not None:
            self.logger.debug(
                f"Updating interface type to {interface_type} in confstore"
                )
            PillarSet().run(
                f'cluster/{node_id}/network/data/interface_type',
                f'{interface_type}',
                targets=node_id,
                local=True
            )
            Conf.set(
                'node_config_index',
                f'server_node>{machine_id}>network>data>interface_type',
                interface_type
            )

        if interfaces is not None:
            if network_type == 'data':
                iface_key = (
                    'private_interfaces' if private else 'public_interfaces'
                )
                self.logger.debug(
                    f"Updating {iface_key} to {interfaces} for data network "
                    "in confstore"
                )
                PillarSet().run(
                    f'cluster/{node_id}/network/data/{iface_key}',
                    interfaces,
                    targets=node_id,
                    local=True
                )
                Conf.set(
                    'node_config_index',
                    f'server_node>{machine_id}>network>data>{iface_key}',
                    interfaces
                )
            elif network_type == 'mgmt':
                self.logger.debug(
                    f"Updating interfaces to {interfaces} for management "
                    "network in confstore"
                )
                PillarSet().run(
                    f'cluster/{node_id}/network/mgmt/interfaces',
                    interfaces,
                    targets=node_id,
                    local=True
                )
                Conf.set(
                    'node_config_index',
                    f'server_node>{machine_id}>network>management>interfaces',
                    interfaces
                )
            else:
                self.logger.error(
                    "Network type should specified for provided interfaces"
                )
        Conf.save('node_config_index')
        self.logger.debug("Done")
