import argparse
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pymongo

MONGO_CONNECTION_STRING = "mongodb://localhost:27017/"

def rename_algo(algo, dataset=None):
    if algo.startswith("PQEvolve"):
        return algo.split('_')[-1]
    elif algo == "PolicySmith-Oracle":
        return "PS-Oracle"
    elif algo == "Baselines-Oracle":
        return "B-Oracle"
    elif algo.startswith("S3FIFO"):
        return "S3-FIFO"
    elif "FIFO" in algo and "reinsertion" in algo.lower():
        return "FIFO-Re"
    else:
        return algo

def main(args):
    client = pymongo.MongoClient(MONGO_CONNECTION_STRING)
    db = client["policysmith"]

    # collect baselines
    df = pd.DataFrame(list(db["baselines_percent"].find({})))
    df = df[df['trace_name'].str.startswith(f"{args.dataset}/") & (df['cache_name'] != 'Belady')]

    # collect evaluations
    evals = list(db["evaluation"].find())
    eval_df = pd.DataFrame(evals)

    # Update 'cache_name' to 'cache_name'+'collection' for each row
    eval_df['cache_name'] = eval_df.apply(
        lambda row: f"{row['cache_name']}_{row['collection'].split('_')[-1]}", axis=1
    )
    
    if args.dataset == 'msr':
        collections = ["PS-W", "PS-X", "PS-Y", "PS-Z"]
    else:
        collections = ["PS-A", "PS-B", "PS-C", "PS-D"]

    eval_df = eval_df[eval_df['collection'].isin(collections)]

    full_df = pd.concat((df, eval_df))

    full_df = full_df[full_df['percent'] == args.cache_size_percent]
    full_df = full_df.reset_index(drop=True)

    # Iterate through full_df to create a sorted dictionary of algorithms by (trace_name, cache_size_mb)
    algos = {}
    for _, row in full_df.iterrows():
        trace_name = row['trace_name']
        algo = row['cache_name']
        miss_ratio = row['miss_ratio']

        assert float(row['percent']) == args.cache_size_percent
        if trace_name not in algos:
            algos[trace_name] = {}
        algos[trace_name][algo] = min(miss_ratio, algos[trace_name].get(algo, float('inf')))

    # Sort the algorithms by miss_ratio for each (trace_name, cache_size_mb)
    sorted_algos = {}

    for key in algos:
        sorted_algos[key] = sorted(algos[key].items(), key=lambda x: x[1])  # Sort by miss_ratio    

    print(f"Found {len(sorted_algos)} traces")

    # Get the average miss_ratio for each algorithm across all traces
    miss_ratio_curr_cache_size = {}

    # Choose a baseline algo, that will be used for comparison.
    baseline_perf = {}
    baseline = "FIFO"
    for trace_name, algo_list in sorted_algos.items():
        for algo, miss_ratio in algo_list:
            if algo == baseline:
                baseline_perf[trace_name] = miss_ratio
                break

    for trace_name, algo_list in sorted_algos.items():
        if trace_name not in baseline_perf:
            continue

        baseline_oracle_perf = -float('inf')
        policysmith_oracle_perf = -float('inf')
        
        for algo, miss_ratio in algo_list:
            # Get the stat to store.
            if algo == baseline:
                continue
            else:
                if miss_ratio < baseline_perf[trace_name]:
                    perf_stat = (baseline_perf[trace_name] - miss_ratio) / baseline_perf[trace_name]
                else:
                    perf_stat = (baseline_perf[trace_name] - miss_ratio) / miss_ratio

            if algo not in miss_ratio_curr_cache_size:
                miss_ratio_curr_cache_size[algo] = []
            miss_ratio_curr_cache_size[algo].append(perf_stat)
            
            if "PQEvolve" not in algo:
                baseline_oracle_perf = max(baseline_oracle_perf, perf_stat)
            policysmith_oracle_perf = max(policysmith_oracle_perf, perf_stat)

        # Add performance for Oracles.
        if "PolicySmith-Oracle" not in miss_ratio_curr_cache_size:
            miss_ratio_curr_cache_size["PolicySmith-Oracle"] = []
        miss_ratio_curr_cache_size["PolicySmith-Oracle"].append(policysmith_oracle_perf)

        if "Baselines-Oracle" not in miss_ratio_curr_cache_size:
            miss_ratio_curr_cache_size["Baselines-Oracle"] = []
        miss_ratio_curr_cache_size["Baselines-Oracle"].append(baseline_oracle_perf)

    # Calculate the average miss_ratio for each algorithm
    avg_miss_ratio_curr_cache_size = {k: np.mean(v) for k, v in miss_ratio_curr_cache_size.items()}

    print("\nAverage miss_ratio improvement for big cache size:")
    for algo in miss_ratio_curr_cache_size:
        if algo.startswith("PQEvolve") or "Oracle" in algo or algo in ["GDSF", "LHD", "S3-FIFO"]:
            print(f"{algo}: {avg_miss_ratio_curr_cache_size.get(algo, 0)}")

    # Plot a box for each algorithm, showing the distribution of miss ratios for the big cache.
    plt.figure(figsize=(8.4, 2.8))

    plt.rcParams.update({'font.size': 18})
    # plt.rcParams['text.usetex'] = True

    algos_to_plot = ["PQEvolve", "GDSF", "LHD", "S3-FIFO", "LIRS", "Sieve", "Cacheus", "Oracle"]
    algo_list = []
    for algo in avg_miss_ratio_curr_cache_size.keys():
        if any(x in algo for x in algos_to_plot):
            if algo not in algo_list:
                algo_list.append(algo)
    

    algo_list = sorted(algo_list, key=lambda x: avg_miss_ratio_curr_cache_size[x])
    print(algos_to_plot, algo_list)

    for algo in algo_list:
        plt.boxplot(
            miss_ratio_curr_cache_size[algo],
            positions=[algo_list.index(algo)],
            label=algo,
            widths=0.5,
            patch_artist=True,
            boxprops=dict(facecolor='lightblue', color='black'),
            meanprops=dict(marker='^', markeredgecolor='black', markerfacecolor='red', markersize=8),
            showmeans=True,
            showfliers=False,
            medianprops=dict(visible=False)
        )

    plt.ylim(-0.3, 1.0)
    plt.grid(axis='y', linestyle='--', alpha=0.7)

    # Add a vertical line before the last two algorithms
    plt.axvline(x=len(algo_list) - 2.5, color='gray', linestyle='--', linewidth=1)

    labels = [rename_algo(algo, dataset=args.dataset) for algo in algo_list]
    plt.xticks(range(len(algo_list)), labels, rotation=40, fontsize=18)

    yticks = np.arange(-0.25, 1.25, 0.25)
    plt.yticks(yticks, fontsize=16)
    plt.ylabel("Miss Ratio Improvement\nfrom FIFO", fontsize=18)
    plt.subplots_adjust(left=0.12, right=0.75, top=0.95, bottom=0.2)
    plt.savefig(f"{args.dataset.lower()}-0.1-oracle.png", dpi=200, bbox_inches='tight')

if __name__ == "__main__":
    parser = argparse.ArgumentParser("Boxplot comparison of caching algorithms on (a) traces from a specific dataset, and (b) of a certain size (e.g. 10 percent of trace footprint)")
    parser.add_argument('--dataset', default='msr', choices=['CloudPhysics', 'msr'], type=str)
    parser.add_argument('--cache_size_percent', default=0.1, type=float, help="What fraction of the trace footprint is the cache size?")
    args = parser.parse_args()
    main(args)