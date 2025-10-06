import argparse
import json
import os
import signal
import subprocess
import time
import textwrap
from typing import List, Tuple

from Evolve import EvolveInterface
from utils import cpp_comment_remover

def parse_sum_file(lines):
    utilization = 0
    throughput = 0
    queuing_delay_95p = 0
    signal_delay_95p = 0

    for line in lines:
        if "utilization" in line:
            utilization = float(line.split()[-2][1:-1])
            throughput = float(line.split()[2])
        if "95th percentile per-packet queueing delay" in line:
            queuing_delay_95p = float(line.split()[-2])
        if "95th percentile signal delay" in line:
            signal_delay_95p = float(line.split()[-2])

    return_dict = {
        'utilization': utilization, 
        'queuing_delay_95p': queuing_delay_95p, 
        'signal_delay_95p': signal_delay_95p, 
        'throughput': throughput
    }
    print(return_dict)
    
    return return_dict

class CongestionControlBPF(EvolveInterface):
    def __init__(self, task_args = []):
        assert os.geteuid() != 0, "Must not run the script with sudo - causes mm-delay issues"
        task_parser = argparse.ArgumentParser()
        task_parser.add_argument("--bw", type=int, default=12)
        task_parser.add_argument("--delay", type=int, default=20)
        task_parser.add_argument("--bdp_multiplier", type=int, default=2)
        task_parser.add_argument("--timeout", type=int, default=20)
        self.task_args = task_parser.parse_args(task_args)

        # trace
        self.trace_dir = os.path.join(os.getcwd(), "./tcp_cc/evaluate/sage_traces/traces/")
        self.trace_path = os.path.join(self.trace_dir, f"wired{self.task_args.bw}")

        # code
        self.code_dir = os.path.join(os.getcwd(), "./tcp_cc/bpf_scaffolding/")
        self.build_dir = self.code_dir        
        self.llm_code_path = os.path.join(self.build_dir, "LLMCode.h")
        self.utils_dir = os.path.join(os.getcwd(), "tcp_cc/utils")

        # logging
        self.log_dir = os.path.join(os.getcwd(), "./tcp_cc/evaluate/logs/")

        # run parameters
        self.task_args.bdp = (2 * self.task_args.bw * self.task_args.delay)/12.0
        self.task_args.qs = int(round(self.task_args.bdp * self.task_args.bdp_multiplier, 0))

    def run_info(self):
        return {
            "task_args": vars(self.task_args)
        }

    def common_prompt(self) -> str:
        return textwrap.dedent('''\
            You are a networking engineer expert designing a new TCP congestion control algorithm for the Linux kernel. You have to implement the `cong_control_logic` function:

            ```c
            // Purpose: Decide the new congestion window (cwnd) based on the latest flow statistics and ACK information.
            static inline u32 bpf_core_logic(u8 ca_state, struct heuristic_state* st, const struct rate_sample* rs, u32 prev_cwnd);
            ```

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
            
            Important rules when writing code: These functions are compiled into a eBPF probe. Do not allocate memory, use floating point, or access globals. Only use provided inputs. Do not access or define globals or external variables. Assume all structs (e.g., `heuristic_state`, `qwindow_sample`) are pre-defined. Standard kernel headers (<linux/module.h>, <linux/kernel.h>, <linux/init.h>, <net/tcp.h>) are already included. Do NOT add any others. No floating point: use integer math - e.g., `(x * 8) / 10` instead of `0.8 * x`. Note that this might lead to loss of accuracy due to integer truncation. 
        ''')
    
    def initial_prompt(self) -> str:
        return textwrap.dedent(f'''\
            {self.common_prompt()}
            REPLY FORMAT:
            <think about the inputs provided come up with 2-3 concrete heuristic ideas using these inputs.>
            <Weigh the ideas, and shortlist one that you will try.>
            <For this shortlisted idea, explain it clearly in plain English. A kernel developer should be able to understand your idea and implement it from the explanation>
            <write the actual code for `cong_control_logic()`in a single code block as shown below - there must be exactly ONE code block in your response. No more than that>
            Code:
            ```c
            static inline u32 bpf_core_logic(u8 ca_state, struct heuristic_state* st, const struct rate_sample* rs, u32 prev_cwnd) {{
                <your logic here.>
            }}
            ```
        ''')

    def mutate_prompt(self, versions: List[str]) -> str:
        prompt = self.common_prompt() + textwrap.dedent(f'''\
            Below are earlier versions of the functions. You must now write a new version that improves upon these.
            Don't just rename or slightly reorder logic - introduce a meaningful change. Be creative but safe.
        ''')

        for i, code in enumerate(versions):
            cleaned_code = cpp_comment_remover(code).strip()

            prompt += f'''```cpp\n// Version {i}\n{cleaned_code}\n```\n\n'''

        prompt += textwrap.dedent(f'''\
            Now write your new version in a single code block:
            Code:
            ```cpp
            // Version {i+1}
            <<Your new version of eviction_heuristic here>>
            ```
            ''')

        return textwrap.dedent(prompt)
    
    def debug_prompt(self, stdout: str, stderr: str) -> str:
        # strip stdout and stderr to the first 2000 chars
        return textwrap.dedent(f'''\
            Your code unfortunately errored out. Read the build stderr logs (given below), think about what the error messages might mean, and then provide a complete, corrected version of the code in a formatted code block like you did earlier. Line numbers you see in the stderr logs do not correspond to line numbers in your code block; the build system is complex and it copies your code into the correct place amongst a bunch of other code, so it will be off by an offset.\n'''
        ) + f'''### <stderr>: {stderr.strip()}'''

    def cleanup_build_env(self): 
        os.system(f"ps aux | grep logi[c].py | tr -s ' ' | cut -d ' ' -f2 | xargs sudo kill -9")
        os.system(f"cd {self.build_dir} && make clean > /dev/null 2>&1")
        os.system(f"sudo pkill iperf3")
        os.system(f"sudo pkill mm-link")
        os.system(f"sudo pkill mm-delay")
        
        if os.path.exists(self.llm_code_path):
            os.system(f"rm {self.llm_code_path} > /dev/null 2>&1")
        else:
            print("LLM generated codefile does not exist")
    
    def copy_code(self, code: str):
        # add code to LLM code path
        with open(self.llm_code_path, "w") as f:
            f.write(code)

    def build(self, code: str) -> Tuple[bool, str, str]:
        """
        Returns (success, stdout, stderr)
        """
        self.cleanup_build_env()
        self.copy_code(code)

        for i in range(3):
            try:
                assert os.system(f"cd {self.build_dir} && make") == 0
                break
            except AssertionError:
                print(f"[i={i}] Build failed. Trying to force remove tcp_heuristic kmod")
                os.system("sudo rmmod tcp_heuristic")
                time.sleep(3)
        
        proc = subprocess.Popen(
            f"cd {self.build_dir} && sudo python3 logic.py test",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        

        try:
            stdout, stderr = proc.communicate(timeout=60) # we wait 3 minutes at most for build
        except subprocess.TimeoutExpired:
            assert os.name == "posix"
            os.killpg(proc.pid, signal.SIGKILL)
            stdout, stderr = proc.communicate()
            return False, stdout.strip(), stderr.strip()
        
        success = (proc.returncode == 0)
        return success, stdout.strip(), stderr.strip()
    
    def kill_process(self, proc):
        proc.send_signal(signal.SIGINT)

        for i in range(3):
            try:
                outputs = proc.communicate(timeout=5) 
                return outputs
            except subprocess.TimeoutExpired:
                proc.kill()
                os.killpg(proc.pid, signal.SIGKILL)
        
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)

    def run_experiment(self):
        bpf_probe_proc = subprocess.Popen(
            f"cd {self.build_dir} && sudo python3 logic.py",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            preexec_fn=os.setsid
        )

        iperf_server = subprocess.Popen(
            f"pkill iperf3; iperf3 -s",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            preexec_fn=os.setsid
        )
        log_location = os.path.join(self.log_dir, f"down")
        sum_location = os.path.join(self.log_dir, f"sum")
        os.system(f"rm -rfv {log_location} {sum_location}")

        cmd = f"mm-delay {self.task_args.delay} mm-link {self.trace_path} {os.path.join(self.trace_dir, 'wired192')} --uplink-queue-args=\"packets={self.task_args.qs}\"  --downlink-queue-args=\"packets={self.task_args.qs}\" --uplink-queue=droptail --downlink-queue=droptail --uplink-log={log_location} -- bash -c 'cd {self.utils_dir} && sudo LD_PRELOAD=./heuristic.so iperf3 -c $MAHIMAHI_BASE -t {self.task_args.timeout}'"
        print(cmd)

        measurement_proc = subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            preexec_fn=os.setsid
        )

        try:
            measurement_proc.communicate(timeout=self.task_args.timeout + 5)
        except subprocess.TimeoutExpired:
            output = self.kill_process(measurement_proc)
        
        # get BPF probe stats
        bpftool_proc = subprocess.Popen(
            "sudo bpftool prog show",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        bpftool_stdout, bpftool_stderr = bpftool_proc.communicate(timeout=10)


        # kill the BPF probe
        os.system(f"ps aux | grep logi[c].py | tr -s ' ' | cut -d ' ' -f2 | xargs sudo kill -9")

        bpf_output = self.kill_process(bpf_probe_proc)
        iperf_output = self.kill_process(iperf_server)
        
        eval_log_dict = {
            "bpf_logs": bpf_output,
            "iperf_logs": iperf_output,
            "bpftool_logs": bpftool_stdout
        }

        if os.path.exists(log_location):
            mm_thr_proc = subprocess.Popen(
                f"cd {self.log_dir} && mm-throughput-graph 500 down > /dev/null",
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                preexec_fn=os.setsid
            )
            
            mm_thr_stdout, mm_thr_stderr = mm_thr_proc.communicate(timeout=5)
            print(mm_thr_stderr)
            final_results_dict = {
                "results": parse_sum_file(mm_thr_stderr.splitlines())
            }
            
            if 'queuing_delay_95p' in final_results_dict['results'].keys() and 'throughput' in final_results_dict['results'].keys():
                final_results_dict['score'] = final_results_dict['results']['throughput'] / (1e-5 + final_results_dict['results']['queuing_delay_95p'])
                return True, final_results_dict, eval_log_dict
            else:
                return False, final_results_dict, eval_log_dict
        else:
            print("LOG MISSING! :------(")
            return False, {}, eval_log_dict