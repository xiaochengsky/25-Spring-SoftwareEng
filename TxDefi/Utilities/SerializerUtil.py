from abc import abstractmethod
import json
from typing import TypeVar, Generic
from FileUtil import FileReaderWriter
from pathlib import Path
import threading

T = TypeVar('T')
        
class ObjectFactory:
    @abstractmethod
    def create(self):
        pass

def serialize(object):
    return json.dumps(object.to_dict())

def deserialize(jsonString: str, objectFactory: ObjectFactory):
    jsonItems = json.loads(jsonString)
    object = objectFactory.create(**jsonItems)

    return object

class StateSaverLoader:
    def __init__(self, filePath: str):
        
        self.filePath = filePath
        self.fileWriter = FileReaderWriter(self.filePath)
        self.lock = threading.Lock()
    
    def get_lock(self):
        return self.lock
    
    def save_to_file(self, object):
        jsonString = json.dumps(object)
        self.fileWriter.write(jsonString)

    def load_from_file(self)->dict[str, str]:
        file_path = Path(self.filePath)
        
        if file_path.is_file():
            jsonString = self.fileWriter.read()

            if jsonString and len(jsonString) > 0:
                jsonItems = json.loads(jsonString)
                    
                return jsonItems
        
        return dict()

    