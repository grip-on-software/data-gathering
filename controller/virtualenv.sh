#!/bin/bash

path=$1
shift

VIRTUAL_ENV="$path" PATH="$path/bin:$PATH" $path/bin/python "$@"
