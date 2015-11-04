#!/bin/sh
#
# solo-cli - CLI for Solo API.
#
# It is recommended to link it to your PATH before using.
#
# e.g:
# ~ $ ln -sf ~/code/zenmate/chef/tools/solo/solo-cli.sh /usr/local/bin/solo
#
# NOTE: Remember to export SOLO_API_KEY as CHEF_REPO_DIR properly.
#

set -e

action=${1:-list}
api=${SOLO_API:-https://soloapi.yourdomain.tld}
role=${ROLE:-base}
run_list="role[$role]"

if [ -n "$RUN_LIST" ]
then
    run_list="$run_list,$RUN_LIST"
    echo $run_list
fi

api_key=${SOLO_API_KEY:-bananas}
chef_dir=${CHEF_REPO_DIR:-$(pwd)}

if [ ! -f "$chef_dir/solo.rb" ]; then
    cat >&2 <<EOF
solo.rb not found. You need to export CHEF_REPO_DIR to your local chef repo
or change your working directory to it.
EOF
    exit 2
fi

my_solo=$( curl -s "$api/solos" | awk "/$USER$/ { print \$3 }" )

check_my_solo () {
    # To check if one has a solo node before some actions
    if [ -z "$my_solo" ]; then
        echo "You need to own your solo before you run 'solo $action'."
        exit 2
    fi
}

case $action in
    list)
        curl -s "$api/solos"
        ;;
    create|open|up)
        curl -s -d "user=$USER" "$api/solos/create?api_key=$api_key"
        ;;
    upload|sync)
        check_my_solo
        rsync -azP \
            -e 'ssh -p22' \
            --delete \
            --exclude vendor/bundle/ --exclude .bundle/ \
            --exclude .git/ --exclude .kitchen/ \
            --exclude tmp/ \
            "$chef_dir/" "root@solo${my_solo}.yourdomain.tld:chef/"
        rsync -e 'ssh -p22' -a "$HOME/.chef/$USER.pem" "root@solo${my_solo}.yourdomain.tld:/etc/chef/client.pem"
        ;;
    status|mine)
        check_my_solo
        curl -s "$api/solos/$my_solo?api_key=$api_key"
        ;;
    ssh)
        check_my_solo
        ssh -p22 "root@solo${my_solo}.yourdomain.tld"
        ;;
    run|provision)
        check_my_solo
        # Update the remote chef directory forcefully before provision to keep it sync'd
        $0 sync
        # recipe[chef-solo-search] is used by some cookbooks like Icinga, and is already
        # included in the former Vagrantfile.
        ssh -p22 "root@solo${my_solo}.yourdomain.tld" "chef-solo -c chef/solo.rb -o 'recipe[chef-solo-search],$run_list'"
        ;;
    destroy|close)
        check_my_solo
        curl -s -X DELETE "$api/solos/$my_solo?api_key=$api_key"
        # Remove the current SSH host key because it will be re-generated every rebuild
        ssh-keygen -R "solo${my_solo}.yourdomain.tld" >/dev/null 2>&1
        ;;
    *)
        echo "Usage: $(basename $0) {up|destroy|sync|status|ssh|provision}"
        ;;
esac

