import os
import telebot
import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion

# Environment variables
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
MQTT_BROKER = os.getenv('MQTT_BROKER', 'localhost')
MQTT_PORT = int(os.getenv('MQTT_PORT', 1883))
MQTT_TOPIC = os.getenv('MQTT_TOPIC', 'telegram/#')
MQTT_USER = os.getenv('MQTT_USER')
MQTT_PASS = os.getenv('MQTT_PASS')

bot = telebot.TeleBot(TELEGRAM_TOKEN)

def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print(f"INFO - Connected to the broker: {MQTT_BROKER}")
        client.subscribe(MQTT_TOPIC)
    else:
        print(f"ERROR - Connection error code: {rc}")

def on_message(client, userdata, msg):
    payload = msg.payload.decode()
    message_text = f"Topic: {msg.topic}\nMessage: {payload}"
    print(f"INFO - Message received: {payload}")
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message_text, parse_mode='Markdown')
    except Exception as e:
        print(f"ERROR - Sending to Telegram: {e}")

client = mqtt.Client(callback_api_version=CallbackAPIVersion.VERSION2)
if MQTT_USER and MQTT_PASS:
    client.username_pw_set(MQTT_USER, MQTT_PASS)

client.on_connect = on_connect
client.on_message = on_message

try:
    print(f"INFO - Connection tentative to: {MQTT_BROKER}...")
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    client.loop_forever()
except Exception as e:
    print(f"ERROR - {e}")
