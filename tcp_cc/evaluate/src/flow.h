#ifndef FLOW_H_
#define FLOW_H_
#include <arpa/inet.h>
#include <stdio.h>
#include <signal.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <netinet/tcp.h>
#include <pthread.h>
#include <errno.h>

// common macros for logging
#define DBGPRINT(curlvl, showlvl, fmt, arg...)	do{if(curlvl>=showlvl){fprintf(stdout, "[%s] " fmt, __FUNCTION__ , ## arg );fflush(stdout);}}while(0)
#define DBGMARK(curlvl, showlvl, fmt, arg...)	do{if(curlvl>=showlvl){fprintf(stdout, "[%s-%s-%d] " fmt, __FILE_NAME__, __FUNCTION__, __LINE__ , ## arg );fflush(stdout);}}while(0)
#define DBGERROR(fmt, arg...)	do{fprintf(stdout, "[%s] " fmt, __FUNCTION__ , ## arg );fflush(stdout);}while(0)
#define DBGWARN(fmt, arg...)	do{fprintf(stdout, "[%s] " fmt, __FUNCTION__ , ## arg );fflush(stdout);}while(0)
#define DBGINFO(fmt, arg...)	do{fprintf(stdout, "[%s] " fmt, __FUNCTION__ , ## arg );fflush(stdout);}while(0)
#define __FILE_NAME__ (strrchr(__FILE__,'/')?strrchr(__FILE__,'/')+1:__FILE__)

struct sFlowinfo
{
	int sock;
	int flowid;
	uint64_t size;
  uint64_t rem_size;

	sFlowinfo& operator=(const sFlowinfo& other);
	void Copy(sFlowinfo);
	void Init();
};

/**
 * Server-Side Flows!
 * Client has sent its request including data-size, {src,dst}
 */

class cFlow
{
public:
	cFlow();
	cFlow(sFlowinfo);

public:
	sockaddr_in dst_addr;
	sFlowinfo flowinfo;
};

#endif /* FLOW_H_ */