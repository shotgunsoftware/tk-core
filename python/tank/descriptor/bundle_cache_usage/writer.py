# Copyright (c) 2013 Shotgun Software Inc.
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

import sqlite3
import os
import time
from datetime import datetime, timedelta

from . import BundleCacheUsageLogger as log

class BundleCacheUsageWriter(object):
    """
    A local flat file SQLite-based database for tracking bundle cache accesses.
    """

    DB_MAIN_TABLE_NAME = "bundles"
    DB_FILENAME = "bundle_usage.sqlite3"
    DB_COL_ID = "id"
    DB_COL_ID_INDEX = 0
    DB_COL_PATH = "path"
    DB_COL_PATH_INDEX = 1
    DB_COL_ADD_DATE = "add_date"
    DB_COL_ADD_DATE_INDEX = 2
    DB_COL_LAST_ACCESS_DATE = "last_access_date"
    DB_COL_LAST_ACCESS_DATE_INDEX = 3
    DB_COL_ACCESS_COUNT = "access_count"
    DB_COL_ACCESS_COUNT_INDEX = 4

    def __init__(self, bundle_cache_root):
        log.debug_db_inst("__init__")
        self._bundle_cache_root = bundle_cache_root
        self._bundle_cache_usage_db_filename = os.path.join(
            self.bundle_cache_root,
            BundleCacheUsageWriter.DB_FILENAME
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

        :param sql_statement:
        :param tuple:
        :return:
        """
        if tuple:
            return self._get_cursor().execute(sql_statement, tuple)
        else:
            return self._get_cursor().execute(sql_statement)

    def _create_main_table(self):
        """
        Create the database main table if it doesn't exists.

        NOTE:
        SQLite does not have a storage class set aside for storing dates and/or times.
        Instead, the built-in Date And Time Functions of SQLite are capable of storing
        dates and times as TEXT, REAL, or INTEGER values:

        Reference:
        https://sqlite.org/datatype3.html
        """
        sql_statement = \
            """CREATE TABLE IF NOT EXISTS %s ( 
                %s integer PRIMARY KEY,
                %s text NOT NULL UNIQUE,
                %s integer,
                %s integer,
                %s integer
            );""" % (
                BundleCacheUsageWriter.DB_MAIN_TABLE_NAME,
                BundleCacheUsageWriter.DB_COL_ID,
                BundleCacheUsageWriter.DB_COL_PATH,
                BundleCacheUsageWriter.DB_COL_ADD_DATE,
                BundleCacheUsageWriter.DB_COL_LAST_ACCESS_DATE,
                BundleCacheUsageWriter.DB_COL_ACCESS_COUNT
            )
        self._execute(sql_statement)

    def _connect(self):
        """
        Open or re-open a connection to the database and returns it's connected object.
        The method simply returns the existing connected if database is alreayd opened.

        :return: A `sqlite3.Connection` object.
        """
        if self._db_connection is None:
            self._db_connection = sqlite3.connect(self.path)
            log.debug_db_inst("connected: %s" % (self.path))

        return self._db_connection

    def _create_bundle_entry(self, bundle_path, timestamp, initial_access_count):
        sql_statement = """INSERT INTO %s(%s, %s, %s, %s) VALUES(?,?,?,?)""" % (
            BundleCacheUsageWriter.DB_MAIN_TABLE_NAME,
            BundleCacheUsageWriter.DB_COL_PATH,
            BundleCacheUsageWriter.DB_COL_ADD_DATE,
            BundleCacheUsageWriter.DB_COL_LAST_ACCESS_DATE,
            BundleCacheUsageWriter.DB_COL_ACCESS_COUNT
        )

        """ Connects and execute some SQL statement"""
        bundle_entry_tuple = (bundle_path, timestamp, timestamp, initial_access_count)
        result = self._execute(sql_statement, bundle_entry_tuple)

    def _delete_bundle_entry(self, bundle_path):
        'DELETE FROM tasks WHERE id=?'
        sql_statement = "DELETE FROM %s WHERE %s=?" % (
            BundleCacheUsageWriter.DB_MAIN_TABLE_NAME,
            BundleCacheUsageWriter.DB_COL_PATH,
        )
        result = self._execute(sql_statement, (bundle_path,))

    def _find_bundle(self, bundle_path):
        """

        0 = {int} 1
        1 = {str} 'some-bundle-path1'
        2 = {int} 1511302427
        3 = {int} 1511302427
        4 = {int} 1

        :param bundle_path:
        :return: A bundle entry tuple or None if an entry was not found
        """
        result = self._execute("SELECT * FROM %s "
                               "WHERE %s = ?" % (
                                   BundleCacheUsageWriter.DB_MAIN_TABLE_NAME,
                                   BundleCacheUsageWriter.DB_COL_PATH
                               ), (bundle_path,))

        if result is None:
            return None

        rows = result.fetchall()
        if len(rows) == 0:
            return None

        return rows[0]

    def _get_cursor(self):
        """
        Returns a SQLite database cursor
        :return: A `sqlite3.Cursor` object
        """
        return self._connect().cursor()

    def _get_entries_unused_since_last_days(self, days):
        """

        :param days:
        :param initial_access_count: An optional integer, typically set to 1 from log_usage and zero from initial db polating.
        """

        oldest_date = datetime.today() - timedelta(days=days)
        oldest_timestamp = time.mktime(oldest_date.timetuple())

        try:
            sql_statement = "SELECT * FROM %s " \
                            "WHERE %s <= %d " % (
                                BundleCacheUsageWriter.DB_MAIN_TABLE_NAME,
                                BundleCacheUsageWriter.DB_COL_LAST_ACCESS_DATE,
                                oldest_timestamp
                            )

            result = self._execute(sql_statement)
            return result.fetchall()

        except Exception as e:
            print(e)
            raise e

    def _log_usage(self, bundle_path, initial_access_count=1):
        """

        :param bundle_path:
        :param initial_access_count: An optional integer, typically set to 1 from log_usage and zero from initial db polating.
        """
        if bundle_path:
            now_unix_timestamp = int(time.time())
            bundle_entry = self._find_bundle(bundle_path)
            if bundle_entry:
                # Update
                log.debug_db_hf("_update_bundle_entry('%s')" % bundle_path)
                access_count = bundle_entry[BundleCacheUsageWriter.DB_COL_ACCESS_COUNT_INDEX]
                self._update_bundle_entry(bundle_entry[BundleCacheUsageWriter.DB_COL_ID_INDEX],
                                          now_unix_timestamp,
                                          bundle_entry[BundleCacheUsageWriter.DB_COL_ACCESS_COUNT_INDEX]
                                          )
            else:
                # Insert
                log.debug_db_hf("_create_bundle_entry('%s')" % bundle_path)
                self._create_bundle_entry(bundle_path, now_unix_timestamp, initial_access_count)

            self._db_connection.commit()

    def _update_bundle_entry(self, entry_id, timestamp, last_access_count):
        sql_statement = "UPDATE %s SET %s = ?, %s = ? " \
                        "WHERE %s = ?" % (
            BundleCacheUsageWriter.DB_MAIN_TABLE_NAME,
            BundleCacheUsageWriter.DB_COL_LAST_ACCESS_DATE,
            BundleCacheUsageWriter.DB_COL_ACCESS_COUNT,
            BundleCacheUsageWriter.DB_COL_ID
        )
        update_tuple = (timestamp, last_access_count + 1, entry_id)
        result = self._execute(sql_statement, update_tuple)

    ###################################################################################################################
    #
    # PUBLIC API - methods
    #
    ###################################################################################################################

    def add_unused_bundle(self, bundle_path):
        """
        Add an entry to the database which usage count is initialized with zero.
        :param bundle_path: a str path to a bundle cache item
        """
        self._log_usage(bundle_path, 0)

    @property
    def bundle_cache_root(self):
        """
        Returns the path to the cache bundle this instance was initialized with.
        :return: A str path t bundle cache folder.
        """
        return self._bundle_cache_root

    @property
    def bundle_count(self):
        """
        Returns the number of bundles tracked in the database.
        :return: An integer of a tracked bundle count
        """
        result = self._execute("SELECT * FROM %s" % (BundleCacheUsageWriter.DB_MAIN_TABLE_NAME))
        if not result:
            return 0

        rows = result.fetchall()
        return len(rows)

    def close(self):
        """
        Close the database connection.
        """
        if self._db_connection is not None:
            log.debug_db_inst("close")
            self._db_connection.close()
            self._db_connection = None

    @property
    def connected(self):
        """
        Returns whether or not teh database is currently connected.
        :return: A bool True if the datase is connected else False.
        """
        return self._db_connection is not None

    def delete_entry(self, bundle_path):
        """
        Delete the specified entry from the database
        and the bundle cache usage database.
        :param path: a str path of an entry to be deleted from database
        """
        if self._find_bundle(bundle_path):
            self._delete_bundle_entry(bundle_path)
            log.debug_db_delete("Delete entry '%s'" % str(bundle_path))

    def get_unused_bundles(self, since_days=60):
        return []

    def get_usage_count(self, bundle_path):
        bundle_entry = self._find_bundle(bundle_path)
        if bundle_entry is None:
            return 0

        return bundle_entry[BundleCacheUsageWriter.DB_COL_ACCESS_COUNT_INDEX]

    def get_last_usage_date(self, bundle_path):
        bundle_entry = self._find_bundle(bundle_path)
        if bundle_entry is None:
            return None

        return bundle_entry[BundleCacheUsageWriter.DB_COL_LAST_ACCESS_DATE_INDEX]

    def get_last_usage_timestamp(self, bundle_path):
        bundle_entry = self._find_bundle(bundle_path)
        if bundle_entry is None:
            return None

        return bundle_entry[BundleCacheUsageWriter.DB_COL_LAST_ACCESS_DATE_INDEX]

    def log_usage(self, bundle_path):
        """
        Increase the database usage count and access date for the specified entry.
        If the entry was not in the database already, the usage count will be
        initialized to 1.

        NOTE: The specified path is truncated and relative to the `bundle_cache_root` property.

        :param bundle_path: A str path to a bundle
        """
        self._log_usage(bundle_path, 1)

    @property
    def path(self):
        """
        Returns the full path & filename to the database for this instance.
        NOTE: The filename is not cleared on closing the database.
        :return: A string of the path & filename to the database file.
        """
        return self._bundle_cache_usage_db_filename



