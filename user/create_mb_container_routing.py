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

    Popen("docker create --privileged --net=none -t -i --cap-add=ALL --name %s mb_base:latest" % container_name, shell=True).wait()
    Popen("docker container start %s" % container_name, shell=True).wait()

    Popen("docker exec --privileged %s sysctl -p sysctl.conf" % container_name, shell=True).wait()
    
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

    #Popen("docker exec -it %s echo 0 > /proc/sys/net/ipv4/conf/default/rp_filter" % (container_name), shell=True).wait()
    #Popen("docker exec -it %s echo 0 > /proc/sys/net/ipv4/conf/all/rp_filter" % (container_name), shell=True).wait()
    
    Popen("ip netns exec %s ip link add %s link tap0 type macvlan mode bridge" % (ns_mux, con1), shell=True).wait()
    Popen("ip netns exec %s ip link add %s link tap0 type macvlan mode bridge" % (ns_mux, con3), shell=True).wait()

    # Transfer interfaces to MB container
    Popen("ip netns exec %s ip link set %s netns %s up" % (ns_mux, con1, ns_mb), shell=True).wait()
    Popen("ip netns exec %s ip link set %s netns %s up" % (ns_mux, con3, ns_mb), shell=True).wait()

    Popen("docker exec -it %s ip link set lo up" % container_name, shell=True).wait()
    Popen("docker exec -it %s ip addr add %s/24 dev %s" % (container_name, con1_ip, con1), shell=True).wait()
    Popen("docker exec -it %s ip addr add %s/24 dev %s" % (container_name, con3_ip, con3), shell=True).wait()

    # Configure routes
    Popen("docker exec -it %s ip route add %s via %s" % (container_name, ip_prefix, con0_ip), shell=True).wait()
    Popen("docker exec -it %s ip route add default via %s" % (container_name, con2_ip), shell=True).wait()
    
    #Popen("docker exec -it %s echo 1 > /proc/sys/net/ipv4/ip_forward" % (container_name), shell=True).wait()


def main(argv):
    parser = argparse.ArgumentParser(description='Create Docker Container with named interfaces for steering.')
    parser.add_argument('-c', '--container-name', required=True, help="Name for container")
    parser.add_argument('-p', '--iface-prefix', required=True, help="Interface prefix name")

    args = parser.parse_args()
    
    container_name = vars(args)['container_name']
    iface_prefix = vars(args)['iface_prefix']
    ip_prefix = "184.164.224.128/25"
    con0_ip = "100.65.128.2" #not used anymore
    con1_ip = "100.65.128.100"
    con2_ip = "100.65.192.1"   #not used the orginal way anymore. now it is the default gateway.
    con3_ip = "100.65.192.100"
    mb_config(container_name, iface_prefix, ip_prefix, con0_ip, con1_ip, con2_ip, con3_ip)

    
if __name__ == '__main__':
    main(sys.argv)
    

