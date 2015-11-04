#!/bin/sh
#
# This script is used to sync the latest staging branch of chef
# repo to solo base node and solo nodes that are not in use.
#
# NOTE: Remember to set proper env var WORK_DIR.
#

set -e

branch=${1:-banana}
api=${SOLO_API:-https://soloapi.youdomain.tld}
workdir=${WORK_DIR:-/opt/TeamCity/agents/buildAgent/work/chef/}

if [ "$branch" != "refs/heads/staging" ]; then
    echo "Only staging branch will be pushed to solo. Exiting."
    exit 0
fi

for solo_id in -base \
    $( curl -s "$api/solos" | awk '{print $3}' )
do
    solo_host="solo${solo_id}.yourdomain.tld"

    echo "===================================================="
    echo "Updating chef directory on $solo_host"
    echo "===================================================="

    rsync -azP \
        -e "ssh -o StrictHostKeyChecking=no" \
        --delete \
        --exclude vendor/bundle/ --exclude .bundle/ \
        --exclude .git/ --exclude .kitchen/ \
        --exclude tmp/ \
        "$workdir/" "root@$solo_host:chef/"
done
