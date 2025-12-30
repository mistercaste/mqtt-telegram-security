import os
import telebot
import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion
import threading
import re
import requests  # To download the image locally
import io        # To handle data in memory

# Environment variables
TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
MQTT_BROKER = os.getenv('MQTT_BROKER', 'localhost')
MQTT_PORT = int(os.getenv('MQTT_PORT', 1883))
MQTT_USER = os.getenv('MQTT_USER')
MQTT_PASS = os.getenv('MQTT_PASS')
MQTT_TOPICS_OUTPUT = os.getenv('MQTT_TOPICS_OUTPUT', 'telegram/output/#,mt32/#').split(',')
MQTT_TOPIC_INPUT = os.getenv('MQTT_TOPIC_INPUT', 'telegram/input')

bot = telebot.TeleBot(TOKEN)

# Regex to match image names URLs
IMAGE_URL_PATTERN = re.compile(
    r'^https?://[^/]+(?::\d+)?/.*\.(jpg|jpeg|png|gif|webp)(\?.*)?$',
    re.IGNORECASE
)

def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print(f"INFO - Connesso a MQTT: {MQTT_BROKER}")
        for topic in MQTT_TOPICS_OUTPUT: # Subscribe to multiple MQTT topics
            topic = topic.strip()
            client.subscribe(topic)
            print(f"INFO - Subscribed to topic: {topic}")
    else:
        print(f"ERROR - MQTT connection failed with code: {rc}")

# MQTT to Telegram (text/images)
def on_message(client, userdata, msg):
    payload = msg.payload.decode().strip()
    print(f"INFO - From MQTT [{msg.topic}]: {payload}")

    try:
        match = IMAGE_URL_PATTERN.match(payload)
        if match:
            # Extract the original image file extension ('png', 'jpg'...)
            ext = match.group(1).lower()
            caption = f"Topic: {msg.topic}"
            
            print(f"INFO - Downloading ({ext}) image . . .")
            
            # Use a context manager (with) to handle the HTTP request
            with requests.get(payload, timeout=15, stream=True) as response:
                response.raise_for_status()
                
                # Use BytesIO to load the image in memory
                with io.BytesIO(response.content) as photo_buffer:
                    photo_buffer.name = f"snapshot.{ext}"                    
                    # If GIF sends as animation, to keep it dynamic
                    if ext == 'gif':
                        bot.send_animation(CHAT_ID, photo_buffer, caption=caption)
                        print(f"INFO - GIF sent")
                    else:
                        bot.send_photo(CHAT_ID, photo_buffer, caption=caption)
                        print(f"INFO - Image {photo_buffer.name} sent")
            # Note on memory usage: once outside the 'with' the buffer gets automatically garbage collected                
        else:
            message_text = f"Topic: {msg.topic}\nMessage: {payload}"
            bot.send_message(CHAT_ID, message_text, parse_mode='Markdown')
            print(f"INFO - Message sent to Telegram")
            
    except Exception as e:
        print(f"ERROR - Errore durante l'invio o il download: {e}")

# MQTT client initialization
mqtt_client = mqtt.Client(callback_api_version=CallbackAPIVersion.VERSION2)
if MQTT_USER and MQTT_PASS:
    mqtt_client.username_pw_set(MQTT_USER, MQTT_PASS)
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message

# Telegram to MQTT
@bot.message_handler(func=lambda message: True)
def handle_telegram_message(message):
    if str(message.chat.id) == str(CHAT_ID):
        payload = message.text
        result = mqtt_client.publish(MQTT_TOPIC_INPUT, payload)
        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            bot.reply_to(message, f"Sent to `{MQTT_TOPIC_INPUT}`")
        else:
            bot.reply_to(message, "ERROR - An error occurred while publishing to MQTT")

def run_mqtt():
    try:
        mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
        mqtt_client.loop_forever()
    except Exception as e:
        print(f"ERROR - Error in MQTT loop: {e}")

if __name__ == "__main__":
    print("INFO - Starting advanced monitoring . . .")
    mqtt_thread = threading.Thread(target=run_mqtt, daemon=True)
    mqtt_thread.start()

    try:
        bot.infinity_polling()
    except Exception as e:
        print(f"ERROR - Telegram bot error: {e}")
