# distributed-network-federation-probe
This probe pushes the virtual link availability and the virtual link latency metrics to the TMA framework.

### Deploy
This software is expected to be located in the same VM in which the OPA and the influxDB database are deployed.

#### Run
```
python network-probe.py http://tma_endpoint:port
```
