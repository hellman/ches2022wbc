SHELL := /bin/bash

all: lib/libfastcircuit.so

# bin/runcircuit: bin/runcircuit.c lib/fastcircuit.c lib/fastcircuit.h
# 	gcc -Wall -O3 -Iwhitebox/ lib/fastcircuit.c bin/runcircuit.c -o bin/runcircuit

lib/libfastcircuit.so: wboxkit/fastcircuit.c wboxkit/fastcircuit.h
	gcc -Wall -O3 -Iwboxkit/ wboxkit/fastcircuit.c -fPIC -shared -o lib/libfastcircuit.so

clean:
# 	rm -f bin/runcircuit lib/libfastcircuit.so
	rm -f lib/libfastcircuit.so

submit:
	gcc -O3 build/submit.c build/main.c -o build/submit
	diff <(./build/submit <build/plain | xxd) <(xxd build/cipher)
