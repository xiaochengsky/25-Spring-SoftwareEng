import threading
import asyncio
import websockets
import logging
import json
from websockets.exceptions import ConnectionClosedOK, ConnectionClosedError
from abc import abstractmethod
import asyncio
import concurrent.futures
import TxDefi.Utilities.LoggerUtil as logger_util

class MarketDataSocket(threading.Thread):    
    def __init__(self, wss_uri: str, custom_ping = True):
        threading.Thread.__init__(self, daemon=True)
        self.name = MarketDataSocket.__name__
        self.wss_uri = wss_uri
        self.cancel_token = threading.Event()
        self.receive_queue = asyncio.Queue()  # Queue for incoming messages 
        self.write_queue = asyncio.Queue()  # Queue for outgoing messages
        self.custom_ping = custom_ping
        self.lock = threading.Lock()
        self.paused_event = threading.Event()
        self.paused_event.set()
        self.websocket = None
       
    def stop(self):
        self.cancel_token.set()
  
    def toggle(self):
        if self.paused_event.is_set():
            self.paused_event.clear()
        else:
            self.paused_event.set()

    def send_request_no_wait(self, request: str):
        if self.is_alive():
            #print("Sending request: " + request) #DELETE
            with concurrent.futures.ThreadPoolExecutor() as executor:
                loop = asyncio.new_event_loop()  # Create a new event loop
                asyncio.set_event_loop(loop)  # Set it as the current loop
                future = executor.submit(loop.run_until_complete, self.send_request(request))  # Run async_task() inside the executor
                result = future.result()  # Get the result from the future
    
    async def send_request(self, request: str):
        await self.write_queue.put(request)

    async def _ping(self):
        if self.websocket:
            while not self.cancel_token.is_set():
                try:
                    #print(f"Pinging {self.wss_uri}")
                    await self.websocket.send(json.dumps(self.get_ping_request()))                
                    await asyncio.sleep(30)   
                except Exception as e:
                    print(f"Error sending ping: {e}")
          
    async def _send_requests(self):
        try:
            while not self.cancel_token.is_set():
                request = await self.write_queue.get()
                if request:
                    await self.websocket.send(request)
        except Exception as e:
            print("Error in _send_requests " + str(e))

    async def connect(self):
        if not self.custom_ping:
            ping_interval = 30 #Set an auto ping using websocket layer
        else:
            ping_interval = None

        while not self.cancel_token.is_set():
            tasks = []
            try:
                async with websockets.connect(self.wss_uri, ping_interval = ping_interval) as websocket:
                    print("Socket initialized " + self.wss_uri)
                    self.websocket = websocket
          
                    logging.getLogger('websockets.client').setLevel(logging.ERROR)
    
                    # Start the ping and send requests task
                    if self.custom_ping:
                        tasks.append(asyncio.create_task(self._ping()))

                    tasks.append(asyncio.create_task(self._send_requests()))

                    self._init()                    

                    # Start the listening task
                    await self._read_socket()
          
            except ConnectionClosedError as e:
                print("Error with websocket " + str(e))
                if self.cancel_token.is_set():
                    break
            finally:
                if self.cancel_token.is_set():
                    await self.write_queue.put(None) #Make _send_requests kick out of blocking state
                    for task in tasks:
                        task.cancel() #TODO this doesn't work
                        tasks.clear()
                    break
          
    async def _read_socket(self):        
        while not self.cancel_token.is_set():
            if self.paused_event.wait():                
                received = await self.websocket.recv()

                if received:
                    self.process_data(received)

    def run(self):
        asyncio.run(self.connect())

    @abstractmethod
    def _init(self):
        pass
    
    @abstractmethod
    async def process_data(self, data: str):
        pass
    
    @staticmethod
    def get_ping_request():
        return  {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "ping"
        }