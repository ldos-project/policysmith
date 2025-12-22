import os
import re
import subprocess
import argparse
from datetime import datetime
import uuid
from openai import OpenAI

# Configuration
FULLCODE_EVOLVE_DIR = "libcachesim/libCacheSim/cache/eviction/FullCodeEvolve"
BUILD_DIR = os.path.abspath("build")
RUNS_DIR = os.path.abspath("runs")
LRU_CPP_PATH = os.path.join(FULLCODE_EVOLVE_DIR, "LRU.cpp")

# The generated logic file (included by the interface)
TARGET_LOGIC_FILE = "LLMCode.hpp"
TARGET_LOGIC_PATH = os.path.join(FULLCODE_EVOLVE_DIR, TARGET_LOGIC_FILE)

def get_lru_cpp_template():
    """Reads LRU.cpp template."""
    with open(LRU_CPP_PATH, "r") as f:
        return f.read()

def generate_heuristic_logic(args, api_key, lru_cpp):
    """Generates the C++ CacheManager class using OpenAI API."""
    client = OpenAI(api_key=api_key)
    
    prompt = f"""
You are an expert systems programmer specializing in cache replacement policies.
I need you to write a C++ class `CacheManager` that implements a NOVEL cache eviction heuristic to be used within a cache engine.

Here is the reference `CacheManager` implementation (LRU.cpp):
```cpp
{lru_cpp}
```

Requirements:
0. First, think about possible novel ideas/algorithms for cache eviction. Select ONE to implement and state it explicitly (1 - 3 sentences).
1. Then output the C++ code for the CacheManager class inside a single ```...``` fenced block.
2. The constructor MUST be declared exactly as `CacheManager()` with no parameters and no default arguments. Do NOT add capacity parameters, default values, or overloaded constructors. Assume capacity is managed externally by the engine. Your manager class must define the same public methods as the reference: `find`, `insert`, `evict`.
3. The cache engine will call find() to check for objects, insert() to record that an object is now in cache, and evict() only when it needs a victim. The cache engine calls `evict()` only when it needs a victim; when `evict()` returns an `obj_id_t`, the engine will delete that object from the cache. After this point, the policy must treat the object as not present in cache: a subsequent `find()` for that object must return `false` unless it is later re-inserted. `find()` and `insert()` must never evict objects themselves or call the `evict()` function.
4. The `find` method should return `true` on hit, `false` on miss.
5. The `evict` method should return the `obj_id_t` of the victim.
6. You can use standard C++ headers if needed (e.g., `<bits/stdc++.h>` or individual headers like `<list>`, `<unordered_map>`).
7. Be creative - implement a novel heuristic.
8. Do NOT include `main()` or any wrapper functions. Just the class. `obj_id_t` has already been defined - do not attempt to redefine it.
"""

    response = client.chat.completions.create(
        model=args.model,
        messages=[
            {"role": "system", "content": "You are a C++ programming expert."},
            {"role": "user", "content": prompt}
        ],
        temperature=1.0, top_p=0.95
    )
    
    print(f"Finish reason: {response.choices[0].finish_reason}")
    content = response.choices[0].message.content
    
    # Extract code block
    match = re.search(r"```cpp(.*?)```", content, re.DOTALL)
    if match:
        return match.group(1).strip()
    match = re.search(r"```c(.*?)```", content, re.DOTALL)
    if match:
        return match.group(1).strip()
    match = re.search(r"```(.*?)```", content, re.DOTALL)
    if match:
        return match.group(1).strip()
        
    return content

def save_run(args, code, status_log):
    """Saves the run to runs/<model>/<timestamp>.hpp and appends status."""
    model_dir = os.path.join(RUNS_DIR, args.model)
    if not os.path.exists(model_dir):
        os.makedirs(model_dir)
        
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_id = str(uuid.uuid4())[:8]
    filename = f"heuristic_{timestamp}_{run_id}.hpp"
    filepath = os.path.join(model_dir, filename)
    
    with open(filepath, "w") as f:
        f.write(code)
        f.write("\n\n/*\n")
        f.write("=== RUN STATUS LOG ===\n")
        f.write(status_log)
        f.write("*/\n")
        
    print(f"Run saved to {filepath}")
    return filepath

def compile_project():
    """Runs cmake and make in the build directory."""
    if not os.path.exists(BUILD_DIR):
        os.makedirs(BUILD_DIR)
        
    try:
        subprocess.check_output(["cmake", ".."], cwd=BUILD_DIR, stderr=subprocess.STDOUT)
        subprocess.check_output(["make", "-j"], cwd=BUILD_DIR, stderr=subprocess.STDOUT)
        return True, "Compilation Success"
    except subprocess.CalledProcessError as e:
        return False, f"Compilation Failed:\n{e.output.decode('utf-8')}"

def run_benchmark(trace_path):
    try:
        output = subprocess.check_output([os.path.join(BUILD_DIR, "run_algos.o"), trace_path, "percent", "0.1"], stderr=subprocess.STDOUT)
        return True, f"Execution Success:\n{output.decode('utf-8')}"
    except subprocess.CalledProcessError as e:
        return False, f"Execution Failed:\n{e.output.decode('utf-8')}"

def main():
    parser = argparse.ArgumentParser(description="Try generating a heuristic entirely using an LLM.")
    parser.add_argument("--trace_path", default="libcachesim/data/cloudPhysicsIO.csv", type=str, help="Path to the trace file")
    parser.add_argument("--model", default="gpt-4o-mini", type=str, help="LLM model to use")
    args = parser.parse_args()
    
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Error: OPENAI_API_KEY environment variable not set.")
        return

    log = []
    
    print("Reading context...")
    lru_cpp = get_lru_cpp_template()
    
    print(f"Generating heuristic logic with {args.model}...")
    try:
        code = generate_heuristic_logic(args, api_key, lru_cpp)
        log.append("Generation: Success")
    except Exception as e:
        print(f"Generation failed: {e}")
        return

    # Write logic file
    print(f"Writing logic to {TARGET_LOGIC_PATH}...")
    with open(TARGET_LOGIC_PATH, "w") as f:
        f.write(code)
    
    print("Compiling...")
    success, msg = compile_project()
    log.append(msg)
    
    if success:
        print("Running benchmark...")
        run_success, run_msg = run_benchmark(args.trace_path)
        log.append(run_msg)
        if run_success:
            print("Benchmark finished successfully.")
            print(run_msg)
        else:
            print("Benchmark failed during execution.")
    else:
        print("Compilation failed.")
        
    print("Saving run archive...")
    save_run(args, code, "\n".join(log))

    # delete the generated logic file
    os.remove(TARGET_LOGIC_PATH)

if __name__ == "__main__":
    main()