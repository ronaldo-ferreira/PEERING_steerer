#########################################################
# Dockerfile for testing client <-> server interactions #
#########################################################

# Set the base image to Debian
FROM debian:jessie

# File Author / Maintainer
MAINTAINER Brivaldo Junior <brivaldo@facom.ufms.br>

# Install utilities
RUN apt-get update && apt-get install -y tcpdump traceroute

ADD sysctl.conf .


