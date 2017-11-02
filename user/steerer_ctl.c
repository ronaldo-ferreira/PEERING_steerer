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
	printf("\nUsage: %s <vpn0> <vpn1> <con0> <con1> <con2> <con3>\n\n"
	       "\tvpn0: name of the vpn interface in the current namespace\n"
	       "\tvpn1: name of the peer interface of vpn0\n"
	       "\tcon0: name of the first interface (closer to the vpn) that connects to the container\n"
	       "\tcon1: name of the peer interface of con0\n"
	       "\tcon2: name of the second interface (closer to the peer) that connects to the container\n\n",
	       PROG_NAME);
	exit(1);
}

#define MSG_LENGTH 1024	/* Maximum message length */

struct sockaddr_nl saddr, daddr;
struct if_names	   ifs;
struct nlmsghdr    *nlh;
struct iovec       iov;
struct msghdr      msg;

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
	
	strcpy(ifs.vpn0_name, argv[1]);
	strcpy(ifs.vpn1_name, argv[2]);
	strcpy(ifs.con0_name, argv[3]);
	strcpy(ifs.con1_name, argv[4]);
	strcpy(ifs.con2_name, argv[5]);
	strcpy(ifs.con3_name, argv[6]);
	
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
	
	memcpy(NLMSG_DATA(nlh), &ifs, sizeof(struct if_names));

	iov.iov_base = (void *)nlh;
	iov.iov_len  = nlh->nlmsg_len;
	       
	msg.msg_name    = (void *)&daddr;
	msg.msg_namelen = sizeof(struct sockaddr_nl);
	msg.msg_iov     = &iov;
	msg.msg_iovlen  = 1;

	if (sendmsg(sock, &msg, 0) < 0)
		perror("Error sending the netlink message");
}
