#!/usr/bin/env python
# -*- coding: utf-8 -*-

import time
import os
import sys, getopt
import subprocess
import argparse
from subprocess import Popen, PIPE, call


def mb_destroy(container_name, iface_prefix):
    # TODO: write this function to undo what mb_config does
    print "mb_destroy not implemented yet"

    
def mb_config(container_name, iface_prefix, ip_prefix, con0_ip, con1_ip, con2_ip, con3_ip):
    print 'Container name: ', container_name
    print 'Interface prefix: ', iface_prefix
    print 'IP prefix: ', ip_prefix
    
    try:
        Popen("docker stop %s" % container_name, shell=True).wait()
        Popen("docker rm %s" % container_name, shell=True).wait()
        os.mkdir("/var/run/netns")
    except:
        pass

    time.sleep(5)

    Popen("docker create --net=none -t -i --cap-add=ALL --name %s peering_container:latest" % container_name, shell=True).wait()
    Popen("docker container start %s" % container_name, shell=True).wait()

    # The line below is no longer needed. Now the two container interfaces are in separte layer-two domains
    # Popen("docker exec --privileged %s sysctl -p sysctl.conf" % container_name, shell=True).wait()
    
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

    ns_mux_path = "/var/run/netns/" + ns_mux
    if (os.path.isfile(ns_mux_path) == False):
        if(Popen("ln -s /proc/%s/ns/net /var/run/netns/%s" % (out_mux, ns_mux), shell=True).wait()):
            print "Error naming the mux namespace"
            sys.exit(1)
        
    con0 = iface_prefix + "0"
    con1 = iface_prefix + "1"
    con2 = iface_prefix + "2"
    con3 = iface_prefix + "3"

    # Create a veth interface that works as a pipe between the containers and the upstream interfaces
    Popen("ip netns exec %s ip link add veth-ctr0 type veth peer name veth-ctr1" % ns_mux, shell=True).wait()

    # Add the container interface facing the client
    Popen("ip netns exec %s ip link add %s link tap0 type macvlan" % (ns_mux, con1), shell=True).wait()

    # Add the container interface facing the upstream peers.
    Popen("ip netns exec %s ip link add %s link veth-ctr1 type macvlan" % (ns_mux, con3), shell=True).wait()

    # Add the IP address to the veth-ctr0 interface and up the veth interfaces
    Popen("ip netns exec %s ip addr add %s/24 dev veth-ctr0" % (ns_mux, con2_ip), shell=True).wait()
    Popen("ip netns exec %s ip link set veth-ctr0 up" % ns_mux, shell=True).wait()
    Popen("ip netns exec %s ip link set veth-ctr1 up" % ns_mux, shell=True).wait()

    # The interfaces below should be configured from a file (interface-container.json, for example). We should
    # reuse the interface.py code. The IP addresses are the same as the ones in the file interface.json, but
    # we rewrite the third octect from 0 to 192.
    Popen("ip netns exec %s ip link add upstream1b link veth-ctr0 type macvlan" % ns_mux, shell=True).wait() 
    Popen("ip netns exec %s ip link add upstream2b link veth-ctr0 type macvlan" % ns_mux, shell=True).wait() 
    Popen("ip netns exec %s ip link add upstream4b link veth-ctr0 type macvlan" % ns_mux, shell=True).wait() 
    Popen("ip netns exec %s ip link add upstream5b link veth-ctr0 type macvlan" % ns_mux, shell=True).wait()
    Popen("ip netns exec %s ip link add upstream6b link veth-ctr0 type macvlan" % ns_mux, shell=True).wait()

    Popen("ip netns exec %s ip addr add 100.65.192.1/24 dev upstream1b" % ns_mux, shell=True).wait()
    Popen("ip netns exec %s ip addr add 100.65.192.2/24 dev upstream2b" % ns_mux, shell=True).wait()
    Popen("ip netns exec %s ip addr add 100.65.192.4/24 dev upstream4b" % ns_mux, shell=True).wait()
    Popen("ip netns exec %s ip addr add 100.65.192.5/24 dev upstream5b" % ns_mux, shell=True).wait()
    Popen("ip netns exec %s ip addr add 100.65.192.6/24 dev upstream6b" % ns_mux, shell=True).wait()

    # Add the mirror interfaces for the upstream peers. These interfaces are used to route
    # packets coming out of the container. This configuration should be done using interfaces.json or
    # a separate file with only these interfaces.
    Popen("ip netns exec %s ip link set upstream1b up" % ns_mux, shell=True).wait()
    Popen("ip netns exec %s ip link set upstream2b up" % ns_mux, shell=True).wait()
    Popen("ip netns exec %s ip link set upstream4b up" % ns_mux, shell=True).wait()
    Popen("ip netns exec %s ip link set upstream5b up" % ns_mux, shell=True).wait()
    Popen("ip netns exec %s ip link set upstream6b up" % ns_mux, shell=True).wait()
    
    
    # Add rules to lookup the upstream tables for packets coming from the container enroute to upstream.
    # These rules should be configured from the information in the database.
    Popen("ip netns exec %s ip rule add iif veth-ctr0 table 10000 priority 10000" % ns_mux, shell=True).wait()
    Popen("ip netns exec %s ip rule add iif upstream1b table 10001 priority 10001" % ns_mux, shell=True).wait()
    Popen("ip netns exec %s ip rule add iif upstream2b table 10002 priority 10002" % ns_mux, shell=True).wait()
    Popen("ip netns exec %s ip rule add iif upstream4b table 10004 priority 10004" % ns_mux, shell=True).wait()
    Popen("ip netns exec %s ip rule add iif upstream5b table 10005 priority 10005" % ns_mux, shell=True).wait()
    Popen("ip netns exec %s ip rule add iif upstream6b table 10006 priority 10006" % ns_mux, shell=True).wait()
    
    # Transfer interfaces to MB container
    Popen("ip netns exec %s ip link set %s netns %s up" % (ns_mux, con1, ns_mb), shell=True).wait()
    Popen("ip netns exec %s ip link set %s netns %s up" % (ns_mux, con3, ns_mb), shell=True).wait()

    # Add the IP addresses of the container interfaces
    Popen("docker exec -it %s ip link set lo up" % container_name, shell=True).wait()
    Popen("docker exec -it %s ip addr add %s/24 dev %s" % (container_name, con1_ip, con1), shell=True).wait()
    Popen("docker exec -it %s ip addr add %s/24 dev %s" % (container_name, con3_ip, con3), shell=True).wait()

    # Configure routes
    Popen("docker exec -it %s ip route add %s via %s" % (container_name, ip_prefix, con0_ip), shell=True).wait()

    # The default route below should be commented out if we configure an iBGP session between the client and
    # the container.
    # Popen("docker exec -it %s ip route add default via %s" % (container_name, con2_ip), shell=True).wait()

    Popen("docker exec -it %s ip rule add table 151 priority 1510" % container_name, shell=True).wait()

def main(argv):
    parser = argparse.ArgumentParser(description='Create Docker Container with named interfaces for steering.')
    parser.add_argument('-c', '--container-name', required=True, help="Name for container")
    parser.add_argument('-p', '--iface-prefix', required=True, help="Interface prefix name")

    args = parser.parse_args()
    
    container_name = vars(args)['container_name']
    iface_prefix = vars(args)['iface_prefix']
    ip_prefix = "184.164.224.128/25"
    con0_ip = "100.65.128.2" 
    con1_ip = "100.65.128.254"
    con2_ip = "100.65.192.254"   
    con3_ip = "100.65.192.253"
    mb_config(container_name, iface_prefix, ip_prefix, con0_ip, con1_ip, con2_ip, con3_ip)

    
if __name__ == '__main__':
    main(sys.argv)
    

