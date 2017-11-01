obj-m    := steerer.o


steerer-y	:= s.o

CXX = gcc 
KDIR    := /lib/modules/$(shell uname -r)/build
PWD    := $(shell pwd)

default: 
	$(MAKE) $(CF) -C $(KDIR) SUBDIRS=$(PWD) modules

clean: cleanuser
	$(MAKE) -C $(KDIR) SUBDIRS=$(PWD) clean

cleanuser:
	rm -rf *.o *~ 
