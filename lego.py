import time
import datetime
import json
import csv
import cv2
import numpy as np
import RPi.GPIO as gpio
from AWSIoTPythonSDK.exception.AWSIoTExceptions import connectTimeoutException
from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient

class StockReport:

    def __init__(self): #open csv file and change format to dictionary
        self.items_dictionary = {}
        with open('export.csv', 'r') as d:
            data = d.read().splitlines()

            for item in data:
                item = item.split(';')
                item_name = item[0]
                stock = int(item[1])
                self.items_dictionary.update({item_name:stock})

    def updateStockCSV(self, color): #add stock +1 and update to csv
        self.color = color
        self.items_dictionary[color+'_stock'] += 1

        with open('export.csv', 'w') as f:
            for k,v in self.items_dictionary.items():
                f.write("%s;%s\n"%(k,v))

    def updateStockAWS(self, color): #get actual stock
        self.color = color
        return self.items_dictionary[color+'_stock']
        
              
class AWSIot:

    MQTT_CLIENT_ID = ""
    MQTT_HOST = ""
    MQTT_TOPIC = ""

    # Certificate files
    CERT_FILE_PATH = ""
    CA_ROOT_CERT_FILE = ""
    THING_CERT_FILE = ""
    THING_PRIVATE_KEY = ""

    def create_mqtt_client(self):

        ''' This function creates and configures the MQTT client
            using the parameters given above'''

        mqtt_client = AWSIoTMQTTClient(self.MQTT_CLIENT_ID)
        mqtt_client.configureEndpoint(self.MQTT_HOST, 8883)
        mqtt_client.configureCredentials(self.CERT_FILE_PATH + self.CA_ROOT_CERT_FILE, self.CERT_FILE_PATH + self.THING_PRIVATE_KEY,
                                     self.CERT_FILE_PATH + self.THING_CERT_FILE)

        mqtt_client.configureOfflinePublishQueueing(-1)  # Infinite offline Publish queueing
        mqtt_client.configureDrainingFrequency(2)  # Draining: 2 Hz
        mqtt_client.configureConnectDisconnectTimeout(10)  # 10 sec
        mqtt_client.configureMQTTOperationTimeout(5)  # 5 sec

        return mqtt_client

    def publish_data(self, mqtt_client, sequence_nr):

        message = {}
        message['Timestamp'] = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
        message['Red_Stock'] = StockReport().updateStockAWS('red')
        message['Blue_Stock'] = StockReport().updateStockAWS('blue')
        messageJson = json.dumps(message)
        mqtt_client.publish(self.MQTT_TOPIC, messageJson, 0) # Topic AwS


if __name__ == '__main__':
    
    #define servomotor
    servo_pin = 14
    gpio.setmode(gpio.BCM)
    gpio.setup(servo_pin, gpio.OUT)
    servo = gpio.PWM(servo_pin, 50)
    servo.start(0)

    #define range of the color, no_item = white
    color_boundaries = {'red':      ([170, 100, 20], [180, 255, 255]),\
                        'blue':     ([100, 100, 20], [130, 255, 255]),\
                        'no_item':  ([10,    0, 20], [180, 100, 255])}

    count = 0     # counter for aws
    counter = 0   # counter for stock
    cap = cv2.VideoCapture(0)
    mqtt_client = AWSIot().create_mqtt_client()

    while True:

        _, frame = cap.read()
        full_frame = frame
        frame = frame[240:243, 320:323] #only this range of frame used to detect the color
        cv2.rectangle(full_frame,(320,240),(325,245),(0,255,0),1)

        cv2.imshow('Live Aufnahme!', full_frame)
        cv2.waitKey(1)

        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        
        for color_name, (lower, upper) in color_boundaries.items():
            lower = np.array(lower)
            upper = np.array(upper)
            mask = cv2.inRange(hsv, lower, upper)
                    
            if mask.any():
                counter += 1
                
                if color_name == 'red':
                    if counter == 1:
                        StockReport().updateStockCSV('red')
                        print('Red :' ,StockReport().updateStockAWS('red'))
                        servo.ChangeDutyCycle(5)
                        servo.ChangeDutyCycle(0)
                        try:
                            if mqtt_client.connect():
                                AWSIot().publish_data(mqtt_client, count)
                        except connectTimeoutException as e:
                            print(e.message)
                                
                elif color_name == 'blue':
                    if counter == 1:
                        StockReport().updateStockCSV('blue')
                        print('Blue :' ,StockReport().updateStockAWS('blue'))
                        servo.ChangeDutyCycle(1)
                        servo.ChangeDutyCycle(0)
                        try:
                            if mqtt_client.connect():
                                AWSIot().publish_data(mqtt_client, count)
                        except connectTimeoutException as e:
                            print(e.message)

                else:
                    counter = 0

            else:
                servo.ChangeDutyCycle(7)
                servo.ChangeDutyCycle(0)
                
        count += 1
        c = cv2.waitKey(5)
        if c == 27:
            break
                
cv2.destroyAllWindows()
