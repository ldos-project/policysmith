import argparse
import json
import os
import signal
import subprocess
import textwrap
from typing import List, Tuple

from Evolve import EvolveInterface
from utils import cpp_comment_remover

class WebCacheEvolve(EvolveInterface):
    def __init__(self, web_args = []):
        task_parser = argparse.ArgumentParser()
        task_parser.add_argument("--trace", type=str, default="CloudPhysics/w106.oracleGeneral.bin.zst")
        task_parser.add_argument("--cache_sizes", type=float, nargs=1, default=[128], help="List of cache sizes to test")
        task_parser.add_argument("--eval_cache_size", type=float, default=128, help="Final cache size (objective)")
        task_parser.add_argument('--percent', action='store_true', default=False, help='Using --percent means that cache_sizes and eval_cache_sizes are treated as a percentage (b/w 0 and 100)')
        task_parser.add_argument('--byte', action='store_true', default=True, help='Use byte miss ratio instead of request miss ratio')
        self.task_args = task_parser.parse_args(web_args)

        assert self.task_args.eval_cache_size in self.task_args.cache_sizes, f"Eval cache size {self.task_args.eval_cache_size} must be in cache sizes {self.task_args.cache_sizes}"
        assert len(set(self.task_args.cache_sizes)) == len(self.task_args.cache_sizes)
        assert self.task_args.percent or self.task_args.byte
        
        self.code_dir = os.path.join(os.getcwd(), "webcache")
        self.build_dir = os.path.join(self.code_dir, "build")
        os.makedirs(self.build_dir, exist_ok=True)

        self.llm_code_path = os.path.join(self.code_dir, "./libCacheSim/libCacheSim/cache/eviction/PQEvolve/LLMCode.h")

        self.trace_dir = "../libCacheSim/data/"
        self.trace_path = os.path.join(self.trace_dir, self.task_args.trace)
        assert os.path.exists(os.path.join(self.build_dir, self.trace_path)), f"{os.path.join(self.build_dir, self.trace_path)} not found."
    
    def run_info(self):
        return {
            "task_args": vars(self.task_args)
        }

    def common_prompt(self) -> str:
        return textwrap.dedent('''\
            You are designing a new heuristic for an eviction-based caching system. This system uses a priority queue to store cached objects. The object with the lowest numeric priority is evicted when space is needed. On every access, the caching system:
                - Removes the accessed object from the priority queue.
                - Calls a `priority` function to compute the new priority of the object being accessed.
                - Reinserts the object into the priority queue with the updated priority.                               
            
            The `priority` function signature is:
            ```cpp
            int priority(
                uint64_t current_time, obj_id_t obj_id, pq_cache_obj_info& obj_info, 
                CountsInfo<int32_t>& counts, AgeInfo<int64_t> ages, SizeInfo<int64_t>& sizes,
                History& history
            );
            ```
            This function returns an integer priority. Higher values -> more likely to stay in cache; lower values -> more likely to be evicted. The inputs to this function are:
                - `current_time` (`uint64_t`): the current virtual timestamp.
                - `obj_id` (`obj_id_t`): unique identifier for the object being accessed
                - `obj_info` includes: 
                    * `obj_info.count` (`int32_t`)
                    * `obj_info.last_access_vtime` (`int64_t`)
                    * `obj_info.size` (`int64_t`)
                    * `obj_info.addition_to_cache_vtime` (`int64_t`).
            * `counts`, `ages`, and `sizes`: provide aggregate statistics on objects in cache. They all support `.percentile(p)` for `p \\in [0.0, 1.0]`. For example, `ages.percentile(0.5)` returns the median age of all objects currently in cache (same unit as vtime).
            * `history`: stores recently evicted objects. Use `history.contains(obj_id)` to check if `curr` was recently evicted and readded to cache. Additionally, if `obj_id` is in `history`, `auto info = history.get_metadata(obj_id)` fetches information on the object - specifically `info->count` (count of how many times it was accessed before eviction) and `info->age_at_eviction_time` (how long - in time - was the object present in cache before it's previous eviction).

            You do not have to define function prototypes or include any headers - just write the implementation of `priority()`. You can choose to use all of these features or a subset of them'''
        )
    
    def initial_prompt(self) -> str:
        return self.common_prompt() + textwrap.dedent(f'''\
            REPLY FORMAT: think about the provided inputs, brainstorm possible scoring functions, weigh the possibilities, and then select one of them (ideally, the mosty promising one). Describe the idea you have chosen in plain English, and what you are hoping the heuristic achieves. After this text, write the code for `priority()` in a single code block as shown below. For inspiration here is how you would define the priority functions for some simple heuristics: 
                // return current_time; // LRU
                // return -1 * obj_info.last_access_vtime; // MRU
                // return obj_info.addition_to_cache_vtime; // FIFO
                // return obj_info.count; // approximately LFU (not sure what baseline LFU does if there are multiple objects of same size)
            Code:
            ```cpp
            // priority implementation here
            ```
        ''').strip()
    
    def mutate_prompt(self, versions: List[str]) -> str:
        prompt = self.common_prompt() + textwrap.dedent(f'''\
            Below are earlier versions of the `priority` functions that worked well. Use these as inspiration to write a new version that improves upon these.
            Don't just rename or slightly reorder logic - introduce a meaningful change. Be creative but safe.
            Write the code for `priority()` as a single code block.
        ''')

        for i, code in enumerate(versions):
            cleaned_code = cpp_comment_remover(code).strip()

            prompt += f'''```cpp\n// Version {i}\n{cleaned_code}\n```\n\n'''

        prompt += textwrap.dedent(f'''\
            Now write your new version in a single code block:
            Code:
            ```cpp
            // Version {i+1}
            <<Your new version of eviction_heuristic here>>
            ```
            ''')
        return textwrap.dedent(prompt)

    def debug_prompt(self, stdout: str, stderr: str) -> str:
        # strip stdout and stderr to the first 2000 chars
        return textwrap.dedent(f'''\
            Your code unfortunately errored out. Read the build stderr logs (given below), think about what the error messages might mean, and then provide a complete, corrected version of the code in a formatted code block like you did earlier. Line numbers you see in the stderr logs do not correspond to line numbers in your code block; the build system is complex and it copies your code into the correct place amongst a bunch of other code, so it will be off by an offset.\n'''
        ) + f'''### <stderr>: {stderr.strip()}'''

    def cleanup_build_env(self): 
        os.system(f"rm -rfv {self.build_dir} > /dev/null 2>&1") 
        if os.path.exists(self.llm_code_path):
            os.system(f"rm {self.llm_code_path} > /dev/null 2>&1")
        else:
            print("llmcode.h not exists")
    
    def copy_code(self, code: str):
        # add code to LLM code path
        with open(self.llm_code_path, "w") as f:
            f.write(code)

    def build(self, code: str) -> Tuple[bool, str, str]:
        """
        Returns (success, stdout, stderr)
        """
        self.cleanup_build_env()
        self.copy_code(code)
        
        os.mkdir(self.build_dir)
        assert os.system(f"cd {self.build_dir} && cmake ../ > /dev/null 2>&1") == 0

        proc = subprocess.Popen(
            f"cd {self.build_dir} && make -j",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        

        try:
            stdout, stderr = proc.communicate(timeout=180) # we wait 3 minutes at most for build
        except subprocess.TimeoutExpired:
            assert os.name == "posix"
            os.killpg(proc.pid, signal.SIGKILL)
            stdout, stderr = proc.communicate()
            return False, stdout.strip(), stderr.strip()
        
        success = (proc.returncode == 0)
        return success, stdout.strip(), stderr.strip()
    
    def run_experiment(self):
        proc = subprocess.Popen(
            f"cd {self.build_dir} && ./run_multiple_sizes.o {self.trace_path} {'percent' if self.task_args.percent else 'mb'} {' '.join(map(str, self.task_args.cache_sizes))}",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        try:
            stdout, stderr = proc.communicate()
        except subprocess.TimeoutExpired:
            assert os.name == "posix"
            os.killpg(proc.pid, signal.SIGKILL)
            stdout, stderr = proc.communicate()
            eval_logs_tmp = {
                "returncode": proc.returncode,
                "stdout": stdout,
                "stderr": stderr
            }
            return False, {}, eval_logs_tmp

        success = (proc.returncode == 0)

        eval_logs = {
            "returncode": proc.returncode,
            "stdout": stdout,
            "stderr": stderr
        }
        
        if success:
            stdout = stdout.splitlines()
            results_list = list(
                map(
                    lambda x: json.loads(x),
                    list(filter(lambda x: x.startswith("{"), stdout))
                )
            )

            if self.task_args.percent:
                assert len(results_list) == len(self.task_args.cache_sizes), f"How?"
                relevant_index = sorted(self.task_args.cache_sizes).index(self.task_args.eval_cache_size)
                relevant_result = sorted(results_list, key=lambda x: x['cache_size_mb'])[relevant_index]
            else:
                relevant_result = list(filter(lambda x: x['cache_size_mb'] == self.task_args.eval_cache_size, results_list))
                assert len(relevant_result) == 1
                relevant_result = relevant_result[0]

            # Determine the relevant column based on the task argument
            relevant_column = "byte_miss_ratio" if self.task_args.byte else "miss_ratio"
            
            # final score is average hit rate
            final_result_dict = {
                "score": 1 - relevant_result[relevant_column],
                "results": results_list
            }
            return success, final_result_dict, eval_logs
        else:
            return success, {}, eval_logs
