import json
import re
import os.path

#--------- Basic data manipulation ------- #
class ItemDatabase():
    INDENT_SPACES = 4
    INVALID_CHARS = "{}[]()<>^"
    MAX_REGEX_SIZE = 500
    
    DEFAULT_JSON_TEMPLATE = {
            "product_title": "",
            "product_brand": "",
            "product_url": "",
            "product_id": "",
            "product_package_size": "",
            "price_descriptor": "",
            "prices": {
                "regular_price": "",
                "sale_price": "",
                "mop_price": "",
                "non_member_price": "",
                "before_price": ""
                    },
            "codes": {
                "upc": "",
                "ean": "",
                "plu": ""
                }
            }

    def __init__(self,
                 file_path: str,
                 json_format: dict=DEFAULT_JSON_TEMPLATE):
        assert isinstance(file_path, str)
        assert isinstance(json_format, dict)
        self._file_path = file_path
        self._handle_file(file_path)
        assert os.path.exists(file_path)
        self._json_format = json_format

    def _handle_file(self,
                     file_path: str):
        ''' Handle errors in file.'''
        # Check if the file exists but the
        # format is incorrect.
        if os.path.exists(file_path):
            with open(file_path, "r+") as rfile:
                if rfile.read().strip() == "":
                    rfile.write("{}")
            
        # Create the file if necessary.
        if not os.path.exists(file_path):
            with open(file_path, "w+") as wfile:
                wfile.write("{}")

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

    def search_matches(self, regex):
        '''
        Search through all dictionary items to find match.
        Return json of all items that match.
        '''
        assert isinstance(regex, str)

        # If file does not exist, bubble exception.
        with open(self._file_path, "r") as rfile:
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

    def search_matches_iterative(self, regex):
        ''' Search through all dictionary items to find matches
        iteratively.'''
        assert isinstance(regex, str)
        
        # Remove redundant whitespace from the regex string
        regex = self._clean_whitespace(regex)
        tokens = regex.split(" ")
        curr_dict = {}

        with open(self._file_path, "r") as rfile:
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
        with open(self._file_path, "r") as rfile:
            items_dict = json.load(rfile)

        return search_driver(tokens, items_dict)

    def write_data(self,
                    identifier: str,
                    data: dict,
                   indent_spaces: int=INDENT_SPACES) -> bool:
        ''' Write data to the supplied file path.
            In the supplied file (which acts as a semi-database/table),
            items will always be stored by their product title.'''
        # Verify that the data dictionary follows the
        # established json template at initialization.
        if self._verify_dict(data):
            # If file does not exist, bubble exception
            with open(self._file_path, "r+") as rwfile:
                values_dict = json.load(rwfile)
                
                # Update the original values dictionary
                values_dict[identifier] = data
                
                # Rewrite the dictionary into the file
                rwfile.seek(0)
                json.dump(values_dict, rwfile, indent=indent_spaces)
                return True

        return False
        
    def _verify_dict(self,
                    dictionary: dict) -> bool:
        ''' Verify that <json_data> has the same
        key template as the template established
        upon initialization.'''
        assert isinstance(dictionary, dict)
        
        # Verify that the keys match in
        # both dictionaries and that
        # the class of each respective key
        # is equal.
        def verify_dict(dict_a: dict,
                         dict_b: dict) -> bool:
            a_items = dict_a.items()
            b_items = dict_b.items()

            # Check length
            if len(a_items) != len(b_items):
                return False

            # Compare item by item
            for a_item in a_items:
                a_key, a_value = a_item

                # Check that the keys are exact
                if a_key not in dict_b.keys():
                    return False
                
                # Check that each key's respective
                # value's class are equal.
                b_value = dict_b[a_key]

                if a_value.__class__ != b_value.__class__:
                    return False

                # In the event that the values are
                # dictionaries, check all values inside.
                if isinstance(a_value, dict) and isinstance(b_value, dict):
                    return verify_dict(a_value, b_value)

            # Dictionaries are equal
            # key wise and class of value wise.
            return True

        # Begin recursion. Dictionaries are self similiar:
        # it is possible to store a dictionary within itself.
        return verify_dict(self._json_format, dictionary)
