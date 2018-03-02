# PEERING_steerer
Packet Steerer for the PEERING Testbed

The figure below identifies the network devices used by the packet steerer.
* Packets in the INPUT of vpn0 are sent to con0 with their MAC addresses changed to the address of con1.
* Packets in the OUTPUT of vpn0 are sent to con2 with their MAC addresses changed to the address of con3.
* Packets in the INPUT of con0 are sent to vpn0 with their MAC addresses changed to vpn1.
* The device peer0 is not 

INPUT and OUTPUT here refer to the netfilter hooks NF_INET_PRE_ROUTING and NF_INET_POST_ROUTING, respectively.

```
+----------------+       +--------------+         +---------------+
| Client1        |       | Mux          |         | Peer1         |
|            vpn1---------vpn0          |       --- 10.100.0.121  |
+----------------+       |              |      /  +---------------+
                         |              |     /
                         |         peer0------    +---------------+
                         |              |     \   |               |
                         |              |      \  | Peer2         |
                         |con0     con2 |       --- 10.100.0.122  |
                         +-|----------|-+         +---------------+
                           \          /
                            \        /				      
                        +---------------+
                        |  con1    con3 |
                        |               |
                        | Container MB  |
                        |               |
                        +---------------+
```