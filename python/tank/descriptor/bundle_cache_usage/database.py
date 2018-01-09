# Copyright (c) 2017 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.


import os
import time
import sqlite3
import datetime

from ...import LogManager
from ...util.local_file_storage import LocalFileStorageManager

from .errors import BundleCacheTrackingInvalidBundleCacheRootError


log = LogManager.get_logger(__name__)


class BundleCacheUsageDatabaseEntry(object):
    """
    Simple helper class wrapping database returned record into easier to access object.
    """

    def __init__(self, db_record):
        """
        Initialise an object with content of the specified database record.
        :param db_record: a tuple of the following form:
            ( str path, int record creation time, int last usage time, int usage count )
        """
        self._path = db_record[BundleCacheUsageDatabase.DB_COL_INDEX_PATH]
        self._creation_time = db_record[BundleCacheUsageDatabase.DB_COL_INDEX_CREATION_TIMESTAMP]
        self._last_usage_time = db_record[BundleCacheUsageDatabase.DB_COL_INDEX_LAST_USAGE_TIMESTAMP]
        self._usage_count = db_record[BundleCacheUsageDatabase.DB_COL_INDEX_USAGE_COUNT]

    @classmethod
    def _format_date_from_timestamp(cls, time):
        """
        Class local date formatting method.

        :param time: An int unix timestamp
        :return: an str human readable formatted datetime such as: Tuesday, 21. November 2017 14:30:22
        """
        return datetime.datetime.fromtimestamp(time).strftime("%A, %d. %B %Y %H:%M%:%S")

    @property
    def creation_date_formatted(self):
        """
        Returns the entry date when added to the database in a human readable
        formatted datetime string such as: Tuesday, 21. November 2017 14:30:22
        """
        return BundleCacheUsageDatabaseEntry._format_date_from_timestamp(
            self.creation_time
        )

    @property
    def creation_time(self):
        """
        Returns the entry time when initially added to the database in an integer Unix timestamp
        """
        return self._creation_time

    @property
    def last_usage_date_formatted(self):
        """
        Returns the entry last accessed date in a human readable
        formatted datetime string such as: Tuesday, 21. November 2017 14:30:22
        """
        return BundleCacheUsageDatabaseEntry._format_date_from_timestamp(
            self.last_usage_time
        )

    @property
    def last_usage_time(self):
        """
        Returns the entry last accessed time in an integer Unix timestamp
        """
        return self._last_usage_time

    @property
    def path(self):
        """
        Returns the entry identifier with truncated path
        """
        return self._path

    @property
    def usage_count(self):
        """
        Returns an integer of the entry usage count
        """
        return self._usage_count

    def __str__(self):
        """
        Returns a conveniently in the form: `path, last usage Unix, last usage date (formatted)`
        """
        return "%s, %d (%s)" % (self.path, self.last_usage_time, self.last_usage_date_formatted)


class BundleCacheUsageDatabase(object):
    """
    Simple SQLite-based database for tracking bundle cache accesses.
    """

    DB_FILENAME = "bundle_usage.sqlite3"

    # A database flag that indicates that the the initial bundle cache scan was performed.
    INITIAL_DB_POPULATE_DONE_MARKER = "INITIAL_POPULATE_DONE"

    # database column indexes
    (
        DB_COL_INDEX_PATH,
        DB_COL_INDEX_CREATION_TIMESTAMP,
        DB_COL_INDEX_LAST_USAGE_TIMESTAMP,
        DB_COL_INDEX_USAGE_COUNT
    ) = range(4)

    def __init__(self):

        bundle_cache_root = os.path.join(
            LocalFileStorageManager.get_global_root(
                LocalFileStorageManager.CACHE
            ),
            "bundle_cache"
        )

        if bundle_cache_root is None:
            raise BundleCacheUsageInvalidBundleCacheRootError(
                "The 'bundle_cache_root' is None."
            )

        if not os.path.exists(bundle_cache_root):
            raise BundleCacheUsageInvalidBundleCacheRootError(
                "The 'bundle_cache_root' folder does not exists: %s" % (bundle_cache_root)
            )

        if not os.path.isdir(bundle_cache_root):
            raise BundleCacheUsageInvalidBundleCacheRootError(
                "The 'bundle_cache_root' is not a directory: %s" % (bundle_cache_root)
            )

        self._bundle_cache_root = bundle_cache_root
        self._bundle_cache_usage_db_filename = os.path.join(
            self.bundle_cache_root,
            BundleCacheUsageDatabase.DB_FILENAME
        )

        self._create_main_table()

    def _execute(self, sql_statement, sql_params=None):
        """
        Connects the database if not already connected and execute the
        specified SQL statement.

        :param sql_statement: a str of some SQL statement to be executed.
        :param sql_params: An optional tuple with required SQL statement parameters
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
                if sql_params:
                    return cursor.execute(sql_statement, sql_params)
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
                creation integer,
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
            db_record = result.fetchone()
            if db_record:
                return BundleCacheUsageDatabaseEntry(db_record)

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

    def _track_usage(self, bundle_path, initial_usage_count):
        """
        Track usage of an entry specified by the `bundle_path` parameter.
        The method creates new entries if the specified entry cannot be found..

        :param bundle_path: a str entry identifier
        :param initial_usage_count: an int initial entry usage count value
        """
        truncated_path = self._truncate_path(bundle_path)
        if truncated_path:
            now_unix_timestamp = self._get_timestamp()
            self._execute(
                """
                INSERT OR REPLACE INTO bundles (
                    path,
                    creation,
                    last_usage,
                    usage_count
                )
                VALUES(
                    ?,
                    COALESCE((SELECT creation FROM bundles WHERE path=?), ?),
                    ?,
                    COALESCE((SELECT usage_count FROM bundles WHERE path=?)+1, ?)
                )
                """,
                (
                    truncated_path,                      # Set 'path'
                    truncated_path, now_unix_timestamp,  # Get OR set 'creation'
                    now_unix_timestamp,                  # Set 'last_usage'
                    truncated_path, initial_usage_count  # Update OR set 'usage_count'
                )
            )

    @property
    def _marker_path(self):
        """
        Helper property returning a bundle-like full path marker name which includes the base path

        .. note:: the marker is used to specify that the initial bundle search was performed.
        """
        return os.path.join(self.bundle_cache_root, self.INITIAL_DB_POPULATE_DONE_MARKER)

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
        self._track_usage(bundle_path, 0)

    @property
    def bundle_cache_root(self):
        """
        Returns the path of the typical global bundle cache root folder.
        """
        return self._bundle_cache_root

    @property
    def bundle_count(self):
        """
        Returns an integer of the number of currently tracked bundles in the database
        """
        result = self._execute(
            """
            SELECT COUNT(*)
            FROM bundles
            WHERE path!=?
            """
            , (self.INITIAL_DB_POPULATE_DONE_MARKER,)
        )

        return result.fetchone()[0] if result else 0

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
                return bundle

        return None

    def get_unused_bundles(self, since_timestamp):
        """
        Returns a list of entries that have a last access date older than
        the specified `since_timestamps` parameter.

        :param since_timestamp: An int unix timestamp
        :return: A list of :class:`~BundleCacheUsageDatabaseEntry`
        """
        result = self._execute(
            """
            SELECT *
            FROM bundles
            WHERE last_usage <= ? AND path!=?
            """,
            (since_timestamp, self.INITIAL_DB_POPULATE_DONE_MARKER)
        )

        return [BundleCacheUsageDatabaseEntry(r) for r in result.fetchall()]

    def track_usage(self, bundle_path):
        """
        Update the last access date and increase the access count of the
        specified database entry if it exists in the database already
        otherwise a new entry is created with a usage count of 1.
        :param bundle_path: a str path inside of the bundle cache
        """
        self._track_usage(bundle_path, 1)

    @property
    def path(self):
        """
        Returns a string of the full path & filename to the database
        NOTE: The filename is not cleared on closing the database.
        """
        return self._bundle_cache_usage_db_filename

    @property
    def initial_populate_performed(self):
        """
        Returns whether or not the initial database population was performed.
        :return: bool True if the initial population was performed else False
        """
        return self.get_bundle(self._marker_path) is not None

    @initial_populate_performed.setter
    def initial_populate_performed(self, performed):
        """
        Sets or clears the initial database population was performed flag by adding a special record marker.
        :param performed: Bool
        """
        if performed:
            # Add marker
            self.track_usage(self._marker_path)
        else:
            # Remove marker
            # NOTE: No need to use full path and then truncate
            self._execute(
                """
                DELETE FROM bundles
                WHERE path=?
                """,
                (self.INITIAL_DB_POPULATE_DONE_MARKER,)
            )



