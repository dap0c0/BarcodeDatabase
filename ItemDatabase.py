import json
import re

# Compatible with Python 2.7 and Python3.13

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

    def _clean_whitespace(self, string):
        assert isinstance(string, str)
        return " ".join(string.split())

    def _search_dictionary(self, regex, items_dict):
        '''
        Search through all dictionary items to find match.
        Return json of all items that match.
        '''
        assert isinstance(regex, str)
        assert isinstance(items_dict, dict)

        # Start matching by iterating through each item.
        # If the string is present in the item
        # title, return the entire item. If the string is present
        # as a key value of the item, return the entire item.
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

    def search_matches_iterative(self, regex):
        ''' Search through all dictionary items to find matches
        iteratively.'''
        assert isinstance(regex, str)
        
        # Remove redundant whitespace from the regex string
        regex = self._clean_whitespace(regex)
        tokens = regex.split(" ")
        curr_dict = {}

        with open(self.file_path, "r") as rfile:
            curr_dict = json.load(rfile)
            
        # Make sure that each token is a valid for search
        for token in tokens:
            if not self._check_valid_regex(token) or not isinstance(token, str):
                raise ValueError(f"Token {token} is not valid.")

        # Narrow search tokenwise
        for token in tokens:
            matches = self._search_dictionary(token, curr_dict)
            curr_dict = matches

        return curr_dict

    def search_matches_recursive(self, regex):
        ''' Search through all dictionary items to find match
        recursively. Parse through all tokens in regex string.'''
        assert isinstance(regex, str)

        # Define recursive driver
        def search_driver(tokens: list, items_dict: dict):
            assert isinstance(tokens, list)
            assert isinstance(items_dict, dict)

            for token in tokens:
                assert isinstance(token, str)

            # Case 0: no tokens supplied
            if len(tokens) == 0:
                return items_dict

            # Case n: n tokens supplied, n >= 1
            else:
                next_token = tokens.pop()
                return search_driver(tokens, self._search_dictionary(next_token, items_dict))

        # Remove redundant whitespace from the regex string
        regex_cleaned = self._clean_whitespace(regex)
        tokens = regex_cleaned.split(" ")

        # Check if tokens are valid!
        for token in tokens:
            if not self._check_valid_regex(regex):
                raise re.error(f"Invalid regex {regex}")

        # Place the items dictionary into memory for search
        with open(self.file_path, "r") as rfile:
            items_dict = json.load(rfile)

        return search_driver(tokens, items_dict)

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
    db = ItemDatabase("test_file.json")

    def test_write_data():
        db.write_data("Oreos")
        db.write_data("Oreos party pack")
        db.write_data("Oreos White")
        db.write_data("Oreos white")
        db.write_data("OREOS WHITE")
        db.write_data("Real Canadian Water", volume="500mL", upc="060383013422")

    def test_search_single():
        print("\nSingle search test")
        search = lambda db, regex: db.search_matches(regex)
        matches = search(db, "water")
        pretty_print(matches, db.INDENT_SPACES)

    def test_search_iterative():
        print("\n---------------Iterative search test-------------")
        search = lambda db, regex: db.search_matches_iterative(regex)
        search_print = lambda db, regex: pretty_print(search(db, regex), db.INDENT_SPACES)
        # search_print(db, "water")
        search_print(db, "500 water canadian real")
        search_print(db, "pack oreos")

    def test_search_recursive():
        print("\n\n------------ Recursive search test ------------")
        search = lambda db, regex: db.search_matches_recursive(regex)
        search_print = lambda db, regex: pretty_print(search(db, regex), db.INDENT_SPACES)
        search_print(db, "500 water canadian real")
        search_print(db, "pack oreos")

    def test_cleaning():
        print(db._clean_whitespace("hello there"))
        print(db._clean_whitespace("  hello  there"))
        print(db._clean_whitespace("  hello         there   "))
        print(db._clean_whitespace("\n  hello   \r\n\r\n\t\n there \n    \r\n"))

    # test_write_data()
    test_search_single()
    test_search_iterative()
    test_search_recursive()
    # test_cleaning()

if __name__ == "__main__":
    test()
