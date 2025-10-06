import argparse
from llm_wrappers import ALL_LLM_MODELS
from EvolveRunner import EvolutionRunner

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", type=str, default="webcache", help="What task are you running PolicySmith on?")
    parser.add_argument("--model", type=str, default="gemini-2.0", help="Model name to use. Options: " + ", ".join(ALL_LLM_MODELS.keys()))
    parser.add_argument("--n_samples", type=int, default=25, help="How many samples per iteration of evolution?")
    parser.add_argument("--start_iter_idx", type=int, default=0, help="Start iteration index")
    parser.add_argument("--end_iter_idx", type=int, default=1, help="End iteration index")
    parser.add_argument("--collection_id", type=str, default=None, help="if start_iter_idx > 0, this is the MongoDB collection ID to continue from")
    args, unknown_args = parser.parse_known_args()    
    assert args.model in ALL_LLM_MODELS.keys()

    evolver = EvolutionRunner(args.task, args.model, args.n_samples, args.start_iter_idx, args.end_iter_idx, args.collection_id, unknown_args)
    evolver.evolve()