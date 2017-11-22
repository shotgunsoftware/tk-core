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

from .. import LogManager
from ..util import LocalFileStorageManager

log = LogManager.get_logger(__name__)
DEBUG = True


class Timer(object):
    def __init__(self):
        self._start_time = time.time()
        self._stop_time = None

    @property
    def elapsed(self):
        if self.stopped:
            return self._stop_time - self._start_time
        else:
            now = time.time()
            return now - self._start_time

    @property
    def elapsed_msg(self):
        return "Elapsed: %s seconds" % ( str(self.elapsed))

    def stop(self):
        self._stop_time = time.time()

    @property
    def stopped(self):
        return self._stop_time is not None


class BundleCacheUsage(object):
    """
    A local flat file SQLite-based database tracking bundle cache accesses.
    """

    # Shotgun field definitions to store the path cache data
    SHOTGUN_ENTITY = "FilesystemLocation"
    SG_ENTITY_FIELD = "entity"
    SG_PATH_FIELD = "path"
    SG_METADATA_FIELD = "configuration_metadata"
    SG_IS_PRIMARY_FIELD = "is_primary"
    SG_ENTITY_ID_FIELD = "linked_entity_id"
    SG_ENTITY_TYPE_FIELD = "linked_entity_type"
    SG_ENTITY_NAME_FIELD = "code"
    SG_PIPELINE_CONFIG_FIELD = "pipeline_configuration"

    DB_MAIN_TABLE_NAME = "bundles"
    DB_FILENAME = "usage.db"
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

    def __init__(self, bundle_cache_root=None):
        """
        Constructor.Sets up the database
        """

        if bundle_cache_root is None:
            self._bundle_cache_root = LocalFileStorageManager.get_global_root(LocalFileStorageManager.CACHE)
            check_app_root = False
            self._bundle_cache_usage_db_filename = os.path.join(
                self.bundle_cache_root,
                BundleCacheUsage.DB_FILENAME
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
                BundleCacheUsage.DB_FILENAME
            )

        self._app_store_root = os.path.join(self._bundle_cache_root, "app_store")

        if check_app_root:
            if not os.path.exists(self._app_store_root) or not os.path.isdir(self._app_store_root):
                raise Exception("BundleCacheUsage initialisation failure, cannot find the 'app_store' folder.")

        # A few statistic metrics for tracking overall usage
        self._stat_connect_count = 0
        self._stat_close_count = 0
        self._stat_exec_count = 0

        self._db_connection = None
        #self._db_location = None

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
                                      );""" % (BundleCacheUsage.DB_MAIN_TABLE_NAME,
                                               BundleCacheUsage.DB_COL_ID,
                                               BundleCacheUsage.DB_COL_PATH,
                                               BundleCacheUsage.DB_COL_ADD_DATE,
                                               BundleCacheUsage.DB_COL_LAST_ACCESS_DATE,
                                               BundleCacheUsage.DB_COL_ACCESS_COUNT)
        self._execute(sql_create_main_table)

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
            BundleCacheUsage.DB_MAIN_TABLE_NAME,
            BundleCacheUsage.DB_COL_PATH
        ), (bundle_path, ))

        if result is None:
            return None

        rows = result.fetchall()
        if len(rows) == 0:
            return None

        return rows[0]

    def _create_bundle_entry(self, bundle_path, timestamp):
        sql_statement = """INSERT INTO %s(%s, %s, %s, %s) VALUES(?,?,?,?)""" % (
            BundleCacheUsage.DB_MAIN_TABLE_NAME,
            BundleCacheUsage.DB_COL_PATH,
            BundleCacheUsage.DB_COL_ADD_DATE,
            BundleCacheUsage.DB_COL_LAST_ACCESS_DATE,
            BundleCacheUsage.DB_COL_ACCESS_COUNT
        )

        """ Connects and execute some SQL statement"""
        try:
            bundle_entry_tuple = (bundle_path, timestamp, timestamp, 1)
            result = self._execute(sql_statement, bundle_entry_tuple)

        except Exception as e:
            print(e)
            raise e

    def _update_bundle_entry(self, entry_id, timestamp, last_access_count):
        try:
            sql_statement = "UPDATE %s SET %s = ?, %s = ? " \
                            "WHERE %s = ?" % (
                BundleCacheUsage.DB_MAIN_TABLE_NAME,
                BundleCacheUsage.DB_COL_LAST_ACCESS_DATE,
                BundleCacheUsage.DB_COL_ACCESS_COUNT,
                BundleCacheUsage.DB_COL_ID
            )
            update_tuple = (timestamp, last_access_count + 1, entry_id)
            result = self._execute(sql_statement, update_tuple)

        except Exception as e:
            print(e)
            raise e

    def _get_cursor(self):
        return self.connect().cursor()

    @classmethod
    def _find_app_store_path(cls, base_folder):
        for (dirpath, dirnames, filenames) in os.walk(base_folder):
            if dirpath.endswith('app_store'):
                return dirpath

        return None

    @classmethod
    def _walk_bundle_cache(cls, bundle_cache_root, MAX_DEPTH_WALK=2):
        """
        Scan the bundle cache (specified at object creation) for bundles and add them to the database

        TODO: Find a tk-core reference about why MAX_DEPTH_WALK should be set to 2
        """

        # Initial version, although I know already this is not exactly what
        # I want since we do want to leave a folder upon finding a info.yml file.
        # https://stackoverflow.com/a/2922878/710183

        #
        # Walk up to a certain level
        # https://stackoverflow.com/questions/42720627/python-os-walk-to-certain-level

        bundle_list = []
        bundle_cache_app_store = cls._find_app_store_path(bundle_cache_root)

        if bundle_cache_app_store:
            for (dirpath, dirnames, filenames) in os.walk(bundle_cache_app_store):
                if dirpath[len(bundle_cache_app_store) + 1:].count(os.sep) <= MAX_DEPTH_WALK:
                    for filename in filenames:
                        if filename.endswith('info.yml'):
                            bundle_list.append(dirpath)

        return bundle_list

    ###################################################################################################################
    #
    # PUBLIC API
    #
    ###################################################################################################################

    def connect(self):
        if self._db_connection is None:
            log.debug("connect")
            self._db_connection = sqlite3.connect(self._bundle_cache_usage_db_filename)
            self._stat_connect_count += 1

        return self._db_connection

    def close(self):
        """
        Close the last access database connection.
        """
        if self._db_connection is not None:
            log.debug("close")
            self._stat_close_count += 1
            self._db_connection.close()
            self._db_connection = None

    def commit(self):
        """
        Commit data uncommited yet.
        """
        if self.connected:
            log.debug("commit")
            self._db_connection.commit()

    def log_usage(self, bundle_path):
        now_unix_timestamp = int(time.time())
        bundle_entry = self._find_bundle(bundle_path)
        if bundle_entry:
            #print("UPDATING: %s" % (bundle_path))
            # Update
            log.debug("_update_bundle_entry('%s')" % bundle_path)
            access_count = bundle_entry[BundleCacheUsage.DB_COL_ACCESS_COUNT_INDEX]
            self._update_bundle_entry(bundle_entry[BundleCacheUsage.DB_COL_ID_INDEX],
                                      now_unix_timestamp,
                                      bundle_entry[BundleCacheUsage.DB_COL_ACCESS_COUNT_INDEX]
                                      )
        else:
            # Insert
            log.debug("_create_bundle_entry('%s')" % bundle_path)
            self._create_bundle_entry(bundle_path, now_unix_timestamp)

        self._db_connection.commit()

    def get_usage_count(self, bundle_path):
        bundle_entry = self._find_bundle(bundle_path)
        if bundle_entry is None:
            return 0

        return bundle_entry[BundleCacheUsage.DB_COL_ACCESS_COUNT_INDEX]

    def get_last_usage_date(self, bundle_path):
        bundle_entry = self._find_bundle(bundle_path)
        if bundle_entry is None:
            return None

        return bundle_entry[BundleCacheUsage.DB_COL_LAST_ACCESS_DATE]

    def get_last_usage_timestamp(self, bundle_path):
        bundle_entry = self._find_bundle(bundle_path)
        if bundle_entry is None:
            return None

        return bundle_entry[BundleCacheUsage.DB_COL_LAST_ACCESS_DATE]

    @property
    def bundle_cache_root(self):
        return self._bundle_cache_root

    @property
    def bundle_count(self):
        """
        Returns the number of tracked bundles in the database.
        :return: An integer of a tracked bundle count
        """
        result = self._execute("SELECT * FROM %s" % (BundleCacheUsage.DB_MAIN_TABLE_NAME))
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

    def find_bundles(self):
        """
        Scan the bundle cache (specified at object creation) for bundles and add them to the database
        """

        t = Timer()
        # Initial version, although I know already this is not exactly what
        # I want since we do want to leave a folder upon finding a info.yml file.
        # https://stackoverflow.com/a/2922878/710183
        bundle_path_list = self._walk_bundle_cache(self.bundle_cache_root)
        for bundle_path in bundle_path_list:
            self.log_usage(bundle_path)

        log.debug("find_bundles: %s" % (t.elapsed_msg))



