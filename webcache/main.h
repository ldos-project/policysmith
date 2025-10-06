#include "libCacheSim/libCacheSim/include/libCacheSim.h"

#include <thread>
#include <string>
#include <unordered_set>

long calculate_trace_footprint(reader_t *reader) {
    reset_reader(reader);
    long footprint = 0;
    request_t req;
    std::unordered_set<uint64_t> unique_objects;

    while (read_trace(reader, &req) == 0) {
        if(unique_objects.find(req.obj_id) == unique_objects.end()) {
          unique_objects.insert(req.obj_id);
          footprint += req.obj_size;
          assert(req.obj_size > 0);
        }
    }
    reset_reader(reader); // Reset the reader to the beginning
    fprintf(stderr, "Trace footprint: %.3f MB\n", footprint/(1024.0 * 1024.0));
    return footprint;
}

bool ends_with(const char *str, const char *suffix) {
    size_t len_str = strlen(str);
    size_t len_suffix = strlen(suffix);
    return len_str >= len_suffix && strcmp(str + len_str - len_suffix, suffix) == 0;
}

reader_t* get_reader(const char* trace_path) {
    reader_init_param_t init_params = default_reader_init_params();
    /* the first column is the time, the second is the object id, the third is the
    * object size */
    init_params.time_field = 2;
    init_params.obj_id_field = 5;
    init_params.obj_size_field = 4;

    /* the trace has a header */
    init_params.has_header = true;
    init_params.has_header_set = true;

    /* the trace uses comma as the delimiter */
    init_params.delimiter = ',';

    /* object id in the trace is numeric */
    init_params.obj_id_is_num = true;
    
    if(ends_with(trace_path, ".csv")) return open_trace(trace_path, CSV_TRACE , &init_params);
    else if(ends_with(trace_path, ".zst")) return open_trace(trace_path, ORACLE_GENERAL_TRACE , &init_params);
    else {
        fprintf(stderr, "Unsupported trace format: %s\n", trace_path);
        assert(false);
    }
}

long TRACE_FOOTPRINT_BYTES;