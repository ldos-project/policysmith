#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/types.h>  
#include <sys/socket.h>  
#include <netinet/in.h>  
#include <arpa/inet.h> 
#include <pthread.h>
#include <errno.h>
#include <netinet/tcp.h>
#include <time.h>
#include <inttypes.h>

#include "tcp_eval.h" 

#define DBG 0
#define HASH_RANGE 5

// Print usage information
void usage()
{
	DBGWARN("./client [server IP address] [server port] \n");
}

int main(int argc, char **argv)
{
	int connected=0;
    int i;

	if(argc!=3)
	{
		usage();
        for(int i=0;i<argc;i++)
        {   
            DBGERROR("%s\n",argv[i]);
        }
           DBGERROR("ARGC:%d\n",argc);
                
		return 0;
	}

	char* server=(char*)malloc(16*sizeof(char));;	//IP address (e.g. 192.168.101.101) 
	char query[100];	                                //query=data_size+' '+deadline+' '+agnostic
	int port;                                   	//TCP port number

	int sockfd;	                                    //Socket
	struct sockaddr_in servaddr;                	//Server address (IP:Port)

	int len;                                    	//Read length
	char buf[BUFSIZ];                           	//Receive buffer

	//Initialize ‘server’
	memset(server,'\0',16);
	//Initialize 'query'
	memset(query,'\0',150);

	//Get server address
	server=argv[1];
    port=atoi(argv[2]);
	    
	//If the inputs are legal
	
	strcat(query,argv[1]);
	strcat(query," ");
	strcat(query,argv[2]);
	strcat(query," ");
	strcat(query,"2700");
	strcat(query," ");
	strcat(query,"10.10.10.10");
	strcat(query," ");
	strcat(query,"2700");
		
	//Init sockaddr_in
	memset(&servaddr,0,sizeof(servaddr));
	servaddr.sin_family=AF_INET;
	//IP address
	servaddr.sin_addr.s_addr=inet_addr(server);
	//Port number
	servaddr.sin_port=htons(port);


	//Init socket
	if((sockfd=socket(PF_INET,SOCK_STREAM,0))<0)
	{
		DBGMARK(0,0,"socket error:%s\n",strerror(errno));
		return 0;
	}
	int reuse = 1;

	if (setsockopt(sockfd, IPPROTO_TCP, TCP_NODELAY, &reuse, sizeof(reuse)) < 0)
	{
		DBGMARK(0,0,"ERROR: set TCP_NODELAY option %s\n",strerror(errno));
		close(sockfd);
		return 0;
	}
	DBGPRINT(DBG,5,"%s ---\n",inet_ntoa(servaddr.sin_addr));

	//Establish connection
    for(i=0;i<120;i++)
    {
        if(connect(sockfd,(struct sockaddr *)&servaddr,sizeof(struct sockaddr))<0)
        {
            DBGPRINT(0,0,"Trying to connect to %s\n",server);
            usleep(500000);
        }
        else
        {
            connected=1;
            DBGPRINT(0,0,"Connected!\n");
            break;
        }
    }
    if(!connected)
    {
        DBGPRINT(0,0,"No success after 120 tries :(\n");
        close(sockfd);
        return 0;
    }

    DBGPRINT(DBG,5,"%s ---\n",inet_ntoa(servaddr.sin_addr));
    
	//Send request
	len=strlen(query);
	while(len>0)
	{
		len-=send(sockfd,query,strlen(query),0);
	}

    DBGMARK(DBG,1,"after sending request\n");
	//Receive data
	while(1)
	{
		len=recv(sockfd,buf,BUFSIZ,0);
		if(len<=0)
		{
			//DBGPRINT(DBG,2,"len:%d\n",len);	
			break;
		}
	}
	// Close connection
	close(sockfd);
    DBGMARK(DBG,1,"after receiving data\n\n");
    return 0;
}