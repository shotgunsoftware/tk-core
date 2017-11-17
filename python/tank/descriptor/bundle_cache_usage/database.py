# Copyright (c) 2017 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
Methods relating to the Path cache, a central repository where metadata about
all Tank items in the file system are kept.

"""

import os
import sqlite3
import datetime

from . import BundleCacheUsageLogger as log


class BundleCacheUsageDatabaseEntry(object):
    """
    Simple helper class for wrapping database returned tuple into easier to access object.
    """

    def __init__(self, tuple):
        self._path = tuple[BundleCacheUsageDatabase.DB_COL_INDEX_PATH]
        self._add_timestamp = tuple[BundleCacheUsageDatabase.DB_COL_INDEX_ADD_TIMESTAMP]
        self._last_access_timestamp = tuple[BundleCacheUsageDatabase.DB_COL_INDEX_LAST_ACCESS_TIMESTAMP]
        self._usage_count = tuple[BundleCacheUsageDatabase.DB_COL_INDEX_USAGE_COUNT]

    @classmethod
    def _format_date_from_timestamp(cls, timestamp):
        """
        Class local date formatting method.

        :param timestamp: An int unix timestamp
        :return: A str human readable is the form:  Tuesday, 21. November 2017 04:30PM
        """

        #return datetime.datetime.fromtimestamp(n).isoformat()
        # Formats something like: 2017-09-19T13:08:28

        # TODO: is there an existing preset to this?
        return datetime.datetime.fromtimestamp(timestamp).strftime("%A, %d. %B %Y %I:%M%p")

    @property
    def add_date(self):
        """
        Returns the entry date when initially added to the database
        :return: an int unix timestamp
        """
        return BundleCacheUsageDatabaseEntry._format_date_from_timestamp(self.add_timestamp)

    @property
    def add_timestamp(self):
        """
        Returns the entry timestamp when initially added to the database 
        :return: an int unix timestamp
        """
        return self._add_timestamp

    @property
    def last_access_date(self):
        """
        Returns the entry last accessed date
        :return: an str datetime
        """
        return BundleCacheUsageDatabaseEntry._format_date_from_timestamp(self.last_access_timestamp)

    @property
    def last_access_timestamp(self):
        """
        Returns the entry last accessed timestamp
        :return: an int unix timestamp
        """
        return self._last_access_timestamp

    @property
    def path(self):
        """
        Returns the entry identifier
        :return: a str
        """
        return self._path

    @property
    def usage_count(self):
        """
        Returns the entry usage count
        :return: a int
        """
        return self._usage_count


class BundleCacheUsageDatabase(object):
    """
    Simple SQLite-based database for tracking bundle cache accesses.
    """

    DB_FILENAME = "bundle_usage.sqlite3"

    # database column indexes
    (
        DB_COL_INDEX_PATH,
        DB_COL_INDEX_ADD_TIMESTAMP,
        DB_COL_INDEX_LAST_ACCESS_TIMESTAMP,
        DB_COL_INDEX_USAGE_COUNT
    ) = range(4)

    def __init__(self, bundle_cache_root):
        self._bundle_cache_root = bundle_cache_root
        self._bundle_cache_usage_db_filename = os.path.join(
            self.bundle_cache_root,
            BundleCacheUsageDatabase.DB_FILENAME
        )

        self._db_connection = None
        self._connect()
        self._create_main_table()

        # this is to handle unicode properly - make sure that sqlite returns
        # str objects for TEXT fields rather than unicode. Note that any unicode
        # objects that are passed into the database will be automatically
        # converted to UTF-8 strs, so this text_factory guarantees that any character
        # representation will work for any language, as long as data is either input
        # as UTF-8 (byte string) or unicode. And in the latter case, the returned data
        # will always be unicode.
        self._db_connection.text_factory = str

    def _execute(self, sql_statement, tuple=None):
        """
        Connects the database if not already connected and execute the
        specified SQL statement.

        :param sql_statement: a str of some SQL statement to be executed.
        :param tuple: An optional tuple with required SQL statement parameters
        :return:
        """
        if tuple:
            return self._get_cursor().execute(sql_statement, tuple)
        else:
            return self._get_cursor().execute(sql_statement)

    def _create_main_table(self):
        """
        Create the database main table if it doesn't exists.

        .. note:: SQLite does not have a storage class set aside for storing dates
        and/or times. Instead, the built-in Date And Time Functions of SQLite are
         capable of storing dates and times as TEXT, REAL, or INTEGER values:

        Reference:
        https://sqlite.org/datatype3.html
        """
        self._execute(
            """
            CREATE TABLE IF NOT EXISTS bundles ( 
                path text NOT NULL UNIQUE PRIMARY KEY,
                add_timestamp integer,
                last_access integer,
                usage_count integer
            );
            """
        )

    def _connect(self):
        """
        Open or re-open a connection to the database and returns it's connected object.
        The method simply returns the existing connected if database is alreayd opened.

        :return: a :class `~sqlite3.Connection` object.
        """
        if self._db_connection is None:
            self._db_connection = sqlite3.connect(self.path)
            log.debug("connected: %s" % (self.path))

        return self._db_connection


    def _find_entry(self, bundle_path):
        """
        Returns the specified entry if found in the database else returns None.

        :param bundle_path: a str entry identifier
        :return: a :class `~BundleCacheUsageDatabaseEntry` object or None
        """
        result = self._execute(
            """
            SELECT *
            FROM bundles
            WHERE path = ?
            """,
            (bundle_path,)
        )
        if result:
            tuple = result.fetchone()
            if tuple:
                return BundleCacheUsageDatabaseEntry(tuple)

        return None

    def _get_cursor(self):
        """
        Returns a database cursor.

        :return: A :class:`~sqlite3.Cursor` object
        """
        return self._connect().cursor()

    def _log_usage(self, bundle_path, timestamp, initial_usage_count):
        """
        Track usage of an entry specified by the `bundle_path` parameter.
        The method creates new entries if the specified entry cannot be found..

        :param bundle_path: a str entry identifier
        :param timestamp: An int unix timestamp
        :param initial_usage_count: an int initial entry usage count value
        """
        if bundle_path:
            entry = self._find_entry(bundle_path)
            if entry:
                # Update
                self._execute(
                    """
                    UPDATE bundles
                    SET last_access = ?,
                    usage_count = ?
                    WHERE path = ?
                    """,
                    (timestamp, entry.usage_count + 1, entry.path)
                )
            else:
                # Insert
                self._execute(
                    """
                    INSERT INTO bundles(
                        path,
                        add_timestamp,
                        last_access,
                        usage_count
                    ) 
                    VALUES(?,?,?,?)
                    """,
                    (bundle_path, timestamp, timestamp, initial_usage_count)
                )

            self._db_connection.commit()

    ###################################################################################################################
    #
    # PUBLIC API - methods
    #
    ###################################################################################################################

    def add_unused_bundle(self, bundle_path, timestamp):
        """
        Add an entry to the database which usage count is initialized to zero.

        .. note:: This is mostly for initial-pupulating the database as it allows
        differentiating entries added in the initial database population versus
        entries being updated in subsequent sessions.

        :param bundle_path: a str entry identifier
        """
        self._log_usage(bundle_path, timestamp, 0)

    @property
    def bundle_cache_root(self):
        """
        Returns the path the database was created in.

        :return: A str path, typically the bundle cache folder.
        """
        return self._bundle_cache_root

    def close(self):
        """
        Close the database connection.
        """
        if self._db_connection is not None:
            log.debug("close")
            self._db_connection.close()
            self._db_connection = None

    @property
    def connected(self):
        """
        Returns whether or not the database is currently connected.

        :return: A bool True if the datase is connected else False.
        """
        return self._db_connection is not None

    def delete_entry(self, bundle_path):
        """
        Delete the specified entry from the database

        :param bundle_path: a str entry identifier
        """
        self._execute(
            """
            DELETE FROM bundles
            WHERE path=?
            """,
            (bundle_path,)
        )

    def get_bundle_count(self):
        """
        Returns the number of bundles being tracked in the database.

        :return: an int count
        """
        result = self._execute(
            """
            SELECT COUNT(*)
            from bundles
            """
        )

        return result.fetchone()[0] if result else 0

    def get_last_usage_timestamp(self, bundle_path):
        """
        Returns the last accessed date of the specified entry as a unix timestamp integer.

        :param bundle_path: a str entry identifier
        :return: a int unix timestamp or 0 if the entry could not be found.
        """
        entry = self._find_entry(bundle_path)
        if entry:
            return entry.last_access_timestamp

        return 0

    def get_unused_bundles(self, since_timestamps):
        """
        Returns a list of entries that have a last access date older than
        the specified `since_timestamps` parameter.

        :param since_timestamps: An int unix timestamp
        :return: A list of :class:`~BundleCacheUsageDatabaseEntry`
        """
        result = self._execute(
            """
            SELECT *
            FROM bundles
            WHERE last_access <= ?
            """,
            (since_timestamps,)
        )

        entry_list = []
        if result:
            tuples = result.fetchall()
            for tuple in tuples:
                entry_list.append(BundleCacheUsageDatabaseEntry(tuple))

        return entry_list

    def get_usage_count(self, bundle_path):
        """
        Returns the number of time the specified entry was updated.
        :param bundle_path: A str identifier
        :return: An int count
        """
        entry = self._find_entry(bundle_path)
        if entry:
            return entry.usage_count

        return 0

    def log_usage(self, bundle_path, timestamp):
        """
        Update the last access date and increase the access count of the
        specified database entry if it exists in the database already
        otherwise a new entry is created with a usage count of 1.
        :param bundle_path: A str identifier
        :param timestamp: A int unix timestamp
        """
        self._log_usage(bundle_path, timestamp, 1)

    @property
    def path(self):
        """
        Returns the full path & filename to the database
        NOTE: The filename is not cleared on closing the database.
        :return: A string of the path & filename to the database file.
        """
        return self._bundle_cache_usage_db_filename



