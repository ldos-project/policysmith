import argparse
import os
import shutil
import subprocess
import pymongo
from concurrent.futures import ThreadPoolExecutor, as_completed
from bson import ObjectId

import code

# Default MongoDB URI
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
if MONGO_URI.endswith("/"):
    MONGO_URI = MONGO_URI[:-1]

def check_done(collection, oid, trace_name, percent, db_name="policysmith"):
    client = pymongo.MongoClient(MONGO_URI)
    return client[db_name]["evaluation"].count_documents({
        "collection": collection, "mongo_id": oid, "trace_name": trace_name, "percent": float(percent)
    }) > 0

def run_eval(cmd, cwd):
    subprocess.run(cmd, env=os.environ.copy(), cwd=cwd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


BUILD_DIR = os.path.join(os.path.dirname(__file__), "build")
CODE_PATH = os.path.join(os.path.dirname(__file__), "libCacheSim/libCacheSim/cache/eviction/PQEvolve/LLMCode.h")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("collection", type=str, help="Collection name"); 
    parser.add_argument("object_id", type=str, help="Object ID"); 
    parser.add_argument("--dataset", type=str, default="CloudPhysics", help="Name of trace dataset")
    parser.add_argument("--percent", type=float, default = 0.1, help="Fraction of trace footprint to use as cache size")
    parser.add_argument("--db", type=str, default="policysmith", help="Database name")
    parser.add_argument("--max-parallel-workers", type=int, default=64)
    args = parser.parse_args()

    # cleanup old code
    if os.path.exists(BUILD_DIR):
        shutil.rmtree(BUILD_DIR)
    if os.path.exists(CODE_PATH): 
        os.remove(CODE_PATH)
    os.makedirs(BUILD_DIR)
    
    # inject new code
    client = pymongo.MongoClient(MONGO_URI)
    final_code = client[args.db][args.collection].find_one({"_id": ObjectId(args.object_id)})['final_code']
    with open(CODE_PATH, "w") as f: 
        f.write(final_code)

    # build
    subprocess.run("(cmake .. && make -j) > /dev/null 2>&1", cwd=BUILD_DIR, shell=True, check=True)
    print("Done building")

    # find & run traces
    data_dir = os.path.join("libCacheSim", "data", args.dataset)
    cmds = []
    num_complete = client[args.db]["evaluation"].count_documents({
        "collection": args.collection, "mongo_id": args.object_id, "percent": float(args.percent)
    })
    print(f"Found {num_complete} complete evaluations")
    
    for file in os.listdir(data_dir):
        full_path = os.path.join("../", data_dir, file)
        if not check_done(args.collection, args.object_id, f"{args.dataset}/{file}", args.percent, args.db):
            print(f"Processing: {file}")
            # Construct command mimicking shell script pipe to mongoimport
            cmd = f"./eval_final_heuristic.o {full_path} percent {args.percent} {args.collection} {args.object_id} 2>/dev/null | mongoimport --uri {MONGO_URI} --db {args.db} --collection evaluation"
            cmds.append(cmd)

    print(f"Running {len(cmds)} evaluations with {args.max_parallel_workers} workers...")
    code.interact(local=locals())
    with ThreadPoolExecutor(max_workers=args.max_parallel_workers) as executor:
        futures = [executor.submit(run_eval, cmd, "build") for cmd in cmds]
        for i, f in enumerate(as_completed(futures)):
            print(f"[{i+1}/{len(cmds)}] Finished")

if __name__ == "__main__":
    main()