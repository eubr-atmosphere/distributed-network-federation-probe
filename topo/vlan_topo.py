#!/usr/bin/env python

from mininet.node import Host
from mininet.topo import Topo
from mininet.cli import CLI
from mininet.net import Mininet
from mininet.node import RemoteController
from mininet.link import TCLink

VLAN_ID = 10
base_address ="10.0.0."

class CustomTopo(Topo):
    def __init__(self, bw=1e3, **opts):
        super(CustomTopo, self).__init__(**opts)

        s = [self.addSwitch('s%d' % n) for n in range(1, 4)]
        h = [self.addHost('h%d' % n, cls=VLANHost, vlan=VLAN_ID, ip=base_address+str(n)) for n in range(1, 3)]
        h.extend([self.addHost('h%d' % n, cls=VLANHost, vlan=20, ip=base_address+str(n)) for n in range(3, 5)])

        self.addLink(s[0], s[1], bw=bw)
        self.addLink(s[0], s[2], bw=bw)
        self.addLink(s[2], s[1], bw=bw)

        self.addLink(h[0], s[0], bw=bw)
        self.addLink(h[1], s[1], bw=bw)
        self.addLink(h[2], s[0], bw=bw)
        self.addLink(h[3], s[1], bw=bw)

class VLANHost( Host ):
    "Host connected to VLAN interface"

    def config( self, vlan=1, **params):
        """Configure VLANHost according to (optional) parameters:
           vlan: VLAN ID for default interface"""

        r = super( VLANHost, self ).config( **params )
        intf = self.defaultIntf()
        # remove IP from default, "physical" interface
        self.cmd( 'ifconfig %s inet 0' % intf )
        # create VLAN interface
        self.cmd( 'vconfig add %s %d' % ( intf, vlan ) )
        # assign the host's IP to the VLAN interface
        self.cmd( 'ifconfig %s.%d inet %s' % ( intf, vlan, params['ip'] ) )
        # update the intf name and host's intf map
        newName = '%s.%d' % ( intf, vlan )
        # update the (Mininet) interface to refer to VLAN interface name
        intf.name = newName
        # add VLAN interface to host's name to intf map
        self.nameToIntf[ newName ] = intf
        return r



if __name__ == '__main__':
    net = Mininet(topo=CustomTopo(),
                  controller=RemoteController,
                  cleanup=True,
                  autoSetMacs=True,
                  autoStaticArp=True,
                  link=TCLink)
    net.start()
    CLI(net)
    net.stop()
