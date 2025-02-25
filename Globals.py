import time
from enum import Enum
GROCERY_NAME = "grocery"
HOME_BEAUTY_BABY_NAME = "home-beauty-baby"
JF_NAME = "joe-fresh"

class Department(Enum):
    GROCERY_NAME = "grocery"
    HOME_BEAUTY_BABY_NAME = "home-beauty-baby"
    JF_NAME = "joe-fresh"

# TODO: remove this! will be deprecated after
# reformatting code with DateFormatter
TIME_FORMAT = "%Y-%m-%d"

# TODO: Remove this!
def today():
    return time.strftime(TIME_FORMAT)

if __name__ == "__main__":
    formatter = DateFormatter()
    print(formatter._date_format)
