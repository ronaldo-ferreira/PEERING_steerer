#!/usr/bin/python

import time
import sys, getopt
import subprocess
from subprocess import Popen, PIPE, call

def run(container_name, iface_prefix):
    print 'Container name: ', container_name
    print 'Interface prefix: ', iface_prefix

    Popen("docker stop %s" % container_name, shell=True).wait()
    Popen("docker rm %s" % container_name, shell=True).wait()

    time.sleep(2)
    
    Popen("docker create --net=none -t -i --name %s debian:jessie" % container_name, shell=True).wait()
    Popen("docker container start %s" % container_name, shell=True).wait()

    str = "docker inspect --format '{{.State.Pid}}' %s" % container_name
    print str
    p = Popen("docker inspect --format '{{.State.Pid}}' %s" % container_name, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    
    out, err = p.communicate()
    print out
    out = out.rstrip()
    ns_name = "ns-" + out
    Popen("ln -s /proc/%s/ns/net /var/run/netns/%s" % (out, ns_name), shell=True).wait()

    con0 = iface_prefix + "0"
    con1 = iface_prefix + "1"
    con2 = iface_prefix + "2"
    con3 = iface_prefix + "3"

    print con0, con1, con2, con3

    Popen("ip link add %s type veth peer name %s" % (con0, con1), shell=True).wait()
    Popen("ip link add %s type veth peer name %s" % (con2, con3), shell=True).wait()
    Popen("ip link set %s netns %s up" % (con1, ns_name), shell=True).wait()
    Popen("ip link set %s netns %s up" % (con3, ns_name), shell=True).wait()
          

def main(argv):    
    try:
        opts, args = getopt.getopt(argv, "hs:t:",["container","iface_prefix"])
    except getopt.GetoptError:
        print 'create_mv_container.py -c <container_name> -p <iface_prefix>'
        sys.exit(2)

    container_name = "container_mb"
    iface_prefix = "cmb"
    
    for opt, arg in opts:
        if opt == '-h':
            print 'create_mv_container.py -c <container_name> -p <iface_prefix>'
            sys.exit()
        elif opt in ("-c", "--container-name"):
            container_name = arg
        elif opt in ("-p", "--iface-prefix"):
            iface_prefix = arg

    run(container_name, iface_prefix)

if __name__ == '__main__':
    main(sys.argv[1:])
    
