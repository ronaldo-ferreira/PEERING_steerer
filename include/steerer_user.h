/*
 *
 *	steerer: Packet Steerer for the PEERING testbed: steerer_user.h
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

#define ETHER_ADDR_LEN	6

#define MAX_NAME_LEN	30
#define MAX_IP_LEN	16

#define STEERER_ALERT	"Steerer: "

#define STEERER_NETLINK_USER	27
#define NETLINK_HEADER_LENGTH	16

#define STEERER_NEW_EXP	1

struct conf_msg {
	char vpn0_name[MAX_NAME_LEN];
	char con1_name[MAX_NAME_LEN];
	char con3_name[MAX_NAME_LEN];

	char ip_block[MAX_IP_LEN];
	char ip_mask[MAX_IP_LEN];
	
	unsigned char mac_tap1[ETHER_ADDR_LEN];
};
