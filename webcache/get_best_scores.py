import argparse
import numpy as np
import pandas as pd
import pymongo

from functools import reduce

MONGO_CONNECTION_STRING = "mongodb://localhost:27017/"

def get_mrr(curr_miss_ratio, fifo_miss_rate):
    if curr_miss_ratio < fifo_miss_rate:
        return (fifo_miss_rate - curr_miss_ratio) / fifo_miss_rate
    else:
        return (fifo_miss_rate - curr_miss_ratio) / curr_miss_ratio

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('run_id', type=str, help='Run ID to fetch results for')
    args = parser.parse_args()

    print("Using raw hit ratios as reward")

    client = pymongo.MongoClient(MONGO_CONNECTION_STRING)
    db = client["policysmith"]
    df = pd.DataFrame(list(db[args.run_id].find()))
    df['combined_score'] = df['eval_results'].apply(lambda x: x['score'] if x is not None else -1)
    df = df.sort_values(by='combined_score', ascending=False)

    print("Top three source_hash:")
    for _, row in df.head(3).iterrows():
        print(f"\tID: {row['_id']} (score: {round(row['combined_score'], 5):.4f})")

if __name__ == "__main__":
    main()