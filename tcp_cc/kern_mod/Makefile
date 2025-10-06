obj-m := tcp_heuristic.o

all: kmod

kmod:
	mkdir -p $(PWD)/build
	make -C /lib/modules/$(shell uname -r)/build M=$(PWD) modules
	mv *.order *.symvers *.ko *.mod *.mod.c *.mod.o *.o .*.cmd .*.o.d build/ 2>/dev/null || true

clean:
	rm -rfv *.o *.so build/
