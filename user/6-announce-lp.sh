docker exec peeringmux_client1_1 bash -c "ip addr add 184.164.224.129/32 dev lo"
docker exec peeringmux_client1_1 bash -c "ip rule add from 184.164.224.128/25 table 5000 priority 100"
docker exec peeringmux_client1_1 bash -c "ip route add default via 100.65.128.254 table 5000"
sleep 1s
docker exec peeringmux_client1_1 bash -c "cd /root/mount/client ; ./peering prefix announce -v 100.65.192.2 184.164.224.128/25"
