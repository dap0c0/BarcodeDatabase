from abc import ABCMeta, abstractmethod
import random
import re
import os
import barcode

# For me, runs only on python 2.7

class BarcodeGenerator(object):
    __metaclass__ = ABCMeta
    MIN_ID_LENGTH = 10
    MAX_ID_LENGTH = 50
    BASE64_CHARS = "abcdefghijklmnopqrstuvwxyz" + \
                    "ABCDEFGHIJKLMNOPQRSTUVWXYZ" + \
                    "0123456789" + \
                    "_-"

    def __init__(self, id_length, add_checksum):
        assert isinstance(id_length, int)
        assert id_length > 0
        self.id_length = id_length
        self.add_checksum = add_checksum
        self.options = dict(add_checksum=self.add_checksum)

        # Barcode class will be overridden by children
        self.barcode_class = None

    @abstractmethod
    def verify_code(self, code):
        pass

    def write(self, code, io):
        ''' Generate the barcode image in svg format.
        Write it into the io stream.'''
        assert io != None

        # Instantiate the driver
        assert self.barcode_class != None, "Barcode Class not instantianted"
        temp = self.barcode_class(code)

        # Write into the stream
        temp.write(io, options=self.options)
        
    def generate_barcode(self, code, directory="./"):
        ''' Generate the barcode image in svg.
        Returns the name of the file, which is randomly
        generated.

        Place the svg file into the supplied directory'''
        assert isinstance(directory, str)

        # Instantiate the driver
        assert self.barcode_class != None, "Barcode Class not instantiated."
        temp = self.barcode_class(code)
        
        # Write into the svg file. Add relevant prefixes
        # to assure that the file is written into the appropriate
        # directory.
        file_id = self._generate_image_id()
        file_id = directory + file_id
        filename = temp.save(file_id, options=self.options)
        return filename

    def _generate_image_id(self):
        ''' Generate a random base64 id of length self.id_length.'''
        result = ""

        for i in range(self.id_length):
            result += random.choice(BarcodeGenerator.BASE64_CHARS)

        return result

class EANBarcodeGenerator(BarcodeGenerator):
    def __init__(self, id_length, add_checksum=False):
        BarcodeGenerator().__init__(id_length, add_checksum)
        self.barcode_class = barcode.get_barcode_class("ean")

    def verify_code(self, code):
        pass

class UPCBarcodeGenerator(BarcodeGenerator):
    def __init__(self, id_length, add_checksum=False):
        BarcodeGenerator.__init__(self, id_length, add_checksum)
        self.barcode_class = barcode.get_barcode_class("upc")

    def verify_code(self, code):
        pass

# gen = UPCBarcodeGenerator(50)
# file_path = gen.generate_barcode(u"060383758783", directory="../")
# file_path = gen.generate_barcode(u"60383758783", directory="")
#
# raises an error! might be better to not allow creation of directories
# file_path = gen.generate_barcode(u"60383758783", directory="barcodes/")
#
# # Exceeding max does not lead to error!
# file_path = gen.generate_barcode(u"160383758783451225")

