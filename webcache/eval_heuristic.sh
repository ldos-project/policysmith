if [[ $# -ne 4 ]]; then
    echo "Usage: $0 <collection> <objectId> <dataset> <percent>" >&2
    exit 1
fi

if [[ -z "$MONGO_URI" ]]; then
    echo "MONGO_URI env var not set" >&2
    exit 1
fi

pkill eval_final_heuristic.o

COL="$1";
OID="$2";
DATASET="$3"
PERCENT="$4"
DIR=../libCacheSim/data/$DATASET/

rm -rfv build/ && mkdir build # remove old build files
rm libCacheSim/libCacheSim/cache/eviction/PQEvolve/LLMCode.h # remove old code if any
mongosh "$MONGO_URI/policysmith" --eval "console.log(db.getCollection('$COL').findOne({_id: new ObjectId('$OID')}).final_code)" > libCacheSim/libCacheSim/cache/eviction/PQEvolve/LLMCode.h

i=0
pushd build
    cmake ../ && make -j
    for file in `find $DIR -type f -size -500M`;
    do
        ./eval_final_heuristic.o $file percent $PERCENT $COL $OID 2>/dev/null | mongoimport --db policysmith --collection evaluation
        i=$((i+1))
        echo "[#$i] Done with $file"
    done
popd