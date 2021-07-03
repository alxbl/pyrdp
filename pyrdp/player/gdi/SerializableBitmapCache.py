from typing import Dict

from PySide2.QtCore import QByteArray
from PySide2.QtGui import QImage


class SerializableBitmapCache:

    def __init__(self, cache: Dict[int, QImage]):
        super().__init__()
        self.cache = cache

    def __getstate__(self):
        state = []
        for key, qImage in self.cache.items():
            data = {
                'width': qImage.width(),
                'height': qImage.height(),
                'format': qImage.format(),
                'data': QByteArray(bytes(qImage.bits()))
            }
            state.append((key, data))
        return state

    def __setstate__(self, state):

        self.cache = {}
        for key, data in state:
            self.cache[key] = QImage(width=data['width'],
                                     height=data['height'],
                                     format=data['format'],
                                     data=data['data'])
