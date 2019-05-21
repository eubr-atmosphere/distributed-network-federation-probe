from influxdb import InfluxDBClient
import logging


resource_id_map = {'link_availability':1, 'link_latency':2}
query_latency_stats = 'select max(latency) from link_latency where time > %ds group by link_key'
query_availability_stats = 'select mean(availability) from link_availability where time > %ds group by link_key'

class MetricsManager(object):
    def __init__(self, db_name='metrics_db', db_address='localhost'):
        self.db_name = db_name
        self.db_address = db_address
        self.client = InfluxDBClient(host=self.db_address, database=self.db_name)

    @staticmethod
    def convert_link_to_descriptionId(link):
        link_1, link_2 = link.split('-')
        return ((int(link_1) & 0xF) << 4) + (int(link_2) & 0xF)

    def get_stats(self, name, ts):
        if name == 'link_availability':
            return self.get_availability_stats(ts)
        elif name == 'link_latency':
            return self.get_latency_stats(ts)

    def get_availability_stats(self, ts):
        query = query_availability_stats % (ts)
        res = self.client.query(query)
        d = dict()
        for key, value in res.items():
            dict_key = self.convert_link_to_descriptionId(key[1][u'link_key'])
            dict_value = int(list(value)[0][u'mean'])
            logging.debug("link = %s, key = %d, availability = %d" % (key[1][u'link_key'], dict_key, dict_value))
            d[dict_key] =  dict_value
        return d

    def get_latency_stats(self, ts):
        query = query_latency_stats % (ts)
        res = self.client.query(query)
        d = dict()
        for key, value in res.items():
            dict_key = self.convert_link_to_descriptionId(key[1][u'link_key'])
            dict_value = int(list(value)[0][u'max'])
            logging.debug("link = %s, key = %d, latency = %d" % (key[1][u'link_key'], dict_key, dict_value))
            d[dict_key] =  dict_value
        return d
