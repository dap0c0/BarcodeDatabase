import sys
import os
from abc import ABC, abstractmethod

class FileInterface(ABC):
    def __init__(self, file_path: str):
        assert isinstance(file_path, str)
        self.file_path = file_path
        
        # Open the file for writing
        self.wfile = open(self.file_path, "w")

    @abstractmethod
    def append(self, data: object):
        pass

    def close(self):
        self.wfile.close()

class LinkWriter(FileInterface):
    def append(self, data: str):
        ''' Append the link to the end of the file.'''
        self.wfile.write(data + "\n")

def test_writing_existing_file():
    lw = LinkWriter("test_linkwriter.txt")
    lw.append("bruh")
    lw.append("how are you!")
    lw.append("hellooooooo")
    lw.close()

def test_opening_file_nonexistent():
    lw = LinkWriter("non_existent.txt")
    lw.append("bruh")
    lw.append("how are you!")
    lw.append("hellooooooo")
    lw.close()

    # if __name__ == "__main__":
    # test_writing_existing_file()
    # test_opening_file_nonexistent()
