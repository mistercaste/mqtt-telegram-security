# mqtt-to-telegram
A container providing full-duplex communication between MQTT (topics) and Telegram.

## Setup Telegram
To allow the container connecting to your Telegram, you need to get some references from the communication app.

### Telgram - Create Bot (Token)
The "father" of all bots is @BotFather. Follow these steps within the Telegram app:
  * Search for **@BotFather** in the Telegram search bar and start the conversation.
  * Type or click the `/newbot` command.
  * Name: Choose a display name (e.g., `MyMqttBot`).
  * Username: Choose a unique username that must end with "bot" (e.g., `mqtt_to_telegram_bot`).
  * Token: BotFather will reply with a message containing the **HTTP API Token** (a string similar to `123456789:ABCdefGhI_jklmNoP`). Save it, as it is the key to controlling the bot.

### Telegram - Get Chat ID
The bot needs to know who to send messages to. The `Chat ID` is the unique numeric code for your account.
  * Search for the @userinfobot bot on Telegram and click "Start."
  * It will immediately respond with your ID (a number, e.g., `987654321`).

Important: Now open a chat with your new bot (the one you created in step 1) and click **"Start"** If you don't start it, the bot won't have permission to message you.

### Security features
The application provides:
- Strict access to a Telegram list of User IDs (comma-separated)
- Telegram notifications when an unauthorized user tries to connect (`TELEGRAM_SECURITY_ALERT_CHANNEL=true`)
- Limited message rates. Default: 5 messages every 10 seconds from a single user

## Docker Compose
```                                                                            
# MQTT topics to Telegram (phone)                                                                                                             
  mqtt-to-telegram:                                                                                                             
    container_name: mqtt-to-telegram                                                                                            
    image: mistercaste/mqtt-to-telegram:latest                                                                                   
    restart: unless-stopped
    network_mode: host                                                                                                           
    environment:                                                                                                                      
      - TELEGRAM_TOKEN=${SECURITY_TELEGRAM_TOKEN}
      - TELEGRAM_ALLOWED_USER_IDS=${TELEGRAM_ALLOWED_USER_IDS_COMMA_SEPARATED}
      - MQTT_BROKER=mqtt.home
      - MQTT_PORT=1883
      - MQTT_USER=${SECURITY_MQTT_USERNAME}
      - MQTT_PASS=${SECURITY_LOW}
      - MQTT_TOPICS_OUTPUT=telegram/output/#,esp32/#    # Monitors multiple topics and their sub-topics
      - MQTT_TOPIC_INPUT=telegram/input/#    # Monitors all sub-topics
      - RATE_LIMIT_MESSAGES=5
      - RATE_LIMIT_WINDOW_SECONDS=10
      - LOG_LEVEL=INFO
      - TELEGRAM_SECURITY_ALERT_CHANNEL=true
```

## Testing
In order to test from the command line your setup, you will need some toolset.
Please install it with `apt install mosquitto-clients`.

### MQTT to Telegram
To test the setup by sending a manual message to the MQTT broker, run:
```
mosquitto_pub \                                                                                                                        
        -h ${MQTT_SERVER} \                                                                                                                 
        -p 1883 \                                                                                                                      
        -u ${MQTT_USERNAME} \                                                                                                               
        -P ${MQTT_PASSWORD} \                                                                                                               
        -t "telegram/output" \                                                                                                
        -m "MQTT to Telegram works fine!"
```
If everything works fine, you should receive a text message in your phone's Telegram.

### MQTT to Telegram (images)
If the manual message sent to the MQTT broker contains an URL to an image, like below:
```
mosquitto_pub \                                                                                                                        
        -h ${MQTT_SERVER} \                                                                                                                 
        -p 1883 \                                                                                                                      
        -u ${MQTT_USERNAME} \                                                                                                               
        -P ${MQTT_PASSWORD} \                                                                                                               
        -t "telegram/output" \                                                                                                
        -m "https://www.google.com/images/branding/googlelogo/1x/googlelogo_white_background_color_272x92dp.png"
```
Then you should receive such an image your phone's Telegram (also mentioning the topic sharing it).

### Telegram to MQTT
To test the other direction, please run the command below, and write something in your Telegram Bot:
```
mosquitto_sub \                                                                                                                        
        -h ${MQTT_SERVER} \                                                                                                                 
        -p 1883 \                                                                                                                      
        -u ${MQTT_USERNAME} \                                                                                                               
        -P ${MQTT_PASSWORD} \                                                                                                               
        -t "telegram/input"
```
If everything works fine, you should read your Telegram message in the topic-subscriber, and have a message `Sent to telegram/input` in your Telegram chat.
