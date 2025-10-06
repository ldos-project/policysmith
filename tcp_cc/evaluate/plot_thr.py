"""
Read the log file of mm-link and plot the throughput.
"""

import os
import sys
import matplotlib.pyplot as plt
from utils import *

if __name__ == "__main__":
    if len(sys.argv) < 5:
        print(
            f"Usage: {sys.argv[0]} <start-time (use 0 for beginning)> <end-time (use -1 for entire plot)> <offset> <path-to-log-file1> <path-to-log-file2> ..."
        )
        sys.exit(1)
    start_time = int(sys.argv[1])
    end_time = int(sys.argv[2])
    offset = int(sys.argv[3])
    log_files = sys.argv[4:]
    ms_per_bin = 500

    # Plot formatting
    plt.rcParams["font.size"] = 16
    plt.figure(figsize=(10, 3.6))
    # plt.figure(figsize=(10, 4))

    colors = ["#82B366", "#D79B00", "#B85450", "#D6B656", "#9673A6", "#6C8EBF", "#BF5700"]
    markers = ["o", "P", "^", "s", "v", "^"]
    styles = ["-", "--", "-.", ":", (0, (3, 1, 1, 1)), (0, (2, 1)), (0, (5, 1))]

    # Time range to plot
    start_bin = ms_to_bins(start_time * 1000, ms_per_bin)
    if end_time != -1:
        end_bin = ms_to_bins(end_time * 1000, ms_per_bin)
    # print(f"Plotting from bin {start_bin} to {end_bin}")

    for index, log_file in enumerate(log_files):
        if not os.path.exists(log_file):
            print(f"Log file {log_file} does not exist.")
            sys.exit(1)

        arrivals, departures, capacity, running_duration = read_down_file(
            log_file, ms_per_bin
        )

        # Plot the throughput
        time_bins = [i for i in range(ms_to_bins(running_duration, ms_per_bin))]
        print(f"Total running duration: {running_duration} ms = {len(time_bins)} bins")

        sending_rate = []
        total_capacity = []
        for bin in time_bins:
            arrival = arrivals.get(bin, 0) / (10**3 * ms_per_bin)
            departure = departures.get(bin, 0) / (10**3 * ms_per_bin)
            unused_capacity = capacity.get(bin, 0) / (10**3 * ms_per_bin)
            # print(f"Bin {bin}: {arrival} Mbps, {departure} Mbps, {unused_capacity} Mbps")

            sending_rate.append(arrival)
            total_capacity.append(unused_capacity)

        if end_time != -1:
            time_bins = [(x - start_bin) for x in time_bins[start_bin:end_bin]]
            sending_rate = sending_rate[start_bin:end_bin]
            total_capacity = total_capacity[start_bin:end_bin]
        else:
            end_bin = len(time_bins) - 1

        label=log_file

        time_bins = [x/2 + index*offset for x in time_bins]
        if index == 0:
            # Plot the capacity as area under the curve
            plt.fill_between(time_bins, 0, total_capacity, label="Capacity", alpha=0.2)
        
        plt.plot(
            time_bins,
            sending_rate,
            label=label,
            linewidth=4,
        )

    
    # Add vertical lines to show the times of conern.
    # plt.axvline(x=20, color="black", linestyle="--", linewidth=2)
    # plt.axvline(x=24, color="black", linestyle="--", linewidth=2)


    # Convert the x-axis to seconds
    interval = int((end_bin - start_bin) // 5)

    # plt.xticks(
    #     [i for i in range(0, end_bin - start_bin + 1, interval)],
    #     [
    #         int(i * ms_per_bin / 1000)
    #         for i in range(0, end_bin - start_bin + 1, interval)
    #     ],
    # )
    plt.xlabel("Time (s)", fontsize=20)
    plt.ylabel("Sending Rate (Mbps)", fontsize=20)

    # # Use this configuration when plotting many curves.
    # plt.legend(loc="upper center", bbox_to_anchor=(0.5, 1.4), ncol=3, fontsize=20, frameon=False)
    # plt.subplots_adjust(top=0.78, bottom=0.16, left=0.09, right=0.98)
    
    plt.legend(loc="upper center", bbox_to_anchor=(0.5, 1.25), ncol=4, fontsize=20, frameon=False)
    plt.subplots_adjust(top=0.85, bottom=0.18, left=0.1, right=0.98)

    plt.savefig("throughput.png")
