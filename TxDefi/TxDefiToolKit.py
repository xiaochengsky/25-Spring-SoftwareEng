import ast
import threading
import os
import json
from dotenv import load_dotenv
from solders.keypair import Keypair
import TxDefi.Data.Globals as globals
from TxDefi.Data.TradingDTOs import *
from TxDefi.DataAccess.Blockchains.Solana.PumpAmmTxBuilder import PumpAmmTxBuilder
from TxDefi.DataAccess.Blockchains.Solana.PumpTxBuilder import PumpTxBuilder
from TxDefi.DataAccess.Blockchains.Solana.RaydiumTxBuilder import RaydiumTxBuilder
from TxDefi.DataAccess.Blockchains.Solana.RiskAssessor import RiskAssessor
from TxDefi.DataAccess.Blockchains.Solana.grpc.GRpcStreamer import YellowstoneGrpcStreamReader
from TxDefi.Engines.TokenInfoRetriever import TokenInfoRetriever
from TxDefi.Engines.DiscordMonitor import DiscordMonitor
from TxDefi.Engines.WebhookServer import WebhookServer
from TxDefi.Engines.TokenAccountsMonitor import TokenAccountsMonitor
from TxDefi.Engines.CaCallsMonitor import CaCallsMonitor
from TxDefi.Managers.MarketManager import MarketManager
from TxDefi.Managers.TradesManager import TradesManager
from TxDefi.Managers.WalletTracker import WalletTracker
from TxDefi.DataAccess.Blockchains.Solana.SubscribeSocket import SubscribeSocket
from TxDefi.DataAccess.Blockchains.Solana.AccountSubscribeSocket import AccountSubscribeSocket
from TxDefi.DataAccess.Blockchains.Solana.SolanaRpcApi import SolanaRpcApi
from TxDefi.DataAccess.Blockchains.Solana.SolanaTradeExecutor import SolanaTradeExecutor
from TxDefi.DataAccess.Blockchains.Solana.SolPubKey import SolPubKey
from TxDefi.DataAccess.Decoders.JupDataDecoder import JupDataDecoder
from TxDefi.DataAccess.Decoders.PumpAmmDataDecoder import PumpAmmDataDecoder
from TxDefi.DataAccess.Decoders.RaydiumDataDecoder import RaydiumDataDecoder
from TxDefi.DataAccess.Decoders.TransactionsDecoder import TransactionsDecoder
from TxDefi.DataAccess.Decoders.MessageDecoder import MessageDecoder
from TxDefi.DataAccess.Decoders.SolanaLogsDecoder import SolanaLogsDecoder
from TxDefi.DataAccess.Decoders.PumpDataDecoder import *
from TxDefi.Strategies.StrategyFactory import StrategyFactory
from TxDefi.Utilities.DEX.RugCheckerApi import RugCheckerApi

#Tx Defi Toolkit Primary Setup
class TxDefiToolKit(threading.Thread):
    default_none = "None"

    def __init__(self, disable_social_media = False):
        threading.Thread.__init__(self, daemon=True)
        self.name = TxDefiToolKit.__name__
        self.disable_social_media = disable_social_media

        wdir = os.getcwd()
        load_dotenv(wdir + "/.env", override=True)
        self.discord_monitor = None
        self.ifttt_webhook_monitor = None

        #RPC Credemtials
        # os.environ('TX_SUBS_WITH_GEYSER') = 'true'
        use_geyser = True if os.getenv('TX_SUBS_WITH_GEYSER').lower() == 'true' else False
        rpc_http_uri = os.getenv('HTTP_RPC_URI')
        rpc_backup_uri = os.getenv('HTTP_RPC_URI_BACKUP', None)

        if rpc_backup_uri == "None":
            use_backup_rpc = False
            rpc_backup_uri = None
        else:
            use_backup_rpc = True

        rpc_wss_uri = os.getenv('WSS_RPC_URI')
        rpc_geyser_uri = os.getenv('GEYSER_WSS')
        rpc_rate_limit = int(os.getenv('RPC_RATE_LIMIT', '10'))

        #Default Keys      
        #FYI you can also set custom payers in custom strategies
        payer_keys_hash = os.getenv('PAYER_HASH') #TODO Add encryption loading
        self.solana_rpc_api = SolanaRpcApi(rpc_http_uri, rpc_wss_uri, rpc_rate_limit, rpc_backup_uri)
        default_signer_keypair = Keypair.from_base58_string(payer_keys_hash)

        #Custom Strategies Path
        custom_strategies_path = os.getenv("CUSTOM_STRATEGIES_PATH") 

        #Social Credentials (Optional)
        if not disable_social_media:
            discord_pubkey = os.getenv("DISCORD_PUBLIC_KEY", None)
            discord_botkey = os.getenv("DISCORD_BOT_TOKEN", None)
            discord_channels_subs = os.getenv("DISCORD_CHANNEL_NAMES", None)
            
            if discord_channels_subs:
                discord_channels_subs = ast.literal_eval(discord_channels_subs)            
                self.discord_monitor = DiscordMonitor(discord_botkey, discord_channels_subs, globals.topic_socials_messages)

            #IFTTT Server Configuration (Requires an IFTTT Pro Subscription)
            #Used to receive customized phone notifications; used to get immediate  X posts and more
            ifttt_server_port = os.getenv("IFTTT_WEBHOOK_PORT", None)
            ifttt_webhook_name = os.getenv("IFTTT_WEBHOOK_NAME", None)

            if ifttt_server_port:
                ifttt_server_port = int(ifttt_server_port)
                self.ifttt_webhook_monitor = WebhookServer(ifttt_webhook_name, ifttt_server_port, globals.topic_socials_messages, discord_pubkey)
      
        # Current ray idl does not load; had to build a custome decoder; keeping this here for future reference in case we get the idl working
        # ray_amm_client = SolanaTradeExecutor.create_program("TxDefi/DataAccess/Decoders/idl/raydiumstandard_sfm.json", 
        #                                                 signer_wallet, solana_rpc_api.async_client)
        #Init anchor Program so we can take advantage of the decoder  
        pump_client = SolanaTradeExecutor.create_program(globals.idl_path + "/pumpidl.json",
                                                         default_signer_keypair, self.solana_rpc_api.async_client)
        #self.pump_amm_client = SolanaTradeExecutor.create_program(globals.idl_path + "/pump_ammedit.json", #FIXME DELETE
        #                                                 default_signer_keypair, solana_rpc_api.async_client)
        jup_client = SolanaTradeExecutor.create_program(globals.idl_path + "/jupsolanafm.json",
                                                         default_signer_keypair, self.solana_rpc_api.async_client)
    
        jup_program_address = str(jup_client.program_id)
        
        jup_instruction_decoder = JupDataDecoder(jup_program_address, jup_client.coder.instruction, MessageDecoder.base58_encoding)
        ray_instruction_decoder = RaydiumDataDecoder(RaydiumTxBuilder.RAYDIUM_V4_PROGRAM_ADDRESS, MessageDecoder.base58_encoding)
        pump_decoder = PumpDataDecoder(PumpTxBuilder.PUMP_PROGRAM_ADDRESS, pump_client.coder, MessageDecoder.base58_encoding)
        pump_amm_decoder = PumpAmmDataDecoder(PumpAmmTxBuilder.PUMP_AMM_PROGRAM_ADDRESS, MessageDecoder.base58_encoding)
        self.pump_decoder = pump_amm_decoder
        
        self.sockets : dict[SupportedPrograms, SubscribeSocket] = {}
        self.wallet_transaction_socket = AccountSubscribeSocket(rpc_wss_uri, globals.topic_wallet_update_event, False) #Custom ping doesn't work for accountSubscribe so it's disabled here

        transactions_decoder = TransactionsDecoder()
        #transactions_decoder.add_data_decoder(jup_program_address, jup_instruction_decoder)
        transactions_decoder.add_data_decoder(RaydiumTxBuilder.RAYDIUM_V4_PROGRAM_ADDRESS, ray_instruction_decoder)
        transactions_decoder.add_data_decoder(PumpTxBuilder.PUMP_PROGRAM_ADDRESS, pump_decoder)
        transactions_decoder.add_data_decoder(PumpAmmTxBuilder.PUMP_AMM_PROGRAM_ADDRESS, pump_amm_decoder)
        pump_logs_decoder = SolanaLogsDecoder(PumpTxBuilder.PUMP_PROGRAM_ADDRESS, self.solana_rpc_api, pump_decoder, transactions_decoder)
        
        #Auto Trade Settings
        auto_buy_in = float(os.getenv("AUTO_BUY_IN_SOL", ".001"))
        default_slippage = float(os.getenv('DEFAULT_SLIPPAGE', "50"))
        default_priority_fee = float(os.getenv('DEFAULT_PRIORITY_FEE', ".001"))    
        auto_trade_settings = SwapOrderSettings(Amount.sol_ui(auto_buy_in), Amount.percent_ui(default_slippage), Amount.sol_ui(default_priority_fee))
             
        #Setup Managers and Monitors
        self.wallet_tracker = WalletTracker(self.wallet_transaction_socket, self.solana_rpc_api)

        if os.path.exists(custom_strategies_path) and os.path.isdir(custom_strategies_path):
            strategy_factory = StrategyFactory(custom_strategies_path)
        else:
            strategy_factory = None
            print("TxDefiToolKit: No strategies to load from " + custom_strategies_path +  ". Check your configuration.")

        tokens_info_retriever = TokenInfoRetriever(self.solana_rpc_api, pump_decoder, transactions_decoder, use_backup_rpc)        
        
        #Need the events coder for pump logs
        self.risk_assessor = RiskAssessor(self.solana_rpc_api)
        self.token_accounts_monitor = TokenAccountsMonitor(self.solana_rpc_api, tokens_info_retriever, pump_logs_decoder, self.risk_assessor)
        self.market_manager = MarketManager(self.solana_rpc_api, self.token_accounts_monitor, self.risk_assessor)

        default_payer = SolPubKey(payer_keys_hash, SupportEncryption.NONE, False, Amount.sol_ui(auto_buy_in))
        wallet_settings = SignerWalletSettings(default_payer)
        
        self.trades_manager = TradesManager(self.solana_rpc_api, self.market_manager, self.wallet_tracker, strategy_factory, auto_trade_settings, wallet_settings)       
        
        self.social_calls_monitor = CaCallsMonitor()

        #Setup Geyser Connections (Optional, need access to Geyser RPC)
        if use_geyser and rpc_geyser_uri:
            #Init Transaction Subscribe (only compatible with geyser rpc sockets)
            print("Using geyser rpc for token updates")
            programs = [PumpAmmTxBuilder.PUMP_AMM_PROGRAM_ADDRESS, PumpTxBuilder.PUMP_PROGRAM_ADDRESS, RaydiumTxBuilder.RAYDIUM_V4_PROGRAM_ADDRESS]
            if rpc_geyser_uri.startswith("ws"):
                transaction_request = json.dumps(SolanaRpcApi.get_geyser_transaction_sub_request(programs))
                amm_transaction_socket = SubscribeSocket(rpc_geyser_uri, transactions_decoder, globals.topic_incoming_transactions, [transaction_request], True)
            else:
                amm_transaction_socket = YellowstoneGrpcStreamReader(rpc_geyser_uri, self.solana_rpc_api, transactions_decoder, programs)
                
            self.sockets[SupportedPrograms.ALL] = amm_transaction_socket
        else:
            #Init Logs Subscribe            
            ray_program_sub_request = json.dumps(SolanaRpcApi.get_logs_sub_request([RaydiumTxBuilder.RAYDIUM_V4_PROGRAM_ADDRESS]))
            pump_program_sub_request = json.dumps(SolanaRpcApi.get_logs_sub_request([PumpTxBuilder.PUMP_PROGRAM_ADDRESS]))
            pump_amm_program_sub_request = json.dumps(SolanaRpcApi.get_logs_sub_request([PumpAmmTxBuilder.PUMP_AMM_PROGRAM_ADDRESS]))
            
            raydium_logs_decoder = SolanaLogsDecoder(RaydiumTxBuilder.RAYDIUM_V4_PROGRAM_ADDRESS, self.solana_rpc_api, ray_instruction_decoder, transactions_decoder)
            pump_amm_logs_decoder = SolanaLogsDecoder(PumpAmmTxBuilder.PUMP_AMM_PROGRAM_ADDRESS, self.solana_rpc_api, pump_amm_decoder, transactions_decoder)
        
            #Need 3 sockets to differentiate log messages
            amm_logs_socket = SubscribeSocket(rpc_wss_uri, raydium_logs_decoder, globals.topic_amm_program_event, [ray_program_sub_request], True)
            pump_logs_socket = SubscribeSocket(rpc_wss_uri, pump_logs_decoder, globals.topic_amm_program_event, [pump_program_sub_request], True)
            pump_amm_logs_socket = SubscribeSocket(rpc_wss_uri, pump_amm_logs_decoder, globals.topic_amm_program_event, [pump_amm_program_sub_request], True)

            self.sockets[SupportedPrograms.RAYDIUMLEGACY] = amm_logs_socket
            self.sockets[SupportedPrograms.PUMPFUN_AMM] = pump_amm_logs_socket
            self.sockets[SupportedPrograms.PUMPFUN] = pump_logs_socket
              
        self.sockets[SupportedPrograms.GENERAL_WALLET] = self.wallet_transaction_socket
        self.cancel_event = threading.Event() #Create an Event object
        self.start()

    def toggle_socket_listener(self, program: SupportedPrograms):
        socket = self.sockets.get(program)

        if socket:
            socket.toggle()

    def run(self):
        if not self.disable_social_media:
            self.social_calls_monitor.start()

            if self.discord_monitor:
                self.discord_monitor.start()

            if self.ifttt_webhook_monitor:
                self.ifttt_webhook_monitor.start()   

        for socket in self.sockets.values():
            time.sleep(.5)
            socket.start() 
 
        self.risk_assessor.start()
        self.wallet_tracker.start()
        self.market_manager.start()
        self.trades_manager.start()        
        self.solana_rpc_api.start()   
        self.token_accounts_monitor.start()
        self.cancel_event.wait()

    def shutdown(self):
        if not self.disable_social_media:
            self.social_calls_monitor.stop()
            
            if self.discord_monitor:
                self.discord_monitor.stop()
        
            if self.ifttt_webhook_monitor:
                self.ifttt_webhook_monitor.stop()   

        for socket in self.sockets.values():
            socket.stop() 
  
        self.wallet_tracker.stop()
        self.market_manager.stop()        
        self.trades_manager.stop()          
        self.solana_rpc_api.stop()   
        self.risk_assessor.stop()
        self.cancel_event.set() 
        
