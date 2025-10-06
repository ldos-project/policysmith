import textwrap
from Evolve import EvolveInterface
from utils import cpp_comment_remover
from typing import List

class TCPEvolve(EvolveInterface):
    def __init__():
        self.make_dir = os.path.join(os.getcwd(), "./tcp_cc/kern_mod")
        self.template_path = os.path.join(self.make_dir, "tcp_heuristic.template")

        assert os.path.exists(self.make_dir), "Build directory does not exist :-("
    
    def common_prompt(self) -> str:
        return '''\
            You are a networking engineer expert designing a new TCP congestion control algorithm for the Linux kernel. You have to implement two functions:

            ```c
            // Purpose: Decide the new congestion window (cwnd) based on the latest flow statistics and ACK information.
            static u32 cong_control_logic(u8 ca_state, const struct heuristic_state *st, const struct rate_sample *rs, u32 prev_cwnd);
            
            // Purpose: Recover cwnd after a loss recovery (e.g., fast retransmit) by partially or fully restoring the previous congestion window, balancing between fast recovery and stability.
            static u32 undo_cwnd_logic(u8 ca_state, const struct heuristic_state *st, u32 prev_cwnd);
            ```

            These functions are compiled into a kernel module. Do not allocate memory, use floating point, or access globals. You may use only the inputs provided.

            Inputs:
            1. `ca_state` (u8): ca_state (u8) indicates the current TCP congestion state: TCP_CA_Open means no signs of loss or ECN; TCP_CA_Disorder suggests possible reordering or early loss from DUPACKs/SACKs; TCP_CA_CWR follows ECN marks or local congestion; TCP_CA_Recovery indicates fast retransmit is active; and TCP_CA_Loss is used for timeout-based recovery. 

            2. `rs` (const struct rate_sample*): This is the rate sample dict that BBR uses in the modern cong_control Linux API
                - u64  prior_mstamp; /* starting timestamp for interval */
                - u32  prior_delivered;	/* tp->delivered at "prior_mstamp" */
                - s32  delivered;		/* number of packets delivered over interval */
                - long interval_us;	/* time for tp->delivered to incr "delivered" */
                - u32 snd_interval_us;	/* snd interval for delivered packets */
                - u32 rcv_interval_us;	/* rcv interval for delivered packets */
                - long rtt_us;		/* RTT of last (S)ACKed packet (or -1) */
                - int  losses;		/* number of packets marked lost upon ACK */
                - u32  acked_sacked;	/* number of packets newly (S)ACKed upon ACK */
                - u32  prior_in_flight;	/* in flight before this ACK */
                - bool is_app_limited;	/* is sample from packet with bubble in pipe? */
                - bool is_retrans;	/* is sample from retransmission? */
                - bool is_ack_delayed;	/* is this (likely) a delayed ACK? */

            3. `prev_cwnd` (u32): The current cwnd size before your logic runs.
            
            4. Heuristic state: In addition to the above standard Linux TCP inputs, you are provided a `heuristic_state` (`st`) object that tracks persistent flow-level statistics. It contains:
                - `st->last_ack_time_ns` (u64): timestamp of most recent ACK (nanoseconds since flow start)
                - `st->global_max_cwnd_seen` (u32): max cwnd observed in flow lifetime
                - `st->global_min_bandwidth_bps`, `st->global_max_bandwidth_bps` (u32): min/max bandwidth seen over flow lifetime (bits/second)
                - `st->global_min_rtt_us`, `st->global_max_rtt_us` (u32): Min/max RTT seen over the flow's lifetime (microseconds) 
                - `st->inflight_bytes` (u64): bytes in flight (not acked yet)
            You may query recent time windows using: `const struct qwindow_sample *s = history_get(st, i); // i = 0 (latest) to st->count - 1`. Each qwindow is approximately 1 RTT in duration. `st->bytes_acked_from_start_of_curr_qwindow` is another attribute available. Each qwindow_sample (history entry) includes:
                - `start_time_ns`, `end_time_ns` (u64): Start/end timestamp of the window (nanoseconds). e.g, `history_get(st, 1)->start_time_ns`
                - `packets_delivered` (u32): number of packets delivered in the window.
                - `bytes_acked` (u64): Total number of bytes acknowledged in the window
                - `bandwidth_bps` (u64): estimated bandwidth for the window (bits per second)             
                - `n_loss_notifications`, `n_ecn_notifications` (u32): Number of loss events and ECN CE marks seen during this window, respectively.
                - `min_rtt_us`, `avg_rtt_us`, `max_rtt_us` (u32): min/avg/max RTT observed in the window (microseconds).
                - `ecn_enabled` (bool): was ECN seen active during the window
            
            Important rules when writing code:
            1. Only use provided inputs. Do not access or define globals or external variables
            2. Assume all structs (e.g., `heuristic_state`, `qwindow_sample`) are pre-defined.
            3. Standard kernel headers (<linux/module.h>, <linux/kernel.h>, <linux/init.h>, <net/tcp.h>) are already included. Add others only if needed.
            4. No floating point: use integer math - e.g., `(x * 8) / 10` instead of `0.8 * x`. Note that this might lead to loss of accuracy due to integer truncation. 

            Function signatures once again (you must write implementations for both - function signature prototypes already exist so don't redefine them):
            ```c
            // Purpose: Decide the new congestion window (cwnd) based on the latest flow statistics and ACK information.
            static u32 cong_control_logic(u8 ca_state, const struct heuristic_state *st, const struct rate_sample *rs, u32 prev_cwnd);
            
            // Purpose: Recover cwnd after a loss recovery (e.g., fast retransmit) by partially or fully restoring the previous congestion window, balancing between fast recovery and stability.
            static u32 undo_cwnd_logic(u8 ca_state, const struct heuristic_state *st, u32 prev_cwnd);
            
            // your generated code is inserted here
            ```
        '''


    def initial_prompt(self, initial: str) -> str:
        return textwrap.dedent(f'''\
            {self.common_prompt()}
            Use this format for your reply:
            <think through the inputs provided and the key tradeoff: throughput vs delay>
            <come up with 2-3 concrete heuristic ideas using these inputs. Be specific and make these heuristics as precise (well-defined) as possible>
            <weigh the ideas, and shortlist one that you will try.>
            <Pick your best idea and explain it clearly with a short title. Describe the logic in plain English - just enough that a kernel developer could implement it from the explanation>
            <write the actual code for both `cong_control_logic()` and `undo_cwnd_logic()` in a single code block as shown below>
            Code:
            ```c
            <Fill in the functions here.>
            ```
        ''')

    def mutate_prompt(self, versions: List[str]) -> str:
        prompt = f'''\
            {self.common_prompt()}

            Below are earlier versions of the function(s). You must now write a new version that improves or explores a different heuristic.
            Don't just rename or slightly reorder logic - introduce a meaningful change. Be creative but safe.
        '''
        for i, code in enumerate(versions):
            cleaned_code = cpp_comment_remover(code).strip()

            prompt += f'''\
                ```c
                // Version {i}
                {cleaned_code}
                ```
            '''
        
        prompt += '''\
            Now write your new version in a single code block:
            Code:
            ```c
            // cong_control_logic and undo_cwnd_logic
            ```
        '''

        return textwrap.dedent(prompt)

    def debug_prompt(self, stdout, stderr):
        return f'''\
            Your code unfortunately errored out. Given below is the stdout and stderr. Read the logs, reason about what might have gone wrong, and then provide an updated version of the code in a similar code block as before. The line numbers you see in the stdout/stderr logs may not corrspond to line numbers in your provided code block; the build system is complex and it copies your code into the correct place amongst a bunch of other code, so it might be off by an offset. 

            ### <stdout>: {stdout.strip()}

            ### <stderr>: {stderr.strip()}
        '''


    # template_path="", output_path="tcp_heuristic.c",,
    # output_dir=None, idx=None, version=None
    def build_and_test(self, code_text):
        """
        - Reads the template file.
        - Appends LLM-generated code to it.
        - Writes the combined result to tcp_heuristic.c.
        - Runs `make` in the specified directory (default: current directory).
        
        Returns:
            (status: bool, stdout: str, stderr: str)
        """
        # Read the template
        with open(self.template_path, "r") as f:
            template_content = f.read()

        # Write to tcp_heuristic.c
        with open(os.path.join(self.make_dir, output_path), "w") as f:
            f.write(template_content)
            f.write("\n\n")
            f.write(code_text)
            f.write("\n")

        # Run `make`
        cmd = f"cd {self.make_dir} && make"
        proc = subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        stdout, stderr = proc.communicate()

        status = (proc.returncode == 0)
        
        # write logs to file
        return status, stdout, stderr