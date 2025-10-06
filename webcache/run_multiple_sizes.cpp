#include "main.h"

const int NUM_SIZES = 1;
uint64_t cache_sizes[NUM_SIZES];

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
  
  for (int i = 0; i < NUM_SIZES; i++) {
    printf(
      "{\"cache_name\": \"%s\", \"cache_size_mb\": %llu, \"n_miss\": %lu, \"n_req\": %lu, "
      "\"miss_ratio\": %.4f, \"byte_miss_ratio\": %.4f, \"runtime_seconds\":%.6f}\n",
        result[i].cache_name, result[i].cache_size / MiB, result[i].n_miss, result[i].n_req,
        (double)result[i].n_miss / result[i].n_req,
        (double)result[i].n_miss_byte / result[i].n_req_byte,
        duration_sec
    );
  }
  cache->cache_free(cache);
  free(result);
}

int main(int argc, char *argv[]) {
  assert(argc == 3 + NUM_SIZES );
  // <trace_path> <size_type: percent/mb> <size1> <size2> ... <sizeN>
  const char *trace_path = argv[1];
  reader_t *reader = get_reader(trace_path);
  TRACE_FOOTPRINT_BYTES = calculate_trace_footprint(reader);

  for(int i=3;i<3+NUM_SIZES;i++){
    if(std::string(argv[2]) == "percent") cache_sizes[i-3] = std::stod(std::string(argv[i])) * TRACE_FOOTPRINT_BYTES;
    else if(std::string(argv[2]) == "mb") cache_sizes[i-3] = std::stoi(std::string(argv[i])) * MiB;
    else assert(false);
    assert(cache_sizes[i-4] < TRACE_FOOTPRINT_BYTES);
  }

  run_one_cache_multiple_sizes(reader);
  close_trace(reader);
}
