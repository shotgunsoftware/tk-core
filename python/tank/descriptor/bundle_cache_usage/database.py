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
import time
import sqlite3
import datetime

from .errors import BundleCacheUsageInvalidBundleCacheRootError

from . import BundleCacheUsageMyLogger as log


class BundleCacheUsageDatabaseEntry(object):
    """
    Simple helper class wrapping database returned tuple into easier to access object.
    """

    def __init__(self, tuple):
        self._path = tuple[BundleCacheUsageDatabase.DB_COL_INDEX_PATH]
        self._add_timestamp = tuple[BundleCacheUsageDatabase.DB_COL_INDEX_ADD_TIMESTAMP]
        self._last_usage_timestamp = tuple[BundleCacheUsageDatabase.DB_COL_INDEX_LAST_USAGE_TIMESTAMP]
        self._usage_count = tuple[BundleCacheUsageDatabase.DB_COL_INDEX_USAGE_COUNT]

    @classmethod
    def _format_date_from_timestamp(cls, timestamp):
        """
        Class local date formatting method.

        :param timestamp: An int unix timestamp
        :return: A str human readable is the form:  Tuesday, 21. November 2017 04:30PM
        """

        # Usage of the 'datetime.datetime.fromtimestamp(n).isoformat()'
        # method formats something like: 2017-09-19T13:08:28

        # TODO: NICOLAS: is there an existing preset to this?
        return datetime.datetime.fromtimestamp(timestamp).strftime("%A, %d. %B %Y %I:%M%p")

    @property
    def add_date(self):
        """
        Returns the entry date when initially added to the database
        :return: an int unix timestamp
        """
        return BundleCacheUsageDatabaseEntry._format_date_from_timestamp(
            self.add_timestamp
        )

    @property
    def add_timestamp(self):
        """
        Returns the entry timestamp when initially added to the database 
        :return: an int unix timestamp
        """
        return self._add_timestamp

    @property
    def last_usage_date(self):
        """
        Returns the entry last accessed date
        :return: an str datetime
        """
        return BundleCacheUsageDatabaseEntry._format_date_from_timestamp(
            self.last_usage_timestamp
        )

    @property
    def last_usage_timestamp(self):
        """
        Returns the entry last accessed timestamp
        :return: an int unix timestamp
        """
        return self._last_usage_timestamp

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

    def __str__(self):
        return "%s, %d (%s)" % (self.path, self.last_usage_timestamp, self.last_usage_date)


class BundleCacheUsageDatabase(object):
    """
    Simple SQLite-based database for tracking bundle cache accesses.
    """

    DB_FILENAME = "bundle_usage.sqlite3"

    # database column indexes
    (
        DB_COL_INDEX_PATH,
        DB_COL_INDEX_ADD_TIMESTAMP,
        DB_COL_INDEX_LAST_USAGE_TIMESTAMP,
        DB_COL_INDEX_USAGE_COUNT
    ) = range(4)

    def __init__(self, bundle_cache_root):

        if bundle_cache_root is None:
            raise BundleCacheUsageInvalidBundleCacheRootError(
                "The 'bundle_cache_root' parameter is None."
            )

        if not os.path.exists(bundle_cache_root):
            raise BundleCacheUsageInvalidBundleCacheRootError(
                "The specified 'bundle_cache_root' parameter folder does not exists: %s" % (bundle_cache_root)
            )

        if not os.path.isdir(bundle_cache_root):
            raise BundleCacheUsageInvalidBundleCacheRootError(
                "The specified 'bundle_cache_root' parameter is not a directory: %s" % (bundle_cache_root)
            )

        self._bundle_cache_root = bundle_cache_root
        self._bundle_cache_usage_db_filename = os.path.join(
            self.bundle_cache_root,
            BundleCacheUsageDatabase.DB_FILENAME
        )

        self._create_main_table()

    def _execute(self, sql_statement, tuple=None):
        """
        Connects the database if not already connected and execute the
        specified SQL statement.

        :param sql_statement: a str of some SQL statement to be executed.
        :param tuple: An optional tuple with required SQL statement parameters
        :return:
        """
        with sqlite3.connect(self.path) as connection:

            # this is to handle unicode properly - make sure that sqlite returns
            # str objects for TEXT fields rather than unicode. Note that any unicode
            # objects that are passed into the database will be automatically
            # converted to UTF-8 strs, so this text_factory guarantees that any character
            # representation will work for any language, as long as data is either input
            # as UTF-8 (byte string) or unicode. And in the latter case, the returned data
            # will always be unicode.
            connection.text_factory = str

            cursor = connection.cursor()
            if cursor:
                if tuple:
                    return cursor.execute(sql_statement, tuple)
                else:
                    return cursor.execute(sql_statement)

                connection.commit()

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
                last_usage integer,
                usage_count integer
            );
            """
        )

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

    def _get_timestamp(self):
        """
        Internal utility method used throughout the interface to return a timestamp
        The return value can be overriden by assigning a Unix timestamp to the
        following env. variable: SHOTGUN_BUNDLE_CACHE_USAGE_TIMESTAMP_OVERRIDE

        :return: An int Unix timestamp.
        """
        timestamp_override = os.environ.get("SHOTGUN_BUNDLE_CACHE_USAGE_TIMESTAMP_OVERRIDE")
        if timestamp_override and len(timestamp_override):
            return int(timestamp_override)

        return int(time.time())

    def _log_usage(self, bundle_path, initial_usage_count):
        """
        Track usage of an entry specified by the `bundle_path` parameter.
        The method creates new entries if the specified entry cannot be found..

        :param bundle_path: a str entry identifier
        :param timestamp: An int unix timestamp
        :param initial_usage_count: an int initial entry usage count value
        """
        truncated_path = self._truncate_path(bundle_path)
        if truncated_path:
            now_unix_timestamp = self._get_timestamp()
            log.debug("_log_usage('%s', %d)" % (truncated_path, now_unix_timestamp))

            entry = self._find_entry(truncated_path)
            if entry:
                # Update
                self._execute(
                    """
                    UPDATE bundles
                    SET last_usage = ?,
                    usage_count = ?
                    WHERE path = ?
                    """,
                    (now_unix_timestamp, entry.usage_count + 1, entry.path)
                )
            else:
                # Insert
                self._execute(
                    """
                    INSERT INTO bundles(
                        path,
                        add_timestamp,
                        last_usage,
                        usage_count
                    ) 
                    VALUES(?,?,?,?)
                    """,
                    (truncated_path, now_unix_timestamp, now_unix_timestamp, initial_usage_count)
                )

    def _truncate_path(self, bundle_path):
        """
        Helper method that returns a truncated path of the specified bundle path.
        The returned path is relative to the `self._bundle_cache_root` property.

        :param bundle_path:
        :return: A str truncated path if path exists in `self._bundle_cache_root` else None
        """

        if not bundle_path or not bundle_path.startswith(self._bundle_cache_root):
            return None

        truncated_path = bundle_path.replace(self._bundle_cache_root, "")

        # also remove leading separator as it prevents os.path.join
        if truncated_path.startswith(os.sep):
            truncated_path = truncated_path[len(os.sep):]

        return truncated_path

    ###################################################################################################################
    #
    # PUBLIC API - methods
    #
    ###################################################################################################################

    def add_unused_bundle(self, bundle_path):
        """
        Add an entry to the database which usage count is initialized to zero.

        .. note:: This is mostly for initial-pupulating the database as it allows
        differentiating entries added in the initial database population versus
        entries being updated in subsequent sessions.

        :param bundle_path: a str path inside of the bundle cache
        """
        self._log_usage(bundle_path, 0)

    @property
    def bundle_cache_root(self):
        """
        Returns the path the database was created in.

        :return: A str path, typically the bundle cache folder.
        """
        return self._bundle_cache_root

    def delete_entry(self, bundle):
        """
        Delete the specified entry from the database

        :param bundle: a :class:`~BundleCacheUsageDatabaseEntry` object instance
        """
        self._execute(
            """
            DELETE FROM bundles
            WHERE path=?
            """,
            (bundle.path,)
        )

    def get_bundle(self, bundle_path):
        """
        Returns the database bundle entry matching the specified path or
        None if a match could not be found in the database.

        :param bundle_path: A str path inside the bundle cache folder.
        :return: A :class:`~BundleCacheUsageDatabaseEntry` object instance or None
        """

        truncated_path = self._truncate_path(bundle_path)
        if truncated_path:
            bundle = self._find_entry(truncated_path)
            if bundle:
                log.debug("get_bundle('%s') = %s" % (bundle_path, bundle))
                return bundle

        return None

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
            WHERE last_usage <= ?
            """,
            (since_timestamps,)
        )

        entry_list = []
        if result:
            tuples = result.fetchall()
            for tuple in tuples:
                entry_list.append(BundleCacheUsageDatabaseEntry(tuple))

        return entry_list

    def log_usage(self, bundle_path):
        """
        Update the last access date and increase the access count of the
        specified database entry if it exists in the database already
        otherwise a new entry is created with a usage count of 1.
        :param bundle_path: a str path inside of the bundle cache
        """
        self._log_usage(bundle_path, 1)

    @property
    def path(self):
        """
        Returns the full path & filename to the database
        NOTE: The filename is not cleared on closing the database.
        :return: A string of the path & filename to the database file.
        """
        return self._bundle_cache_usage_db_filename



