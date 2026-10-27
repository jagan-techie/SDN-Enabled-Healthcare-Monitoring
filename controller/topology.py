# controller/topology.py - Mininet topology with bandwidth-limited TCLink for QoS evaluation
"""
Mininet Topology:
  sensor  (10.0.0.1) \
                       [s1] ===== 10 Mbps TCLink ===== [s2] ---- gateway (10.0.0.10)
  noise   (10.0.0.99)/                                      \---- server  (10.0.0.20)

Bottleneck: The s1-s2 link is throttled to 10 Mbps with 5ms propagation delay.
Background noise traffic from 'noise' host saturates best-effort Queue 0.
When patient telemetry triggers an alert, Ryu directs sensor traffic to Queue 1 (Priority),
restoring low latency and zero packet loss even under heavy background load.
"""

import sys
from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.link import TCLink
from mininet.cli import CLI
from mininet.log import setLogLevel, info

class HealthcareSDNTopo(Topo):
    def build(self):
        info("*** Creating Switches (OpenFlow 1.3)\n")
        s1 = self.addSwitch("s1", protocols="OpenFlow13", dpid="0000000000000001")
        s2 = self.addSwitch("s2", protocols="OpenFlow13", dpid="0000000000000002")

        info("*** Creating End-Hosts\n")
        sensor = self.addHost("sensor", ip="10.0.0.1/24", mac="00:00:00:00:00:01")
        noise = self.addHost("noise", ip="10.0.0.99/24", mac="00:00:00:00:00:99")
        gateway = self.addHost("gateway", ip="10.0.0.10/24", mac="00:00:00:00:00:10")
        server = self.addHost("server", ip="10.0.0.20/24", mac="00:00:00:00:00:20")

        info("*** Adding Access Links (100 Mbps FastEthernet)\n")
        self.addLink(sensor, s1, bw=100, delay="1ms")
        self.addLink(noise, s1, bw=100, delay="1ms")
        self.addLink(s2, gateway, bw=100, delay="1ms")
        self.addLink(s2, server, bw=100, delay="1ms")

        info("*** Adding Congested Inter-Switch Core Link (10 Mbps TCLink with 5ms delay)\n")
        # s1-eth3 <-> s2-eth3
        self.addLink(s1, s2, bw=10, delay="5ms", max_queue_size=100, use_htb=True)

def run_network():
    setLogLevel("info")
    topo = HealthcareSDNTopo()
    net = Mininet(
        topo=topo,
        controller=lambda name: RemoteController(name, ip="127.0.0.1", port=6653),
        switch=OVSSwitch,
        link=TCLink,
        autoSetMacs=True
    )
    info("*** Starting Mininet Network...\n")
    net.start()
    info("*** Network active. Dumping Host IP Configurations:\n")
    for host in net.hosts:
        info(f"Host {host.name}: IP={host.IP()}, MAC={host.MAC()}\n")

    CLI(net)
    net.stop()

topos = {"healthcare_sdn": (lambda: HealthcareSDNTopo())}

if __name__ == "__main__":
    run_network()
