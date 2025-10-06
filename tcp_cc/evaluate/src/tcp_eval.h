#include "flow.h"
#define __STDC_FORMAT_MACROS
#include <inttypes.h>
//-------------------------*

//----------------------------------------------------*
typedef uint64_t  u64;

uint64_t start = 0;
unsigned int duration=0;                     //If not zero, it would be the total duration for sending out the traffic.

bool done=false;
char *scheme;
int flow_index=0;
#define FLOW_NUM 1
int sock[FLOW_NUM];
int sock_for_cnt[FLOW_NUM];
                   
struct sTrace
{
    double time;
    double bw;
    double minRtt;
};
struct sInfo
{
    sTrace *trace;
    int sock;
};
int delay_ms;
int client_port;
sTrace *trace;

#define DBGSERVER 0 

uint64_t raw_timestamp( void )
{
    struct timespec ts;
    clock_gettime( CLOCK_REALTIME, &ts );
    uint64_t us = ts.tv_nsec / 1000;
    us += (uint64_t)ts.tv_sec * 1000000;
    return us;
}

//Start server
void start_server(int flow_num, int client_port);

//thread functions
void* DataThread(void*);
void* TimerThread(void*);

//Print usage information
void usage();