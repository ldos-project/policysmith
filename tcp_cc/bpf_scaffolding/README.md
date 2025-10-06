# Steps to use this
Tested this on `linux-6.8.0-60-generic`

1. Run `make` to create the kernel module and insert it. 
2. Populate the `bpf_core_logic` function inside `logic.py` with your code, and then run `sudo python3 logic.py`.
3. Run `iperf3 -s`
4. Use `mm-delay 20ms` and then go into `tcp_cc/utils` and do `LD_PRELOAD=./heuristic.so iperf3 -c $MAHIMAHI_BASE`