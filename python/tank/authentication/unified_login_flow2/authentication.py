# Copyright (c) 2023 Autodesk.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import requests
import webbrowser
from time import sleep

def login_path():
    body = {
       "appName": "Example App",
       "machineId": "Example machine ID"
    }

    response = requests.post('http://shotgunlocalhost.com/internal_api/app_session_request', data=body)

    session_id = response.json()['sessionRequestId']
    webbrowser.open(f'http://shotgunlocalhost.com/app_session_request/{session_id}')
    print("awaiting browser login...")

    counter = 0
    sleep_time = 0.5
    logout_time = 180
    while counter * sleep_time < logout_time:
        response = requests.put(f'http://shotgunlocalhost.com/internal_api/app_session_request/{session_id}')
        if response.status_code != 200:
            print("Request expired or was denied")
            return -1
        elif response.json()['approved']:
            break
        sleep(sleep_time)
    print('Request approved')
    data = response.json()
    print(f"Session token: {data['sessionToken']}")
    
if __name__ == '__main__':
    login_path()
