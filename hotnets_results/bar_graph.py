
import argparse
import json
import matplotlib.pyplot as plt
import numpy as np
import subprocess
import sys

# Define the clusters and their eval IDs
RESULTS = [
    ("cluster_0", "cluster_0", "694b9231e67f33648af7d142"),
    ("PS-B", "cluster_1", "686a908665614c43f2c8d803"),
    ("PS-C", "cluster_2", "686ad41f3626d4810100b30d"),
    ("PS-A", "cluster_3", "686aea309ba953162c4e686c"),
    ("cluster_4", "cluster_4", "694bce0cf0213f4f0c8be157"),
    # ("cluster_5", "cluster_5", "694e692ca6d7defb77190246"),
    # ("cluster_6", "cluster_6", "694b92356bffc1e60e6f7d58"),
    # ("cluster_7", "cluster_7", "694b8e0b645759a64e3b884c"),
    # ("cluster_8", "cluster_8", "694c09c690ab97745c60a416"),
    # ("cluster_9", "cluster_9", "694ee24e8974ab8c731fe817")
]

def get_data(dataset):
    """
    Runs boxplot.py for each cluster and collects the data.
    """    
    all_data = []
    for i, (run_name, cluster_name, eval_id) in enumerate(RESULTS):
        print(f"Collecting data for {run_name} ({i+1}/{len(RESULTS)})...", file=sys.stderr)
        cmd = f"python3 boxplot.py {dataset} --cluster {cluster_name} --eval-names {eval_id} --json"
        
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, shell=True)
        output_json = result.stdout.strip()
        data = json.loads(output_json)
        # Rename key
        new_data = {}
        for k, v in data.items():
            if k.startswith("Vulcan-"):
                new_data["Vulcan"] = v
            else:
                new_data[k] = v
        all_data.append(new_data)
        print(new_data)
    return all_data

def plot_graph(all_data, algos_to_plot):
    num_clusters = len(all_data)
    
    # Filter algos to plot: map "Vulcan" in args to the key in data
    # If user passes "Vulcan", we look for "Vulcan" in data.
    
    # Setup the plot
    fig, ax = plt.subplots(figsize=(15, 6))
    
    # Bar configuration
    num_algos = len(algos_to_plot)
    width = 0.8 / num_algos
    x = np.arange(num_clusters)
    
    # Hatches and colors to match the style somewhat
    patterns = ['//', '\\\\', 'xx', '++', '**', '..', 'oo']
    colors = ['tab:blue', 'tab:orange', 'tab:green', 'tab:red', 'tab:purple', 'tab:brown', 'tab:pink']
    
    # Create bars
    for i, algo in enumerate(algos_to_plot):
        miss_ratios = []
        for cluster_data in all_data:
            miss_ratios.append(cluster_data.get(algo, 0)) # Default to 0 if missing
        
        # Determine label
        label = algo
        if algo == "Vulcan":
            label = "Vulcan" 

        offset = (i - num_algos / 2) * width + width / 2
        ax.bar(x + offset, miss_ratios, width, label=label,
               color=colors[i % len(colors)], hatch=patterns[i % len(patterns)], edgecolor='black')

    # Formatting
    ax.set_ylabel('Miss Ratio\n(improvement over FIFO)', fontsize=18)
    ax.set_xlabel('Cluster', fontsize=18)
    
    # X-axis labels: 0, 1, 2...
    ax.set_xticks(x)
    ax.set_xticklabels([str(i) for i in range(num_clusters)], fontsize=18)
    
    # Legend
    # Put legend at the top
    # Check if we should use latex for the legend text of Vulcan
    handles, labels = ax.get_legend_handles_labels()
    new_labels = []
    for l in labels:
        if l == "Vulcan":
            new_labels.append("Vulcan")
        else:
            new_labels.append(l)
            
    ax.legend(handles, new_labels, loc='upper center', bbox_to_anchor=(0.5, 1.15), ncol=len(algos_to_plot), frameon=False, fontsize=12)
    
    # Grid
    ax.yaxis.grid(True, linestyle='--', alpha=0.7)
    
    # Save
    output_file = "bar_graph_comparison.png"
    plt.tight_layout()
    plt.savefig(output_file, dpi=300)
    print(f"Graph saved to {output_file}")


def main():
    parser = argparse.ArgumentParser(description="Generate bar graph for heuristic comparison across clusters.")
    parser.add_argument('--dataset', type=str, default="CloudPhysics", help="Dataset name")
    parser.add_argument('--algos', nargs='+', default=['Vulcan', 'LRU', 'Sieve', 'S3-FIFO', 'GDSF'], help="Algorithms to plot")
    
    args = parser.parse_args()
    
    data = get_data(args.dataset)
    plot_graph(data, args.algos)

if __name__ == "__main__":
    main()