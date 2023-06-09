from oc_ds_converter.oc_idmanager.pmcid import PMCIDManager
import json
import sqlite3
import os.path
import unittest
from os import makedirs
from os.path import exists, join

import xmltodict
from oc_ds_converter.oc_idmanager import *
from oc_ds_converter.oc_idmanager.base import IdentifierManager
from requests import ReadTimeout, get
from requests.exceptions import ConnectionError
from oc_ds_converter.oc_idmanager.oc_data_storage.storage_manager import StorageManager
from oc_ds_converter.oc_idmanager.oc_data_storage.in_memory_manager import InMemoryStorageManager
from oc_ds_converter.oc_idmanager.oc_data_storage.sqlite_manager import SqliteStorageManager

class pmcIdentifierManagerTest(unittest.TestCase):
    """This class aim at testing identifiers manager."""

    def setUp(self):
        if not exists("tmp"):
            makedirs("tmp")

        self.test_dir = join("test", "data")
        self.test_json_path = join(self.test_dir, "glob.json")
        with open(self.test_json_path, encoding="utf-8") as fp:
            self.data = json.load(fp)

        self.valid_pmc_1 = "PMC8384044"
        self.valid_pmc_2 = "PMC6716460"
        self.invalid_pmc_1 = "0128564"
        self.invalid_pmc_2 = "PMC6716"
        self.invalid_pmc_3 = "PMC10000716468"
        self.invalid_pmc_4 = "PMC100007468"

    def test_exists(self):
        with self.subTest(msg="get_extra_info=True, allow_extra_api=None"):
            pmc_manager = PMCIDManager()
            output = pmc_manager.exists('PMC8384044', get_extra_info=True, allow_extra_api=None)
            expected_output = (True, {'id': 'PMC8384044', 'valid': True})
            self.assertEqual(output, expected_output)
        with self.subTest(msg="get_extra_info=False, allow_extra_api=None"):
            pmc_manager = PMCIDManager()
            output = pmc_manager.exists('PMC6716460', get_extra_info=False, allow_extra_api=None)
            expected_output = True
            self.assertEqual(output, expected_output)


    def test_pmcid_normalise(self):
        pcm = PMCIDManager()
        self.assertEqual(
            pcm.normalise(self.valid_pmc_1),
            pcm.normalise(' ' + self.valid_pmc_1),
        )
        self.assertEqual(
            pcm.normalise(self.valid_pmc_2),
            pcm.normalise("https://www.ncbi.nlm.nih.gov/pmc/articles/" + self.valid_pmc_2),
        )

    def test_pmcid_is_valid(self):
        pcm = PMCIDManager()
        self.assertTrue(pcm.is_valid(self.valid_pmc_1))
        self.assertTrue(pcm.is_valid(self.valid_pmc_2))
        self.assertFalse(pcm.is_valid(self.invalid_pmc_1))
        self.assertFalse(pcm.is_valid(self.invalid_pmc_2))

    def test_pmc_is_valid(self):
        dm_nofile = PMCIDManager()
        self.assertTrue(dm_nofile.is_valid(self.valid_pmc_1))
        self.assertTrue(dm_nofile.is_valid(self.valid_pmc_2))
        self.assertFalse(dm_nofile.is_valid(self.invalid_pmc_1))
        self.assertFalse(dm_nofile.is_valid(self.invalid_pmc_2))

        dm_file = PMCIDManager(storage_manager=InMemoryStorageManager(self.test_json_path), use_api_service=False)
        self.assertTrue(dm_file.normalise(self.valid_pmc_1, include_prefix=True) in self.data)
        self.assertTrue(dm_file.normalise(self.invalid_pmc_4, include_prefix=True) in self.data)
        self.assertTrue(dm_file.is_valid(self.valid_pmc_1))
        self.assertFalse(dm_file.is_valid(self.invalid_pmc_4))


    def test_pmc_default(self):
        am_nofile = PMCIDManager()
        # No support files (it generates it)
        # Default storage manager : in Memory + generates file on method call (not automatically)
        # uses API
        self.assertTrue(am_nofile.is_valid(self.valid_pmc_1))
        self.assertTrue(am_nofile.is_valid(self.valid_pmc_2))
        self.assertFalse(am_nofile.is_valid(self.invalid_pmc_2))
        self.assertFalse(am_nofile.is_valid(self.invalid_pmc_1))
        am_nofile.storage_manager.store_file()
        validated_ids = [self.valid_pmc_1, self.valid_pmc_2, self.invalid_pmc_1, self.invalid_pmc_2]
        validated = [am_nofile.normalise(x, include_prefix=True) for x in validated_ids if am_nofile.normalise(x, include_prefix=True)]
        # check that the support file was correctly created
        self.assertTrue(os.path.exists("storage/id_value.json"))
        lj = open("storage/id_value.json")
        load_dict = json.load(lj)
        lj.close()
        stored = [am_nofile.normalise(x, include_prefix=True) for x in load_dict if am_nofile.normalise(x, include_prefix=True)]

        # check that all the validated ids are stored in the json file
        self.assertTrue(all(x in stored for x in validated))
        am_nofile.storage_manager.delete_storage()
        # check that the support file was correctly deleted
        self.assertFalse(os.path.exists("storage/id_value.json"))

    def test_pmc_memory_file_noapi(self):
        # Uses support file (without updating it)
        # Uses InMemoryStorageManager storage manager
        # does not use API (so a syntactically correct id is considered to be valid)
        am_file = PMCIDManager(storage_manager=InMemoryStorageManager(self.test_json_path), use_api_service=False)
        self.assertTrue(am_file.normalise(self.valid_pmc_1, include_prefix=True) in self.data)
        self.assertTrue(am_file.normalise(self.invalid_pmc_4, include_prefix=True) in self.data)
        self.assertFalse(am_file.is_valid(self.invalid_pmc_1)) # is stored in support file as invalid
        self.assertTrue(am_file.is_valid(am_file.normalise(self.invalid_pmc_3, include_prefix=True))) # is not stored in support file as invalid, does not exist but has correct syntax

    def test_pmc_memory_file_api(self):
        # Uses support file (without updating it)
        # Uses InMemoryStorageManager storage manager
        # uses API (so a syntactically correct id which is not valid is considered to be invalid)
        am_file = PMCIDManager(storage_manager=InMemoryStorageManager(self.test_json_path), use_api_service=True)
        self.assertFalse(am_file.is_valid(self.invalid_pmc_1))

    def test_pmc_memory_nofile_noapi(self):
        # Does not use support file
        # Uses InMemoryStorageManager storage manager
        # Does not use API (so a syntactically correct id which is not valid is considered to be valid)
        am_nofile_noapi = PMCIDManager(storage_manager=InMemoryStorageManager(), use_api_service=False)
        self.assertTrue(am_nofile_noapi.is_valid(self.valid_pmc_1))
        self.assertTrue(am_nofile_noapi.is_valid(self.invalid_pmc_3))
        am_nofile_noapi.storage_manager.delete_storage()



    def test_pmc_sqlite_nofile_api(self):
        # No support files (it generates it)
        # storage manager : SqliteStorageManager
        # uses API
        sql_am_nofile = PMCIDManager(storage_manager=SqliteStorageManager())
        self.assertTrue(sql_am_nofile.is_valid(self.valid_pmc_1))
        self.assertTrue(sql_am_nofile.is_valid(self.valid_pmc_2))
        self.assertFalse(sql_am_nofile.is_valid(self.invalid_pmc_1))
        self.assertFalse(sql_am_nofile.is_valid(self.invalid_pmc_2))
        # check that the support db was correctly created and that it contains all the validated ids
        self.assertTrue(os.path.exists("storage/id_valid_dict.db"))
        validated_ids = [self.valid_pmc_1, self.valid_pmc_2, self.invalid_pmc_1, self.invalid_pmc_2]
        all_ids_stored = sql_am_nofile.storage_manager.get_all_keys()
        # check that all the validated ids are stored in the json file
        stored = [x for x in all_ids_stored]
        validated = [sql_am_nofile.normalise(x, include_prefix=True) for x in validated_ids if sql_am_nofile.normalise(x, include_prefix=True)]
        self.assertTrue(all(x in stored for x in validated))
        sql_am_nofile.storage_manager.delete_storage()
        # check that the support file was correctly deleted
        self.assertFalse(os.path.exists("storage/id_valid_dict.db"))

    def test_pmc_sqlite_file_api(self):
        # Uses support file
        # Uses SqliteStorageManager storage manager
        # does not use API (so a syntactically correct id is considered to be valid)
        # db creation
        test_sqlite_db = os.path.join(self.test_dir, "database.db")
        if os.path.exists(test_sqlite_db):
            os.remove(test_sqlite_db)
        #con = sqlite3.connect(test_sqlite_db)
        #cur = con.cursor()
        to_insert = [self.invalid_pmc_1, self.valid_pmc_1]
        sql_file = PMCIDManager(storage_manager=SqliteStorageManager(test_sqlite_db), use_api_service=True)
        for id in to_insert:
            norm_id = sql_file.normalise(id, include_prefix=True)
            is_valid = 1 if sql_file.is_valid(norm_id) else 0
            insert_tup = (norm_id, is_valid)
            sql_file.storage_manager.cur.execute( f"INSERT OR REPLACE INTO info VALUES (?,?)", insert_tup )
            sql_file.storage_manager.con.commit()
        sql_file.storage_manager.con.close()

        sql_no_api = PMCIDManager(storage_manager=SqliteStorageManager(test_sqlite_db), use_api_service=False)
        all_db_keys = sql_no_api.storage_manager.get_all_keys()
        #check that all the normalised ind in the list were correctly inserted in the db
        self.assertTrue(all(sql_no_api.normalise(x,include_prefix=True) in all_db_keys for x in to_insert))
        self.assertTrue(sql_no_api.is_valid(self.valid_pmc_1)) # is stored in support file as valid
        self.assertFalse(sql_no_api.is_valid(self.invalid_pmc_1)) # is stored in support file as invalid
        self.assertTrue(sql_no_api.is_valid(sql_no_api.normalise(self.invalid_pmc_3, include_prefix=True))) # is not stored in support file as invalid, does not exist but has correct syntax
        sql_no_api.storage_manager.delete_storage()

    def test_pmc_sqlite_nofile_noapi(self):
        # Does not use support file
        # Uses SqliteStorageManager storage manager
        # Does not use API (so a syntactically correct id which is not valid is considered to be valid)
        am_nofile_noapi = PMCIDManager(storage_manager=SqliteStorageManager(), use_api_service=False)
        self.assertTrue(am_nofile_noapi.is_valid(self.valid_pmc_1))
        self.assertTrue(am_nofile_noapi.is_valid(self.invalid_pmc_3))
        am_nofile_noapi.storage_manager.delete_storage()
