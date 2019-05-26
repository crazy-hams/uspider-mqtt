""" This is uSpider-MQTT """
#
# uSpider MQTT
# DX spider client telnet microservice with JSON/MQTT backend
#

# pylint: disable=invalid-name;
# pylint: disable=too-few-public-methods;
# pylint: disable=C0301, R0912, R0914, R0915, R1702, W0703


__author__ = 'CrazyHams'

import sys
import json
import re
import telnetlib
from time import sleep
from datetime import datetime
import paho.mqtt.client as mqtt
import settings


# Global variables ----------------------------------------------------------------------------------------------------
#
HOST = 've7cc.net'
PORT = 23
PASS = ''
TOUT = 90
MQTT_SSL = False
MQTT_PORT = 1883
MQTT_CA_CERT = 'mosquitto-ca.crt'
TOPIC_SPOT = 'dxspots'
TOPIC_WWV = 'wwv'
TOPIC_WCY = 'wcy'
DATEFORMAT = '%Y%m%dT%H%M%S.%f'

try:
    CALL = settings.Config.CALL
except KeyError:
    CALL = 'ec1zzz-666'
except Exception as e:
    print('Unexpected: %s' % e)
    sys.exit(1)

try:
    MQTT_HOST = settings.Config.MQTT_HOST
except KeyError:
    MQTT_HOST = '127.0.0.1'
except Exception as e:
    print('Unexpected: %s' % e)
    sys.exit(1)


# PROGAM STARTS HERE --------------------------------------------------------------------------------------------------
#
def do_telnet():
    """
    This function connects to a telnet-based cluster service in
    order to receive spots, weather, solar and skimmer data.

    :param: none
    :return: MQTT publication on a predefined set of topics in a Mosquitto server
    """

    # Local variables -------------------------------------------------------------------------------------------------
    #
    SPOTBYUSERS = 0
    SPOTBYSKIMMER = 0
    SPOTWWV = 0
    SPOTWCY = 0

    # Telnet connection to cluster ------------------------------------------------------------------------------------
    #
    try:
        print('+ Connecting to cluster service...')
        print('|-> Using call: ' + CALL)
        t = telnetlib.Telnet(HOST, PORT, TOUT)
    except Exception as e:
        print('|- Unable to connect to cluster %s: %s' % HOST, e)
        return

    # DEBUG: Telnet session -------------------------------------------------------------------------------------------
    #
    # t.set_debuglevel(100)
    #

    # Login procedure -------------------------------------------------------------------------------------------------
    #
    t.read_until(b'login: ', 10)
    t.write(CALL.encode('ascii') + b'\n')
    if PASS:
        t.read_until(b'password: ', 10)
        t.write(PASS.encode('ascii') + b'\n')

    #  Cluster setup (CC Cluster v3) ----------------------------------------------------------------------------------
    #
    print('|-> Enabling Skimmer')
    t.write(b'set/skimmer\n')
    t.read_until(b'enabled', 5)
    sleep(1)

    print('|-> Setting up buffer length')
    t.write(b'set/width 130\n')
    t.read_until(b'characters', 5)
    sleep(1)

    print('|-> Configuring QRG format')
    t.write(b'set/res 1\n')
    t.read_until(b'digit', 5)
    sleep(1)

    print('|-> Enabling WWV')
    t.write(b'set/wwv\n')
    t.read_until(b'enabled', 5)
    sleep(1)

    print('|-> Enabling WCY')
    t.write(b'set/wcy\n')
    t.read_until(b'enabled', 5)
    sleep(1)

    print('|-> Enabling enhaced spot format')
    t.write(b'set/ve7cc\n')
    t.read_until(b'enabled\r\n', 5)
    sleep(1)

    #  MQTT broker ----------------------------------------------------------------------------------------------------
    #
    mqtt_client = mqtt.Client(client_id='uspider', transport='tcp')

    try:
        print('+ Connecting to MQTT server')
        if MQTT_SSL:
            mqtt_client.tls_set(MQTT_CA_CERT, cert_reqs=0)
            mqtt_client.tls_insecure_set(True)
        mqtt_client.connect(MQTT_HOST, MQTT_PORT, 60)
        print('|-> Connected')
    except Exception as e:
        print(
            '\n** Closing connection due to MQTT error: %s' % e
        )
        sys.exit(1)

    while True:
        try:
            rawdata = t.read_until(b'\r\n').decode('ISO-8859-1')
            data = rawdata.split('^')
            #
            # DEBUG: String manipulation ------------------------------------------------------------------------------
            #
            # print()
            print(data)
            #
            # ---------------------------------------------------------------------------------------------------------
            #
            if not data:
                continue

            else:
                if data[0] == 'CC11':
                    comment = ' '.join(re.sub(r'[^a-zA-Z0-9/ñ#:()!\.\+\-\_\s]', '', str(data[5])).split())
                    comment = (comment[:75] + '...') if len(comment) > 75 else comment

                    if data[9] == 'SK1MMR' or data[9] == 'SK1MMR-1-#' or data[6] == 'VE7CC-#' or data[9] == 'RBN':
                        SPOTYPE = 'by-skim'
                        SPOTBYSKIMMER += 1
                        data[22] = data[21]
                        data[21] = ''
                        data.append('0.0.0.0')
                    else:
                        SPOTYPE = 'by-user'
                        SPOTBYUSERS += 1

                    processed_data = json.dumps(
                        {
                            'tstamp': str(datetime.now().strftime(DATEFORMAT)),
                            'b-data': {
                                'dx': data[2],
                                'qrg': '%.1f' % float(data[1]),
                                'src': data[6],
                                'cmt': comment
                            },
                            'e-data': {
                                'type': SPOTYPE,
                                'cluster': data[9],
                                'src-ip': data[23],
                                'src-dxcc': data[16],
                                'dst-dxcc': data[17],
                            }

                        }, sort_keys=False
                    )

                    #  MQTT broker ------------------------------------------------------------------------------------
                    #
                    if mqtt_client and (len(data) > 7):
                        mqtt_client.publish(TOPIC_SPOT, str(processed_data))

                else:
                    data = ' '.join(data)
                    data = data.split()

                    if data[0] == 'WWV':
                        k = re.sub(r'\D', '', data[6])
                        a = re.sub(r'\D', '', data[5])
                        sfi = re.sub(r'\D', '', data[4])
                        SPOTWWV += 1

                        processed_data = json.dumps(
                            {
                                'tstamp': str(datetime.now().strftime(DATEFORMAT)),
                                'b-data': {
                                    'k': k,
                                    'a': a,
                                    'sfi': sfi,
                                    'sa': data[7]
                                },
                                'e-data': {
                                    'type': 'wwv'
                                }
                            }, sort_keys=False
                        )

                        print(processed_data)

                        #  MQTT broker --------------------------------------------------------------------------------
                        #
                        if mqtt_client and (len(data) > 7):
                            mqtt_client.publish(TOPIC_WWV, str(processed_data))

                    elif data[0] == 'WCY':
                        k = re.sub(r'\D', '', data[5])
                        ek = re.sub(r'\D', '', data[6])
                        a = re.sub(r'\D', '', data[7])
                        ssn = re.sub(r'\D', '', data[8])
                        sfi = re.sub(r'\D', '', data[9])
                        SPOTWCY += 1

                        processed_data = json.dumps(
                            {
                                'tstamp': str(datetime.now().strftime(DATEFORMAT)),
                                'b-data': {
                                    'k': k,
                                    'ek': ek,
                                    'a': a,
                                    'ssn': ssn,
                                    'sfi': sfi,
                                    'sa': (data[10])[3:],
                                    'gmf': (data[11])[4:],
                                    'au': (data[12])[3:]
                                },
                                'e-data': {
                                    'type': 'wcy'
                                }
                            }, sort_keys=False
                        )

                        print(processed_data)

                        #  MQTT broker --------------------------------------------------------------------------------
                        #
                        if mqtt_client and (len(data) > 7):
                            mqtt_client.publish(TOPIC_WCY, str(processed_data))

                    else:
                        print('* UNHANDLED ***********************************')
                        print(data)
                        print('***********************************************')

                        with open('unhandled.txt', 'a+') as f:
                            f.write(str(type(data)) + '\n')
                            for item in data:
                                f.write(' %s\n' % item)

        except KeyboardInterrupt:
            print(
                '\n** User exited.'
                '\n** User\' spots processed in this session: %s' % SPOTBYUSERS,
                '\n** Skimmers processed in this session: %s' % SPOTBYSKIMMER,
                '\n** WWV announces processed in this session: %s' % SPOTWWV,
                '\n** WCY announces processed in this session: %s' % SPOTWCY
            )
            mqtt_client.disconnect()
            sys.exit(0)
        except EOFError:
            print('\n** Closing connection due to EOFError: %s' % EOFError)
            mqtt_client.disconnect()
            sys.exit(1)
        except OSError:
            print('\n** Closing connection due to OSError: %s' % OSError)
            mqtt_client.disconnect()
            sys.exit(1)
        except Exception as e:
            print('\n** Closing connection due to an exception: %s' % e)
            mqtt_client.disconnect()
            sys.exit()


if __name__ == '__main__':
    do_telnet()
