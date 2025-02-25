#! /opt/homebrew/bin/python3.11
# Change the path to match your python location
from MongoClient import MongoClientAsync, CollectionNotFound
from DateFormatter import DateFormatter
from datetime import datetime, timedelta
from Globals import Department
import sys
import asyncio
import argparse

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
        num_days = self._get_date_distance(self._df.get_datetime(start_date),
                                           self._df.get_datetime(end_date))
        start_dt = self._df.get_datetime(start_date)
        
        # Start iterating over the dates
        # It does not matter whether start_date is more
        # recent than the end date or vice versa.
        for delta in range(0,
                           (num_days - 1) if num_days <= 0 else (num_days + 1),
                           -1 if num_days <= 0 else 1):
            curr_date_str = self._df.get_date_str(start_dt - timedelta(delta))
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

    def _prompt_action(self, message: str, agreement: list=AGREE_CHARS):
        assert isinstance(message, str)
        assert isinstance(agreement, list)
        assert len(agreement) > 0
        user_input = input(message).strip()
        return user_input in agreement

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-isuri", "--item-server-uri", action="store", dest="isuri", required=True, type=str)
    parser.add_argument("-dbs", "--databases", action="append", nargs="+", dest="databases", required=True, type=str)
    parser.add_argument("-s", "--start-date", action="store", dest="start_date", required=True, type=str)
    parser.add_argument("-e", "--end-date", action="store", dest="end_date", required=True, type=str)
    parser.add_argument("-i", dest="interactive", action="store_true")
    args = parser.parse_args()
    db_maintainer = DBMaintainer(args.isuri, args.interactive)
    deps = args.databases[0]
    existing_deps = [dep.value for dep in Department]

    # Allow "all" to be supplied to --databases.
    # If it is, iterate through all databases.
    # Get all existing department names in the Department enum.
    if "all" in deps:
        deps = existing_deps

    # Check that every department/department is valid
    for dep in deps:
        assert isinstance(dep, str)
        if dep not in existing_deps:
            print(f"The department '{dep}' is invalid!\nPlease choose from {existing_deps}", file=sys.stderr)
            sys.exit()

    # Every department is valid!
    # Now, drop every collection in
    # the established range for each dep.
    for dep in deps:
        print(f"#---- Current department: {dep} ----#")
        await db_maintainer.drop_collections(dep, args.start_date, args.end_date)
        print()
    
asyncio.run(main())
