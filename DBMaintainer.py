from MongoClient import MongoClientAsync, CollectionNotFound
from DateFormatter import DateFormatter
from datetime import datetime, timedelta

class DateTimeRange():
    def __init__(self, start_date: str, end_date: str):
        assert isinstance(start_date, str)
        assert isinstance(end_date, str)
        self.start_date = start_date
        self.end_date = end_date
        df = DateFormatter()
        self._start_dt = df.get_datetime(start_date)
        self._end_dt = df.get_datetime(end_date)
        self.num_days = self._get_date_distance(self._start_dt, self._end_dt)
        self._curr_delta = 0
        self._stop_condition = (self.num_days - 1) if self.num_days <= 0 \
                                else (self.num_days + 1)
        self._step = -1 if self.num_days <= 0 \
                        else 1

    def __iter__(self):
        return self

    def __next__(self):
        if self._curr_delta != self._stop_condition:
            result = self._start_dt - timedelta(self._curr_delta)
            self._curr_delta += self._step
            return result
        raise StopIteration()

    def _get_date_distance(self,
                          start_dt: datetime,
                          end_dt: datetime) -> int:
        ''' Return the number of days between
        the two dates as an int.

        start_dt: the datetime object representing the most
        recent date (inclusive).

        end_dt: the datetime object representing the last date
        in the interval (inclusive).'''
        assert isinstance(start_dt, datetime)
        assert isinstance(end_dt, datetime)
        return (start_dt - end_dt).days

class DBMaintainer():
    AGREE_CHARS = ["Y", "y"]

    def __init__(self, endpoint_url: str, interactive: bool):
        assert isinstance(endpoint_url, str)
        assert isinstance(interactive, bool)
        self._client = MongoClientAsync(endpoint_url)
        self._interactive = interactive
        self._df = DateFormatter()

    async def drop_collections(self, db: str, start_date: str, end_date: str):
        ''' Drop every collection from <start_date> (incl.) to
        end_date (incl.).'''
        assert isinstance(db, str)
        assert isinstance(start_date, str)
        assert isinstance(end_date, str)
        assert await self._client.check_exists_db(db)
        
        # Start iterating over the dates
        # It does not matter whether start_date is more
        # recent than the end date or vice versa.
        for date in DateTimeRange(start_date, end_date):
            curr_date_str = self._df.get_date_str(date)
            proceed = True

            if self._interactive:
                message = f"Do you wish to drop {db}.{curr_date_str}? (y/n): "
                proceed = self._prompt_action(message)

            if proceed:
                if await self._client.check_exists_col(db, curr_date_str):
                    self._client.select_collection(db, curr_date_str)
                    await self._client.drop_collection()
                    print(f"Deleting {db}.{curr_date_str}")

                else:
                    print(f"{db}.{curr_date_str} doesn't exist! Skipping.")

    async def aggregrate_codes(self, db: str, start_date: str, end_date: str, dest_col: str) -> int:
        ''' For <db> from <start_date> (incl.) to <end_date> (incl.),
        aggregrate all code data (upc, ean, plu) to <dest_col>.
        Disregard all price data of all products.
        Include product name, code data, as well as link,
        item id and brand if applicable.
        
        db: string representing department to aggregrate code data
        start_date: date string defining collection boundary
        end_date: date string defining collection boundary
        dest_col: string defining destination of all aggregrated data

        returns: the amount of unique products added to <dest_col>'''
        assert isinstance(db, str)
        assert isinstance(start_date, str)
        assert isinstance(end_date, str)
        assert isinstance(dest_col, str)

        return 1

    def _prompt_action(self, message: str, agreement: list=AGREE_CHARS):
        assert isinstance(message, str)
        assert isinstance(agreement, list)
        assert len(agreement) > 0
        user_input = input(message).strip()
        return user_input in agreement
