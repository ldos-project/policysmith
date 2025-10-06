#include <uapi/linux/ptrace.h>
#include "tcp_heuristic.h"
// from net/tcp.h
struct rate_sample {
    u64  prior_mstamp; /* starting timestamp for interval */
    u32  prior_delivered;	/* tp->delivered at "prior_mstamp" */
    u32  prior_delivered_ce;/* tp->delivered_ce at "prior_mstamp" */
    s32  delivered;		/* number of packets delivered over interval */
    s32  delivered_ce;	/* number of packets delivered w/ CE marks*/
    long interval_us;	/* time for tp->delivered to incr "delivered" */
    u32 snd_interval_us;	/* snd interval for delivered packets */
    u32 rcv_interval_us;	/* rcv interval for delivered packets */
    long rtt_us;		/* RTT of last (S)ACKed packet (or -1) */
    int  losses;		/* number of packets marked lost upon ACK */
    u32  acked_sacked;	/* number of packets newly (S)ACKed upon ACK */
    u32  prior_in_flight;	/* in flight before this ACK */
    u32  last_end_seq;	/* end_seq of most recently ACKed packet */
    bool is_app_limited;	/* is sample from packet with bubble in pipe? */
    bool is_retrans;	/* is sample from retransmission? */
    bool is_ack_delayed;	/* is this (likely) a delayed ACK? */
};

BPF_ARRAY(cwnd_map, u32, 1);
BPF_PERCPU_ARRAY(bpf_arr_heuristic_state, struct heuristic_state, 1);
BPF_PERCPU_ARRAY(bpf_arr_rate_sample, struct rate_sample, 1);

static inline u32 bpf_core_logic(u8 ca_state, struct heuristic_state* st, const struct rate_sample* rs, u32 prev_cwnd);

int bpf_heuristic_logic_wrapper(struct pt_regs *ctx) {
    u8 ca_state = (u8)PT_REGS_PARM1(ctx);
    struct heuristic_state *st = (struct heuristic_state *)PT_REGS_PARM2(ctx);
    struct rate_sample *rs = (struct rate_sample *)PT_REGS_PARM3(ctx);
    u32 prev_cwnd = (u32)PT_REGS_PARM4(ctx);

    u32 key = 0;

    // get old cwnd
    u32 *old_val = cwnd_map.lookup(&key);

    // read BPF maps
    struct heuristic_state* st_copy = bpf_arr_heuristic_state.lookup(&key);
    struct rate_sample* rs_copy = bpf_arr_rate_sample.lookup(&key);
    if (st_copy == 0 || rs_copy == 0) return 0;
    bpf_probe_read_kernel(st_copy, sizeof(*st_copy), st);
    bpf_probe_read_kernel(rs_copy, sizeof(*rs_copy), rs);    
    
    // core logic
    u32 value = bpf_core_logic(ca_state, st_copy, rs_copy, prev_cwnd);
    
    // update cwnd
    cwnd_map.update(&key, &value);
    bpf_trace_printk("cwnd old=%d new=%d\\n", old_val ? *old_val : 0, value);
    return 0;
}