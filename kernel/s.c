/*
 *
 *	steerer: Packet Steerer for the PEERING testbed: s.c
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
#include <net/xfrm.h>
#include <linux/module.h>
#include <linux/netfilter.h>
#include <linux/netfilter_ipv4.h>
#include <linux/inetdevice.h>
#include <linux/rhashtable.h>
#include <steerer.h>

struct veth_priv {
	struct net_device __rcu	*peer;
	atomic64_t		dropped;
};

static struct nf_hook_ops netfilter_ops_in;  /* IP PRE ROUTING     */
static struct nf_hook_ops netfilter_ops_out; /* NF_IP_POST_ROUTING */

struct sock *nl_sk = NULL;

/* This  struct contains  the information  for an  experiment.  Device
   pointers and names. */
struct experiment {
	struct rhash_head vpn0_node;
	struct rhash_head con0_node;
	
	struct net_device *vpn0_dev;	
	struct net_device *vpn1_dev;
	struct net_device *con0_dev;	
	struct net_device *con1_dev;	
	struct net_device *con2_dev;	
	struct net_device *con3_dev;
	
	struct if_names ifs;		// This is not necesssary. It is here for convenience only.
};


/* I  use  two  hash  tables  because  I  search  with  two  different
   keys. However, there is only one object per experiment. */
struct rhashtable vpn0_table;
struct rhashtable con0_table;

const struct rhashtable_params rhashtable_params_vpn0 = {
	.nelem_hint	= 100,
	.key_len	= sizeof(struct net_device *),
	.key_offset	= offsetof(struct experiment, vpn0_dev),
	.head_offset	= offsetof(struct experiment, vpn0_node),
	.min_size	= 50,
	.nulls_base	= (1U << RHT_BASE_SHIFT),
};

const struct rhashtable_params rhashtable_params_con0 = {
	.nelem_hint	= 100,
	.key_len	= sizeof(struct net_device *),
	.key_offset	= offsetof(struct experiment, con0_dev),
	.head_offset	= offsetof(struct experiment, con0_node),
	.min_size	= 50,
	.nulls_base	= (1U << RHT_BASE_SHIFT),
};


struct netlink_kernel_cfg nl_cfg = {
	.groups = 0,
	.input  = steerer_user_kernel
};

/*********************************************************************
 *
 *	steerer_user_kernel:  this  function  does  the  communication
 *	between kernel and user space.
 *
 *********************************************************************/
void steerer_user_kernel(struct sk_buff *skb)
{
	struct nlmsghdr	*nlh;
	unsigned char	*payload;

	payload = (unsigned char *)skb->data;
	payload += NETLINK_HEADER_LENGTH;
	
	nlh = (struct nlmsghdr *)skb->data;
	
	switch (nlh->nlmsg_type) {
	case STEERER_NEW_EXP:
		init_experiment((struct if_names *)payload);
		break;
	}
}
/* steerer_user_kernel */


/*********************************************************************
 *
 *	steerer_in: input processing for Linux Netfilter.
 *
 *********************************************************************/
static unsigned int steerer_in(void *priv,
			       struct sk_buff *skb,
			       const struct nf_hook_state *state)
{
	struct experiment *e;

	e = rhashtable_lookup_fast(&vpn0_table, &skb->dev, rhashtable_params_vpn0);
	if (e) {
		// Received the packet from the interface vpn0 (VPN tunnel).
		skb->dev   = e->con0_dev;
		skb_push(skb, ETHER_HDR_LEN);
		skb_reset_mac_header(skb);
		memcpy(eth_hdr(skb)->h_dest, e->con1_dev->dev_addr, ETHER_ADDR_LEN);
		dev_queue_xmit(skb);
		return NF_STOLEN;
	}
	e = rhashtable_lookup_fast(&con0_table, &skb->dev, rhashtable_params_con0);
	if (e) {
		// Received the packet from the interface con0 (container).
		skb->dev = e->vpn0_dev;
		skb_push(skb, ETHER_HDR_LEN);
		skb_reset_mac_header(skb);		
		memcpy(eth_hdr(skb)->h_dest, e->vpn1_dev->dev_addr, ETHER_ADDR_LEN);
		dev_queue_xmit(skb);
		return NF_STOLEN;
	}
	return NF_ACCEPT;
}
/* steerer_in */


/*********************************************************************
 *
 *	steerer_out: output processing for Linux Netfilter.
 *
 *********************************************************************/
static unsigned int steerer_out(void *priv,
				struct sk_buff *skb,
				const struct nf_hook_state *state)
{
	struct experiment *e;

	e = rhashtable_lookup_fast(&vpn0_table, &skb->dev, rhashtable_params_vpn0);
	if (e) {
		skb->dev = e->con2_dev;
		skb_push(skb, ETHER_HDR_LEN);
		skb_reset_mac_header(skb);
		memcpy(eth_hdr(skb)->h_dest, e->con3_dev->dev_addr, ETHER_ADDR_LEN); 
		dev_queue_xmit(skb);
		return NF_STOLEN;
		
	}
	return NF_ACCEPT;
}
/* steerer_out */


/*********************************************************************
 *
 *	steerer_init: initializes the Linux Netfilter hooks.
 *
 *********************************************************************/
void steerer_init(void)
{
	netfilter_ops_in.hook     = (typeof(netfilter_ops_out.hook))steerer_in;
	netfilter_ops_in.pf       = NFPROTO_IPV4; //PF_INET;
	netfilter_ops_in.hooknum  = NF_INET_PRE_ROUTING; 
	netfilter_ops_in.priority = NF_IP_PRI_FIRST;
	
	nf_register_hook(&netfilter_ops_in);	

	netfilter_ops_out.hook     = (typeof(netfilter_ops_out.hook))steerer_out;
	netfilter_ops_out.pf       = NFPROTO_IPV4; //PF_INET;
	netfilter_ops_out.hooknum  = NF_INET_POST_ROUTING; 
	netfilter_ops_out.priority = NF_IP_PRI_FIRST;
	
	nf_register_hook(&netfilter_ops_out);	
}
/* steerer_init */


/*********************************************************************
 *
 *	init_experiment: initializes one new experiment.
 *
 *********************************************************************/
void init_experiment(struct if_names *ifs)
{
	struct net *netns;
	int mux_ns, con_ns, vpn_ns;
	struct experiment *e;

	e = kmalloc(sizeof(struct experiment), GFP_KERNEL);
	if (!e) {
		printk(STEERER_ALERT "could not allocate memory for the new experiment\n");
		return;
	}
	
	mux_ns = con_ns = vpn_ns = 0;
	rcu_read_lock();
	for_each_net_rcu(netns) {
		struct veth_priv *priv;
		
		if (!mux_ns) {
			e->vpn0_dev = dev_get_by_name(netns, ifs->vpn0_name);
			if (e->vpn0_dev) {
				priv = netdev_priv(e->vpn0_dev);
				//e->vpn1_dev = rtnl_dereference(priv->peer);
				e->vpn1_dev = priv->peer;
				mux_ns = 1;
				if (con_ns)
					break;
			}
		}
		if (!con_ns) {
			e->con1_dev = dev_get_by_name(netns, ifs->con1_name);
			if (e->con1_dev) {
				priv = netdev_priv(e->con1_dev);
				e->con0_dev =priv->peer;
				//e->con0_dev = rtnl_dereference(priv->peer);
				e->con3_dev = dev_get_by_name(netns, ifs->con3_name);
				priv = netdev_priv(e->con3_dev);
				e->con2_dev = priv->peer;
				//e->con2_dev = rtnl_dereference(priv->peer);
				con_ns = 1;
				if (mux_ns)
					break;
			}
		}
	};
	rcu_read_unlock();
	
	if (!e->vpn0_dev || !e->vpn1_dev ||
	    !e->con0_dev || !e->con1_dev ||
	    !e->con2_dev || !e->con3_dev) {
		printk(STEERER_ALERT
		       "could not get all the devices (%s,%s,%s,%s,%s,%s)\n",
		       ifs->vpn0_name, ifs->vpn1_name,
		       ifs->con0_name, ifs->con1_name,
		       ifs->con2_name, ifs->con3_name);
		kfree(e);
		return;
	}

	memcpy(&e->ifs, ifs, sizeof(struct if_names));
	rhashtable_insert_fast(&vpn0_table, &e->vpn0_node, rhashtable_params_vpn0);
	rhashtable_insert_fast(&con0_table, &e->con0_node, rhashtable_params_con0);
	
	printk(STEERER_ALERT
	       "have just configured a new experiment with the devices: (%s,%s,%s,%s,%s,%s)\n",
	       e->vpn0_dev->name, e->vpn1_dev->name,
	       e->con0_dev->name, e->con1_dev->name,
	       e->con2_dev->name, e->con3_dev->name);	
	
}
/* init_experiment */


/*********************************************************************
 *
 *	init_experiment: initializes one new experiment.
 *
 *********************************************************************/
void init_experiment_old(struct if_names *ifs)
{
	struct net *netns;
	int mux_ns, con_ns, vpn_ns;
	struct experiment *e;

	printk(STEERER_ALERT
	       "configuring a new experiment with the devices: (%s,%s,%s,%s,%s,%s)\n",
	       ifs->vpn0_name, ifs->vpn1_name,
	       ifs->con0_name, ifs->con1_name,
	       ifs->con2_name, ifs->con3_name);	
	
	e = kmalloc(sizeof(struct experiment), GFP_KERNEL);
	if (!e) {
		printk(STEERER_ALERT "could not allocate memory for the new experiment\n");
		return;
	}
	
	mux_ns = con_ns = vpn_ns = 0;
	rcu_read_lock();
	for_each_net_rcu(netns) {
		if (!mux_ns) {
			e->vpn0_dev = dev_get_by_name(netns, ifs->vpn0_name);
			if (e->vpn0_dev) {
				e->con0_dev = dev_get_by_name(netns, ifs->con0_name);
				e->con2_dev = dev_get_by_name(netns, ifs->con2_name);
				mux_ns = 1;
			}
		}
		if (!con_ns) {
			e->con1_dev = dev_get_by_name(netns, ifs->con1_name);
			if (e->con1_dev) {
				e->con3_dev = dev_get_by_name(netns, ifs->con3_name);
				con_ns = 1;
			}
		}
		if (!vpn_ns) {
			e->vpn1_dev = dev_get_by_name(netns, ifs->vpn1_name);
			if (e->vpn1_dev)
				vpn_ns = 1;
		}
	};
	rcu_read_unlock();
	
	if (!e->vpn0_dev || !e->vpn1_dev ||
	    !e->con0_dev || !e->con1_dev ||
	    !e->con2_dev || !e->con3_dev) {
		printk(STEERER_ALERT
		       "could not get all the devices (%s,%s,%s,%s,%s,%s)\n",
		       ifs->vpn0_name, ifs->vpn1_name,
		       ifs->con0_name, ifs->con1_name,
		       ifs->con2_name, ifs->con3_name);
		kfree(e);
		return;
	}

	memcpy(&e->ifs, ifs, sizeof(struct if_names));
	rhashtable_insert_fast(&vpn0_table, &e->vpn0_node, rhashtable_params_vpn0);
	rhashtable_insert_fast(&con0_table, &e->con0_node, rhashtable_params_con0);
}
/* init_experiment_old */


/*********************************************************************
 *
 *	steerer_free_entry: frees  an entry  from the  experiment hash
 *	table.
 *
 *********************************************************************/
void steerer_free_entry(void *ptr, void *arg)
{
	if (ptr) {
		struct experiment *e = (struct experiment *)ptr;
		
		printk(STEERER_ALERT "freeing entry for device %s\n",
		       e->ifs.vpn0_name);
		kfree(ptr);
	}
	else
		printk(STEERER_ALERT "BUG: trying to free a NULL pointer to an experiment\n");
}
/* steerer_free_entry */


/*********************************************************************
 *
 *	steerer_cleanup:  unregisters the  Linux  Netfilter hooks  and
 *	cleans up the data structures.
 *
 *********************************************************************/
void steerer_cleanup(void)
{
	nf_unregister_hook(&netfilter_ops_in);
	nf_unregister_hook(&netfilter_ops_out);
	
	rhashtable_free_and_destroy(&vpn0_table, steerer_free_entry, NULL);
	rhashtable_destroy(&con0_table);

	if (nl_sk)
		netlink_kernel_release(nl_sk);
}


/*********************************************************************
 *
 *	steerer_exit: clean up the module and removes it.
*
 *********************************************************************/
static __exit void steerer_exit(void)
{
	steerer_cleanup();
	printk(STEERER_ALERT "Packet Steerer removed\n");
}
/* steerer_exit */



/*********************************************************************
 *
 *	steerer_start: unitializes  the packet steerer module  and the
 *	Linux Netfilter hooks.
 *
 *********************************************************************/
static __init int steerer_start(void)
{

	if (rhashtable_init(&vpn0_table, &rhashtable_params_vpn0) < 0)
		return -1;
	
	if (rhashtable_init(&con0_table, &rhashtable_params_con0) < 0) {
		rhashtable_destroy(&vpn0_table);
		return -1;
	}

	steerer_init();
	
	// Create the netlink socket
	nl_sk = netlink_kernel_create(&init_net, STEERER_NETLINK_USER, &nl_cfg);
	if (nl_sk == NULL) {
		printk(STEERER_ALERT "error creating netlink socket\n");
		steerer_cleanup();
		return -1;
	}
	
	printk(STEERER_ALERT "Packet Steerer initialized\n");
	return 0;
}
/* steerer_start */


module_init(steerer_start);
module_exit(steerer_exit);


MODULE_DESCRIPTION("Steerer - Packet Steerer for the PEERING testbed");
MODULE_AUTHOR("Ronaldo A. Ferreira");
MODULE_LICENSE("GPL v2");
MODULE_VERSION("1.0");
