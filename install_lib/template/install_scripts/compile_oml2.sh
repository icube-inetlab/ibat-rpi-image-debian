#!/bin/sh

cd /usr/local/src/oml2-2.11.0
./configure --disable-doc --disable-doxygen-doc --disable-doxygen-dot --disable-android --disable-doxygen-html --disable-option-checking
make
make install
