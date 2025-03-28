from MongoClient import MongoClientAsync, CollectionNotFound, DatabaseInvalid
from DateFormatter import DateFormatter, DateFormatterToday, InvalidDateFormatStringError, InvalidFormatError
from datetime import date, datetime, timedelta

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
    DEFAULT_ACCUMULATE_COL = "accumulate"
    AGREE_CHARS = ["Y", "y"]

    def __init__(self, endpoint_url: str, interactive: bool):
        assert isinstance(endpoint_url, str)
        assert isinstance(interactive, bool)
        self._client = MongoClientAsync(endpoint_url)
        self._interactive = interactive
        self._df = DateFormatterToday()

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

            if await self._client.check_exists_col(db, curr_date_str):
                if self._interactive:
                    message = f"Do you wish to drop {db}.{curr_date_str}? (y/n): "
                    proceed = self._prompt_action(message)

                if proceed:
                    self._client.select_collection(db, curr_date_str)
                    print(f"Dropping {db}.{curr_date_str}")
                    await self._client.drop_collection()

            else:
                print(f"{db}.{curr_date_str} doesn't exist! Skipping.")

    async def sync_codes(self, db: str, dest_col: str, accumulate_col: str, upsert: bool=False):
        ''' Synchronize codes from db.accumulate_col into db.dest_col.

        db: the selected department
        dest_col: collection to synchronize
        accumulate_col: source of codes to synchronize from
        upsert: boolean for whether a document should be
                inserted into the collection if not previously
                indexed'''
        assert isinstance(db, str)
        assert isinstance(dest_col, str)
        assert isinstance(accumulate_col, str)
        assert isinstance(upsert, bool)
        if not await self._client.check_exists_db(db):
            raise DatabaseInvalid(f"The database {db} doesn't exist!")

        if not await self._client.check_exists_col(db, dest_col):
            raise CollectionNotFound(f"The collection {db}.{dest_col} doesn't exist.")

        if not await self._client.check_exists_col(db, accumulate_col):
            raise CollectionNotFound(f"The collection {db}.{accumulate_col} doesn't exist.")
        
        # This boolean can potentially be negated
        # by the user if the script is set to interactive.
        proceed = True

        if self._interactive:
            message = f"Do you wish to synchronize from {db}.{accumulate_col}\n" +\
                f"to {db}.{dest_col}? (y/n): "
            proceed = self._prompt_action(message)

        if proceed:
            print(f"Synchronizing codes from {db}.{accumulate_col} to {db}.{dest_col}")
            extra_fields = ["product_title", "product_brand", "product_url", "product_id"]

            await self._migrate_codes(extra_fields, db,
                                        accumulate_col, db, dest_col, upsert=upsert)

    async def aggregrate_codes(self, db: str, start_date: str, end_date: str, dest_col: str, upsert: bool):
        ''' For <db> from <start_date> (incl.) to <end_date> (incl.),
        aggregrate all code data (upc, ean, plu) to <dest_col>.
        Disregard all price data of all products.
        Include product name, code data, as well as link,
        item id and brand if applicable.
        
        db: string representing department to aggregrate code data
        start_date: date string defining collection boundary
        end_date: date string defining collection boundary
        dest_col: string defining destination of all aggregrated data'''
        assert isinstance(db, str)
        assert isinstance(start_date, str)
        assert isinstance(end_date, str)
        assert isinstance(dest_col, str)
        assert await self._client.check_exists_db(db)

        # Iterate over the established interval of dates
        # (inclusively). It does not matter whether
        # start_date < end_date or vice versa.
        for date in DateTimeRange(start_date, end_date):
            curr_date_str = self._df.get_date_str(date)
            proceed = True

            if await self._client.check_exists_col(db, curr_date_str):
                if self._interactive:
                    message = f"Do you wish to aggregrate {db}.{curr_date_str}\n" +\
                        f"to {db}.{dest_col}? (y/n): "
                    proceed = self._prompt_action(message)

                if proceed:
                    print(f"Migrating codes from {db}.{curr_date_str} to {db}.{dest_col}")
                    extra_fields = ["product_title", "product_brand", "product_url", "product_id"]

                    await self._migrate_codes(extra_fields, db,
                                              curr_date_str, db, dest_col, upsert=upsert)
                
            else:
                print(f"{db}.{curr_date_str} doesn't exist! Skipping.")

    def is_date_col(self, date_col: str):
        assert isinstance(date_col, str)

        try:
            self._df.get_datetime(date_col)
            return True

        except InvalidDateFormatStringError:
            return False

    def handle_date_input(self, string: str):
        ''' If the string is a correctly formatted date, return.
        Otherwise, assume that the string is a variant of t or t-n,
        where -n is an integer representing the day offset from today.

        If the passed string is a variant of t or t-n,
        return the respective date string.

        If the passed string is neither a correctly formatted date nor
        a variant of t or t-n, bubble InvalidDateFormatStringError'''
        assert isinstance(string, str)
    
        # Check if the string is a concrete date
        # like 2025-03-27
        if self.is_date_col(string):
            return string

        # The string isn't a concrete date.
        # Assume that its a variant of t or t-n.
        # Bubble exception if not a variant.
        date = self._df.date_offset_today_str(string)
        return date

    async def _migrate_codes(self,
                            extra_fields: list,
                            db_src: str,
                            col_src: str,
                            db_dest: str,
                            col_dest: str,
                            upsert: bool):
        ''' For every product in db_src.col_src with
        any data (UPC, EAN, etc.), migrate those codes to the
        respective item in db_dest.col_dest.'''
        # Verify that all the provided extra fields
        # are strings!
        for field in extra_fields:
            if not isinstance(field, str):
                raise TypeError(f"{field} is not a string!")

        # Get all documents with code data
        # from the source collection
        self._client.select_collection(db_src, col_src)
        code_cursor = await self._client.find({
            "$or": [
                {"codes.upc": {"$ne": "" } },
                {"codes.ean": {"$ne": "" } },
                {"codes.plu": {"$ne": "" } },
            ]
        })
        updates = []

        async for doc in code_cursor:
            to_set = {"codes": doc["codes"]}
            code_found = False

            for _, val in to_set["codes"].items():
                if val != "":
                    code_found = True

            assert code_found

            try:
                to_set.update({field: doc[field] for field in extra_fields})

            except KeyError:
                breakpoint()
            updates.append(({"_id": doc["_id"]},
                            {"$set": to_set}))

        # Update all the code data in
        # the destination collection
        self._client.select_collection(db_dest, col_dest)
        if len(updates) != 0:
            result = await self._client.bulk_update(updates, upsert=upsert)
            return result
        return None

    def _prompt_action(self, message: str, agreement: list=AGREE_CHARS):
        assert isinstance(message, str)
        assert isinstance(agreement, list)
        assert len(agreement) > 0
        user_input = input(message).strip()
        return user_input in agreement
