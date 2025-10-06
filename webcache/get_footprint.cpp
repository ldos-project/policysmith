#include "main.h"
int main(int argc, char **argv) {
    const char *trace_path = argv[1];
    reader_t *reader = get_reader(trace_path);

    std::string trace_print_name = reader->trace_path;
    std::string prefix_to_remove = "../libCacheSim/data/";
    size_t pos = trace_print_name.find(prefix_to_remove);
    if (pos != std::string::npos) trace_print_name.replace(pos, prefix_to_remove.size(), "");

    printf("{\"trace\": \"%s\", \"footprint_mb\":%f}\n", trace_print_name.c_str(), calculate_trace_footprint(reader)/(1024.0 * 1024.0));
    close_trace(reader);
    return 0;
}