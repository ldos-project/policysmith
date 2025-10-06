#!/bin/bash

pushd libCacheSim

pushd scripts
bash install_dependency.sh && bash install_libcachesim.sh
popd

popd
