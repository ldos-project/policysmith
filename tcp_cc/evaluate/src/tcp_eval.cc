#include <cstdlib>
#include <sys/select.h>
#include "tcp_eval.h"

int main(int argc, char **argv)
{
    DBGPRINT(DBGSERVER,4,"Main\n");
    if(argc!=4)
	{
        DBGERROR("argc:%d\n",argc);
        for(int i=0;i<argc;i++) DBGERROR("argv[%d]:%s\n",i,argv[i]);
		usage();
		return 0;
	}
    
    srand(raw_timestamp());

	client_port=atoi(argv[1]);
    scheme=argv[2];
    duration=atoi(argv[3]);

    start_server(FLOW_NUM, client_port);
	DBGMARK(DBGSERVER,5,"DONE %lu!\n", (raw_timestamp()-start)/1000000);

    return 0;
}

void usage()
{
	DBGMARK(0,0,"./tcp_eval.o [port] [scheme] [duration]\n");
}

void start_server(int flow_num, int client_port)
{
	cFlow *flows;
	sInfo *info;
	info = new sInfo;
	flows = new cFlow[flow_num];
	if(flows==NULL)
	{
		DBGMARK(0,0,"flow generation failed\n");
		return;
	}

	//threads
	pthread_t data_thread;

	//Server address
	struct sockaddr_in server_addr[FLOW_NUM];
	//Client address
	struct sockaddr_in client_addr[FLOW_NUM];
	//Controller address
	
    for(int i=0;i<FLOW_NUM;i++)
    {
        memset(&server_addr[i],0,sizeof(server_addr[i]));
        //IP protocol
        server_addr[i].sin_family=AF_INET;
        //Listen on "0.0.0.0" (Any IP address of this host)
        server_addr[i].sin_addr.s_addr=INADDR_ANY;
        //Specify port number
        server_addr[i].sin_port=htons(client_port+i);

        //Init socket
        if((sock[i]=socket(PF_INET,SOCK_STREAM,0))<0)
        {
            DBGMARK(0,0,"sockopt: %s\n",strerror(errno));
            return;
        }

        int reuse = 1;
        if (setsockopt(sock[i], SOL_SOCKET, SO_REUSEADDR, (const char*)&reuse, sizeof(reuse)) < 0)
            perror("setsockopt(SO_REUSEADDR) failed");
        //Bind socket on IP:Port
        if(bind(sock[i],(struct sockaddr *)&server_addr[i],sizeof(struct sockaddr))<0)
        {
            DBGMARK(0,0,"bind error srv_ctr_ip: 000000: %s\n",strerror(errno));
            close(sock[i]);
            return;
        }
        if (scheme) 
        {
            if (setsockopt(sock[i], IPPROTO_TCP, TCP_CONGESTION, scheme, strlen(scheme)) < 0) 
            {
                DBGMARK(0,0,"TCP congestion doesn't exist: %s\n",strerror(errno));
                return;
            } 
        }
    }
    
    info->trace=trace;

        
    //Start listen
    int maxfdp=-1;
    fd_set rset; 
    FD_ZERO(&rset);
    //The maximum number of concurrent connections is 1
	for(int i=0;i<FLOW_NUM;i++)
    {
        listen(sock[i],1);
        //To be used in select() function
        FD_SET(sock[i], &rset); 
        if(sock[i]>maxfdp)
            maxfdp=sock[i];
    }

    //Timeout {1Hour} if something goes wrong! (Maybe  mahimahi error...!)
    maxfdp=maxfdp+1;
    struct timeval timeout;
    timeout.tv_sec  = 60 * 60;
    timeout.tv_usec = 0;
    int rc = select(maxfdp, &rset, NULL, NULL, &timeout);
    /**********************************************************/
    /* Check to see if the select call failed.                */
    /**********************************************************/
    if (rc < 0)
    {
        DBGERROR("=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-==-=-=-=-=-=-=- select() failed =-=-=-=-=-=--=-=-=-=-=\n");
        return;
    }
    /**********************************************************/
    /* Check to see if the time out expired.                  */
    /**********************************************************/
    if (rc == 0)
    {
        DBGERROR("=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-==-=-=-=-=-=-=- select() Timeout! =-=-=-=-=-=--=-=-=-=-=\n");
        return;
    }

	int sin_size=sizeof(struct sockaddr_in);
	while(flow_index<flow_num)
	{
        if (FD_ISSET(sock[flow_index], &rset)) 
        {
            int value=accept(sock[flow_index],(struct sockaddr *)&client_addr[flow_index],(socklen_t*)&sin_size);
            if(value<0)
            {
                perror("accept error\n");
                DBGMARK(0,0,"sockopt: %s\n",strerror(errno));
                DBGMARK(0,0,"sock::%d, index:%d\n",sock[flow_index],flow_index);
                close(sock[flow_index]);
                return;
            }
            sock_for_cnt[flow_index]=value;
            flows[flow_index].flowinfo.sock=value;
            flows[flow_index].dst_addr=client_addr[flow_index];
            if(pthread_create(&data_thread, NULL , DataThread, (void*)&flows[flow_index]) < 0)
            {
                perror("could not create thread\n");
                close(sock[flow_index]);
                return;
            }
                      
            if (flow_index==0)
            {
                /** TCP_NODELAY was being set in cnt_thread for Orca socket.
                 * For regular TCP socket, we need to set it here, as there is no control thread. */
                int reuse = 1;
                if (setsockopt(sock_for_cnt[flow_index], IPPROTO_TCP, TCP_NODELAY, &reuse, sizeof(reuse)) < 0)
                {
                    DBGMARK(0,0,"ERROR: set TCP_NODELAY option %s\n",strerror(errno));
                    return;
                }

                start=raw_timestamp();
            }
                
            DBGPRINT(0,0,"Server is Connected to the client...\n");
            flow_index++;
        }
    }
    pthread_join(data_thread, NULL);
}

void* DataThread(void* info)
{
	cFlow* flow = (cFlow*)info;
	int sock_local = flow->flowinfo.sock;
	char* src_ip;
	char write_message[BUFSIZ+1];
	char read_message[1024]={0};
	int len;
	char *savePtr;
	char* dst_addr;

	memset(write_message,1,BUFSIZ);
	write_message[BUFSIZ]='\0';
	/**
	 * Get the RQ from client : {src_add} {flowid} {size} {dst_add}
	 */
	len=recv(sock_local,read_message,1024,0);
	if(len<=0)
	{
		DBGMARK(DBGSERVER,1,"recv failed! \n");
		close(sock_local);
		return 0;
	}
	/**
	 * For Now: we send the src IP in the RQ to!
	 */
	src_ip=strtok_r(read_message," ",&savePtr);
	if(src_ip==NULL)
	{
		//discard message:
		DBGMARK(DBGSERVER,1,"id: %d discarding this message:%s \n",flow->flowinfo.flowid,savePtr);
		close(sock_local);
		return 0;
	}
	char * isstr = strtok_r(NULL," ",&savePtr);
	if(isstr==NULL)
	{
		//discard message:
		DBGMARK(DBGSERVER,1,"id: %d discarding this message:%s \n",flow->flowinfo.flowid,savePtr);
		close(sock_local);
		return 0;
	}
	flow->flowinfo.flowid=atoi(isstr);
	char* size_=strtok_r(NULL," ",&savePtr);
	flow->flowinfo.size=1024*atoi(size_);
    DBGPRINT(DBGSERVER,4,"%s\n",size_);
	dst_addr=strtok_r(NULL," ",&savePtr);
	if(dst_addr==NULL)
	{
		//discard message:
		DBGMARK(DBGSERVER,1,"id: %d discarding this message:%s \n",flow->flowinfo.flowid,savePtr);
		close(sock_local);
		return 0;
	}
	DBGPRINT(DBGSERVER,2,"Got message: %" PRIu64 " us\n",raw_timestamp());
    flow->flowinfo.rem_size=flow->flowinfo.size;

	DBGPRINT(0,0,"Server is sending the traffic ...\n");

    while((unsigned int)((raw_timestamp()-start)/1000000 < duration))
    {
		len=strlen(write_message);
		while(len>0)
		{
			DBGMARK(DBGSERVER,5,"++++++\n");
			len-=send(sock_local,write_message,strlen(write_message),0);
		    usleep(50);         
            DBGMARK(DBGSERVER,5,"------\n");
		}
        usleep(100);
	}
	flow->flowinfo.rem_size=0;
    done=true;
    DBGPRINT(DBGSERVER,1,"done=true\n");
    close(sock_local);
    DBGPRINT(DBGSERVER,1,"done\n");
	return((void *)0);
}