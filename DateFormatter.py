from datetime import datetime, timedelta
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

    def date_offset_today(self, offset: int) -> str:
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

