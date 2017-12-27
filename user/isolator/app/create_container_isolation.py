#!/usr/bin/env python
# -*- coding: utf-8 -*-

import time
import os
import sys, getopt
import subprocess
import argparse
from subprocess import Popen, PIPE, call

from pyroute2 import NetNS


def mb_destroy(container_name, iface_prefix):
    # TODO: write this function to undo what mb_config does
    print "mb_destroy not implemented yet"

    
def mb_config(container_name, iface_prefix, veth_prefix, ip_prefix, con0_ip, con1_ip, con2_ip, con3_ip):
    print 'Container name: ', container_name
    print 'Interface prefix: ', iface_prefix
    print 'IP prefix: ', ip_prefix
    print 'VETH Prefix: ', veth_prefix

    #TODO: change to Docker Lib
    try:
        Popen("docker stop %s" % container_name, shell=True).wait()
        Popen("docker rm %s" % container_name, shell=True).wait()
        os.mkdir("/var/run/netns")
    except:
        pass

    time.sleep(5)

    Popen("docker create --privileged --net=none -t -i --cap-add=ALL --name %s mb_base:latest" % container_name, shell=True).wait()
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

    # After last change con0 and con2 are irrelevants
    #con0 = iface_prefix + "0"
    #con2 = iface_prefix + "2"
    con1 = iface_prefix + "1"
    con3 = iface_prefix + "3"

    veth0 = veth_prefix + "0"
    veth1 = veth_prefix + "1"
   
    # Connect using IPRoute NetNS
    mux_ip = NetNS(ns_mux)

    
    # Create a veth interface that works as a pipe between the containers and the upstream interfaces
    mux_ip.link('add', ifname=veth0, kind='veth', peer=veth1)
            
    # Add the container interface facing the client
    mux_ip.link('add', ifname=con1, kind='macvlan', link=mux_ip.link_lookup(ifname='tap0')[0], macvlan_mode='vepa')
    
    # Add the container interface facing the upstream peers.
    mux_ip.link('add', ifname=con3, kind='macvlan', link=mux_ip.link_lookup(ifname=veth1)[0], macvlan_mode='vepa')

    # Add the IP address to the veth-raf0 interface and up the veth interfaces
    mux_ip.addr('add', index=mux_ip.link_lookup(ifname=veth0)[0], address=con2_ip, mask=24)
    mux_ip.link('set', index=mux_ip.link_lookup(ifname=veth0)[0], state='up')
    mux_ip.link('set', index=mux_ip.link_lookup(ifname=veth1)[0], state='up')
    

    # The interfaces below should be configured from a file (interface-container.json, for example). We should
    # reuse the interface.py code. The IP addresses are the same as the ones in the file interface.json, but
    # we rewrite the third octect from 0 to 192.
    mux_ip.link('add', ifname='upstream1b', kind='macvlan', link=mux_ip.link_lookup(ifname=veth0)[0], macvlan_mode='vepa')
    mux_ip.link('add', ifname='upstream2b', kind='macvlan', link=mux_ip.link_lookup(ifname=veth0)[0], macvlan_mode='vepa')
    mux_ip.link('add', ifname='upstream4b', kind='macvlan', link=mux_ip.link_lookup(ifname=veth0)[0], macvlan_mode='vepa')
    mux_ip.link('add', ifname='upstream5b', kind='macvlan', link=mux_ip.link_lookup(ifname=veth0)[0], macvlan_mode='vepa')
    mux_ip.link('add', ifname='upstream6b', kind='macvlan', link=mux_ip.link_lookup(ifname=veth0)[0], macvlan_mode='vepa')
    

    mux_ip.addr('add', index=mux_ip.link_lookup(ifname='upstream1b')[0], address='100.65.192.1', mask=24)
    mux_ip.addr('add', index=mux_ip.link_lookup(ifname='upstream2b')[0], address='100.65.192.2', mask=24)
    mux_ip.addr('add', index=mux_ip.link_lookup(ifname='upstream4b')[0], address='100.65.192.4', mask=24)
    mux_ip.addr('add', index=mux_ip.link_lookup(ifname='upstream5b')[0], address='100.65.192.5', mask=24)
    mux_ip.addr('add', index=mux_ip.link_lookup(ifname='upstream6b')[0], address='100.65.192.6', mask=24)


    # Add the mirror interfaces for the upstream peers. These interfaces are used to route
    # packets coming out of the container. This configuration should be done using interfaces.json or
    # a separate file with only these interfaces.
    mux_ip.link('set', index=mux_ip.link_lookup(ifname='upstream1b')[0], state='up')
    mux_ip.link('set', index=mux_ip.link_lookup(ifname='upstream2b')[0], state='up')
    mux_ip.link('set', index=mux_ip.link_lookup(ifname='upstream4b')[0], state='up')
    mux_ip.link('set', index=mux_ip.link_lookup(ifname='upstream5b')[0], state='up')
    mux_ip.link('set', index=mux_ip.link_lookup(ifname='upstream6b')[0], state='up')

    
    # Add rules to lookup the upstream tables for packets coming from the container enroute to upstream.
    # These rules should be configured from the information in the database.
    mux_ip.rule('add', iifname=veth0, table=10000, priority=10000)
    mux_ip.rule('add', iifname='upstream1b', table=10001, priority=10001)
    mux_ip.rule('add', iifname='upstream2b', table=10002, priority=10002)
    mux_ip.rule('add', iifname='upstream4b', table=10004, priority=10004)
    mux_ip.rule('add', iifname='upstream5b', table=10005, priority=10005)
    mux_ip.rule('add', iifname='upstream6b', table=10006, priority=10006)

    
    # # Transfer interfaces to MB container
    # Popen("ip netns exec %s ip link set %s netns %s up" % (ns_mux, con1, ns_mb), shell=True).wait()
    # Popen("ip netns exec %s ip link set %s netns %s up" % (ns_mux, con3, ns_mb), shell=True).wait()
    mux_ip.link('set', index=mux_ip.link_lookup(ifname=con1)[0], net_ns_fd=ns_mb)
    mux_ip.link('set', index=mux_ip.link_lookup(ifname=con3)[0], net_ns_fd=ns_mb)

    # Clone the Namespaces communication
    mux_ip.close()
    
    
    # Add the IP addresses of the container interfaces
    Popen("docker exec -it %s ip link set lo up" % container_name, shell=True).wait()
    Popen("docker exec -it %s ip addr add %s/24 dev %s" % (container_name, con1_ip, con1), shell=True).wait()
    Popen("docker exec -it %s ip addr add %s/24 dev %s" % (container_name, con3_ip, con3), shell=True).wait()

    # Configure routes
    Popen("docker exec -it %s ip route add %s via %s" % (container_name, ip_prefix, con0_ip), shell=True).wait()

    # The default route below should commented out if we configure an iBGP session between the client and
    # the container.
    Popen("docker exec -it %s ip route add default via %s" % (container_name, con2_ip), shell=True).wait()
    

def main(argv):
    parser = argparse.ArgumentParser(description='Create Docker Container with named interfaces for steering.')
    parser.add_argument('-c', '--container-name', required=True, help="Name for container")
    parser.add_argument('-p', '--iface-prefix', required=True, help="Interface prefix name")
    parser.add_argument('-v', '--veth-prefix', required=True, help="VETH Interface prefix name")

    args = parser.parse_args()
    
    container_name = vars(args)['container_name']
    iface_prefix = vars(args)['iface_prefix']
    veth_prefix = vars(args)['veth_prefix']
    
    ip_prefix = "184.164.224.128/25"
    con0_ip = '100.65.128.2'
    con1_ip = '100.65.128.254'
    con2_ip = '100.65.192.254'   
    con3_ip = '100.65.192.253'
    mb_config(container_name, iface_prefix, veth_prefix, ip_prefix, con0_ip, con1_ip, con2_ip, con3_ip)

    
if __name__ == '__main__':
    main(sys.argv)
    

