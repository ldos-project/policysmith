#include "util.h"

double cache_percentage = -1.0;
common_cache_params_t cc_params = default_common_cache_params();
std::string dump_name = "";

void run_multiple_caches(reader_t *reader) {
  reset_reader(reader);

  auto start = std::chrono::high_resolution_clock::now();  
  const int NUM_CACHE_ALGORITHMS = 1;
  cache_t *caches[NUM_CACHE_ALGORITHMS] = {
      PQEvolve_init(cc_params, nullptr)
  };
  assert(NUM_CACHE_ALGORITHMS == sizeof(caches) / sizeof(caches[0]));
  cache_stat_t *result;
  if(dump_name.size() > 0) {
    assert(false && "Not supported in policysmith repo - look at general cache search");
    result = simulate_with_multi_caches(
      reader, caches, NUM_CACHE_ALGORITHMS, nullptr, 0.0, 0,
      static_cast<int>(std::thread::hardware_concurrency()), 0, false // , dump_name.data()
    );
  }
  else {
    result = simulate_with_multi_caches(
      reader, caches, NUM_CACHE_ALGORITHMS, nullptr, 0.0, 0,
      static_cast<int>(std::thread::hardware_concurrency()), 0, false // , NULL
    );
  }
  
  auto end = std::chrono::high_resolution_clock::now();

  std::string trace_print_name = reader->trace_path;
  std::string prefix_to_remove = "../libCacheSim/data/";

  double duration_sec = std::chrono::duration<double>(end - start).count();
  size_t pos = trace_print_name.find(prefix_to_remove);
  if (pos != std::string::npos)
      trace_print_name.replace(pos, prefix_to_remove.size(), "");
  for (int i = 0; i < NUM_CACHE_ALGORITHMS; ++i) {
    double miss_ratio      = (double)result[i].n_miss      / (double)result[i].n_req;
    double byte_miss_ratio = (double)result[i].n_miss_byte / (double)result[i].n_req_byte;

    printf(
        "{\"cache_name\":\"%s\","
        "\"trace_name\":\"%s\","
        "\"cache_size\":%lu,"
        "\"percent\":%lf,"
        "\"num_miss\":%lu,"
        "\"num_req\":%ld,"
        "\"miss_ratio\":%.6f,"
        "\"byte_miss_ratio\":%.6f,"
        "\"runtime_seconds\":%.6f}\n",
        result[i].cache_name,
        trace_print_name.c_str(),
        result[i].cache_size,
        cache_percentage,
        result[i].n_miss,
        result[i].n_req,
        miss_ratio,
        byte_miss_ratio,
        duration_sec
    );
  }

  free(result);
  for (int i = 0; i < NUM_CACHE_ALGORITHMS; i++) {
    caches[i]->cache_free(caches[i]);
  }
}

int main(int argc, char *argv[]) {
  assert(argc >= 3 && "./run_algo.o <trace_path> <cache_size: in percentage of number of total objects> <--ignore> <--dump dump_name>");
  const char *trace_path = argv[1];
  cache_percentage = std::stod(std::string(argv[2]));
  
  bool ignore_obj_size = false;
  bool dump_results = false;
  
  for(int i = 3; i < argc; i++) {
    std::string flag = argv[i];
    if(flag == "--ignore") {
        ignore_obj_size = true;
    } else if(flag == "--dump") {
        if(i + 1 >= argc) {
            fprintf(stderr, "Error: --dump requires a name\n");
            exit(1);
        }
        dump_results = true;
        dump_name = std::string(argv[++i]); // consume next argument
    } else {
        fprintf(stderr, "Unknown flag: %s\n", argv[i]);
        exit(1);
    }
  }

  // Initialize reader
  reader_t *reader;
  reader = get_reader(trace_path, ignore_obj_size);
  if(ignore_obj_size) {
    long num_objects = calculate_trace_footprint(reader).second;
    cc_params.cache_size = cache_percentage * num_objects;
  }
  else {
    long trace_footprint_bytes = calculate_trace_footprint(reader).first;
    cc_params.cache_size = cache_percentage * trace_footprint_bytes;
  }
  cc_params.hashpower = 16;
  
  run_multiple_caches(reader);
  close_trace(reader);
}