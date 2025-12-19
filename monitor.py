import os
import telebot
import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion
import threading

# Environment variables
TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
MQTT_BROKER = os.getenv('MQTT_BROKER', 'localhost')
MQTT_PORT = int(os.getenv('MQTT_PORT', 1883))
MQTT_USER = os.getenv('MQTT_USER')
MQTT_PASS = os.getenv('MQTT_PASS')
MQTT_TOPIC_OUTPUT = os.getenv('MQTT_TOPIC', 'telegram/output/#')
MQTT_TOPIC_INPUT = os.getenv('MQTT_TOPIC', 'telegram/input/#')

bot = telebot.TeleBot(TOKEN)

def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print(f"INFO - Connected to MQTT: {MQTT_BROKER}")
        client.subscribe(MQTT_TOPIC_OUTPUT)
    else:
        print(f"ERROR - Connection to MQTT failed: {rc}")

# Initialization of MQTT client
mqtt_client = mqtt.Client(callback_api_version=CallbackAPIVersion.VERSION2)
if MQTT_USER and MQTT_PASS:
    mqtt_client.username_pw_set(MQTT_USER, MQTT_PASS)

mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message

# From MQTT to Telegram
def on_message(client, userdata, msg):
    payload = msg.payload.decode()
    message_text = f"Topic: {msg.topic}\nMessage: {payload}"
    print(f"INFO - From MQTT: {msg.topic} - {payload}")
    try:
        bot.send_message(CHAT_ID, message_text, parse_mode='Markdown')
    except Exception as e:
        print(f"ERROR - An error occurred while contacting Telegram: {e}")

# From Telegram to MQTT
@bot.message_handler(func=lambda message: True)
def handle_telegram_message(message):
    # Security: answers only if the message comes from the provided Chat ID
    if str(message.chat.id) == str(CHAT_ID):
        payload = message.text
        print(f"Message: {payload}")
        result = mqtt_client.publish(MQTT_TOPIC_INPUT, payload)
        
        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            bot.reply_to(message, f"INFO - Sent to MQTT on `{MQTT_TOPIC_INPUT}`")
        else:
            bot.reply_to(message, "ERROR - An error occurred while publishing to MQTT")
    else:
        print(f"WARNING - Ignored message from unknown user: {message.chat.id}")

def run_mqtt():
    try:
        mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
        mqtt_client.loop_forever()
    except Exception as e:
        print(f"ERROR - MQTT error: {e}")

if __name__ == "__main__":
    print("INFO - Starting bidirectional monitor . . .")
    
    # Starting MQTT on a separate thread (to avoid conflicting Telegram)
    mqtt_thread = threading.Thread(target=run_mqtt, daemon=True)
    mqtt_thread.start()

    # Starting the Telegram Bot (main thread)
    try:
        print("INFO - Telegram Bot is listening . . .")
        bot.infinity_polling()
    except Exception as e:
        print(f"ERROR - Telegram error: {e}")
