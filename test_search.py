import re

def has_match(regex: str,
            dictionary: dict) -> bool:
    ''' Check whether the dictionary has a value field
    which matches the regex.
    Key fields are ignored from regex search.'''
    assert isinstance(regex, str)
    assert isinstance(dictionary, dict)
    
    # Start matching by iterating through each key.
    # If the string is present in the item
    # title, return the entire item. If the string is present
    # as a key value of the item, return the entire item.
    # pattern_str = ".*%s.*" % regex
    pattern_str = "%s" % regex
    pattern_compiled = re.compile(re.escape(pattern_str), re.IGNORECASE)

    # Prevent redundant recompilation of regex
    # pattern through the driver.
    def recursive_driver(pattern_compiled,
                            dictionary: dict):
        for key in dictionary:
            assert isinstance(key, str)
            value = dictionary[key]
            assert isinstance(value, str) or isinstance(value, dict)

            if isinstance(value, str):
                if pattern_compiled.search(value) == None:
                    continue
                
                else:
                    return True

            elif isinstance(value, dict):
                return recursive_driver(pattern_compiled, value)

    # Begin recursion
    return recursive_driver(pattern_compiled, dictionary)


def _clean_whitespace(string):
    assert isinstance(string, str)
    return " ".join(string.split())

def get_matches(query: str,
                items: list) -> list:
    assert isinstance(query, str)
    assert isinstance(items, list)
    matches = []

    # If the query has any spaces,
    # treat them as seperate tokens!
    query = _clean_whitespace(query)
    tokens = query.split(" ")

    # Start search for all items.
    # Note that for any given item,
    # all tokens must match within the dictionary.
    for item in items:
        assert isinstance(item, dict)
        item_matched = True

        for token in tokens:
            if not has_match(token, item):
                item_matched = False

        if item_matched:
            matches.append(item)

    return matches

def test_search_recursive():
    print(f"Recursive test search")
    
    def test_no_nest():
        print("Testing no nest")
        a = {"a": "1"}
        assert has_match("1", a)
        assert not has_match("0", a)
        assert has_match("", a)

    def test_one_nest():
        print("Testing one nest")
        b = {"a": {"a": "1"}}
        assert has_match("1", b)
        assert not has_match("0", b)
        assert has_match("", b)

    def test_two_nest():
        print("Testing two nest.")
        c = {"a": {"a": {"a": "1"}}}
        assert has_match("1", c)
        assert has_match("", c)
        assert not has_match(" ", c)
        assert not has_match("brahenath", c)

    def test_real_value():
        print("Testing real value")
        data = {
            "_id": '21023581001_EA',
            "product_title": 'Snap Peas',
            "product_brand": '',
            "product_url": '/en/snap-peas/p/21023581001_EA?source=nspt',
            "product_id": '21023581001_EA',
            "product_package_size": '200 g, $1.49/100g',
            "price_descriptor": 'SAVE $0.81',
            "prices": {
                "regular_price": '',
                "sale_price": '$2.98',
                "mop_price": '',
                "non_member_price": '',
                "before_price": '$3.79'
            },
                "codes": { "upc": '', "ean": '', "plu": '' }
        }
        # id tests
        def id_tests():
            assert has_match("21023581001_EA", data)
            assert has_match("2102", data)
            assert has_match("210235", data)
            assert has_match("_EA", data)
            assert has_match("21023581001", data)

        # title tests
        def title_tests():
            assert has_match("snap", data)
            assert has_match('Snap Peas', data)
            assert has_match("snap peas", data)
            assert has_match("SnAp PeAs", data)
            assert has_match("snap", data)
            assert has_match("peas", data)
            assert not has_match(" snap     peas", data)

        # prices test
        def prices_test():
            assert has_match("$2.98", data)
            assert has_match("$3.79", data)
            assert has_match("$0.81", data)
            assert has_match("2.98", data)

        # vacuous truth test
        def vacuous_truth():
            assert has_match("", data)

        # negatives
        def negative_tests():
            assert not has_match("2131231241", data)
            assert not has_match("SAVED", data)
            assert not has_match("  ", data)
            assert not has_match("source=suputamadre", data)

        id_tests()
        title_tests()
        prices_test()
        vacuous_truth()
        negative_tests()

    test_no_nest()
    test_one_nest()
    test_two_nest()
    test_real_value()

def test_clean_whitespace():
    pos = lambda string, result: _clean_whitespace(string) == result
    neg = lambda string, result: _clean_whitespace(string) != result

    def test_positive():
        print("Testing positives")
        # Basic whitespace
        assert pos("  ", "")
        assert pos("", "")
        assert pos("        ", "")
        assert pos("\n\t   \t", "")

        # With alphanum
        assert pos(" a b c d", "a b c d")
        assert pos(" a    b     c     d", "a b c d")
        assert pos("\t\n   a  \tb  c \t\t  d   \n\t  \t", "a b c d")

        # Long chars, realistic to search tokens
        assert pos("water", "water")
        assert pos("water $3.21 24 pack", "water $3.21 24 pack")
        assert pos("water     $3.21  24 pack ", "water $3.21 24 pack")

    def test_negative():
        print(f"Testing negatives")
        assert neg("    ", " ")

    test_positive()
    test_negative()

def test_get_matches():
    print("Testing get matches")
    def test_one_real_value():
        print("Test one real value")
        data = {
            "_id": '21023581001_EA',
            "product_title": 'Snap Peas',
            "product_brand": '',
            "product_url": '/en/snap-peas/p/21023581001_EA?source=nspt',
            "product_id": '21023581001_EA',
            "product_package_size": '200 g, $1.49/100g',
            "price_descriptor": 'SAVE $0.81',
            "prices": {
                "regular_price": '',
                "sale_price": '$2.98',
                "mop_price": '',
                "non_member_price": '',
                "before_price": '$3.79'
            },
                "codes": { "upc": '', "ean": '', "plu": '' }
        }
        items = [data]
        
        fx = lambda query: get_matches(query, items) == items

        def single_token():
            print(f"Testing single tokens")
            assert fx("21023")
            assert fx("snap")
            assert fx("peas")
            assert fx("200 g")
            assert fx("SAVE $0.81")
            assert fx("$2.98")
            assert fx(".98")
            assert fx("")

            # Negatives
            assert not fx("bruh")
            assert not fx("$3.79 dollars")

        single_token()
    test_one_real_value()

if __name__ == "__main__":
    # test_search_recursive() # passed
    # test_clean_whitespace() # passed
    # test_get_matches() # passed!
    pass
