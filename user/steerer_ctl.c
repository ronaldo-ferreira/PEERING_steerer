/*
 *
 *	steerer_ctl: Packet Steerer for the PEERING testbed: steerer_ctl.c
 *
 *	Author: Ronaldo A. Ferreira (raf@facom.ufms.br)
 *
 *	This program is free software;  you can redistribute it and/or
 *	modify it under the terms of the GNU General Public License as
 *	published by the Free Software Foundation; either version 2 of
 *	the License, or (at your option) any later version.
 *
 *	THIS SOFTWARE IS PROVIDED ``AS IS'' AND ANY EXPRESS OR IMPLIED
 *	WARRANTIES,  INCLUDING,  BUT  NOT   LIMITED  TO,  THE  IMPLIED
 *	WARRANTIES  OF MERCHANTABILITY  AND FITNESS  FOR A  PARTICULAR
 *	PURPOSE  ARE DISCLAIMED.   IN NO  EVENT SHALL  THE AUTHORS  OR
 *	CONTRIBUTORS BE  LIABLE FOR ANY DIRECT,  INDIRECT, INCIDENTAL,
 *	SPECIAL, EXEMPLARY,  OR CONSEQUENTIAL DAMAGES  (INCLUDING, BUT
 *	NOT LIMITED  TO, PROCUREMENT OF SUBSTITUTE  GOODS OR SERVICES;
 *	LOSS  OF  USE, DATA,  OR  PROFITS;  OR BUSINESS  INTERRUPTION)
 *	HOWEVER  CAUSED AND  ON ANY  THEORY OF  LIABILITY, WHETHER  IN
 *	CONTRACT, STRICT  LIABILITY, OR TORT (INCLUDING  NEGLIGENCE OR
 *	OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE,
 *	EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
 *
 */
#include <linux/netlink.h>
#include <sys/socket.h>
#include <sys/types.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <stdio.h>
#include <errno.h>

#include <steerer_user.h>

#define PROG_NAME "steerer_ctl"

void usage()
{
	printf("\nUsage: %s <vpn0> <con1> <con3> <ip_block> <ip_mask> <mac_tap1>\n\n"
	       "\tvpn0: name of the vpn interface in the current namespace\n"
	       "\tcon1: name of the con1 interface in the container\n"
	       "\tcon3: name of the con3 interface in the container\n"
	       "\tip_block: block of IP addresses assigned to the client\n"
	       "\tip_mask: mask of the IP block\n"
	       "\tmac_tap1: MAC address of the tap1 interface on the client vpn\n",
	       PROG_NAME);
	exit(1);
}

#define MSG_LENGTH 1024	/* Maximum message length */

struct sockaddr_nl saddr, daddr;
struct conf_msg	   cm;
struct nlmsghdr    *nlh;
struct iovec       iov;
struct msghdr      msg;

void str_eth(char *str, unsigned char *mac)
{
	unsigned int tmp[6], i;
	
	sscanf(str, "%x:%x:%x:%x:%x:%x", &tmp[0], &tmp[1], &tmp[2], &tmp[3], &tmp[4], &tmp[5]);
	for(i = 0; i < ETHER_ADDR_LEN; i++)
		mac[i] = (unsigned char)tmp[i];	
}

int main(int argc, char *argv[])
{
	int                sock;
	
	if (argc != 7)
		usage();
	
	sock = socket(PF_NETLINK, SOCK_RAW, STEERER_NETLINK_USER);
	if(sock < 0) {
		perror("Error opening the netlink socket");
		return -1;
	}

	// FIXME: validate the input. Strings should be shorter than the allocated space in the struct
	strcpy(cm.vpn0_name, argv[1]);
	strcpy(cm.con1_name, argv[2]);
	strcpy(cm.con3_name, argv[3]);
	strcpy(cm.ip_block, argv[4]);
	strcpy(cm.ip_mask, argv[5]);
	str_eth(argv[6], cm.mac_tap1);

	memset(&saddr, 0, sizeof(struct sockaddr_nl));
	saddr.nl_family = AF_NETLINK;
	saddr.nl_pid    = getpid();
	
	bind(sock, (struct sockaddr*)&saddr, sizeof(struct sockaddr_nl));
	
	memset(&daddr, 0, sizeof(struct sockaddr_nl));
	daddr.nl_family = AF_NETLINK;
	daddr.nl_pid    = 0;		/* The destination is the kernel */
	daddr.nl_groups = 0;		/* Indicates an unicast address  */
	
	nlh = (struct nlmsghdr *)malloc(NLMSG_SPACE(MSG_LENGTH));
	memset(nlh, 0, NLMSG_SPACE(MSG_LENGTH));
	nlh->nlmsg_len   = NLMSG_SPACE(MSG_LENGTH);
	nlh->nlmsg_pid   = getpid();
	nlh->nlmsg_flags = 0;
	nlh->nlmsg_type  = STEERER_NEW_EXP;
	
	memcpy(NLMSG_DATA(nlh), &cm, sizeof(struct conf_msg));

	iov.iov_base = (void *)nlh;
	iov.iov_len  = nlh->nlmsg_len;
	       
	msg.msg_name    = (void *)&daddr;
	msg.msg_namelen = sizeof(struct sockaddr_nl);
	msg.msg_iov     = &iov;
	msg.msg_iovlen  = 1;

	if (sendmsg(sock, &msg, 0) < 0)
		perror("Error sending the netlink message");
}
