import argparse
import matplotlib.pyplot as plt
import json
import numpy as np
import os
import pandas as pd
import pymongo
import sys

MONGO_CONNECTION_STRING = "mongodb://localhost:27017/"

def rename_algo(algo, dataset=None):
    if algo == "Baselines-Oracle":
        return "B-Oracle"
    elif algo.startswith("S3FIFO"):
        return "S3-FIFO"
    elif "FIFO" in algo and "reinsertion" in algo.lower():
        return "FIFO-Re"
    elif "QDLP-0.1000-0.9000-Clock2-1" in algo:
        return "QDLP"
    else:
        return algo

def main(args):
    client = pymongo.MongoClient(MONGO_CONNECTION_STRING)

    db = client["policysmith"]

    # collect baselines
    df = pd.DataFrame(list(db["baselines_percent"].find({})))
    df = df[df['trace_name'].str.contains(f"{args.dataset}/")].copy()

    assert not (args.cluster and args.plot_traces), "Cannot use both --cluster and --plot-traces together."
    if args.plot_traces:
        df = df[df['trace_name'].isin(args.plot_traces)].copy()
    
    if args.cluster is not None:
        from clusters import CLUSTERS
        assert args.cluster in CLUSTERS.keys(), f"Cluster {args.cluster} not found."
        traces_in_cluster = list(
            map(lambda x: f"{args.dataset}/{x}.oracleGeneral.bin.zst", CLUSTERS[args.cluster])
        )
        df = df[df['trace_name'].isin(traces_in_cluster)].copy()
        

    if not args.belady:
        df = df[(df['cache_name'] != 'Belady') & (df['cache_name'] != 'BeladySize')]
    
    print(set(df['cache_name']), file=sys.stderr)
    df = df[df['percent'] == args.cache_size_percent]
    df = df.reset_index(drop=True)

    df = df[['trace_name', 'cache_name', 'miss_ratio', 'percent']]

    if args.eval_names:
        # collect new heuristics
        eval_df = pd.DataFrame(list(db["evaluation"].find({'mongo_id': {'$in': args.eval_names}, 'percent': args.cache_size_percent})))
        eval_df = eval_df[eval_df['trace_name'].str.contains(f"{args.dataset}/")].copy()

        mongo_ids_found = set(eval_df['mongo_id'])
        for name in args.eval_names:
            if name not in mongo_ids_found:
                print(f"Warning: No eval data found for source hash {name}", file=sys.stderr)

        # get the eval trace list by source hash and find the intersection of all three
        trace_sets = [set(g['trace_name']) for _, g in eval_df.groupby('mongo_id')]
        eval_trace_list = sorted(set.intersection(*trace_sets))
        print(f"Found {len(eval_trace_list)} traces common across eval names", file=sys.stderr)
        print(f"Missing traces: {set(df['trace_name']) - set(eval_trace_list)}", file=sys.stderr)

        eval_df = eval_df[['trace_name', 'mongo_id', 'miss_ratio', 'percent']]
        eval_df.rename(columns={'mongo_id': 'cache_name'}, inplace=True)

        eval_df['cache_name'] = eval_df['cache_name'].apply(lambda x: f"Vulcan-{x[:6]}")

        if args.cluster:
            eval_df = eval_df[eval_df['trace_name'].isin(traces_in_cluster)].copy()
        
        if args.plot_traces:
            eval_df = eval_df[eval_df['trace_name'].isin(args.plot_traces)].copy()
        
        assert len(eval_df['trace_name'].unique()) == len(df['trace_name'].unique()), f"Mismatch in traces between baseline and eval data: {len(df['trace_name'].unique())} vs {len(eval_df['trace_name'].unique())}. Difference: {set(df['trace_name']) - set(eval_df['trace_name'])}"

        # create final df by filtering baseline df to only include traces for which we have eval
        df = pd.concat([df, eval_df], ignore_index=True)
        df = df[df['trace_name'].isin(eval_trace_list)].copy()

    # Iterate through df to create a sorted dictionary of algorithms by (trace_name, cache_size_mb)
    algos = {}
    for _, row in df.iterrows():
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

    print(f"Plotting {len(sorted_algos)} traces.", file=sys.stderr)

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
        
        for algo, miss_ratio in algo_list:
            # Get the stat to store.
            if algo == baseline and args.improvement:
                continue
            else:
                if args.improvement:
                    if miss_ratio < baseline_perf[trace_name]:
                        perf_stat = (baseline_perf[trace_name] - miss_ratio) / baseline_perf[trace_name]
                    else:
                        perf_stat = (baseline_perf[trace_name] - miss_ratio) / miss_ratio
                else:
                    perf_stat = 1 - miss_ratio

            if algo not in miss_ratio_curr_cache_size:
                miss_ratio_curr_cache_size[algo] = []
            miss_ratio_curr_cache_size[algo].append(perf_stat)
            if algo not in ['Belady', 'BeladySize']:
                baseline_oracle_perf = max(baseline_oracle_perf, perf_stat)

        # Add performance for oracle
        if "Baselines-Oracle" not in miss_ratio_curr_cache_size:
            miss_ratio_curr_cache_size["Baselines-Oracle"] = []
        miss_ratio_curr_cache_size["Baselines-Oracle"].append(baseline_oracle_perf)

    # Calculate the average miss_ratio for each algorithm
    avg_miss_ratio_curr_cache_size = {k: np.mean(v) for k, v in miss_ratio_curr_cache_size.items()}

    # Plot a box for each algorithm, showing the distribution of miss ratios for the big cache.
    plt.figure(figsize=(0.6 * len(avg_miss_ratio_curr_cache_size.keys()), 4.0))
    
    plt.title(f"Performance of eviction algos on {len(set(df['trace_name']))} {args.dataset.upper()} traces ({args.cache_size_percent * 100}% cache size)")

    plt.rcParams.update({'font.size': 18})
    # plt.rcParams['text.usetex'] = True
    algo_list = []
    for algo in avg_miss_ratio_curr_cache_size.keys():
        algo_list.append(algo)
    
    algo_list = sorted(algo_list, key=lambda x: avg_miss_ratio_curr_cache_size[x])

    if args.improvement:
        print("Miss ratio improvements over FIFO:", file=sys.stderr)
    else:
        print("Raw hit rates:", file=sys.stderr)

    json_out = {}
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
        print(f'"{rename_algo(algo)}": {np.mean(miss_ratio_curr_cache_size[algo]):.4f},', file=sys.stderr)
        json_out[rename_algo(algo)] = float(np.mean(miss_ratio_curr_cache_size[algo]))
    if args.json:
        print(json.dumps(json_out, indent=2))
    
    # plt.ylim(-0.3, 1.0)az
    plt.grid(axis='y', linestyle='--', alpha=0.7)

    # Add a vertical line before the last two algorithms
    plt.axvline(x=len(algo_list) - 1.5, color='gray', linestyle='--', linewidth=1)

    labels = [rename_algo(algo, dataset=args.dataset) for algo in algo_list]
    plt.xticks(range(len(algo_list)), labels, rotation=90, fontsize=18)
    
    if args.improvement:
        plt.ylabel("Miss Ratio\n(improvement over FIFO)", fontsize=15)
    else:
        plt.ylabel("Raw Hit Rate", fontsize=15)
    
    os.makedirs("./images", exist_ok=True)
    save_loc = f"images/boxplot-{args.dataset.lower()}-{args.cache_size_percent}.png"
    if args.plot_traces:
        traces_text = ", ".join(args.plot_traces)
        plt.figtext(
            0.5, -0.15, traces_text,
            wrap=True, ha="center", fontsize=8, va="top"
        )
        plt.subplots_adjust(bottom=0.35)
    plt.savefig(save_loc, dpi=200, bbox_inches='tight')
    print(f"Saved to ./{save_loc}", file=sys.stderr)

if __name__ == "__main__":
    parser = argparse.ArgumentParser("Boxplot comparison of caching algorithms on (a) traces from a specific dataset, and (b) of a certain size (e.g. 10 percent of trace footprint)")
    parser.add_argument('dataset', default='msr', choices=['CloudPhysics', 'msr'], type=str)
    parser.add_argument('--cache_size_percent', default=0.1, type=float, help="What fraction of the trace footprint is the cache size?")
    parser.add_argument('--include-belady', action='store_true', dest='belady')
    parser.add_argument('--plot-traces', nargs='+', default=None, help='List of trace names to include in the plot (space-separated).')
    parser.add_argument('--eval-names', nargs='+', default=None, help='List of new heuristics to include in the plot. Must be in the format <object-id> (space-separated).')
    parser.add_argument('--raw', action='store_false', dest='improvement', help='Plot raw miss ratios instead of improvement over FIFO.')
    parser.add_argument('--cluster', type=str, help='Which cluster to use.')
    parser.add_argument('--json', action='store_true', default=False, help='Output in JSON.')
    parser.set_defaults(improvement=True)
    args = parser.parse_args()
    main(args)