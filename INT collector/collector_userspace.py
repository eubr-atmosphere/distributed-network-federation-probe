from bcc import BPF
import os
import time, datetime
from influxdb import InfluxDBClient
import logging

Log = logging.getLogger('myLogger')
level = logging.getLevelName('INFO')
Log.setLevel(level)

def setup_veth(inif, outif):
    os.system("ip link add %s type veth peer name %s" % (inif, outif))
    os.system("ip link set dev %s up" % inif)
    os.system("ip link set dev %s up" % outif)

def fix_overflowed_value(val):
# Fix overflowed value
    UINT32_MAX = 0xFFFFFFFF
    return val if val >= 0 else val + UINT32_MAX + 1

class INT_collector(object):
    def __init__ (self, filename = "collector.c", max_int_hop = 6, int_dst_port = 54321, shr_ewma = 4, n_switches = 3, n_federations = 100, polling_interval = 5):
        self.FILENAME = filename
        self.MAX_INT_HOP = max_int_hop
        self.INT_DST_PORT = int_dst_port
        self.SHR_EWMA = shr_ewma
        self.N_SWITCHES = n_switches
        self.N_FEDERATIONS = n_federations
        self.POLLING_INTERVAL = polling_interval
        self.HASHMAP_LINK_SIZE = n_switches*(n_switches - 1)
        self.HASHMAP_FED_LINK_SIZE = self.HASHMAP_LINK_SIZE*n_federations
        self.bpf = BPF(src_file=filename, debug=0,
        cflags=["-w",
                "-D_MAX_INT_HOP=%s" % self.MAX_INT_HOP,
                "-D_INT_DST_PORT=%s" % self.INT_DST_PORT,
                "-D_SHR_EWMA=%s" % self.SHR_EWMA,
                "-D_HASHMAP_LINK_SIZE=%s" % self.HASHMAP_LINK_SIZE,
                "-D_HASHMAP_FED_LINK_SIZE=%s" % self.HASHMAP_FED_LINK_SIZE])
        self.link_metrics_map = self.bpf["link_metrics_map"]
        self.link_fed_metrics_map = self.bpf["link_fed_metrics_map"]
        self.link_fed_threshold_map = self.bpf["link_fed_threshold_map"]
        self.prev_link_fed_metrics = dict()
        self.fn = self.bpf.load_func("collector", BPF.XDP)

        self.db_name = "metrics_db"
        self.db_address = "localhost"
        self.client = InfluxDBClient(host=self.db_address, database=self.db_name)
        for db in self.client.get_list_database():
            self.client.drop_database(db["name"])
        self.client.create_database(self.db_name)

    def attach_bpf_program(self, device, flags=0):
        self.device = device;
        self.bpf.attach_xdp(device, self.fn, flags)

    def remove_bpf_program(self, flags=0):
        self.bpf.remove_xdp(self.device, flags)

    def reset_map_values(self, map):
        leaf = map.Leaf()
        # not needed!

    def inject_threshold_in_map(self, d):
        #Expecting a dictionary like d = {(switch1,switch2,vlanid):thresh_value1, ...}
        temp_key = self.link_fed_threshold_map.Key()
        for key, threshold_value in d.items():
            temp_key.link_key.switch_id_1, temp_key.link_key.switch_id_2, temp_key.vlan_id = key
            link_fed_threshold_map[temp_key] = threshold_value

    def print_metrics(self):
        print("Printing stats, hit CTRL+C to stop")
        while True:
            try:
                for link_fed_key, link_fed_metrics in self.link_fed_metrics_map.items():
                    above_threshold_pkts = sum(i.above_threshold_pkts for i in link_fed_metrics)
                    tot_pkts = sum(i.tot_pkts for i in link_fed_metrics)
                    print("LINK_KEY = (%u,%u) VLAN_ID = %u, ABOVE_THRESHOLD_PKTS = %u, TOT_PKTS = %u" \
                    % (link_fed_key.link_key.switch_id_1, link_fed_key.link_key.switch_id_2, link_fed_key.vlan_id, above_threshold_pkts, tot_pkts))


                for link_key, link_metrics in self.link_metrics_map.items():
                    print("LINK_KEY = (%u,%u) LATENCY = %u" \
                    % (link_key.switch_id_1, link_key.switch_id_2, link_metrics.latency))


                print (30*"*")
                time.sleep(self.POLLING_INTERVAL)
            except KeyboardInterrupt:
                print("Removing filter from device")
                self.remove_bpf_program()
                break;

    def send_metrics(self):


        print("Printing stats, hit CTRL+C to stop")
        while True:
            try:
                data = list()
                current_time = time.time()
                wait_time = self.POLLING_INTERVAL - current_time % self.POLLING_INTERVAL
                timestamp_metrics = datetime.datetime.fromtimestamp(int(round(current_time + wait_time))).strftime('%Y-%m-%dT%H:%M:%SZ')
                timestamp_metrics = 10**9*int(round(current_time + wait_time))
                time.sleep(wait_time)
                for link_fed_key, link_fed_metrics in self.link_fed_metrics_map.items():
                    key_dict = (link_fed_key.link_key.switch_id_1, link_fed_key.link_key.switch_id_2, link_fed_key.vlan_id)
                    prev_above_threshold_pkts, prev_tot_pkts = self.prev_link_fed_metrics.setdefault(key_dict, [0]*2)
                    above_threshold_pkts_raw = sum(i.above_threshold_pkts for i in link_fed_metrics)
                    tot_pkts_raw = sum(i.tot_pkts for i in link_fed_metrics)
                    self.prev_link_fed_metrics[key_dict][0] = above_threshold_pkts_raw
                    self.prev_link_fed_metrics[key_dict][1] = tot_pkts_raw
                    above_threshold_pkts = fix_overflowed_value(above_threshold_pkts_raw - prev_above_threshold_pkts)
                    tot_pkts = fix_overflowed_value(tot_pkts_raw - prev_tot_pkts)

                    if tot_pkts:
                        print("LINK_KEY = (%u,%u) VLAN_ID = %u, ABOVE_THRESHOLD_PKTS = %u, TOT_PKTS = %u" \
                        % (link_fed_key.link_key.switch_id_1, link_fed_key.link_key.switch_id_2, link_fed_key.vlan_id, above_threshold_pkts, tot_pkts))

                        data.append(
                        {"measurement": "link_fed_stats",
                        "time": timestamp_metrics,
                        "tags": {
                                #"time": timestamp_metrics,
                                "host_id": 1,
                                "link_key": "%s %s" % (link_fed_key.link_key.switch_id_1, link_fed_key.link_key.switch_id_2),
                                "vlan_id": link_fed_key.vlan_id
                                },
                        "fields": {
                            "above_threshold_pkts": above_threshold_pkts,
                            "tot_pkts": tot_pkts
                            }
                        })

                # TODO if there are no packets don't send latency!
                for link_key, link_metrics in self.link_metrics_map.items():
                    print("LINK_KEY = (%u,%u) LATENCY = %u" \
                    % (link_key.switch_id_1, link_key.switch_id_2, link_metrics.latency))
                    data.append(
                    {"measurement": "link_latency",
                    "tags":{
                    "host_id": 1,
                    "link_key": "%s %s" % (link_key.switch_id_1, link_key.switch_id_2)
                    },
                    "time": timestamp_metrics,
                    "fields": {
                        #"time": timestamp_metrics,
                        "latency": link_metrics.latency
                        }
                    })
                #print(data)
                self.client.write_points(points=data, protocol="json")
                print (30*"*")
                time.sleep(self.POLLING_INTERVAL)
            except KeyboardInterrupt:
                print("Removing filter from device")
                self.remove_bpf_program()
                break;


if __name__ == "__main__":
    setup_veth("veth_1", "veth_2")
    int_collector = INT_collector(filename = "collector.c")
    int_collector.attach_bpf_program("veth_2")
    int_collector.send_metrics()
