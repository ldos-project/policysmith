"""
Util script for plotting functions
"""

def ms_to_bins(ms, ms_per_bin):
    return ms // ms_per_bin


def read_sum_file(filename):
    with open(filename, 'r') as f:
        lines = f.readlines()
    lines = [line.strip() for line in lines]

    utilization = 0
    delay_avg = 0
    delay_95p = 0

    for line in lines:
        if "utilization" in line:
            utilization = float(line.split()[-2][1:-1])
        if "Average per packet delay" in line:
            delay_avg = float(line.split()[-2])
        if "95th" in line:
            delay_95p = float(line.split()[-2])
    
    return utilization, delay_avg, delay_95p


def read_down_file(filename, ms_per_bin):
    base_time = None
    running_duration = None
    
    # For plotting
    arrivals = {}
    departures = {}
    capacity = {}

    drops = 0
    with open(filename, 'r') as f:
        for line in f:
            if line.startswith('#'):
                if "base timestamp" in line:
                    base_time = int(line.split()[-1])
                continue
            
            # Validate if the line is of the form: <time> <event> <bytes>
            tokens = line.strip().split()        

            timestamp = int(tokens[0]) - base_time
            ts_bin = ms_to_bins(timestamp, ms_per_bin)
            running_duration = timestamp

            event = tokens[1]
            bytes = int(tokens[2])
            num_bits = bytes * 8

            if event == '-':
                # Implies a successful packet delivery
                if ts_bin not in departures:
                    departures[ts_bin] = 0
                departures[ts_bin] += num_bits
            elif event == '+':
                # Implies a packet arrival to the link
                if ts_bin not in arrivals:
                    arrivals[ts_bin] = 0
                arrivals[ts_bin] += num_bits
            elif event == '#':
                # Implies an unused capacity
                if ts_bin not in capacity:
                    capacity[ts_bin] = 0
                capacity[ts_bin] += num_bits
            elif event == 'd':
                # Implies a dropped packet
                drops += 1
            else:
                print(f"Unknown event: {event}")

    print_name = filename.split("/")[-1].split("-")[:4]
    print(drops)
    if drops > 10000:
        print(f"{drops} drops in {print_name}")
    return arrivals, departures, capacity, running_duration