import threading
import time

class RateLimiter(threading.Thread):
    def __init__(self, rate_limit: float, log_info: bool = False):  
        threading.Thread.__init__(self, daemon=True)
        self.rate_limit = rate_limit
        self.cancel_event = threading.Event() 
        self.rate_semaphore = threading.Semaphore(rate_limit)       
        self.sems_acquired = 0
        self.log_info = log_info

    def acquire_sem(self)->bool:
        did_acquire = self.rate_semaphore.acquire()
        if did_acquire:
            self.sems_acquired += 1

        return did_acquire
    
    def _reset_num_execs(self):           
        if self.sems_acquired > 0:
            self.rate_semaphore.release(self.rate_limit)
               
            if self.log_info:
                print(f"Calls per second: {self.sems_acquired} Rate Limit: {self.rate_limit}")

            self.sems_acquired = 0

    def run(self):
        while not self.cancel_event.is_set():
            time.sleep(1)
        
            self._reset_num_execs()

    def stop(self):
        self.cancel_event.set()