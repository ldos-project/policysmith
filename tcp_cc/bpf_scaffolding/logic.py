from bcc import BPF
import fcntl
import struct
import sys
import time

REGISTER_CWND = 0x0
UNREGISTER_CWND = 0x1

def register_cwnd(fd_to_register, test_build=False):
    with open("/dev/cwnd_device", "r") as dev:
        packed_fd = struct.pack("i", fd_to_register)
        fcntl.ioctl(dev, REGISTER_CWND, packed_fd)

def unregister_cwnd():
    with open("/dev/cwnd_device", "r") as dev:
        fcntl.ioctl(dev, UNREGISTER_CWND)

def attach_cwnd_setter(test_build=False):
    if test_build:
        print("[logic.py] In TEST mode. Will exit immediately.")
    
    # get BPF program from files.
    with open("bpf_prog.h", 'r') as f:
        bpf_program = f.read()
    bpf_program += "\n\n\n"
    with open("LLMCode.h", 'r') as f:
        bpf_program += f.read()

    b = BPF(text=bpf_program)
    fd = b["cwnd_map"].map_fd
    register_cwnd(fd)

    assert fd >= 0, "Failed to create fd -- why?"

    # Attach kprobe to cong_control_logic
    b.attach_kprobe(event="tcp_heuristic:cong_control_logic", fn_name="bpf_heuristic_logic_wrapper")
    print("Attached to cong_control_logic. Press Ctrl+C to exit.")
    
    try:
        while True:
            time.sleep(1)
            if test_build:
                break
    except KeyboardInterrupt:
        unregister_cwnd()
        print("\nExiting.")

if __name__ == "__main__":
    attach_cwnd_setter(test_build=(len(sys.argv) > 1 and sys.argv[1] == "test"))