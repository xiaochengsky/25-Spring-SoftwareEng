from pathlib import Path
from pubsub import pub
import concurrent.futures
import threading
import os
import customtkinter as ctk

from TxDefi.Data.MarketEnums import *

#Paths
library_root = str(Path(__file__).resolve().parent.parent)
idl_path = library_root + '/DataAccess/Decoders/idl'
sounds_path = library_root + '/Resources/sounds'
images_path = library_root + '/Resources/images'
txdefi_logo_path = images_path + '/txdefilogotransbg.ico'
ray_logo_path = images_path + '/raylogo.png'
sol_logo_path = images_path + '/solanalogosmall.png'
configuration_logo_path = images_path + '/configuration.png'
strategies_logo_path = images_path + '/strategies_settings.png'
trade_successful_sound = sounds_path + '/cm_tradesuccess.wav'
bonding_complete_sound = sounds_path + '/bondingcomplete.mp3'
beep_sound = sounds_path + '/cha-ching.wav'
ray_migration = sounds_path + '/raymigration.mp3'

#Topics
topic_token_update_event = "topic_token_update_event"
topic_amm_program_event = "topic_amm_program_event"
topic_incoming_transactions = "topic_incoming_transactions"
topic_wallet_update_event = "wallet_update_event"
topic_ca_call_event = "topic_ca_call_event"
topic_socials_messages = "topic_socials_messages"
topic_gui_alert = "maingui"
topic_token_alerts = "topic_token_alerts"
topic_general_alerts = "topic_general_alerts"
topic_ui_command = "uicommand"
topic_trade_event = 'tradeevent'
topic_strategies_event = 'strategiesevent'

#UI Settings
pumpBgColor = "#1b1d28"
panelBgColor = "#2e303a"
redButtonColor = "#f87171"
highlightedColor = "#343439"
darkBgColor = "#2b2b2b"
darkHighlightColor = "#343439"
disabledColor = "grey"
greenButtonColor = "#4ade80"
highlight_red = 'highlightRed'
highlight_green = 'highlightGreen'
highlightBlue = "highlightBlue"
default_font = 'Malgun Gothic'
tableStyleId = "Custom.Treeview"

#URLs
default_screener_uri = "https://dexscreener.com/solana"
default_solscanner_uri =  "https://solscan.io"
default_solscanner_account_uri = default_solscanner_uri + "/account"
default_solscanner_tx_uri = default_solscanner_uri + "/tx"

#Helpers
def get_default_frame(parent):
    return ctk.CTkFrame(parent, bg_color=darkBgColor, fg_color=darkBgColor)

def get_default_font(size, isBold):
    if(isBold):
        return (default_font, size, 'bold')
    else:
        return (default_font, size)
    
def send(topicName: str, data):
    processThread = threading.Timer(0, _send_task, [topicName, data])
    processThread.daemon = True
    processThread.start()

def _send_task(topic_name: str, data):
    pub.sendMessage(topicName=topic_name, arg1=data)

class Command:
 def __init__(self, command: UI_Command):
    self.command_type = command

class TopicHelper:
    topic_prefix = "topic_"
    last_topic_id = 0
    topic_creation_lock = threading.Lock()

    def __init__(self, topicname: str):
        self.topic_name = topicname

    def send(self, command: Command):
        with concurrent.futures.ThreadPoolExecutor() as executor:
            executor.submit(self._send_task, (command))

    def _send_task(self, arg: Command):
       pub.sendMessage(topicName=self.topic_name, arg1=arg)

    def get_new_topic_name():
        with TopicHelper.topic_creation_lock:
            last_topic_id += 1
            return f"{TopicHelper.topic_prefix}#{TopicHelper.last_topic_id}"
