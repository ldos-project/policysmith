#include <linux/module.h>
#include <linux/kernel.h>
#include <linux/init.h>
#include <net/tcp.h>

#include "tcp_heuristic.h"
#include "bpf_map_hack.h"


// helper functions to manage circular queue
static inline void history_reset(struct heuristic_state *st) { st->head = 0; st->count = 0; }
static inline void history_append(struct heuristic_state *st)
{
	st->head = (st->count == 0) ? 0 : (st->head + 1) % NUMBER_OF_QWINDOWS;
	struct qwindow_sample *slot = &st->history[st->head];
	memset(slot, 0, sizeof(*slot));
	if (st->count < NUMBER_OF_QWINDOWS) st->count++;
}
static inline struct qwindow_sample *history_get(struct heuristic_state *st, u32 i)
{
	if (i >= st->count) return NULL;
	u32 index = (st->head + NUMBER_OF_QWINDOWS - i) % NUMBER_OF_QWINDOWS;
	return &st->history[index];
}

// function prototypes
static void heuristic_init_state(struct sock *sk);
static void heuristic_release(struct sock *sk);
static void inline append_if_need_new_qwindow(struct tcp_sock* tp, struct heuristic_state *st, u64 now);
static void heuristic_pkts_acked(struct sock *sk, const struct ack_sample *sample);
static void heuristic_cwnd_event(struct sock *sk, enum tcp_ca_event ev);
static void heuristic_set_state(struct sock *sk, u8 new_state){}
static void heuristic_cong_control(struct sock *sk, const struct rate_sample *rs);
u32 noinline cong_control_logic(u8 ca_state, const struct heuristic_state *st, const struct rate_sample *rs, u32 prev_cwnd);


// Allocate state on flow init
static void heuristic_init_state(struct sock *sk)
{
	struct heuristic_ca *ca = (struct heuristic_ca *)inet_csk_ca(sk);
	ca->state = kzalloc(sizeof(struct heuristic_state), GFP_KERNEL);
	ca->start_ts = ktime_get_ns();
	BUG_ON(ca->state->count != 0);
	BUG_ON(ca->state->head != 0);
	if (!ca->state)
		pr_warn("heuristic: kzalloc failed\n");
}

// Free state on flow teardown
static void heuristic_release(struct sock *sk)
{
	struct heuristic_ca *ca = (struct heuristic_ca *)inet_csk_ca(sk);
	kfree(ca->state);
	ca->state = NULL;
}

static void inline append_if_need_new_qwindow(struct tcp_sock* tp, struct heuristic_state *st, u64 now)
{
	if (st->count == 0) {
		history_append(st);
		history_get(st, 0)->start_time_ns = now;
		st->bytes_acked_from_start_of_curr_qwindow = tp->bytes_acked;
		return;
	}
	
	struct qwindow_sample* curr_h = history_get(st, 0);
	u64 time_elapsed_in_qwindow = now - curr_h->start_time_ns;
	u64 threshold = max(MIN_QWINDOW_DURATION_MS * 1000ULL * 1000ULL, (u64) st->global_min_rtt_us);

	if (time_elapsed_in_qwindow >= threshold){
		curr_h->bandwidth_bps = (8ULL * NSEC_PER_SEC * curr_h->bytes_acked) / (now - curr_h->start_time_ns);
		st->global_max_bandwidth_bps = max(st->global_max_bandwidth_bps, curr_h->bandwidth_bps);
		st->global_min_bandwidth_bps = min(st->global_min_bandwidth_bps, curr_h->bandwidth_bps);
		history_append(st);
		history_get(st, 0)->start_time_ns = now;
		st->bytes_acked_from_start_of_curr_qwindow = tp->bytes_acked;
	}
	
}

static void heuristic_pkts_acked(struct sock *sk, const struct ack_sample *sample)
{
	struct heuristic_ca *ca = (struct heuristic_ca *)inet_csk_ca(sk);
	struct heuristic_state *st = ca->state;
	struct tcp_sock *tp = tcp_sk(sk);

	if (!tp || !st || !sample || sample->rtt_us < 0) return;
	u64 now = ktime_get_ns() - ca->start_ts;
	st->last_ack_time_ns = now;
	st->inflight_bytes = tp->bytes_sent - tp->bytes_acked;

	append_if_need_new_qwindow(tp, st, now);

	struct qwindow_sample* h = history_get(st, 0);
	BUG_ON(h == NULL);
	h->end_time_ns = now;
	h->packets_delivered += sample->pkts_acked;
	h->bytes_acked = tp->bytes_acked - st->bytes_acked_from_start_of_curr_qwindow;
	if((now - h->start_time_ns) > 0 ) h->bandwidth_bps = (h->bytes_acked * 8ULL * NSEC_PER_SEC ) / (now - h->start_time_ns);
	
	// update RTTs (global and qwindow)
	if(sample->rtt_us != 0) {
		st->global_max_rtt_us = max_t(u32, st->global_max_rtt_us, sample->rtt_us);
		st->global_min_rtt_us = min_t(u32, st->global_min_rtt_us, sample->rtt_us);
		
		h->max_rtt_us = max_t(u32, h->max_rtt_us, sample->rtt_us);
		h->min_rtt_us = min_t(u32, h->min_rtt_us, sample->rtt_us);
		h->n_rtt_us++;
		h->sum_rtt_us += sample->rtt_us;
		h->avg_rtt_us = h->sum_rtt_us/h->n_rtt_us;
	}	
}

static void heuristic_cwnd_event(struct sock *sk, enum tcp_ca_event ev)
{
	struct tcp_sock *tp = tcp_sk(sk);
	struct heuristic_ca *ca = (struct heuristic_ca*) inet_csk_ca(sk);
	struct heuristic_state *st = ca->state;

	if (!st) return;
	u64 now = ktime_get_ns() - ca->start_ts;
	
	append_if_need_new_qwindow(tp, st, now);

	struct qwindow_sample* h = history_get(st, 0);
	if(!h) return;
	h->end_time_ns = now;
	
	switch (ev) {
		case CA_EVENT_LOSS:
			h->n_loss_notifications++;
			break;

		case CA_EVENT_ECN_IS_CE:
			h->n_ecn_notifications++;
			h->ecn_enabled = true;
			break;
		
		case CA_EVENT_ECN_NO_CE:
			h->ecn_enabled = true;
			break;
			
		default:
			break;
	}
}

static void heuristic_cong_control(struct sock *sk, const struct rate_sample *rs)
{
	struct tcp_sock *tp = tcp_sk(sk);
	struct heuristic_ca *ca = (struct heuristic_ca *)inet_csk_ca(sk);
	struct heuristic_state *st = ca->state;

	if (!st || !rs) return;
	u64 now = ktime_get_ns();

	append_if_need_new_qwindow(tp, st, now);
	
	struct qwindow_sample* h = history_get(st, 0);
	h->end_time_ns = now;	
	
	u8 ca_state = inet_csk(sk)->icsk_ca_state;

	u32 new_cwnd = cong_control_logic(ca_state, st, rs, tp->snd_cwnd);
	st->global_max_cwnd_seen = max(st->global_max_cwnd_seen, new_cwnd);
	tcp_snd_cwnd_set(tp, clamp(new_cwnd, 2U, tp->snd_cwnd_clamp));
}

u32 noinline cong_control_logic(u8 ca_state, const struct heuristic_state *st, const struct rate_sample *rs, u32 prev_cwnd){
	u32 new_cwnd;
	if (lookup_cwnd(&new_cwnd)) {
		pr_info("cong_control_logic: lookup success, new_cwnd = %u\n", new_cwnd);
		return new_cwnd;
	}
	else {
		pr_warn("cong_control_logic: lookup FAILED.\n");
		return 2;
	}
}
EXPORT_SYMBOL_GPL(cong_control_logic);

static struct tcp_congestion_ops tcp_heuristic __read_mostly = {
	.name           = "heuristic",
	.owner          = THIS_MODULE,

    // basics
    .init           = heuristic_init_state,
	.release        = heuristic_release,

	// mini-decision making
    .undo_cwnd      = tcp_reno_undo_cwnd,
	.ssthresh       = tcp_reno_ssthresh,

	// main decision making
	.cong_control   = heuristic_cong_control,
	
    // state managenent
	.pkts_acked     = heuristic_pkts_acked,
	.cwnd_event     = heuristic_cwnd_event,
	.set_state      = heuristic_set_state,
};

static int __init heuristic_register(void)
{
	bool status1 = init_hack();
	bool status2 = tcp_register_congestion_control(&tcp_heuristic);
	pr_info("heuristic_register: hack_status=%d, tcp_register=%d\n", status1, status2);
	return status1 && status2;
}

static void __exit heuristic_unregister(void)
{
	tcp_unregister_congestion_control(&tcp_heuristic);
	destroy_hack();
}

module_init(heuristic_register);
module_exit(heuristic_unregister);

MODULE_AUTHOR("Rohit Dwivedula <rohitdwivedula@gmail.com>");

MODULE_LICENSE("GPL");
