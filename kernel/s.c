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
#include <linux/inet.h>
#include <steerer.h>

struct veth_priv {
	struct net_device __rcu	*peer;
	atomic64_t		dropped;
};

static struct nf_hook_ops netfilter_ops_in;  /* IP PRE ROUTING     */
static struct nf_hook_ops netfilter_ops_out; /* NF_IP_POST_ROUTING */

struct sock *nl_sk = NULL;

struct policy {
	__u8	mac_tap1[ETHER_ADDR_LEN];
	__be32	ip_block;
	__be32	ip_mask;
	
	struct rhash_head con0_node;		// hash table entry
	struct list_head  list;			// connect to the list of policies
	
	struct net_device *vpn0_dev;	
	struct net_device *con0_dev;	
	struct net_device *con1_dev;	
	struct net_device *con2_dev;	
	struct net_device *con3_dev;

};

/* This  struct contains  the information  for an  experiment.  Device
   pointers and names. */
struct experiment {
	struct rhash_head vpn0_node;
	
	struct net_device *vpn0_dev;	
	struct list_head  policies;
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
	.key_offset	= offsetof(struct policy, con0_dev),
	.head_offset	= offsetof(struct policy, con0_node),
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
		init_experiment((struct conf_msg *)payload);
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
	struct policy	  *pol;
	struct ethhdr	  *eth;
	
	e = rhashtable_lookup_fast(&vpn0_table, &skb->dev, rhashtable_params_vpn0);
	if (e) {
		// Received the packet from the interface vpn0 (VPN tunnel).
		skb_push(skb, ETHER_HDR_LEN);
		skb_reset_mac_header(skb);				
		eth = eth_hdr(skb);
		if (likely(ntohs(eth->h_proto) == ETH_P_IP)) {
			struct iphdr *iph = ip_hdr(skb);
			__be32 net_prefix;
			
			rcu_read_lock();
			list_for_each_entry_rcu(pol, &e->policies, list) {
				printk(STEERER_ALERT "received packet with MAC=" MAC_STR "MAC_TAP1=" MAC_STR "\n",
				       MAC_TO_STR(eth->h_source), MAC_TO_STR(pol->mac_tap1));
				net_prefix = iph->saddr & pol->ip_mask;
				if (net_prefix == pol->ip_block) {
					// Change the device to con0 and set the MAC Dest addr to con1
					skb->dev   = pol->con0_dev;
					memcpy(eth->h_dest, pol->con1_dev->dev_addr, ETHER_ADDR_LEN);
					
					dev_queue_xmit(skb);
					
					rcu_read_unlock();
					return NF_STOLEN;
				}
			};
			rcu_read_unlock();
		}
	}
	else {
		pol = rhashtable_lookup_fast(&con0_table, &skb->dev, rhashtable_params_con0);
		if (pol) {
			// Received the packet from the interface con0 (container).			
			skb->dev = pol->vpn0_dev;
			skb_push(skb, ETHER_HDR_LEN);
			skb_reset_mac_header(skb);		
			memcpy(eth_hdr(skb)->h_dest, pol->mac_tap1, ETHER_ADDR_LEN);
			dev_queue_xmit(skb);
			return NF_STOLEN;
		}
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
	struct policy	  *pol;
	struct ethhdr	  *eth;
	
	e = rhashtable_lookup_fast(&vpn0_table, &skb->dev, rhashtable_params_vpn0);
	if (e) {
		eth = eth_hdr(skb);
		if (likely(ntohs(eth->h_proto) == ETH_P_IP)) {
			struct iphdr *iph = ip_hdr(skb);
			__be32 net_prefix;
			
			rcu_read_lock();
			list_for_each_entry_rcu(pol, &e->policies, list) {
				net_prefix = iph->daddr & pol->ip_mask;
				if (net_prefix == pol->ip_block) {
					// Change the packet device to con2 with DST MAC address of con3
					skb->dev = pol->con2_dev;
					
					skb_push(skb, ETHER_HDR_LEN);
					skb_reset_mac_header(skb);
					
					memcpy(eth_hdr(skb)->h_dest, pol->con3_dev->dev_addr, ETHER_ADDR_LEN);
					
					dev_queue_xmit(skb);
					rcu_read_lock();				
					return NF_STOLEN;
				}
			}
			rcu_read_lock();
		}
	}
	return NF_ACCEPT;
}
/* steerer_out */


/*********************************************************************
 *
 *	print_net_devices: print  all the devices in  the system. This
 *	function is for debugging only.
 *
 *	FIXME: Need to remove it once we're done.
 *
 *********************************************************************/
void print_net_devices(void)
{
	struct net		*netns;
	struct hlist_head	*head;
	struct net_device	*dev;
	struct veth_priv	*priv;
	int			i;
	
	rcu_read_lock();
	for_each_net_rcu(netns) {
		for (i = 0; i < NETDEV_HASHENTRIES; i++) {
			head = &netns->dev_name_head[i];
			hlist_for_each_entry_rcu(dev, head, name_hlist) {
				priv = netdev_priv(dev);
				printk(STEERER_ALERT "dev=%s peer=%s ns#=%u\n",
				       dev->name, priv->peer ? priv->peer->name :
				       "NULL", netns->ns.inum);
			};
			
		}
	};
	rcu_read_unlock();
}
/* print_net_devices */


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
 *	steerer_dev_put: decrement the device reference counters.
 *
 *********************************************************************/
void steerer_dev_put(struct policy *pol)
{
	if (pol->vpn0_dev)
		dev_put(pol->vpn0_dev);
	if (pol->con1_dev)
		dev_put(pol->con1_dev);
	if (pol->con3_dev)
		dev_put(pol->con3_dev);
}
/* steerer_dev_put */


/*********************************************************************
 *
 *	init_experiment: initializes one new experiment.
 *
 *********************************************************************/
int init_experiment(struct conf_msg *cm)
{
	struct net		*netns;
	struct experiment	*e = NULL;
	struct veth_priv	*priv;
	struct net_device	*dev;
	struct policy		*pol = NULL;

	printk(STEERER_ALERT
	       "it will configure a new experiment with the devices: (%s,%s,%s) MAC=" MAC_STR "\n",
	       cm->vpn0_name, cm->con1_name, cm->con3_name, MAC_TO_STR(cm->mac_tap1));
	
	rcu_read_lock();
	for_each_net_rcu(netns) {
		dev = dev_get_by_name(netns, cm->vpn0_name);
		if (dev) {
			e = rhashtable_lookup_fast(&vpn0_table, &dev, rhashtable_params_vpn0);
			if (e == NULL) {
				e = kmalloc(sizeof(struct experiment), GFP_KERNEL);
				if (e == NULL)
					goto err_nomem;
				e->vpn0_dev = dev;
				INIT_LIST_HEAD(&e->policies);
			}
			break;
		}
	}

	if (e == NULL)
		goto err_noent;
	
	for_each_net_rcu(netns) {
		dev = dev_get_by_name(netns, cm->con1_name);
		if (dev) {
			pol = kmalloc(sizeof(struct policy), GFP_KERNEL);
			if (pol == NULL)
				goto err_nomem;
			
			pol->vpn0_dev = e->vpn0_dev;
			
			pol->con1_dev = dev;
			priv          = netdev_priv(pol->con1_dev);

			// FIXME: Need to check if the interface is veth
			if (priv == NULL)
				printk(STEERER_ALERT "priv is NULL (1)\n");
				       
			pol->con0_dev = priv->peer;
			
			pol->con3_dev = dev_get_by_name(netns, cm->con3_name);
			if (pol->con3_dev == NULL) {
				printk(STEERER_ALERT "BUG: did not find con3 %s\n", cm->con3_name);
				kfree(pol);
				goto err_noent;
			}
			priv          = netdev_priv(pol->con3_dev);

			// FIXME: Need to check if the interface is veth			
			if (priv == NULL)
				printk(STEERER_ALERT "priv is NULL (1)\n");
				       			
			pol->con2_dev = priv->peer;

			memcpy(pol->mac_tap1, cm->mac_tap1, ETHER_ADDR_LEN);

			pol->ip_block = in_aton(cm->ip_block);
			pol->ip_mask  = in_aton(cm->ip_mask);
			list_add_rcu(&pol->list, &e->policies);
			break;
		}
	};
	rcu_read_unlock();

	if (pol == NULL)
		goto err_noent;
	
	steerer_dev_put(pol);
	
	if (!pol->vpn0_dev || !pol->con0_dev || !pol->con1_dev || !pol->con2_dev || !pol->con3_dev) {
		printk(STEERER_ALERT "could not get all the devices (%s,%s,%s,%s,%s)\n",
		       pol->vpn0_dev->name,
		       pol->con0_dev->name, pol->con1_dev->name,
		       pol->con2_dev->name, pol->con3_dev->name);
		
		kfree(pol);
		return -ENOENT;
	}
	
	rhashtable_insert_fast(&vpn0_table, &e->vpn0_node, rhashtable_params_vpn0);
	rhashtable_insert_fast(&con0_table, &pol->con0_node, rhashtable_params_con0);
	
	printk(STEERER_ALERT
	       "has just configured a new experiment with the devices: (%s,%s,%s,%s,%s)\n",
	       pol->vpn0_dev->name,
	       pol->con0_dev->name, pol->con1_dev->name,
	       pol->con2_dev->name, pol->con3_dev->name);
	
	return 0;

 err_noent:
	rcu_read_unlock();
	printk(STEERER_ALERT "at least one of the devices (%s,%s,%s) wast not found\n",
	       cm->vpn0_name, cm->con1_name, cm->con1_name);
	return -ENOENT;
	
 err_nomem:
	
	rcu_read_unlock();
	printk(STEERER_ALERT "could not allocate memory for the new policy\n");
	return -ENOMEM;
}
/* init_experiment */


/*********************************************************************
 *
 *	steerer_free_entry: frees  an entry  from the  experiment hash
 *	table.
 *
 *********************************************************************/
void steerer_free_entry(void *ptr, void *arg)
{
	if (ptr) {
		printk(STEERER_ALERT "freeing a policy or an experiment entry\n");
		kfree(ptr);
	}
	else
		printk(STEERER_ALERT "BUG: trying to free a NULL pointer to a policy or an experiment\n");
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

	print_net_devices();
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
