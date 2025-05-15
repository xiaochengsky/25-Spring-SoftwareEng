import LoggerUtil as logger_util

class FileReaderWriter:
    def __init__(self, filePath, mode = 'w'):
        self.filePath = filePath
        self.mode = mode
    
    def read(self) -> str:    
        return read_file(self.filePath)

    def write(self, text: str):
        write_file(self.filePath, text, self.mode)
    
    def close(self):
        self.file.close()
    
def write_file(filePath, text, mode = 'a'):
    try:
        with open(filePath, mode) as file:
            file.write(text)
        return True
    except Exception as e:
        # Print the error message if something goes wrong
        logger_util.logger.info(f"An error occurred: {e}")
        return False
    
def read_file(filePath)->str:
    try:
        # Open the file in read mode ('r')
        with open(filePath, 'r') as file:
            return file.read()
    except Exception as e:
        # Print the error message if something goes wrong
        logger_util.logger.info(f"An error occurred while reading the file: {e}")
        return None
