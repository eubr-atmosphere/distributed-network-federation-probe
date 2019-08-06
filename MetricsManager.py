ALFA_availability = 0.1

class MetricsManager(object):
    def __init__(self):
        pass

    @staticmethod
    def compute_ewma(current_val, prev_val, alfa):
        return current_val * alfa + prev_val * (1 - alfa)

    @staticmethod
    def get_metrics_name():
        return ['availability']

    @staticmethod
    def update_availability(is_edge_active, prev_metric_val):
        return MetricsManager.compute_ewma(100*int(is_edge_active), prev_metric_val, ALFA_availability)

    @staticmethod
    def update_metric(metric_name, is_edge_active, prev_metric_val):
        if metric_name == 'availability':
            return MetricsManager.update_availability(is_edge_active, prev_metric_val)
