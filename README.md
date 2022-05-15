## Alarm RTL433 MQTT Setup

**NOTE: This repository is for archive purposes and will not be updated. You may still find some of the code useful for your projects**

This repository contains some useful Python code to turn a "dumb" 433MHz alarm into a "smart" alarm which integrates with Home Assistant, or any other home automation software that uses MQTT.

The code captures the signal from the sensors, publishes the state to an MQTT channel which Home Assitant can read. Then we can use automations etc in Home Assistant to make our "dumb" alarm "smart".

Firstly [Install RTL433](https://github.com/merbanan/rtl_433) by following the instructions on the RTL433 GitHub. I used a $20 RTLSDR from Amazon for this project. Any cheap RTLSDR will do. 

## Find code numbers for sensors

Run RTL433 with the flag -R 68 which seems to be the decoding for the sensors output in json for reading in Python which we use to send to MQTT which HASS (Home Assistant) uses.

```
rtl_433 -R 68 -F json
```

One by one trigger the sensors. In my case I simply moved the magnet away from my door and window sensors to trigger a signal to be sent. In the RTL433 output I could see the signal being captured. Note down the sensor number as we use this to map it to a name. 

An example configutation for sensors is given in `sensor_config.ini`, where my list looks like:

```
Sensor List
634288 - 1 - Living Room PIR
681776 - 2 - Landing PIR
416368 - 4 - Office Window
924080 - 7 - Dining Room Window
707088 - 8 - Backdoor
59968 - 5 - Front Door
232096 - 6 - Spare Room
```

Confirm the location of th RTL433 binary in `config.ini` which is by default set to:

```
[RTL433]
bin='/usr/local/bin/rtl433'
```

## Install dependencies

This project uses paho-mqtt. To install it do:

```
pip install paho-mqtt
```

## Install MQTT

Either use an existing MQTT broker or install one. I installed Mosquitto locally. Set the MQTT config in `config.ini`:

```
[MQTT]
host='localhost'
port='1883'
channel='home/alarm'
```