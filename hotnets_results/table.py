import pymongo
from bson import ObjectId
from collections import defaultdict

from view_heuristic import heuristic_mapping

def get_perf(collection_name, cache_size_percent=0.1, num_places=3):
    eval_items = list(db.evaluation.find({
        "collection": collection_name,
        "percent": cache_size_percent
    }))
    baselines = list(db.baselines_percent.find({
        "percent": cache_size_percent,
        "cache_name": {"$ne": "Belady"}
    }))
    current_dataset = list(set(map(lambda x: x.split('/')[0], {e['trace_name'] for e in eval_items})))
    assert len(current_dataset) == 1 and current_dataset[0] in ['msr', 'CloudPhysics']
    current_dataset = current_dataset[0]

    total_num_traces = len({b["trace_name"] for b in baselines if b['trace_name'].startswith(current_dataset)})
    print(f"Total trace count (from baselines): {total_num_traces}")

    assert len({e["trace_name"] for e in eval_items if e['trace_name'].startswith(current_dataset)}) <= total_num_traces

    trace_names = [e["trace_name"] for e in eval_items]
    assert len(trace_names) == len(set(trace_names)), "Duplicate trace_name entries in evaluation"

    rank_counts = defaultdict(int)

    for e in eval_items:
        tn = e["trace_name"]
        entries = [b for b in baselines if b["trace_name"] == tn]
        entries.append({
            "cache_name": e["cache_name"],
            "miss_ratio": e["miss_ratio"]
        })

        entries.sort(key=lambda x: x["miss_ratio"])
        
        for rank, item in enumerate(entries):
            if item["cache_name"] == e["cache_name"]:
                rank_counts[rank + 1] += 1
                break

    print(f"{collection_name} was #n^th place in: [total_traces={total_num_traces}]")
    for place in sorted(rank_counts.keys()):
        if place > num_places: 
            break
        print(f"\t#{place}: {rank_counts[place]} traces ({round(rank_counts[place]/total_num_traces*100, 1)})")


client = pymongo.MongoClient("mongodb://localhost:27017/")
db = client["policysmith"]

for collection in heuristic_mapping.keys():
    get_perf(collection)