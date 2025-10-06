#ifndef TCP_HEURISTIC_H
#define TCP_HEURISTIC_H

#define NUMBER_OF_QWINDOWS 10
#define MIN_QWINDOW_DURATION_MS 1

struct qwindow_sample {
	u64 start_time_ns;   // 8 bytes
	u64 end_time_ns;    // 8 bytes
	
	u32 packets_delivered; // 4 bytes
	u32 n_loss_notifications; // 4 bytes % lost bytes???
	u32 n_ecn_notifications; // 4 bytes 

	u64 sum_rtt_us; // 8 bytes
	u64 n_rtt_us;  // 8 bytes
	u32 min_rtt_us; // 4 bytes
	u32 avg_rtt_us; // 4 bytes
	u32 max_rtt_us; // 4 bytes
	bool ecn_enabled;

	u64 bytes_acked; // 8 bytes
	u64 bandwidth_bps; // 8 bytes
};

struct heuristic_state {
	struct qwindow_sample history[NUMBER_OF_QWINDOWS];  // 320 bytes
	u32 head;
	u32 count;

	u64 bytes_acked_from_start_of_curr_qwindow;

	// latest metrics
	u64 last_ack_time_ns;      // last ACK timestamp
	u64 inflight_bytes;        // bytes in flight

	// historical / global stats
	u32 global_max_cwnd_seen;         // highest cwnd ever observed (at any point of time)
	
	u32 global_min_bandwidth_bps; // maximum bandwidth in bits/sec seen for one rate_sample (over all time)
	u32 global_max_bandwidth_bps; // maximum bandwidth in bits/sec seen for one rate_sample (over all time)
	
	u32 global_min_rtt_us;               // minimum delay seen for one packet / ACK (over all time)
	u32 global_max_rtt_us;               // maximum delay seen for one packet / ACK (over all time)	
};

struct heuristic_ca {
	struct heuristic_state *state;
	u64 start_ts;
};

#endif