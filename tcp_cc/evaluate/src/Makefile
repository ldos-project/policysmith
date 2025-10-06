all: tcp_eval client nodelay

tcp_eval: tcp_eval.cc flow.cc
	g++ tcp_eval.cc flow.cc -o tcp_eval.o

client: client.c
	g++ client.c -o client.o

nodelay: nodelay.c
	g++ -shared -fPIC nodelay.c -o nodelay.so -ldl

clean:
	rm -rfv *.o