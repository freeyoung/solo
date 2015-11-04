#!/usr/bin/env python
import digitalocean
from time import sleep

from local_settings import digitalocean_token, base_image_name, base_node_name

do_manager = digitalocean.Manager(token=digitalocean_token)


def wait_for_event(droplet, event, check_interval=60):
    while True:
        last_event = droplet.get_events()[0]
        if last_event.type == event and last_event.status != "completed":
            print ">>> In progress..."
            sleep(check_interval)
        else:
            return last_event.status


def remove_old_base_images():
    print ">>> Checking images..."
    my_images = do_manager.get_my_images()
    base_images = [image for image in my_images if image.name == base_image_name]
    if base_images:
        print ">>> Deleting older snapshot(s)..."
        for image in base_images:
            image.destroy()


def make_new_base_image():
    all_droplets = do_manager.get_all_droplets()
    base_node = [droplet for droplet in all_droplets if droplet.name == base_node_name][0]
    if base_node.status != "off":
        print ">>> Powering off..."
        base_node.power_off()
        wait_for_event(base_node, "power_off")

    print ">>> Taking snapshot..."
    base_node.take_snapshot(base_image_name)
    wait_for_event(base_node, "snapshot")
    print ">>> Done."


if __name__ == "__main__":
    remove_old_base_images()
    make_new_base_image()
