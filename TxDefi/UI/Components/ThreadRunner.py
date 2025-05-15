import threading
import time
import threading

class ThreadRunner(threading.Thread):    
    def __init__(self, interval):
        threading.Thread.__init__(self, daemon=True)
        self.name = ThreadRunner.__name__
        self.lock = threading.Lock()
        self.cancelToken = threading.Event()
        self.interval = interval
        self.callbacks = {}

    def add_callback(self, id, callback):
        with self.lock:
            if id not in self.callbacks:
                self.callbacks[id] = callback

    def delete_callback(self, id):
        with self.lock:
            if id in self.callbacks:
                self.callbacks.pop(id)

    def run(self):
        threading.current_thread().name = f"{self.name}-{threading.get_ident()}"
        startTime = time.time() #Record start time
        secondsElapsed = 0

        while not self.cancelToken.is_set():          
            # Calculate target time for the next second
            secondsElapsed += self.interval
            sleepTime = calc_sleep_time(startTime, secondsElapsed)
            
            if sleepTime > 0:
                time.sleep(sleepTime)
            
            with self.lock:
                for callback in self.callbacks.values():
                    try:
                        callback()
                    except:
                        pass
         
    def stop(self):
        self.cancelToken.set()      

def calc_sleep_time(startTime, secondsElapsed):
    nextTime = startTime + secondsElapsed
    currentTime = time.time()
    sleepTime = max(0, nextTime - currentTime)  # Calculate remaining time to sleep

    return sleepTime  
   