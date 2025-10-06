#include <netinet/in.h>
#include <netinet/tcp.h>
#include <sys/socket.h>
#include <unistd.h>
#include <cstring>
#include <dlfcn.h>
#include <cstdio>
#include <cerrno> 

extern "C" int socket(int domain, int type, int protocol) {
    typedef int (*socket_func_t)(int, int, int);
    static socket_func_t real_socket = (socket_func_t)dlsym(RTLD_NEXT, "socket");

    int sock = real_socket(domain, type, protocol);

    if (sock >= 0 && type == SOCK_STREAM && domain == AF_INET) {
        int flag = 1;
        if(setsockopt(sock, IPPROTO_TCP, TCP_NODELAY, &flag, sizeof(flag)) == 0){
            printf("[nodelay.so] Successfully set TCP_NODELAY.\n");
        }
        else {
            printf("[nodelay.so] Failed at setting TCP_NODELAY.\n");
        }
    }
    else {
        printf("[nodelay.so] Did not attempt to set TCP_NODELAY\n");
    }
    return sock;
}
