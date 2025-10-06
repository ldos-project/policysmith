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

        char algorithm[256];
        unsigned int len=sizeof(algorithm);

        if (getsockopt(sock, IPPROTO_TCP, TCP_CONGESTION, algorithm, &len) != 0)
        {
            perror("getsockopt");
            return -1;
        }

        printf("[activate_heuristic.so] Current algorithm: %s\n", algorithm);

        strcpy(algorithm, "heuristic");
        len = strlen(algorithm);

        if (setsockopt(sock, IPPROTO_TCP, TCP_CONGESTION, algorithm, len) != 0)
        {
            perror("setsockopt");
            return -1;
        }

        len = sizeof(algorithm);

        if (getsockopt(sock, IPPROTO_TCP, TCP_CONGESTION, algorithm, &len) != 0)
        {
            perror("getsockopt");
            return -1;
        }

        printf("[activate_heuristic.so] New algorithm: %s\n", algorithm);
        fflush(stdout);
    }
    return sock;
}
