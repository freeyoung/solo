#!/usr/bin/env python
import digitalocean

from soloapi import query, now
from local_settings import digitalocean_token

do_manager = digitalocean.Manager(token=digitalocean_token)


def main():
    # Filter out the Solo nodes with the status "rebuild"
    rebuild_droplets = [d[4] for d in query(
        "select * from solos where status=?", ("rebuild", ))]
    for droplet_id in rebuild_droplets:
        # Check the last event of that droplet, if it is a "rebuild" event and
        # is completed already, then set the solo node back to idle.
        last_event = do_manager.get_droplet(droplet_id).get_events()[0]
        if last_event.type == "rebuild" and last_event.status == "completed":
            sql = """update solos set status=?, user=?, updated_at=?
                     where droplet_id=?"""
            query(sql, ("idle", "nobody", now(), droplet_id, ))


if __name__ == "__main__":
    main()
