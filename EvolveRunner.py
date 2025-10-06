from pymongo import MongoClient
import time

from utils import get_git_info

START_TIME = time.time()

# local imports
from api_key import MONGO_CONNECTION_STRING
from tcp_cc.kern_mod.interface import TCPEvolve
from tcp_cc.bpf_scaffolding.interface import CongestionControlBPF
from webcache.interface import WebCacheEvolve
from llm_wrappers import get_wrapper, ALL_LLM_MODELS

class EvolutionRunner:
    EVOLVE_REGISTRY = {
        "tcp": TCPEvolve,
        "tcpbpf": CongestionControlBPF,
        "webcache": WebCacheEvolve,
    }
    
    def __init__(
        self, task_name: str, llm_name: str,
        n_samples: int, start_iter_idx, end_iter_idx: int,
        collection_id, task_args, n_build_retries = 3
    ):
        self.task_name = task_name
        self.llm_name = llm_name
        self.n_samples = n_samples
        self.start_iter_idx = start_iter_idx
        self.end_iter_idx = end_iter_idx
        self.collection_id = collection_id
        self.n_build_retries = n_build_retries

        self.client = MongoClient(MONGO_CONNECTION_STRING)
        self.db = self.client["policysmith"]

        assert self.task_name in self.EVOLVE_REGISTRY.keys()
        assert self.llm_name in ALL_LLM_MODELS.keys()
        assert self.end_iter_idx > self.start_iter_idx
        
        existing_collections = self.db.list_collection_names()

        if self.collection_id is not None:
            print(f"Using EXISTING collection name = {self.collection_id}")
        else:
            assert self.start_iter_idx == 0, "If self.collection_id = None, we start a fresh run, so start_iter_idx must be 0"
            i = 0
            while f"{self.task_name}_{i}" in existing_collections:
                i += 1
            self.collection_id = f"{self.task_name}_{i}"
            # create this collection
            self.db.create_collection(self.collection_id)
            print(f"Using NEW collection name = {self.collection_id}")
        
        self.interface = self.EVOLVE_REGISTRY[self.task_name](task_args)
        info = self.interface.run_info()
        info["collection_id"] = self.collection_id
        info["policysmith_githash"] = get_git_info()
        self.db["information"].insert_one(info)

    
    def get_priority_programs(self, iter_num, num_snippets=2):
        collection = self.db[self.collection_id]

        self.all_valid_programs = list(collection.find({
            "iter": {"$lte": iter_num}, 
            "build_status": True, 
            "exec_status": True
        }))

        if len(self.all_valid_programs) < 2:
            raise ValueError(f"Expected at least 2 successful programs in iteration {iter_num}, found {len(self.all_valid_programs)}")
           
        self.all_valid_programs = sorted(
            self.all_valid_programs,
            key=lambda doc: doc["eval_results"]["score"],
            reverse=True
        )

        self.priority_program_ids = [doc["_id"] for doc in self.all_valid_programs[:num_snippets]]
        self.priority_programs = [doc["final_code"] for doc in self.all_valid_programs[:num_snippets]]
        print(f"Best score seen in iter={iter_num} is {self.all_valid_programs[0]['eval_results']['score']}")

    def evolve(self):
        for _iter in range(self.start_iter_idx, self.end_iter_idx):
            if _iter > 0:
                self.get_priority_programs(_iter - 1)
            for _sample in range(self.n_samples):
                record = self.db[self.collection_id].find_one({
                    "iter": _iter,
                    "_sample": _sample
                })
                if record:
                    print(f"Skipping iter={_iter}, sample={_sample} since we found it in MongoDB.")
                    continue
                
                print(f"[{round(time.time()-START_TIME, 2)}] Generating iter={_iter}; sample={_sample}")
                llm_chat = get_wrapper(self.llm_name) # start a new chat for every heuristic

                heuristic_mongo_document = {
                    "iter": _iter,
                    "_sample": _sample,
                    "final_code": None,
                    "build_status": None,
                    "exec_status": None,
                    "eval_results": None,
                    "eval_logs": None,
                    "revisions": []
                }

                # send the initial prompt requesting a new heuristic
                if _iter == 0:
                    prompt = self.interface.initial_prompt()
                else:
                    heuristic_mongo_document["priority_program_ids"] = self.priority_program_ids
                    heuristic_mongo_document["priority_programs"] = self.priority_programs
                    prompt = self.interface.mutate_prompt(self.priority_programs)
                
                llm_response = llm_chat.send_message(prompt)
                # attempt to build; retry on failure
                
                for _attempt_count in range(self.n_build_retries):
                    if len(llm_response['code_segs'][0]) > 0:
                        success, stdout, stderr = self.interface.build(llm_response['code_segs'][0])
                        print(f"\t[{round(time.time() - START_TIME, 2)}] Build {_attempt_count+1} status: {success}")
                        heuristic_mongo_document["revisions"].append(
                            {
                                "build_status": success,
                                "stdout": stdout,
                                "stderr": stderr,
                                **llm_response
                            }
                        )

                        heuristic_mongo_document["final_code"] = llm_response['code_segs'][0]
                        heuristic_mongo_document["build_status"] = success

                        if success or _attempt_count == self.n_build_retries - 1:
                            break
                        debug_prompt = self.interface.debug_prompt(stdout, stderr)
                    else:
                        heuristic_mongo_document["revisions"].append(
                            {
                                "build_status": False,
                                "stdout": "Could not find a code block inside your response.",
                            }
                        )
                        debug_prompt = "Could not find a code block inside your previous message. Please format correctly."
                    
                    llm_response = llm_chat.send_message(debug_prompt)
                
                assert heuristic_mongo_document["build_status"] == success, "Just a sanity check" 
                
                if success:
                    eval_status, eval_results, eval_logs = self.interface.run_experiment()
                    print(f"\t[{round(time.time() - START_TIME, 2)}] Build {_attempt_count+1} eval: {success}")
                    heuristic_mongo_document["exec_status"] = eval_status
                    heuristic_mongo_document["eval_results"] = eval_results
                    heuristic_mongo_document["eval_logs"] = eval_logs
                # write the doc to mongo 
                collection = self.db[self.collection_id]
                collection.insert_one(heuristic_mongo_document)
