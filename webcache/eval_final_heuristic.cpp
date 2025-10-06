#include "main.h"

const int NUM_SIZES = 1;
uint64_t cache_sizes[NUM_SIZES];
std::string collection_name;
std::string mongo_id;
double cache_percentage = -1.0;

void run_one_cache_multiple_sizes(reader_t *reader) {
  auto start = std::chrono::high_resolution_clock::now();

  common_cache_params_t cc_params = default_common_cache_params();
  cc_params.cache_size = 1 * GiB;  // any size should work

  cache_t *cache;

  cache = PQEvolve_init(cc_params, nullptr);
  
  assert(NUM_SIZES == sizeof(cache_sizes) / sizeof(cache_sizes[0]));

  cache_stat_t *result = simulate_at_multi_sizes(
      reader, cache, NUM_SIZES, cache_sizes, nullptr, 0.0, 0,
      static_cast<int>(std::thread::hardware_concurrency()), false);
  
  auto end = std::chrono::high_resolution_clock::now();
  double duration_sec = std::chrono::duration<double>(end - start).count();

  std::string trace_print_name = reader->trace_path;
  std::string prefix_to_remove = "../libCacheSim/data/";
  size_t pos = trace_print_name.find(prefix_to_remove);
  if (pos != std::string::npos) trace_print_name.replace(pos, prefix_to_remove.size(), "");

  
  for (int i = 0; i < NUM_SIZES; i++) {
    printf(
      "{\"collection\": \"%s\", \"mongo_id\": \"%s\", "
      "\"trace_name\":\"%s\", \"cache_name\": \"%s\", \"cache_size_mb\": %llu, \"percent\": %lf, \"n_miss\": %lu, \"n_req\": %lu, "
      "\"miss_ratio\": %.4f, \"byte_miss_ratio\": %.4f, \"runtime_seconds\":%.6f}\n",
        collection_name.c_str(), mongo_id.c_str(), trace_print_name.c_str(),
        result[i].cache_name, result[i].cache_size / MiB, cache_percentage, result[i].n_miss, result[i].n_req,
        (double)result[i].n_miss / result[i].n_req,
        (double)result[i].n_miss_byte / result[i].n_req_byte,
        duration_sec
    );
  }
  cache->cache_free(cache);
  free(result);
}


int main(int argc, char *argv[]) {
  assert(argc == 6);
  // <trace_path> <size_type: percent/mb> <size> <collection_name> <mongo_id>
  const char *trace_path = argv[1];
  reader_t *reader = get_reader(trace_path);
  TRACE_FOOTPRINT_BYTES = calculate_trace_footprint(reader);

  if(std::string(argv[2]) == "percent") {
    cache_percentage = std::stod(std::string(argv[3]));
    cache_sizes[0] = cache_percentage * TRACE_FOOTPRINT_BYTES;
  }
  else if(std::string(argv[2]) == "mb") cache_sizes[0] = std::stoi(std::string(argv[3])) * MiB;
  else assert(false);
  
  assert(cache_sizes[0] < TRACE_FOOTPRINT_BYTES);

  collection_name = std::string(argv[4]);
  mongo_id = std::string(argv[5]);

  run_one_cache_multiple_sizes(reader);
  close_trace(reader);
}
