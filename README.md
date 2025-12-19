# mqtt-to-telegram
A container providing full-duplex communication between MQTT (topics) and Telegram.

## Telegram BOT
To allow the container connecting to your Telegram, you need to get some references from the communication app.

### Telgram - Creating the Bot (Getting the Token)
The "father" of all bots is @BotFather. Follow these steps within the Telegram app:
  * Search for **@BotFather** in the Telegram search bar and start the conversation.
  * Type or click the `/newbot` command.
  * Name: Choose a display name (e.g., `MyMqttBot`).
  * Username: Choose a unique username that must end with "bot" (e.g., `mqtt_to_telegram_bot`).
  * Token: BotFather will reply with a message containing the **HTTP API Token** (a string similar to `123456789:ABCdefGhI_jklmNoP`). Save it, as it is the key to controlling the bot.

### Telegram - Getting your Chat ID
The bot needs to know who to send messages to. The `Chat ID` is the unique numeric code for your account.
  * Search for the @userinfobot bot on Telegram and click "Start."
  * It will immediately respond with your ID (a number, e.g., `987654321`).

Important: Now open a chat with your new bot (the one you created in step 1) and click **"Start"** If you don't start it, the bot won't have permission to message you.

## Docker Compose
```                                                                            
# MQTT topics to Telegram (phone)                                                                                                             
  mqtt-to-telegram:                                                                                                             
    container_name: mqtt-to-telegram                                                                                            
    image: mistercaste/mqtt-to-telegram:latest                                                                                   
    restart: unless-stopped                                                                                                           
    environment:                                                                                                                      
      - TELEGRAM_TOKEN=your_token
      - TELEGRAM_CHAT_ID=your_chat_id
      - MQTT_BROKER=192.168...
      - MQTT_PORT=1883
      - MQTT_TOPIC_OUTPUT=telegram/output/#    # Monitors all sub-topics
      - MQTT_TOPIC_INPUT=telegram/input/#    # Monitors all sub-topics
      - MQTT_USER=my_username
      - MQTT_PASS=********
```

## Testing MQTT
In order to test from the command line your setup, you will need to `apt install mosquitto-clients`.

A. To test the setup by sending a manual message to the MQTT broker, run:
 ```
 mosquitto_pub \                                                                                                                        
         -h ${SERVER} \                                                                                                                 
         -p 1883 \                                                                                                                      
         -u ${USERNAME} \                                                                                                               
         -P ${PASSWORD} \                                                                                                               
         -t "telegram/output/helloworld" \                                                                                                
         -m "Your installation of mqtt-to-telegram works!" 
 ```
 If everything works fine, you should receive a message in your phone's Telegram.

B. To test the other direction, please run the command below, and write something in your Telegram Bot:
 ```
 mosquitto_sub \                                                                                                                        
         -h ${SERVER} \                                                                                                                 
         -p 1883 \                                                                                                                      
         -u ${USERNAME} \                                                                                                               
         -P ${PASSWORD} \                                                                                                               
         -t "telegram/input/"
 ```
 If everything works fine, you should read your Telegram message in the topic-subscriber.

