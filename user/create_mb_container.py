#!/usr/bin/env python
# -*- coding: utf-8 -*-

import time
import os
import sys, getopt
import subprocess
import argparse
from subprocess import Popen, PIPE, call

def run(container_name, iface_prefix):
    print 'Container name: ', container_name
    print 'Interface prefix: ', iface_prefix

    try:
        Popen("docker stop %s" % container_name, shell=True).wait()
        Popen("docker rm %s" % container_name, shell=True).wait()
        os.mkdir("/var/run/netns")
    except:
        pass

    time.sleep(5)

    Popen("docker create --net=none -t -i --cap-add=ALL --name %s mb_base:latest" % container_name, shell=True).wait()
    Popen("docker container start %s" % container_name, shell=True).wait()

    str = "docker inspect --format '{{.State.Pid}}' %s" % container_name
    print str
    p = Popen("docker inspect --format '{{.State.Pid}}' %s" % container_name, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)    
    out_mb, err = p.communicate()
    out_mb  = out_mb.rstrip()
    ns_mb   = "ns-" + out_mb

    mux_name = "peeringmux_openvpn_1"
    m = Popen("docker inspect --format '{{.State.Pid}}' %s" % mux_name, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)    
    out_mux, err = m.communicate()
    out_mux = out_mux.rstrip()
    ns_mux  = "ns-" + out_mux
    
    
    if(Popen("ln -s /proc/%s/ns/net /var/run/netns/%s" % (out_mb, ns_mb), shell=True).wait()):
        print "Error naming the mb namespace"
        sys.exit(1)
        
    if(Popen("ln -s /proc/%s/ns/net /var/run/netns/%s" % (out_mux, ns_mux), shell=True).wait()):
        print "Error naming the mux namespace"
        sys.exit(1)
        
    con0 = iface_prefix + "0"
    con1 = iface_prefix + "1"
    con2 = iface_prefix + "2"
    con3 = iface_prefix + "3"

    Popen("ip link add %s type veth peer name %s" % (con0, con1), shell=True).wait()
    Popen("ip link add %s type veth peer name %s" % (con2, con3), shell=True).wait()

    # Transfer interfaces to Mux container
    Popen("ip link set %s netns %s up" % (con0, ns_mux), shell=True).wait()
    Popen("ip link set %s netns %s up" % (con2, ns_mux), shell=True).wait()
    Popen("docker exec -it %s ip addr add 10.60.0.10/24 dev %s" % (mux_name, con0), shell=True).wait()
    Popen("docker exec -it %s ip addr add 10.70.0.20/24 dev %s" % (mux_name, con2), shell=True).wait()
    
    # Transfer interfaces to MB container
    Popen("ip link set %s netns %s up" % (con1, ns_mb), shell=True).wait()
    Popen("ip link set %s netns %s up" % (con3, ns_mb), shell=True).wait()

    Popen("docker exec -it %s ip link set lo up" % container_name, shell=True).wait()
    Popen("docker exec -it %s ip addr add 10.60.0.11/24 dev %s" % (container_name, con1), shell=True).wait()
    Popen("docker exec -it %s ip addr add 10.70.0.23/24 dev %s" % (container_name, con3), shell=True).wait()

    # Configure routes
    Popen("docker exec -it %s ip route add %s via %s" % (container_name, "184.164.224.0/24", "10.60.0.10"), shell=True).wait()
    Popen("docker exec -it %s ip route add default via %s" % (container_name, "10.70.0.20"), shell=True).wait()
    Popen("docker exec -it %s echo 1 > /proc/sys/net/ipv4/ip_forward" % (container_name), shell=True).wait()

    # Rule for dealing with packets COMING OUT of the middlebox and with direction client -> peer (interface con2)
    Popen("docker exec -it %s ip rule add from %s iif %s table %s priority %s" % (mux_name, "184.164.224.0/24", con2, "10000", 300), shell=True).wait()
    
    # Rule for dealing with packets COMING OUT of the middlebox and with direction peer -> client (interface con0)
    Popen("docker exec -it %s ip rule add to %s iif %s table %s priority %s" % (mux_name, "184.164.224.0/24", con0, "20000", 400), shell=True).wait()

    # Rule for dealing with packets GOING TO the middlebox and with direction client -> peer
    Popen("docker exec -it %s ip rule add from %s table %s priority %s" % (mux_name, "184.164.224.0/24", "5000", 700), shell=True).wait()

    # Rule for dealing with packets GOING TO the middlebox and with direction peer -> client
    Popen("docker exec -it %s ip rule add to %s table %s priority %s" % (mux_name, "184.164.224.0/24", "6000", 800), shell=True).wait()

    # Add default routes to the tables 5000 and 6000 to send packets to the containers.
    Popen("docker exec -it %s ip route add default via %s table %s" % (mux_name, "10.60.0.11", 5000), shell=True).wait()    
    Popen("docker exec -it %s ip route add default via %s table %s" % (mux_name, "10.70.0.23", 6000), shell=True).wait()
    
    
def main(argv):
    parser = argparse.ArgumentParser(description='Create Docker Container with named interfaces for steering.')
    parser.add_argument('-c', '--container-name', required=True, help="Name for container")
    parser.add_argument('-p', '--iface-prefix', required=True, help="Interface prefix name")

    args = parser.parse_args()
    container_name = vars(args)['container_name']
    iface_prefix = vars(args)['iface_prefix']
    
    run(container_name, iface_prefix)

    
if __name__ == '__main__':
    main(sys.argv)
    
