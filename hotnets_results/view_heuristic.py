import argparse
import pymongo
from bson import ObjectId

heuristic_mapping = {
    "PS-A": '686aea309ba953162c4e686c',
    "PS-B": '686a908665614c43f2c8d803',
    "PS-C": '686ad41f3626d4810100b30d',
    "PS-D": '686acdc61802f736dc7a621b',
    "PS-W": '686c4a07fdb12bcc1004ef72',
    "PS-X": '686c944704056f7197217e48',
    "PS-Y": '686c729adec761f1d589b987',
    "PS-Z": '686c7f9a29dfd2a5dee68ae2',
}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process heuristic names.")
    parser.add_argument('heuristic_name', type=str, help='Name of the heuristic', choices=list(heuristic_mapping.keys()))
    args = parser.parse_args()
    args.heuristic_id = heuristic_mapping[args.heuristic_name]


    client = pymongo.MongoClient("mongodb://localhost:27017/")
    db = client["policysmith"]
    result = db[args.heuristic_name].find_one({ "_id": ObjectId(args.heuristic_id) })

    print(result['final_code'])