#!/usr/bin/python
from tank_vendor.shotgun_api3 import Shotgun
import time

sg = Shotgun("https://hubertp-studio.shotgunstudio.com", login="automation.admin", password="Admin.12345")

# for i in range(1,11):
start_stamp = last_stamp = int(time.time())
# for i in range(1, 31):
for i in range(1, 501):
    new_stamp = int(time.time())
    delta = new_stamp - last_stamp
    last_stamp = new_stamp
    print "-----> %d - %d" % (i, delta)
    # pprint(sg.find('Project', [], ['id', 'name']))
    sg.find('Project', [], ['id', 'name'])
    # time.sleep(60)
    # time.sleep(6)

print "Total: %d" % (last_stamp - start_stamp)
