import threading
import time
from IMRManager import IMRManager
from TopoManager import TopoManager
from NetworkProbe import NetworkProbe
from config import POLLING_INTERVAL, TMA_URL
import logging
import signal
import sys


DEBUG = True
logging.basicConfig(level=logging.DEBUG if DEBUG else logging.INFO)

class PollingThread(threading.Thread):
    def __init__(self):
        self._stopevent = threading.Event()
        threading.Thread.__init__(self)

    def run(self):
        while not self._stopevent.isSet():
            reroute_event.set()
            time.sleep(POLLING_INTERVAL)

    def stop(self):
        self._stopevent.set()


class ReroutingThread(threading.Thread):
    def __init__(self):
        self._stopevent = threading.Event()
        threading.Thread.__init__(self)

    def run(self):
        while not self._stopevent.isSet():
            reroute_event.wait()
            if self._stopevent.isSet():
                return
            logging.info("Re-routing Intents...")
            reroute_event.clear()
            topoManager.retrieve_topo_from_ONOS()
            iMRManager.reroute_intents(topoManager)
            networkProbe.send_availability_metric(topoManager.get_net_full_topology())

    def stop(self):
        self._stopevent.set()
        reroute_event.set()

def handler_stop_signals(signum, frame):
    pollingThread.stop()
    reroutingThread.stop()
    logging.info('Killing all the threads...')
    sys.exit(0)

if __name__ == "__main__":
    topoManager = TopoManager()
    networkProbe = NetworkProbe(TMA_URL)
    iMRManager = IMRManager()
    reroute_event = threading.Event()

    pollingThread = PollingThread()
    reroutingThread = ReroutingThread()
    pollingThread.start()
    reroutingThread.start()

    signal.signal(signal.SIGINT, handler_stop_signals)

    logging.info('Press any key to exit')
    raw_input('')
    logging.info('Killing all the threads...')
    pollingThread.stop()
    reroutingThread.stop()
