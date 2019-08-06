import json
import logging
import time
from utils import extract_switch_id
from tmalibrary.probes import *


class NetworkProbe(object):

    resource_id_map = {'link_availability': 40001, 'link_latency': 40002}
    N = 16

    def __init__(self, url, probe_id=40001, base_offset=40000, message_id=0):
        self.communication = Communication(url)
        self.probe_id = probe_id
        self.base_offset = base_offset
        self.message_id = message_id

    def convert_device_to_resourceid(self, dev_1, dev_2):
        dev_1 = extract_switch_id(dev_1)
        dev_2 = extract_switch_id(dev_2)
        assert (1 <= dev_1 <= NetworkProbe.N and 1 <= dev_2 <= NetworkProbe.N)
        n = (dev_1-1)*(NetworkProbe.N-1)+dev_2
        n = n-1 if dev_2 > dev_1 else n
        return self.base_offset + n

    def send_availability_metric(self, topo):
        ts = int(time.time())
        for edge in topo.edges():
            resource = self.convert_device_to_resourceid(*edge)
            msg = Message(probeId=self.probe_id, resourceId=resource,
                          messageId=self.message_id, sentTime=ts, data=None)
            val = int(topo[edge[0]][edge[1]]['availability'])
            logging.info('NETWORK PROBE *** MessageId = %d, Sending resource: %d, Val = %d' %
                         (self.message_id, resource, val))
            dt = Data(type="measurement", descriptionId=NetworkProbe.resource_id_map['link_availability'],
                      observations=[Observation(time=ts, value=val)])
            msg.add_data(data=dt)
            json_msg = json.dumps(msg.reprJSON(), cls=ComplexEncoder)
            logging.debug('%s' % json_msg)
            self.communication.send_message(json_msg)
            self.message_id += 1
