# Yocto-Flic

Yocto-Flic is a small python application which leverages the [Fliclib SDK](http://github.com/50ButtonsEach) to interface Yoctopuce devices with [Flic buttons](http://flic.io). More info on  [Yoctopuce's web site](https://www.yoctopuce.com/EN/article/driving-yoctopuce-modules-with-flic-buttons)

![Screenshot example](http://www.yoctopuce.com/pubarchive/2019-05/Yocto-flic-banner_1.jpg)


Supported functions are
  - Relay ([Yocto-Relay](http://www.yoctopuce.com/EN/usb-actuators/yocto-relay), [Yocto-PowerRelay](http://www.yoctopuce.com/EN/products/yocto-powerrelay-v3), [Yocto-MaxiPowerRelay](http://www.yoctopuce.com/EN/products/yocto-maxipowerrelay), [Yocto-MaxiCoupler](http://www.yoctopuce.com/EN/products/yocto-maxicoupler) )
  - Servo ([Yocto-Servo](http://www.yoctopuce.com/EN/products/yocto-servo))
  - VoltageOutput ([Yocto-0-10v-tx](http://www.yoctopuce.com/EN/products/yocto-0-10v-tx))
  - CurrentLoopOutput ([Yocto-4-20mA-tx](http://www.yoctopuce.com/EN/products/yocto-4-20ma-tx))
  - Buzzer ([Yocto-Buzzer](http://www.yoctopuce.com/EN/products/yocto-Buzzer))
 
# Requirement
This application as been developed on a Raspberry PI 3 B+, it might work on other systems, as long as they feature a bluetooth adapter, but we didn't try. 

# Installation
Download and install the [Fliclib SDK for Linux](https://github.com/50ButtonsEach/fliclib-linux-dist), read the [readme.md](https://github.com/50ButtonsEach/fliclib-linux-dist/blob/master/README.md) file. Position yourself in the  _bin/armv6l/_  folder and  make sure the Flic server can access the Bluetooth stack (you only need to do that once) by typing 

```sh
$ sudo setcap cap_net_admin=ep ./flicd
```
then start the Flic server

```sh
$ ./flicd -f flic.sqlite3
```
Download and install the _Yocto-Flic_ files, and start the Yocto-Flic Script
 
```sh
$ python3 Yocto-flic.py
```

Then use a web browser to connect the Raspberry running the script (port 8081).

# Usage
Usage is supposed to be pretty straight forward: just pair some button, add addresses of some YoctoHub or VirtualHub connected to compatible devices, compatible functions will be automatically listed. Then configure buttons _Click_, _Double click_ and _Hold_  actions.  Here are the main points of the user interface: 

![UI description](http://www.yoctopuce.com/pubarchive/2019-05/UI-description_2.png)




 

