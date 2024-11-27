import json
import socket, os
import re

#--------- Basic data manipulation ------- #
INDENT_SPACES = 4
INVALID_CHARS = "{}[]()<>^"
MAX_REGEX_SIZE = 500

def get_item(file_path, item_name):
    assert isinstance(file_path, str)
    assert isinstance(item_name, str)
    
    with open(file_path, "r") as rfile:
        values_dict = json.load(rfile)
        return values_dict[item_name]

def check_valid_regex(regex):
    assert isinstance(regex, str)

    if len(regex) > MAX_REGEX_SIZE:
        return False

    for c in INVALID_CHARS:
        if c in regex:
            return False

    return True

def pretty_print(dictionary, indent_spaces):
    assert isinstance(dictionary, dict)
    assert isinstance(indent_spaces, int)
    json_formatted = json.dumps(dictionary, indent=indent_spaces)
    print(json_formatted)

def search_matches(file_path, regex):
    '''
    Search through all dictionary items to find match.
    Return json of all items that match.
    '''
    assert isinstance(file_path, str)
    assert isinstance(regex, str)

    # If file does not exist, bubble exception.
    with open(file_path, "r") as rfile:
        if not check_valid_regex(regex):
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

def write_data(file_path,
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
    inputted_json = locals()

    # Construct dictionary iteratively.
    # If alternating arguments, always skip file_path
    # product_name, indent_spaces.
    inputted_json.pop("file_path")
    inputted_json.pop("product_name")
    inputted_json.pop("indent_spaces")

    # If file does not exist, bubble exception
    with open(file_path, "r+") as rwfile:
        values_dict = json.load(rwfile)
        
        # Update the original values dictionary
        values_dict[product_name] = inputted_json
        
        # Rewrite the dictionary into the file
        rwfile.seek(0)
        json.dump(values_dict, rwfile, indent=indent_spaces)

#-------------- Server Code ---------------#

#-------------- Test code ----------------#
def test():
    def test_write_data():
        write_data("test_file_json.txt", "Oreos")
        write_data("test_file_json.txt", "Oreos party pack")
        write_data("test_file_json.txt", "Oreos White")
        write_data("test_file_json.txt", "Oreos white")
        write_data("test_file_json.txt", "OREOS WHITE")
        write_data("test_file_json.txt", "Real Canadian Water", volume="500mL", upc="060383013422")

    def test_search():
        search = lambda regex: search_matches("test_file_json.txt", regex)
        matches = search("party")
        pretty_print(matches, INDENT_SPACES)


    test_search()
    # test_write_data()
if __name__ == "__main__":
    test()
    
