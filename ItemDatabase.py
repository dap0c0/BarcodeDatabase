import json
import re

def pretty_print(dictionary, indent_spaces):
    assert isinstance(dictionary, dict)
    assert isinstance(indent_spaces, int)
    json_formatted = json.dumps(dictionary, indent=indent_spaces)
    print(json_formatted)

#--------- Basic data manipulation ------- #
class ItemDatabase():
    INDENT_SPACES = 4
    INVALID_CHARS = "{}[]()<>^"
    MAX_REGEX_SIZE = 500

    def __init__(self, file_path):
        assert isinstance(file_path, str)
        self.file_path = file_path

    def _check_valid_regex(self, regex):
        ''' Check whether the regex string
        qualifies for search.'''
        assert isinstance(regex, str)

        if len(regex) > ItemDatabase.MAX_REGEX_SIZE:
            return False

        for c in ItemDatabase.INVALID_CHARS:
            if c in regex:
                return False

        return True

    def search_matches(self, regex):
        '''
        Search through all dictionary items to find match.
        Return json of all items that match.
        '''
        assert isinstance(regex, str)

        # If file does not exist, bubble exception.
        with open(self.file_path, "r") as rfile:
            if not self._check_valid_regex(regex):
                raise re.error("Invalid regex.")
        
            # Start matching by iterating through each item.
            # If the string is present in the item
            # title, return the entire item. If the string is present
            # as a key value of the item, return the entire item.
            items_dict = json.load(rfile)
            pattern_str = ".*%s.*" % regex
            pattern_compiled = re.compile(pattern_str, re.IGNORECASE)
            matches = {}

            for item_title in items_dict:
                item_title = str(item_title)
                match = pattern_compiled.search(item_title)

                # Append the json to matches
                if match:
                    matches[item_title] = items_dict[item_title]

                # String not in title! Search the item's values instead.
                else:
                    item = items_dict[item_title]
                    
                    for key in item:
                        value = item[key]
                        match = pattern_compiled.search(value)

                        if match:
                            matches[item_title] = items_dict[item_title]

        return matches

    def write_data(self,
                product_name,
                url="",
                brand="",
                flavor="",
                weight="",
                volume="",
                count="",
                company="",
                manufacturer="",
                upc="",
                ean="",
                asin="",
                price="",
                indent_spaces=INDENT_SPACES):
        ''' Write data to the supplied file path.

            In the supplied file (which acts as a semi-database/table),
            items will always be stored by their product title.'''

        # Construct dictionary iteratively.
        # If alternating arguments, always skip self,
        # product_name, indent_spaces.
        inputted_json = locals()
        inputted_json.pop("self")
        inputted_json.pop("product_name")
        inputted_json.pop("indent_spaces")

        # If file does not exist, bubble exception
        with open(self.file_path, "r+") as rwfile:
            values_dict = json.load(rwfile)
            
            # Update the original values dictionary
            values_dict[product_name] = inputted_json
            
            # Rewrite the dictionary into the file
            rwfile.seek(0)
            json.dump(values_dict, rwfile, indent=indent_spaces)

#-------------- Test code ----------------#
def test():
    db = ItemDatabase("test_file_json.txt")

    def test_write_data():
        db.write_data("Oreos")
        db.write_data("Oreos party pack")
        db.write_data("Oreos White")
        db.write_data("Oreos white")
        db.write_data("OREOS WHITE")
        db.write_data("Real Canadian Water", volume="500mL", upc="060383013422")

    def test_search():
        search = lambda db, regex: db.search_matches(regex)
        matches = search(db, "water")
        pretty_print(matches, db.INDENT_SPACES)

    # test_write_data()
    test_search()
if __name__ == "__main__":
    test()
    
