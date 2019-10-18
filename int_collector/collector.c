#define KBUILD_MODNAME "xdp_collector"
#include <linux/ip.h>
#include <linux/udp.h>
#include <linux/tcp.h>
#include <linux/if_vlan.h>
#include <header.h>


BPF_HASH(link_metrics_map, struct link_key_t, struct link_metrics_t, HASHMAP_LINK_SIZE);
BPF_TABLE("percpu_hash", struct link_fed_key_t, struct link_fed_metrics_t, link_fed_metrics_map, HASHMAP_FED_LINK_SIZE);
BPF_HASH(link_fed_threshold_map, struct link_fed_key_t, uint32_t, HASHMAP_FED_LINK_SIZE);

static inline
uint32_t compute_ewma(uint32_t measure, uint32_t avg_measures) {
    return (measure >> SHR_EWMA) + avg_measures - (avg_measures >> SHR_EWMA);
}

int collector(struct xdp_md *ctx) {
    void* data_end = (void*)(long)ctx->data_end;
    void* cursor = (void*)(long)ctx->data;
    // Parse outer: Ether->IP->UDP->INT_Telemetry_Report.
    struct ethhdr *eth;
    CURSOR_ADVANCE(eth, cursor, sizeof(struct ethhdr), data_end);
    if (ntohs(eth->h_proto) != ETH_P_IP)
        return XDP_PASS;

    struct iphdr *ip;
    CURSOR_ADVANCE(ip, cursor, sizeof(struct iphdr), data_end);
    if (ip->protocol != IPPROTO_UDP)
        return XDP_PASS;

    struct udphdr *udp;
    CURSOR_ADVANCE(udp, cursor, sizeof(struct udphdr), data_end);
    if (ntohs(udp->dest) != INT_DST_PORT)
        return XDP_PASS;

    struct INT_telemetry_report_t *tm_rp;
    CURSOR_ADVANCE(tm_rp, cursor, sizeof(struct INT_telemetry_report_t), data_end);

    // Parse Inner: Ether->(VLAN)->IP->UDP/TCP->INT_stack.
    CURSOR_ADVANCE(eth, cursor, sizeof(struct ethhdr), data_end);
    uint16_t eth_proto = ntohs(eth->h_proto);
    uint16_t vlan_id;
    if (eth_proto == ETH_P_8021Q){
        struct vlan_hdr* vlan;
        CURSOR_ADVANCE(vlan, cursor, sizeof(struct vlan_hdr), data_end);
        if (ntohs(vlan->h_vlan_encapsulated_proto) != ETH_P_IP) return XDP_DROP;
        vlan_id = ntohs(vlan->h_vlan_TCI) & 0x0FFF;
    } else if ( eth_proto == ETH_P_IP){
    // If the packet is untagged the default VLAN id is 0.
        vlan_id = 0;
    } else
        return XDP_DROP;

    CURSOR_ADVANCE(ip, cursor, sizeof(struct iphdr), data_end);
    uint8_t remain_size;
    if (ip->protocol == IPPROTO_TCP){
        struct tcphdr *tcp;
        CURSOR_ADVANCE(tcp, cursor, sizeof(struct tcphdr), data_end);
        if (tcp->doff >= 5)
            remain_size = tcp->doff*4 - sizeof(struct tcphdr);
        else
            return XDP_DROP;
    } else if (ip->protocol == IPPROTO_UDP) {
        remain_size = sizeof(struct udphdr);
    } else
        return XDP_DROP;
    CURSOR_ADVANCE_NO_PARSE(cursor, remain_size, data_end);

    struct INT_shim_t *int_shim;
    CURSOR_ADVANCE(int_shim, cursor, sizeof(struct INT_shim_t), data_end);
    // INT specification: "hop by hop" with type == 1
    if (int_shim->type != 1)
        return XDP_DROP;

    struct INT_metadata_fixed_t *int_md_fix;
    CURSOR_ADVANCE(int_md_fix, cursor, sizeof(struct INT_metadata_fixed_t), data_end);
    uint16_t int_ins = ntohs(int_md_fix->ins);
    // Check if sw_id, ingress ts and egress ts are the only fields present (bitmask 10001100)
    if ((int_ins >> 8) & 0x8C != 0x8C) return XDP_DROP;
    uint8_t num_INT_hop = (uint8_t)(int_shim->length - 3) / (int_md_fix->hopMlen);

    //WARNING: the data in the INT_Telemetry_Report is ignored! does the sink node append its metadata in the report?
    struct INT_metadata_stack_t *previous_int_data;
    if (num_INT_hop > 0)
        CURSOR_ADVANCE(previous_int_data, cursor, sizeof(struct INT_metadata_stack_t), data_end);
    else
        return XDP_DROP;

    struct INT_metadata_stack_t *int_data;
    struct link_metrics_t *link_metrics_ptr;
    struct link_key_t link_key;
    struct link_fed_key_t link_fed_key = {.vlan_id = vlan_id};
    struct link_fed_metrics_t *link_fed_metrics_ptr;
    uint32_t latency;
    uint32_t *latency_threshold;

    #pragma unroll
    for (uint8_t i = 0; i < MAX_INT_HOP; i++) {
        if (i >= num_INT_hop -1) break;
        CURSOR_ADVANCE(int_data, cursor, sizeof(struct INT_metadata_stack_t), data_end);
        link_key.switch_id_1 = ntohl(int_data->sw_id);
        link_key.switch_id_2 = ntohl(previous_int_data->sw_id);
        latency = ntohl(previous_int_data->ingressTimestamp) - ntohl(int_data->egressTimestamp);
        previous_int_data = int_data;

        link_metrics_ptr = link_metrics_map.lookup(&link_key);
        if (link_metrics_ptr == NULL) {
            struct link_metrics_t link_metrics = {.latency = latency};
            link_metrics_map.update(&link_key, &link_metrics);
        } else
            link_metrics_ptr->latency = compute_ewma(latency, link_metrics_ptr->latency);

        link_fed_key.link_key = link_key;
        link_fed_metrics_ptr = link_fed_metrics_map.lookup(&link_fed_key);
        if (link_fed_metrics_ptr == NULL) {
            struct link_fed_metrics_t link_fed_metrics = {
                .above_threshold_pkts = 0,
                .tot_pkts = 1
            };
            link_fed_metrics_map.update(&link_fed_key, &link_fed_metrics);
        } else {
            link_fed_metrics_ptr->tot_pkts++;
            latency_threshold = link_fed_threshold_map.lookup(&link_fed_key);
            if (latency_threshold != NULL && (latency > *latency_threshold))
                link_fed_metrics_ptr->above_threshold_pkts++;
        }
    }
    return XDP_DROP;
}
