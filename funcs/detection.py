import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from urls.urls import ENDPOINT


def detection1(*args):
    try:

        pass

    except Exception as e: 
        return {
            "status":"error",
            "reason":str(e)
        }