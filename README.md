Solo
====

A replacement for Vagrant when testing Chef before making a PR, with `chef-solo`.

Currently, `solo` supports DigitalOcean only, as it depends on the snapshot feature.


Design
======

TL;DR: [How to Use](#how-to-use)

Base Image / Node
-----------------

- Solo base image and base node are used to reduce the converge time on the solo nodes

- Solo nodes are the nodes to actually run chef tests on

- Base node is deployed with `role[base]` and running `chef-solo` periodically to keep itself up-to-date

- Base image is the nightly snapshot of base node, and used to rebuild clean solo nodes

- CI will `rsync` latest changes of staging branch to base node and idle solo nodes once tests pass

- SSH pubkeys of DevOps team members and CI machines are pre-deployed in base node


Solo-API
--------

Solo API is a python web app that keeps the statuses of solo nodes, images and interacts with DigitalOcean.

Here are the endpoints of Solo API:

- `/solos`, accepts `GET`: 

    Sample output:
    
    ```
    idle    1234567 1       2015-06-26 18:27:21     nobody
    idle    1234568 2       2015-06-25 18:33:06     nobody
    idle    1234569 3       2015-06-25 18:33:08     nobody
    ```

    Which means:

    ```
    status  droplet solo_id updated_at              user
    ```
    
- `/solos/create`, accepts `POST`:

    Sample params:

    ```
    user        eric
    ```
    
    - Mark an idle solo node as assigned, to you.

- `/solos/2`, accepts `GET` and `DELETE`:
    
    `GET`
    
    ```
    idle    1234568 2       2015-06-25 18:33:06     nobody
    ```
    
    `DELETE`

    ```
    params:
    user        eric
    ```
    
    - Rebuild the Droplet of that solo with the base image
    
    - Mark the user of that solo as `solobot`
    
    - Once the rebuild process is done, the status will be set back to `idle` and user to `nobody`


There are two scripts running as cron jobs on the API server:

- `update_rebuild_status.py`

    - Check if the rebuild process for solo nodes are done and update the status and user accordingly.
    
    - Triggered once per minute.

- `take_base_snapshot.py`

    - Take nightly snapshot of the base node.

    - Triggered once per day in the early morning.


Solo-CLI
--------

Solo CLI is a shell wrapper for solo-api and common tasks for solo nodes with `ssh` and `rsync`.

- `solo list`
    
    `GET /solos`

- `solo up`

    `POST /solos/create`
    
- `solo destroy`

    `DELETE /solos/2`

- `solo status`

    `GET /solos/2`

- `solo ssh`

    `ssh root@solo2.yourdomain.tld`

- `solo sync`

    Sync the solo chef dir with the local one.

- `solo provision`

    Do `solo sync` first and then provision with the given Chef role (`ROLE=banana solo provision`).
    Alternatively, you can also pass `RUN_LIST=...` to `solo provision` (`RUN_LIST=recipe[banana],recipe[orange] solo provision`) to test multiple roles/recipes.


How to Use
==========

Solo-API
--------

Solo-API accepts the requests from Solo-CLI and interacts with DigitalOcean API.

This server does not have to be a DigitalOcean Droplet.

1. Clone the repo and deploy `solo-api` directory on your server.
   Here I will use `/opt/soloapi` for example.

   Note that you need to copy `local_settings.py.example` to `local_settings.py`
   and change `digitalocean_token` as your own.

2. Install dependencies. Use virtualenv if you like.

   ```
   cd /opt/soloapi
   pip install -r requirements.txt
   ```

3. Fire up soloapi service with your favorite service management system.
   Here I will use `supervisor`:

   ```
   cat /etc/supervisor/conf.d/soloapi.conf

   [program:soloapi]
   command = gunicorn soloapi:app -w 4 -b 127.0.0.1:5086 --log-file - --access-logfile -
   autorestart = true
   directory = /opt/soloapi
   environment = API_KEY=YOUR_SOLO_API_KEY
   user = www-data
   ```

   Remeber the `API_KEY` you set here, which will be used for `solo-cli` later.

4. Add nginx config file for SoloAPI.

   ```
   server {
       listen 80;
       listen 443 ssl;
       server_name soloapi.yourdomain.tld;
   
       server_tokens off;
   
       ssl_certificate /etc/certificates/yourdomain-chain.pem;
       ssl_certificate_key /etc/certificates/yourdomain-key.pem;
   
       include proxy_params;
   
       location / {
           proxy_pass http://127.0.0.1:5086;
       }
   } 
   ```

   SSL is not mandatory, but highly recommended. If you have decide to not use SSL, change
   scheme to `http` in `solo-cli.sh`.

5. Create your solo base node, install Chef and drop your chef repo in `/root/chef`.
   Take a snapshot of the base node with the name of `base_image_name` in your `local_settings.py`.

   Add the ssh pubkeys of the potential users of your solo setup to `/root/.ssh/authorized_keys`.
   This can be definitely improved and automated better.

6. Deploy at least one solo node with the snapshot taken and initialise the database.

   ```
   cd /opt/soloapi
   sqlite3 solo.db < schema.sql
   echo "INSERT INTO solos VALUES (1, 'idle', 'nobody', '2015-01-01 11:11:11', 1234567)" | sqlite3 solo.db
   ```

   Here `1234567` is your droplet id.

7. Configure the DNS records for `solo-api.yourdomain.tld` and your solo nodes, like
   `solo1.yourdomain.tld`, etc.

8. Add 2 cron jobs for `update_rebuild_status.py` and `take_base_snapshot.py`. Example:

   ```
   * * * * * www-data /opt/soloapi/update_rebuild_status.py >/dev/null 2>&1
   0 4 * * * www-data /opt/soloapi/take_base_snapshot.py >/dev/null 2>&1
   ```

Solo-CLI
--------

1. Symlink `solo-cli` to your PATH:

    `ln -sf YOUR_PATH_TO_SOLO/solo-cli.sh /usr/local/bin/solo`

2. Export environment variables needed by `solo-cli`, in your `.bashrc` or `.zshrc`.

    ```
    export CHEF_REPO_DIR=....
    export SOLO_API_KEY=....
    ```

3. Play with it like you did with `vagrant`!

    ```
    solo up
    solo provision
    ROLE=alerting solo provision
    solo ssh
    solo destroy
    ```

CI Integration
--------------

1. Modify `ci/ci.example.sh` per your own CI infrastructure.

2. Add an additional build step to your current CI configuration for Chef.
   Remeber to add the ssh pubkey of your CI user to your solo base node.
