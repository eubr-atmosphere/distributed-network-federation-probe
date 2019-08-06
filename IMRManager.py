import json
import networkx as nx
from config import ONOS_IP, ONOS_PORT, VERBOSE
from utils import json_get_req, json_post_req, bps_to_human_string
from pprint import pprint
import logging
from math import log10


class IMRManager(object):
    def __init__(self, verbose=VERBOSE):
        self.intentKey_to_inOutElements = {}
        self.verbose = verbose

    def retrieve_monitored_intents_from_ONOS(self):
        logging.info("Retrieving Monitored Intents...")
        reply = json_get_req('http://%s:%d/onos/v1/imr/imr/monitoredIntents' % (ONOS_IP, ONOS_PORT))
        if 'response' not in reply:
            return
        for apps in reply['response']:
            for intent in apps['intents']:
                if self.verbose:
                    print intent
                flow_id = (intent['key'], apps['id'], apps['name'])
                in_el, out_el = intent['key'].split('-')
                self.intentKey_to_inOutElements[flow_id] = (in_el, out_el)

    def get_monitored_intents(self):
        return set(self.intentKey_to_inOutElements.keys())

    def reroute_intents(self, topoManager):
        self.retrieve_monitored_intents_from_ONOS()
        reroute_msg = {'routingList': []}
        topo = topoManager.get_net_active_topology().copy()

        for link in topo.edges():
            logging.info("link %s-%s with availability %d" % (link[0], link[1], topo[link[0]][link[1]]["availability"]))
            topo[link[0]][link[1]]["weight"] = 1 if topo[link[0]][link[1]]["availability"] >= 90 else 100

        for link in topo.edges():
            logging.info("link %s-%s with weight %d" % (link[0], link[1], topo[link[0]][link[1]]["weight"]))
        """
        print("*"*30)
        print("HOST:", topoManager.hosts)
        print("ITEMS:", self.intentKey_to_inOutElements.items())
        print("NODES:", topo.nodes())
        print("EDGES:", topo.edges())
        print("FULL:", topoManager.get_net_full_topology().edges())
        print("*" * 30)
        """

        for flow_id, elems in self.intentKey_to_inOutElements.items():
            intent_key, app_id, app_name = flow_id
            in_elem, out_elem = elems
            if self.verbose:
                print '\nTrying to route demand %s -> %s' % (in_elem, out_elem)
            try:
                path = nx.shortest_path(topo, topoManager.hosts[in_elem], topoManager.hosts[out_elem], 'weight')
                if self.verbose:
                    print 'Found path %s' % path
                reroute_msg['routingList'].append(
                    {'key': intent_key, 'appId': {'id': app_id, 'name': app_name},
                     'paths': [{'path': path, 'weight': 1.0}]}
                )
            except:
                if self.verbose:
                    print 'No path found'
                    print(topoManager.hosts[in_elem], topoManager.hosts[out_elem])

        if self.verbose:
            logging.info('reroute_msg config:')
            pprint(reroute_msg)
        json_post_req(('http://%s:%d/onos/v1/imr/imr/reRouteIntents' % (ONOS_IP, ONOS_PORT)), json.dumps(reroute_msg))

    def reroute_intents_max_availability(self, topoManager):
        self.retrieve_monitored_intents_from_ONOS()
        reroute_msg = {'routingList': []}
        topo = topoManager.get_net_active_topology().copy()
        for link in topo.edges():
            topo[link[0]][link[1]]["availability"] = - log10(topo[link[0]][link[1]]["availability"]/100)
        for link in topo.edges():
            print("link",link[0], link[1],"availability",topo[link[0]][link[1]]["availability"])

        for flow_id, elems in self.intentKey_to_inOutElements.items():
            intent_key, app_id, app_name = flow_id
            in_elem, out_elem = elems
            if self.verbose:
                print '\nTrying to route demand %s -> %s' % (in_elem, out_elem)
            try:
                path = nx.shortest_path(topo, topoManager.hosts[in_elem], topoManager.hosts[out_elem], 'availability')
                if self.verbose:
                    print 'Found path %s' % path
                reroute_msg['routingList'].append(
                    {'key': intent_key, 'appId': {'id': app_id, 'name': app_name},
                     'paths': [{'path': path, 'weight': 1.0}]}
                )
            except:
                if self.verbose:
                    print 'No path found'
                    print(topoManager.hosts[in_elem], topoManager.hosts[out_elem])

        if self.verbose:
            logging.info('reroute_msg config:')
            pprint(reroute_msg)
        json_post_req(('http://%s:%d/onos/v1/imr/imr/reRouteIntents' % (ONOS_IP, ONOS_PORT)), json.dumps(reroute_msg))

    def reroute_intents_reduced(self, tm, topoManager):
        reroute_msg = {'routingList': []}
        topo = topoManager.G.copy()
        # iterate over flows (sorted by amount, in decreasing order)
        for flow_id, amount in sorted(tm.items(), key=lambda x: x[1], reverse=True):
            intent_key, app_id, app_name = flow_id
            in_elem, out_elem = self.intentKey_to_inOutElements[flow_id]
            if self.verbose:
                print '\nTrying to route %s for demand %s -> %s' % (bps_to_human_string(amount), in_elem, out_elem)

            # build a reduced_topo keeping just links with enough capacity to accomodate the current demand
            reduced_topo = reduced_capacity_topo(topo, amount)
            try:
                path = nx.shortest_path(reduced_topo, in_elem, out_elem)
                if self.verbose:
                    print 'Found path %s' % path
                # update the topology
                topo = reduced_capacity_on_path(topo, amount, path)
                reroute_msg['routingList'].append(
                    {'key': intent_key, 'appId': {'id': app_id, 'name': app_name},
                     'paths': [{'path': path, 'weight': 1.0}]}
                )
            except nx.NetworkXNoPath:
                if self.verbose:
                    print 'No path found'

        if self.verbose:
            logging.info('reroute_msg config:')
            pprint(reroute_msg)
        json_post_req(('http://%s:%d/onos/v1/imr/imr/reRouteIntents' % (ONOS_IP, ONOS_PORT)), json.dumps(reroute_msg))


def reduced_capacity_on_path(topo, amount, path):
    reduced_topo = topo.copy()
    for link in zip(path, path[1:]):
        if reduced_topo[link[0]][link[1]]['bandwidth'] - amount <= 0:
            reduced_topo.remove_edge(link[0], link[1])
        else:
            reduced_topo[link[0]][link[1]]['bandwidth'] -= amount
    return reduced_topo

def reduced_capacity_topo(topo, amount):
    reduced_topo = topo.copy()
    for u, v, data in reduced_topo.edges(data=True):
        if data['bandwidth'] - amount < 0:
            reduced_topo.remove_edge(u, v)
        else:
            data['bandwidth'] -= amount
    return reduced_topo
