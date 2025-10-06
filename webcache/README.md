If you just want to browse the results from the HotNets paper, please go to `../hotnets_results/`. Use this directory only if you want to run heuristic search yourself. 

## Setting up libcachesim
1. Clone all dependencies and install pre-requisites:
    ```bash
    pushd libCacheSim/scripts
      bash install_dependency.sh
    popd
    ```

2. Populate `libCacheSim/libCacheSim/cache/eviction/PQEvolve/LLMCode.h` with the code below. This file contains the code snippet that is created by the LLM -- for now, we just write a priority function that implements LRU. You can play around with this manually to see what sort of policies you can come up with. (e.g. LFU, MRU, etc). We are populating this file manually for now to prevent build errors. 
    ```cpp
    int priority(
      uint64_t current_time, obj_id_t obj_id, pq_cache_obj_info& obj_info, 
      CountsInfo<int32_t>& counts, AgeInfo<int64_t> ages, SizeInfo<int64_t>& sizes,
      History& history
    ){
      return obj_info.last_access_vtime; // LRU
    }
    ```

3. Build `libcachesim`.
    ```bash
    pushd libCacheSim/scripts
        bash install_libcachesim.sh 
    popd
    ```

4. Download the `CloudPhysics` dataset. Other datasets can be downloaded through similar `wget` commands using the URLs in `data/README.md`.
    ```bash
    pushd libCacheSim/data/
      mkdir CloudPhysics && cd CloudPhysics
      wget -r -np -nH --cut-dirs=5 -R "index.html*" https://ftp.pdl.cmu.edu/pub/datasets/twemcacheWorkload/fast23_glcache/cloudphysics/
    popd
    ```

5. Build the code files in `webcache` (e.g., `run_multiple_algos.cpp`) by running the following commands:
    ```bash
    mkdir build && cd build
    cmake ../
    make
    ```

6. Run `./run_multiple_algos.o` to see the performance of various (baseline) caching algorithms: 
    ```bash
    pushd build/
      ./run_multiple_algos.o ../libCacheSim/data/CloudPhysics/w106.oracleGeneral.bin.zst percent 0.1
    popd
    ```

## Test evolution
1. Run policy search using `test_evolve.py` (in the root directory of this repo). Use the `--trace` to specify for which trace the policy should be tailored towards (i.e. the context). 
        ```bash
        python3 test_evolve.py --task webcache --model gpt-4o-mini --n_samples 5 --start_iter_idx 0 --end_iter_idx 5
        ```
2. Use `../notebooks/plot_progress.ipynb` to plot the progress of the run. 
3. Use `eval_heuristic.sh` to evaluate the discovered (final) heuristic on all traces in the dataset.
4. Use `../hotnets_results/boxplot.py` to create boxplots similar to the paper for your policies.

## Getting baseline algorithm miss rates
```bash
for trace_dir in CloudPhysics msr fiu metaCDN; do 
    for file in `find ../libCacheSim/data/$trace_dir -type f `; do
        for cache_size in 0.1 0.001; do
            ./run_multiple_algos.o $file percent $cache_size | mongoimport --uri "mongodb://localhost:27017" --db policysmith --collection baselines_percent --type json
        done
    done
done
```