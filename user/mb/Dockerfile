#########################################################
# Dockerfile for containers that run on a PEERING router
# Create an image with tag peering_container:latest
#
# $ docker build -t peering_container:latest .
#
#########################################################

# Set the base image to Debian
FROM debian:jessie

# File Author / Maintainer
MAINTAINER Brivaldo Junior <brivaldo@facom.ufms.br>

# The bird configuration sections were borrowed from the Dockerfile
# for the bird container of the PEERING testbed. The original
# Dockerfile is maintained by Brandon Schlinker.

# Install utilities
RUN apt-get update && apt-get install -y tcpdump traceroute fping iputils-ping net-tools

# Install wget and SSL certificates
RUN apt-get update && apt-get install --no-install-recommends -y wget ca-certificates

# Add the BIRD Debian package repository
RUN wget -O - http://bird.network.cz/debian/apt.key | apt-key add -
RUN echo "deb http://bird.network.cz/debian/ jessie main" > /etc/apt/sources.list.d/bird.list

# Install BIRD
RUN apt-get update && apt-get install --no-install-recommends -y bird

# Create directories for BIRD control socket
RUN mkdir -p /run/bird

# Install dumb-init to support our entrypoint script
RUN wget https://github.com/Yelp/dumb-init/releases/download/v1.0.1/dumb-init_1.0.1_amd64.deb
RUN dpkg -i dumb-init_*.deb

# Install md5deep to facilitate config comparisons
RUN apt-get update && apt-get install --no-install-recommends -y md5deep

# Install rsync for managed configs
RUN apt-get update && apt-get install --no-install-recommends -y rsync

# Setup application home 
RUN mkdir -p /usr/src/app
WORKDIR /usr/src/app

# Add the bird configuration file for the container
# This file establishes an iBGP session between the container
# and its client
ADD bird.conf .
ENV BIRD_CONFIG_PATH /usr/src/app/bird.conf

# Add the entrypoint script and dependencies
ADD entrypoint.sh .
ADD reload.sh .
ADD checkconfig.sh .
ADD bird-sh.source .
RUN chmod 0755 entrypoint.sh
RUN chmod 0755 reload.sh
RUN chmod 0755 checkconfig.sh

ENTRYPOINT ["./entrypoint.sh"]
