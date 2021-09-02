import os

from demo_reader.compressed import bzipped, gzipped

extension_map = {
    '.bz2': bzipped.opener,
    '.gz': gzipped.opener
}

class Multireader:
    def __init__(self, filename):
        extension = os.path.splitext(filename) [1]
        opener = extension_map(extension, open)
        self.f = opener(filename, 'rt')

    def close(self):
        self.f.close()

    def read(self):
        return self.f.read()
