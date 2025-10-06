#include "main.h"

double cache_percentage = -1.0;
common_cache_params_t cc_params = default_common_cache_params();

void run_multiple_caches(reader_t *reader) {
  reset_reader(reader);

  auto start = std::chrono::high_resolution_clock::now();  
  const int NUM_CACHE_ALGORITHMS = 15;
  cache_t *caches[NUM_CACHE_ALGORITHMS] = {
      LRU_init(cc_params, nullptr),
      LFU_init(cc_params, nullptr),
      FIFO_init(cc_params, nullptr),
      MRU_init(cc_params, nullptr),

      LIRS_init(cc_params, nullptr),
      FIFO_Reinsertion_init(cc_params, nullptr),
      CR_LFU_init(cc_params, nullptr),
      SR_LRU_init(cc_params, nullptr),
      GDSF_init(cc_params, nullptr),
      
      Sieve_init(cc_params, nullptr),
      S3FIFO_init(cc_params, nullptr),
      LHD_init(cc_params, nullptr),  
      LeCaR_init(cc_params, nullptr),
      Cacheus_init(cc_params, nullptr),

      Belady_init(cc_params, nullptr),
      // PQEvolve_init(cc_params, nullptr)
  };
  assert(NUM_CACHE_ALGORITHMS == sizeof(caches) / sizeof(caches[0]));
  cache_stat_t *result = simulate_with_multi_caches(
      reader, caches, NUM_CACHE_ALGORITHMS, nullptr, 0.0, 0,
      static_cast<int>(std::thread::hardware_concurrency()), 0, false);
  
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
        "\"cache_size_mb\":%llu,"
        "\"percent\":%lf,"
        "\"num_miss\":%lu,"
        "\"num_req\":%ld,"
        "\"miss_ratio\":%.6f,"
        "\"byte_miss_ratio\":%.6f,"
        "\"runtime_seconds\":%.6f}\n",
        result[i].cache_name,
        trace_print_name.c_str(),
        result[i].cache_size / MiB,
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
  assert(argc == 4);
  const char *trace_path = argv[1];
  reader_t *reader = get_reader(trace_path);
  TRACE_FOOTPRINT_BYTES = calculate_trace_footprint(reader);

  // set cache parameters
  if(std::string(argv[2]) == "percent") {
    cache_percentage = std::stod(std::string(argv[3]));
    cc_params.cache_size = cache_percentage * TRACE_FOOTPRINT_BYTES;
  }
  else if(std::string(argv[2]) == "mb") cc_params.cache_size = std::stoi(std::string(argv[3])) * MiB;
  else {
    printf("XXX%sXXX\n", argv[2]);
    assert(false);
  }
  assert(cc_params.cache_size < TRACE_FOOTPRINT_BYTES);
  cc_params.hashpower = 16;
  
  run_multiple_caches(reader);
  close_trace(reader);
}
