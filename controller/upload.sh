#!/bin/bash

# Restricted login shell for agents that can only interact with their own home
# directory with limited command access (only Git/SCP uploading and downloading)

if [ $# -ne 2 ] || [ "$1" != "-c" ] ; then
  echo "Interactive logins are not permitted" >&2
  exit 1
fi

cmd=$2
if [[ "$cmd" =~ "/../" ]]; then
  echo "Paths must be provided in absolute form, no parent directory syntax" >&2
  exit 1
fi
if [[ "$cmd" =~ .*\;|\&|\|\|.* ]]; then
  echo "Compound commands may not be provided" >&2
  exit 1
fi

case "$cmd" in
  "git-upload-pack '~/"* | "git-receive-pack '~/"*)
     ;; # Continue execution
  "scp -t ~/"* | "scp -v -d -t ~/"* | "scp -v -d -f ~/"* | "scp -v -f ~/"* | "scp -d -f ~/"* | "scp -f ~/"* | "scp -r -f ~/"* | "scp -d -t ~/"*)
     # Expand braces in the command safely for compatibility with agents which
     # assume that expansion is performed by the shell
     cmd=$(python -c "import sys;from braceexpand import braceexpand;print ' '.join(' '.join(braceexpand(arg)) for arg in sys.argv[1].replace('\\{', '{').replace('\\}', '}').split(' '))" "$cmd")
     ;; # Continue execution
  * )
     echo "Command '$cmd' is not allowed" >&2
     exit 1
     ;;
esac

echo "Executing command '$cmd'" >&2
/bin/bash --restricted -c "$cmd"
