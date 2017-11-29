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

#from collections import deque
from threading import Event, Thread, Lock

from ... import LogManager
from ...util import LocalFileStorageManager
from scanner import BundleCacheScanner

log = LogManager.get_logger(__name__)
DEBUG = False


class BundleCacheUsageWriter(object):
    """
    A local flat file SQLite-based database tracking bundle cache accesses.
    """

    DB_MAIN_TABLE_NAME = "bundles"
    DB_FILENAME = "bundle_usage.db"
    DB_COL_ID = "id"
    DB_COL_ID_INDEX = 0
    DB_COL_PATH = "bundle_path"
    DB_COL_PATH_INDEX = 1
    DB_COL_ADD_DATE = "bundle_add_date"
    DB_COL_ADD_DATE_INDEX = 2
    DB_COL_LAST_ACCESS_DATE = "bundle_last_access_date"
    DB_COL_LAST_ACCESS_DATE_INDEX = 3
    DB_COL_ACCESS_COUNT = "bundle_access_count"
    DB_COL_ACCESS_COUNT_INDEX = 4

    # keeps track of the single instance of the class
    __instance = None

    def __new__(cls, *args, **kwargs):
        """Ensures only one instance of the metrics queue exists."""

        # create the queue instance if it hasn't been created already
        if not cls.__instance:

            log.info("__new__")

            # remember the instance so that no more are created
            singleton = super(BundleCacheUsageWriter, cls).__new__(cls, *args, **kwargs)
            singleton._lock = Lock()

            # The underlying collections.deque instance
            # singleton._queue = deque(maxlen=cls.MAXIMUM_QUEUE_SIZE)
            bundle_cache_root = args[0] if len(args)>0 else None
            singleton.__init_bundle_cache_root__(bundle_cache_root)
            singleton.__init_stats__()
            singleton.__init_db__()

            cls.__instance = singleton

        return cls.__instance

    def __init__(self, bundle_cache_root=None):
        log.info("__init__")

    # TODO: find a better way
    @classmethod
    def delete_instance(cls):
        cls.__instance = None

    #
    #def __del__(self):
    #    log.info("__del__")
    #    # Remove instance from _instances
    #    self.close()
    #    BundleCacheUsageWriter.__instance = None
    #

    def __init_bundle_cache_root__(self, bundle_cache_root):

        if bundle_cache_root is None:
            self._bundle_cache_root = LocalFileStorageManager.get_global_root(LocalFileStorageManager.CACHE)
            check_app_root = False
            self._bundle_cache_usage_db_filename = os.path.join(
                self.bundle_cache_root,
                BundleCacheUsageWriter.DB_FILENAME
            )
        elif bundle_cache_root == ":memory:":
            self._bundle_cache_root = bundle_cache_root
            self._bundle_cache_usage_db_filename = bundle_cache_root
            check_app_root = False
        else:
            self._bundle_cache_root = bundle_cache_root
            check_app_root = False
            self._bundle_cache_usage_db_filename = os.path.join(
                self.bundle_cache_root,
                BundleCacheUsageWriter.DB_FILENAME
            )

            self._app_store_root = os.path.join(self._bundle_cache_root, "app_store")

        if check_app_root:
            if not os.path.exists(self._app_store_root) or not os.path.isdir(self._app_store_root):
                raise Exception("BundleCacheUsageWriter initialisation failure, cannot find the 'app_store' folder.")

    def __init_stats__(self):
        # A few statistic metrics for tracking overall usage
        self._stat_connect_count = 0
        self._stat_close_count = 0
        self._stat_exec_count = 0

    def __init_db__(self):
        self._db_connection = None

        # If the database didn't existed before we'll trigger
        db_exists = os.path.exists(self.path) and os.path.isfile(self.path)

        self._connect()
        self._create_main_table()

        if not db_exists:
            log.info("No database, creating one, populating ...")
            bundle_list_path = BundleCacheScanner.find_bundles(self.bundle_cache_root)
            for bundle_path in bundle_list_path:
                self.log_usage(bundle_path)

        # this is to handle unicode properly - make sure that sqlite returns
        # str objects for TEXT fields rather than unicode. Note that any unicode
        # objects that are passed into the database will be automatically
        # converted to UTF-8 strs, so this text_factory guarantees that any character
        # representation will work for any language, as long as data is either input
        # as UTF-8 (byte string) or unicode. And in the latter case, the returned data
        # will always be unicode.
        self._db_connection.text_factory = str

    def _execute(self, sql_statement, tuple=None):
        """ Connects and execute some SQL statement"""
        try:
            if tuple:
                return self._get_cursor().execute(sql_statement, tuple)
            else:
                return self._get_cursor().execute(sql_statement)

        except Exception as e:
            print(e)
            raise e

    def _create_main_table(self):

        #
        #
        # SQLite does not have a storage class set aside for storing dates and/or times.
        # Instead, the built-in Date And Time Functions of SQLite are capable of storing
        # dates and times as TEXT, REAL, or INTEGER values:
        #
        # ref: https://sqlite.org/datatype3.html
        #
        sql_create_main_table = """CREATE TABLE IF NOT EXISTS %s ( 
                                          %s integer PRIMARY KEY,
                                          %s text NOT NULL UNIQUE,
                                          %s integer,
                                          %s integer,
                                          %s integer
                                      );""" % (BundleCacheUsageWriter.DB_MAIN_TABLE_NAME,
                                               BundleCacheUsageWriter.DB_COL_ID,
                                               BundleCacheUsageWriter.DB_COL_PATH,
                                               BundleCacheUsageWriter.DB_COL_ADD_DATE,
                                               BundleCacheUsageWriter.DB_COL_LAST_ACCESS_DATE,
                                               BundleCacheUsageWriter.DB_COL_ACCESS_COUNT)
        self._execute(sql_create_main_table)

    def _commit(self):
        """
        Commit data uncommited yet.
        """
        if self.connected:
            log.info("commit")
            self._db_connection.commit()

    def _connect(self):
        if self._db_connection is None:

            log.info("connect")
            self._db_connection = sqlite3.connect(self.path)
            self._stat_connect_count += 1

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
        try:
            bundle_entry_tuple = (bundle_path, timestamp, timestamp, initial_access_count)
            result = self._execute(sql_statement, bundle_entry_tuple)

        except Exception as e:
            print(e)
            raise e

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

    def _log_usage(self, bundle_path, initial_access_count=1):
        """

        :param bundle_path:
        :param initial_access_count: An optional integer, typically set to 1 from log_usage and zero from initial db polating.
        """
        if bundle_path:
            now_unix_timestamp = int(time.time())
            bundle_entry = self._find_bundle(bundle_path)
            if bundle_entry:
                #print("UPDATING: %s" % (bundle_path))
                # Update
                log.info("_update_bundle_entry('%s')" % bundle_path)
                access_count = bundle_entry[BundleCacheUsageWriter.DB_COL_ACCESS_COUNT_INDEX]
                self._update_bundle_entry(bundle_entry[BundleCacheUsageWriter.DB_COL_ID_INDEX],
                                          now_unix_timestamp,
                                          bundle_entry[BundleCacheUsageWriter.DB_COL_ACCESS_COUNT_INDEX]
                                          )
            else:
                # Insert
                log.info("_create_bundle_entry('%s')" % bundle_path)
                self._create_bundle_entry(bundle_path, now_unix_timestamp, initial_access_count)

            self._db_connection.commit()

    def _update_bundle_entry(self, entry_id, timestamp, last_access_count):
        try:
            sql_statement = "UPDATE %s SET %s = ?, %s = ? " \
                            "WHERE %s = ?" % (
                BundleCacheUsageWriter.DB_MAIN_TABLE_NAME,
                BundleCacheUsageWriter.DB_COL_LAST_ACCESS_DATE,
                BundleCacheUsageWriter.DB_COL_ACCESS_COUNT,
                BundleCacheUsageWriter.DB_COL_ID
            )
            update_tuple = (timestamp, last_access_count + 1, entry_id)
            result = self._execute(sql_statement, update_tuple)

        except Exception as e:
            print(e)
            raise e

    def _get_cursor(self):
        return self._connect().cursor()

    ###################################################################################################################
    #
    # PUBLIC API - properties
    #
    ###################################################################################################################

    @property
    def bundle_cache_root(self):
        return self._bundle_cache_root

    @property
    def bundle_count(self):
        """
        Returns the number of tracked bundles in the database.
        :return: An integer of a tracked bundle count
        """
        result = self._execute("SELECT * FROM %s" % (BundleCacheUsageWriter.DB_MAIN_TABLE_NAME))
        if result:
            rows = result.fetchall()
            return len(rows)
        else:
            return 0

    @property
    def connected(self):
        return self._db_connection is not None

    @property
    def path(self):
        """
        Returns the full path & filename to the database for this instance of the class.
        NOTE: The filename is not cleared cleared on closing the database.
        :return: A string of the path & filename to the database file.
        """
        return self._bundle_cache_usage_db_filename

    ###################################################################################################################
    #
    # PUBLIC API - methods
    #
    ###################################################################################################################

    def close(self):
        """
        Close the last access database connection.
        """
        if self._db_connection is not None:
            log.info("close")
            self._stat_close_count += 1
            self._db_connection.close()
            self._db_connection = None

    def get_usage_count(self, bundle_path):
        bundle_entry = self._find_bundle(bundle_path)
        if bundle_entry is None:
            return 0

        return bundle_entry[BundleCacheUsageWriter.DB_COL_ACCESS_COUNT_INDEX]

    def get_last_usage_date(self, bundle_path):
        bundle_entry = self._find_bundle(bundle_path)
        if bundle_entry is None:
            return None

        return bundle_entry[BundleCacheUsageWriter.DB_COL_LAST_ACCESS_DATE]

    def get_last_usage_timestamp(self, bundle_path):
        bundle_entry = self._find_bundle(bundle_path)
        if bundle_entry is None:
            return None

        return bundle_entry[BundleCacheUsageWriter.DB_COL_LAST_ACCESS_DATE]

    def log_usage(self, bundle_path):
        """

        :param bundle_path:

        NOTE: Distinguish with 'find_bundles' which add entries initialised to usage count of zero.
        """
        self._log_usage(bundle_path, 1)
