from discord.ext import commands
from pubsub import pub
import threading
import discord
from TxDefi.Data.WebMessage import WebMessage
from TxDefi.Data.WebMessage import WebMessage
from TxDefi.Abstractions.AbstractQueueProcessor import AbstractQueueProcessor
import TxDefi.Data.Globals as globals

#Listen for channel updates
class DiscordMonitor(AbstractQueueProcessor[WebMessage]):
    def __init__(self, bot_token: str, channels: list[str], pub_topic_name: str):
        AbstractQueueProcessor.__init__(self)
        
        # Intents to allow reading messages
        intents = discord.Intents.default()
        intents.messages = True  # Allows reading message content
        intents.message_content = True  # Required for message content in DMs and guilds
        self.subbed_channels = channels
        self.pub_topic_name = pub_topic_name
        self.bot_token = bot_token
        self.bot = commands.Bot(command_prefix="!", intents=intents)
        
        @self.bot.event
        async def on_ready():
            print(f"Bot logged in as {self.bot.user}")

        @self.bot.event
        async def on_message(message):
            # Ignore messages from the bot itself
            if message.author == self.bot.user:
                return

            # Print message details
            #print(f"Message from {message.author}: {message.content} in {message.channel.name}")

            #Process specific channels
            for i in range(len(self.subbed_channels)):            
                if self.subbed_channels[i] in message.channel.name:
                    web_message = WebMessage()
                    web_message.appname = 'discord'
                    web_message.timestamp = str(message.created_at)
                    web_message.user = message.author.name
                    web_message.message = message.content

                    self.message_queue.put_nowait(web_message)
                    pub.sendMessage(topicName=globals.topic_socials_messages, arg1=web_message)
                    #print(f"Message in your channel: {message.content}")
                    return

    def init_processor(self):
        pass

    def process_message(self, message: WebMessage):
        #Notify topic subs
        pub.sendMessage(topicName=self.pub_topic_name, arg1=message)

    def run(self):
        threading.current_thread().name = f"{self.name}-{threading.get_ident()}"
        try:
            self.bot.run(self.bot_token)
        except Exception as e:
            print("DiscordMonitor: bot token not correct. Could not connect to discord server.")
    

