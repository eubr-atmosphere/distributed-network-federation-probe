import networkx as nx
from config import *
from utils import json_get_req
import itertools
import logging
from MetricsManager import MetricsManager


class TopoManager(object):
    def __init__(self):
        self.G = nx.DiGraph()
        self.metricsManager = MetricsManager()
        self.metrics_list = self.metricsManager.get_metrics_name()
        self.hosts = dict()
        self.retrieve_topo_from_ONOS()

    def retrieve_topo_from_ONOS(self):
        logging.info("Retrieving Topology...")
        reply = json_get_req('http://%s:%d/onos/v1/devices' % (ONOS_IP, ONOS_PORT))
        if 'devices' not in reply:
            return
        devices = [dev['id'] for dev in reply['devices'] if dev['available']]
        self.G.remove_nodes_from([n for n in self.G if n not in set(devices)])
        self.G.add_nodes_from(devices)

        reply = json_get_req('http://%s:%d/onos/v1/hosts' % (ONOS_IP, ONOS_PORT))
        if 'hosts' not in reply:
            return
        for host in reply['hosts']:
            for location in host['locations']:
                self.hosts[host['id']] = location['elementId']

        reply = json_get_req('http://%s:%d/onos/v1/links' % (ONOS_IP, ONOS_PORT))
        if 'links' not in reply:
            return
        edges_set = set([(el['src']['device'], el['dst']['device']) \
                    for el in reply['links'] if el['state'] == 'ACTIVE'])
        for edge in itertools.permutations(self.G.nodes(), 2):
            is_edge_active = edge in edges_set
            self.G.add_edge(*edge, **{ 'active':is_edge_active })
            self.update_edge_metrics(is_edge_active, edge)
        self.topo = nx.edge_subgraph(self.G, edges_set)
        logging.debug("Edge set:", edges_set)

    def update_edge_metrics(self, is_edge_active, edge):
        for metric_name in self.metrics_list:
            if metric_name in self.G[edge[0]][edge[1]]:
                prev_metric_val = self.G[edge[0]][edge[1]][metric_name]
            else:
                prev_metric_val = 100 if is_edge_active else 0
            updated_metric_val = self.metricsManager.update_metric(metric_name, is_edge_active, prev_metric_val)
            self.G.add_edge(*edge, **{ metric_name:updated_metric_val })

    def get_net_active_topology(self):
        return self.topo

    def get_net_full_topology(self):
        return self.G
