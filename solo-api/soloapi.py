#!/usr/bin/env python
import os
import sys
import sqlite3
import digitalocean
from functools import wraps
from datetime import datetime
from flask import Flask, request

try:
    from local_settings import digitalocean_token, dbfile, base_image_name
except ImportError:
    print "Missing local_settings.py!"
    sys.exit(2)

app = Flask(__name__)
api_key = os.environ.get("API_KEY", "bananas")

do_manager = digitalocean.Manager(token=digitalocean_token)


def now():
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def query(sql, params=()):
    conn = sqlite3.connect(dbfile)
    with conn:
        cur = conn.cursor()
        cur.execute(sql, params)
        data = cur.fetchall()
    return data


def parse_solos(data):
    """
    Parse sql query result into list of solo dicts.
    """
    return [{"id": d[0], "status": d[1], "user": d[2], "updated_at": d[3],
            "droplet": d[4]} for d in data]


def csv_output(data, delimeter="\t"):
    lines = [delimeter.join([str(v) for v in d.values()]) for d in data]
    return "\n".join(lines) + "\n"


def get_latest_base_image():
    my_images = do_manager.get_my_images()
    base_image = [img for img in my_images if img.name == base_image_name][-1]
    return base_image


def api_key_required(view_function):
    """
    Decorator for endpoints require API key authentication.
    """
    @wraps(view_function)
    def decorated_function(*args, **kwargs):
        if request.args.get('api_key', None) == api_key:
            return view_function(*args, **kwargs)
        else:
            return "Authentication Failed", 401
    return decorated_function


@app.route("/solos", methods=["GET"])
def get_solos():
    solos = parse_solos(query("select * from solos"))
    return csv_output(solos)


@app.route("/solos/create", methods=["POST"])
@api_key_required
def create_solo():
    user = request.form["user"]
    solos = parse_solos(query("select * from solos where user=?", (user, )))
    # Check if the user has one solo already
    if solos:
        return "You already have a solo. You cannot have more.", 503
    # Check if all the solos are busy
    solos = parse_solos(query("select * from solos where status=?", ("idle", )))
    if not solos:
        return "Unfortunately all the solo nodes are busy at the moment.", 503
    # Assign an idle solo to the user
    solo_id = solos[0]["id"]
    query("update solos set status=?, user=?, updated_at=? where id=?",
          ("busy", user, now(), solo_id, ))
    return "Solo node %s is now yours. Happy playing with it." % solo_id, 201


@app.route("/solos/<int:solo_id>", methods=["GET", "DELETE"])
@api_key_required
def operate_solo(solo_id):
    # Check if the specified Solo node exists
    solos = parse_solos(query("select * from solos where id=?", (solo_id, )))
    if not solos:
        return "Solo node %s not found" % solo_id, 404
    solo = solos[0]
    if request.method == "DELETE":
        # DELETE means to rebuild that Solo node
        if solo["status"] != "busy":
            return "This solo node does not need to be rebuilt.", 503
        droplet_id = solo["droplet"]
        droplet = digitalocean.Droplet(id=droplet_id, token=digitalocean_token)
        # Rebuild the node with latest solo base image
        base_image = get_latest_base_image()
        droplet.rebuild(base_image.id)
        query("update solos set status=?, user=?, updated_at=? where id=?",
              ("rebuild", "solobot", now(), solo_id))
        return "Solo node %s released, and is being rebuilt with the base image." \
            % solo["id"]
    return csv_output([solo])


if __name__ == "__main__":
    app.run(debug=True)
