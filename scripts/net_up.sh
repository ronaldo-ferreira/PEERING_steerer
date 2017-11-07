
echo 1 > /proc/sys/net/ipv4/ip_forward
echo 0 > /proc/sys/net/ipv4/conf/all/rp_filter
echo 0 > /proc/sys/net/ipv4/conf/default/rp_filter

ip netns add vpn
ip netns add con
ip netns add peer
ip netns add mux

ip link add vpn0  type veth peer name vpn1
ip link add con0  type veth peer name con1
ip link add con2  type veth peer name con3
ip link add peer0 type veth peer name peer1

ip link set vpn0 netns mux
ip link set vpn1 netns vpn

ip link set con0 netns mux
ip link set con1 netns con

ip link set con2 netns mux
ip link set con3 netns con

ip link set peer0 netns mux
ip link set peer1 netns peer


ip netns exec mux ifconfig vpn0 10.0.1.1 netmask 255.255.255.0 up
ip netns exec mux ifconfig lo up
ip netns exec vpn ifconfig vpn1 10.0.1.2 netmask 255.255.255.0 up
ip netns exec vpn ifconfig lo up

ip netns exec mux  ifconfig peer0 10.0.28.1 netmask 255.255.255.0 up
ip netns exec peer ifconfig peer1 10.0.28.2 netmask 255.255.255.0 up
ip netns exec peer ifconfig lo up

ip netns exec mux ifconfig con0 10.0.3.1 netmask 255.255.255.0 up
ip netns exec con ifconfig con1 10.0.3.2 netmask 255.255.255.0 up
ip netns exec con ifconfig lo up

ip netns exec mux ifconfig con2 10.0.4.1 netmask 255.255.255.0 up
ip netns exec con ifconfig con3 10.0.4.2 netmask 255.255.255.0 up


ip netns exec vpn  route add -net 0.0.0.0/0 gateway 10.0.1.1
ip netns exec peer route add -net 0.0.0.0/0 gateway 10.0.28.1

ip netns exec con route add -net 10.0.1.0/24 gateway 10.0.3.1
ip netns exec con route add -net 10.0.28.0/24 gateway 10.0.4.1

ip netns exec con sh -c 'echo 1 > /proc/sys/net/ipv4/ip_forward'
ip netns exec mux sh -c 'echo 1 > /proc/sys/net/ipv4/ip_forward'
