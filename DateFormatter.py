from datetime import datetime, timedelta
from PatternExtractor import PatternExtractor

class InvalidFormatError(KeyError):
    pass

class InvalidDelimiterError(ValueError):
    pass

class InvalidDateFormatStringError(ValueError):
    pass

class DateFormatter():
    FORMAT_MAP = {
        "year": "%Y",
        "month": "%m",
        "day": "%d"
    }
    DEFAULT_TIME_FORMAT = ("year",
                            "month",
                            "day"
                            )
    DEFAULT_DELIMITER = "-"
    VALID_DELIMITERS = {DEFAULT_DELIMITER}
    def __init__(self, format_order: tuple=DEFAULT_TIME_FORMAT, delimiter: str=DEFAULT_DELIMITER):
        self._verify_delimiter(delimiter)
        self._verify_format_order(format_order)
        self._delimiter = delimiter
        self._format_order = format_order
        self._date_format = self._get_date_format(format_order)
        
    def get_datetime(self, formatted_str: str) -> datetime:
        ''' Given a formatted date string that conforms to
        self._date_format, e.g. "2025-02-22" and "%Y-%m-%d",
        convert the date string into its respective datetime object.
        '''
        assert isinstance(formatted_str, str)

        # Check that the delimiters match
        params = formatted_str.split(self._delimiter)

        # Check that the format is correct!
        if len(params) != len(self._format_order):
            raise InvalidDateFormatStringError(f"{formatted_str} doesn't match {self._date_format}!")

        # Verify that all values provided are indeed numeric
        try:
            params = [int(par) for par in params]

        except ValueError:
            raise InvalidDateFormatStringError(f"{formatted_str} contains an alphabetic value!")

        # All checks have passed!
        # Map each parameter to their value
        # of year, month and date.
        params_map = {par: params[i] for i, par in enumerate(self._format_order)}
        return datetime(params_map["year"], params_map["month"], params_map["day"])

    def get_date_str(self, dt: datetime) -> str:
        ''' Given a datetime object, return the formatted
            date string.

        dt: datetime object'''
        return dt.strftime(self._date_format)

    
    def _verify_delimiter(self, delimiter):
        if not isinstance(delimiter, str):
            raise InvalidDelimiterError(f"The provided delimiter is of class {delimiter.__class__}, not str!")

        if not delimiter in DateFormatter.VALID_DELIMITERS:
            raise InvalidDelimiterError(f"The provided delimiter {delimiter} is not allowed!\n" + \
                                        f"Please pick a delimiter from {DateFormatter.VALID_DELIMITERS}")

    def _verify_format_order(self, format_order):
        if not isinstance(format_order, tuple):
            raise InvalidFormatError(f"{format_order} is not of class tuple!")
            
        if not len(format_order) > 0:
            raise InvalidFormatError(f"The supplied format order is empty!")

        if not len(set(format_order)) == len(format_order):
            raise InvalidFormatError(f"{format_order} contains a duplicate parameter!")

        for param in format_order:
            if not param in DateFormatter.FORMAT_MAP:
                raise InvalidFormatError(f"{param} is not a valid format parameter!\n" + \
                                         f"Please pick a format parameter from {DateFormatter.FORMAT_MAP.keys()}")

    def _get_date_format(self, format_order: tuple):
        params = []

        for param in format_order:
            assert isinstance(param, str)

            try:
                params.append(DateFormatter.FORMAT_MAP[param])

            # Override key error with a more descriptive exception.
            except KeyError:
                raise InvalidFormatError(f"{param} is not a valid parameter!")

        # All params are valid.
        # Generate string.
        return self._delimiter.join(params)

class DateFormatterToday(DateFormatter):
    ''' Provides additional formatting functionality
    in terms of today's date.'''
    TODAY_CHAR = "t"
    OFFSET_CHAR = "-"
    def __init__(self,
                 format_order: tuple=DateFormatter.DEFAULT_TIME_FORMAT,
                 delimiter: str=DateFormatter.DEFAULT_DELIMITER):
        DateFormatter.__init__(self, format_order, delimiter)
        self._pe = PatternExtractor()

    def date_offset_today_int(self, offset: int) -> str:
        ''' Get the string of the date that's offsetted
            from today.

            E.g., suppose that today was Mar. 26, 2025.
            If offset = 0, return 2025-03-26.
            If offset = -1, return 2025-03-25.
            If offset = 5, return 2025-03-31.

            offset: integer offset representing days.
                    Can be negative or positive.

            returns: string representing the date, formatted.'''
        assert isinstance(offset, int)
        return self.get_date_str(datetime.today() + timedelta(offset))

    def date_offset_today_str(self, string: str):
        '''Given a string like 't', 't-5', or
        't-0', return the respective date string.
        E.g., suppose that today was Mar. 27, 2025.

        f('t') -> 2025-03-27
        f('t-0') -> 2025-03-27
        f('t-5') -> 2025-03-22'''
        assert isinstance(string, str)

        # Parse the string with regex.
        # The following produces ^(?:t|(?:t-\d*))$
        pattern = fr"^(?:" + \
                    fr"{DateFormatterToday.TODAY_CHAR}|" + \
                    fr"(?:{DateFormatterToday.TODAY_CHAR}{DateFormatterToday.OFFSET_CHAR}\d+)" + \
                    fr")$"
        self._pe.set_pattern(pattern)

        # Check whether the string matches
        # our regex
        matches = self._pe.get_matches(string)
        assert len(matches) == 0 or len(matches) == 1
        if len(matches) == 0:
            raise InvalidFormatError(f"The inputted string doesn't match! Use a string like " + \
                                     f"{DateFormatterToday.TODAY_CHAR} or " + \
                                    f"{DateFormatterToday.TODAY_CHAR}{DateFormatterToday.OFFSET_CHAR}5")

        # The string matches our regex!
        # Proceed with converting it into the respective
        # date string. Firstly, convert 't' into 't-0'
        # to simplify processing.
        matches[0] = f"{DateFormatterToday.TODAY_CHAR}{DateFormatterToday.OFFSET_CHAR}0" if \
            matches[0] == DateFormatterToday.TODAY_CHAR else matches[0]

        # Get the integer offset following the offset delimiter,
        # then use it to convert into date string. Note that we only
        # return previous dates or today, hence we negate offset.
        offset = int(matches[0].split(DateFormatterToday.OFFSET_CHAR)[1]) * -1
        assert offset <= 0

        return self.date_offset_today_int(offset)
