#!/usr/bin/python3

import subprocess
import paho.mqtt.client as mqtt
import time
import json
import sys
import configparser
import logging
import signal
from threading import Thread

debug = False

# set up logger to output to stdout and stderr
logging.basicConfig(stream=sys.stdout, format='%(asctime)s:%(levelname)s:%(name)s:%(message)s', level=logging.DEBUG)

# handle SIGTERM
def signal_term_handler(signal, frame, client, rtl433_proc):
    logging.error("SIGTERM stopping process")
    cleanup(client, rtl433_proc)

def cleanup(client, mqtt_channel, rtl433_proc):
    logging.error(f"RTL_433 exited with code: {rtl433_proc.poll()}")
    logging.info("Killing any RTL_433 process for good measure")
    killcmd = "pkill -f rtl_433"
    subprocess.run(killcmd.split(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    for sid, sensor in sensors.items():
        client.publish(mqtt_channel + sensor, 'offline', qos=0, retain=True)
    client.loop_stop()
    client.disconnect()
    logging.info("EXITED")
    sys.exit(rtl433_proc.poll())

def reset_pir(pirs, pir, client, mqtt_channel, debug):
    while (time.time() - pirs[pir]) <= 60:
        if debug:
            logging.debug(f"Time for reset: {time.time() - v}, Reset: {time.time() - v >= 60}")
        pass
    client.publish({mqtt_channel} + pir, "clear", qos=0, retain=True)
    if debug:
        logging.debug(f"Reset PIR to clear for sensor: {pir}")
    pirs[pir] = False
    #return pirs

# load main config
config = configparser.ConfigParser()
try:
    config.read('config.ini')
    mainconfig = dict(config.items())
    mainconfig = dict((k, v) for k, v in mainconfig.items())
except Exception as e:
    logging.error("Error reading config file")
    logging.debug(e)
    sys.exit()
logging.info("Config file loaded")
if debug:
    logging.debug([print(k, v) for k, v in mainconfig.items()])

# load sensors
sensor_config = configparser.ConfigParser()
try:
    sensor_config.read('sensor_config.ini')
    sensors = dict(sensor_config.items('sensors'))
    sensors = dict((int(k), v) for k, v in sensors.items())
except Exception as e:
    logging.error("Error reading sensor config file")
    logging.debug(e)
    sys.exit()
logging.info("Config file loaded for sensors")
if debug:
    logging.debug([print(k, v) for k, v in sensors.items()])

# rtl 433 command to run
rtl433_cmd = f"{mainconfig['RTL433']['bin']} -F json -R 68"
logging.info(f'RTL_433 command to run: {rtl433_cmd}')

# start mqtt client
try:
    client = mqtt.Client()
    client.connect(mainconfig['MQTT']['host'], mainconfig['MQTT']['port'], 60)
    client.loop_start()
    mqtt_channel = mainconfig['MQTT']['channel']
except Exception as e:
    logging.error("Failed to start MQTT client")
    logging.debug(e)
    client.loop_stop()
    client.disconnect()
    sys.exit()
logging.info("MQTT client started")

#print("Starting RTL433")
# start rtl433 process
try:
    rtl433_proc = subprocess.Popen(rtl433_cmd.split(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
except Exception as e:
    logging.error("RTL_433 process not started")
    logging.debug(e)
    logging.info("Killing any RTL_433 process for good measure")
    subprocess.run("pkill -f rtl_433", stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    client.loop_stop()
    client.disconnect()
    sys.exit()
logging.info("RTL_433 process started")

signal.signal(signal.SIGTERM, signal_term_handler)

# set some initial states for HASS to remove unknown. This relies on that things are initially closed
for sid, sensor in sensors.items():
    if "pir" in sensor:
        state = "clear"
    else:
        state = "closed"
    client.publish(mqtt_channel+sensor, state, qos=0, retain=True)

# initialise dicts for holding triggered pirs
pirs = {}
for k, v in sensors.items():
    if "pir" in v:
        pirs[v] = False

if debug:
    logging.debug("PIR'S to auto reset to clear")
    logging.debug(pirs)

# loop for checking and getting data, then publish to mqtt
try:
    while True:
        if rtl433_proc.poll() is not None: # exit if code is thrown
            #print("RTL433 exited with code: " + str(rtl433_proc.poll()))
            cleanup(client, mqtt_channel, rtl433_proc)

        # loop over output lines
        for line in iter(rtl433_proc.stdout.readline, '\n'):
            if debug:
                logging.debug(str(line))
            if "Tuned" in line: # if tuner not found or tuned then exit
                pass
            elif "No supported devices found" in line:
                logging.error("No supported devices found or tuned")
                cleanup(client, mqtt_channel, rtl433_proc)

            if rtl433_proc.poll() is not None:
                #print("RTL433 exited with code: " + str(rtl433_proc.poll()))
                cleanup(client, mqtt_channel, rtl433_proc)

            # this is where the data is coming in so process and publish to MQTT for HASS
            if "time" in line:
                data = json.loads(line)
                if data['id'] in sensors.keys():
                    id = data['id']
                    state = data['state']
                    sensor = sensors[id]
                    #print(id, sensor, state)

                    # modify state word to be a bit better
                    if state == "close":
                        state = "closed"

                    client.publish(mqtt_channel+sensor, state, qos=0, retain=True)
                    if debug:
                        logging.debug(f"MQTT published to: {mqtt_channel}/{sensor} with data: {state}")

                    if ("pir" in sensor) and (not pirs[sensor]):
                        pirs[sensor] = time.time()
                        if debug:
                            logging.debug(f"Storing pir and time for triggered motion on sensor: {sensor}")
                            logging.debug("Motion diff values for reset:")
                            logging.debug(pirs)
                            logging.debug(f"Running thread to reset PIR to clear: {sensor}")
                        th = Thread(target=reset_pir, args=(pirs, sensor, client, mqtt_channel, debug))
                        th.start()

except (KeyboardInterrupt, Exception):
    cleanup(client, mqtt_channel, rtl433_proc)
