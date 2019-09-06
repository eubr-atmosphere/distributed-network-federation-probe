# onos-opa
Off-Platform Application (OPA) is an application developed for collecting the virtual link availability metric from a network topology managed by SDN. The application is able to force Onos to reroute traffic based on this metric.

OPA is an external python application, it communicates with Onos, exploiting the Intent Monitor and Reroute (IMR) service. For understanding better how IMR works, please see the [official repository](https://github.com/ANTLab-polimi/onos-opa-example).

## Pre-requisites

This tutorial requires an Ubuntu 16.04.3 (64 bit) Server distribution: we suggest a dedicated VM with 4-8 GB of RAM and 20 GB of storage. We assume ONOS was not prevousy installed in the current machine.

You can run an automatic script  and then jump right to "Tutorial" section.

### Installation
```
bash -c "$(wget -O - https://github.com/eubr-atmosphere/distributed-network-federation-probe/raw/master/misc/install.sh)"
source ~/.bashrc
```

### Network probe configuration
For authenticating the TMA site please run this command with the correct ip and port of the tma. The cert.pem needs to be saved in the 'onos-opa' folder.
```
openssl s_client -showcerts -connect <TMA_IP>:<TMA_port> </dev/null 2>/dev/null|openssl x509 -outform PEM >cert.pem
```
Please overwrite the TMA varible in config.py with the real url of the TMA.
```
TMA_URL = 'https://<TMA_IP>:<TMA_port>'
```

## Tutorial

Start ONOS controller
```
cd $ONOS_ROOT
bazel run onos-local -- clean debug
```
Once ONOS is ready, from another terminal deactivate the FWD application and enable IMR service
```
cd ~/distributed-network-federation-probe/ifwd
onos-app localhost deactivate org.onosproject.fwd
onos-app localhost activate org.onosproject.imr
```
Then install and activate IFWD application
```
onos-app localhost install! target/onos-app-ifwd-1.9.0-SNAPSHOT.oar
```
Create a simple Mininet topology
```
cd ~/distributed-network-federation-probe/topo
sudo python vlan_topo.py
```
Let's start a single iperf session from h1 to h2.
```
mininet> h2 iperf -s &
mininet> h1 iperf -c 10.0.0.2 -t 600 &
```
Connect to the GUI at http://[VM_IP]:8181/onos/ui/index.html (credentials are onos/rocks) and verify that the IFWD application established connectivity using shortest paths by pressing (A) key.

Without modifying the IFWD application, we can now require the monitoring and rerouting of all the intents it has submitted using the following CLI command from another terminal. (The appID value might differ from 188, but you can use the Tab Key or check the id with the command onos:app-ids)
```
onos localhost
onos> imr:startmon 188 org.onosproject.ifwd
onos> logout
```
Finally we can start the OPA

```
cd ~/distributed-network-federation-probe
python metrics_main.py
```

The rerouting logic is a simple shortest path algorithm that sets the weights on the graph considering the availability metric. In this case, the availability metric is averaged with a ewma. If the availability metric of a link is below 90%, it is considered unreliable and consequentially a proper weight is set on the edge of the network graph.

```
mininet> link s1 s2 down
```
While OPA is able to reroute intents via IMR, it does not limit the effectiveness of the Intent Framework in recovering from failures. It can be seen that ONOS, in case of the generated link failure, instantly recompiles the intent and continously updates all the availability metrics in the background.

```
mininet> link s1 s2 up
```
When the link is up again, OPA will reroute the intent only when the availability metric for the unreliable link is not below 90%.
