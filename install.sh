#!/bin/bash

set -e

# Bootstrap shellboost.
if [ ! -f "$SHELLBOOST/libsh/include.sh" -a -r "$HOME/etc/shellboost/libsh/include.sh" ]; then
   export SHELLBOOST="$HOME/etc/shellboost"
fi
. "$SHELLBOOST/libsh/include.sh" || exit $?

__shellboost_include libsh/script.sh || exit $?
__shellboost_include libsh/install.sh || exit $?

parse_command_line "$@"

runf cd "${HOME?}"
link "$here/env/mh_profile"   .mh_profile
link "$here/env/mhl.headers"  .mhl.headers
link "$here/env/nmh"          etc/nmh
