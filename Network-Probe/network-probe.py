from tmalibrary.probes import *
import MetricsManager
import sys
import json
import time
import logging

DEBUG = False
SENDING_INTERVAL = 10
# PROBE_ID is hardcoded for now.
PROBE_ID = 1
metricsManager = MetricsManager.MetricsManager()
logging.basicConfig(level=logging.DEBUG if DEBUG else logging.INFO)

def create_message(message_id, resource_name):
    ts = int(time.time())
    message = Message(probeId=PROBE_ID, resourceId=MetricsManager.resource_id_map[resource_name], messageId=message_id, sentTime=ts, data=None)
    stats = metricsManager.get_stats(resource_name, int(ts - SENDING_INTERVAL))
    for id, val in stats.items():
        dt = Data(type="measurement", descriptionId=id, observations=[Observation(time=ts, value=val)])
        message.add_data(data=dt)
    res = json.dumps(message.reprJSON(), cls=ComplexEncoder)
    logging.debug(res)
    return res

if __name__ == '__main__':
    message_id = 0
    url = str(sys.argv[1])
    communication = Communication(url)
    while True:
        for resource_name in MetricsManager.resource_id_map.keys():
            message_formated = create_message(message_id, resource_name)
            logging.info('MessageId = %d, Sending resource: %s' % (message_id, resource_name))
            response = communication.send_message(message_formated)
            message_id += 1
        time.sleep(SENDING_INTERVAL)
