# Copyright (c) 2013 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

import os, copy, datetime
import cPickle as pickle

from shotgun_api3 import sg_timezone, ShotgunError

_schema_filename = "schema.pickle"
_schema_entity_filename = "schema_entity.pickle"

def generate_schema():
    module_dir = os.path.split(__file__)[0]
    schema_path = os.path.join(module_dir, _schema_filename)
    schema_entity_path = os.path.join(module_dir, _schema_entity_filename)
    
    import tank.constants
    sg = tank.constants.get_sg_connection()
    
    schema = sg.schema_read()
    with open(schema_path, "w") as f:
        pickle.dump(schema, f)
        
    schema_entity = sg.schema_entity_read()
    with open(schema_entity_path, "w") as f:
        pickle.dump(schema_entity, f)
    
    print "Schema generated."

class Shotgun(object):
    def __init__(self, base_url, script_name, api_key, convert_datetimes_to_utc=True, http_proxy=None):
        # set up the schema (must be generated with generate_schema)
        module_dir = os.path.split(__file__)[0]
        schema_path = os.path.join(module_dir, _schema_filename)
        schema_entity_path = os.path.join(module_dir, _schema_entity_filename)
        
        with open(schema_path, "r") as f:
            self._schema = pickle.load(f)
            
        with open(schema_entity_path, "r") as f:
            self._schema_entity = pickle.load(f) 

        # initialize the "database"
        self._db = dict((entity, {}) for entity in self._schema)


    def schema_read(self):
        return self._schema

    def schema_field_create(self, entity_type, data_type, display_name, properties=None):
        raise NotImplementedError
    
    def schema_field_update(self, entity_type, field_name, properties):
        raise NotImplementedError

    def schema_field_delete(self, entity_type, field_name):
        raise NotImplementedError
    
    def schema_entity_read(self):
        return self._schema_entity

    def schema_field_read(self, entity_type, field_name=None):
        if field_name is None:
            return self._schema[entity_type]
        else:
            return dict((k, v) for k, v in self._schema[entity_type].items() if k == field_name)

    def _validate_entity_type(self, entity_type):
        if entity_type not in self._schema:
            raise ShotgunError("%s is not a valid entity" % entity_type)
    
    def _validate_entity_data(self, entity_type, data):
        if "id" in data or "type" in data:
            raise ShotgunError("Can't set id or type on create or update")

        self._validate_entity_fields(entity_type, data.keys())

        for field, item in data.items():
            field_info = self._schema[entity_type][field]

            if field_info["data_type"]["value"] == "multi_entity":
                if not isinstance(item, list):
                    raise ShotgunError("%s.%s is of type multi_entity, but data %s is not a list" % (entity_type, field, item))
                elif item and any(not isinstance(sub_item, dict) for sub_item in item):
                    raise ShotgunError("%s.%s is of type multi_entity, but data %s contains a non-dictionary" % (entity_type, field, item))
                elif item and any("id" not in sub_item or "type" not in sub_item for sub_item in item):
                    raise ShotgunError("%s.%s is of type multi-entity, but an item in data %s does not contain 'type' and 'id'" % (entity_type, field, item))
                elif item and any(sub_item["type"] not in field_info["properties"]["valid_types"]["value"] for sub_item in item):
                    raise ShotgunError("%s.%s is of multi-type entity, but an item in data %s has an invalid type (expected one of %s)" % (entity_type, field, item, field_info["properties"]["valid_types"]["value"]))
                
                
            elif field_info["data_type"]["value"] == "entity":
                if not isinstance(item, dict):
                    raise ShotgunError("%s.%s is of type entity, but data %s is not a dictionary" % (entity_type, field, item))
                elif "id" not in item or "type" not in item:
                    raise ShotgunError("%s.%s is of type entity, but data %s does not contain 'type' and 'id'" % (entity_type, field, item))
                elif item["type"] not in field_info["properties"]["valid_types"]["value"]:
                    raise ShotgunError("%s.%s is of type entity, but data %s has an invalid type (expected one of %s)" % (entity_type, field, item, field_info["properties"]["valid_types"]["value"]))

            else:
                try:
                    sg_type = field_info["data_type"]["value"]
                    python_type = {"number": int,
                                   "float": float,
                                   "checkbox": bool,
                                   "text": basestring,
                                   "date": datetime.date,
                                   "date_time": datetime.datetime,
                                   "url": dict}[sg_type]
                except KeyError:
                    raise ShotgunError("Handling for Shotgun type %s is not implemented" % sg_type) 
                
                if not isinstance(item, python_type):
                    raise ShotgunError("%s.%s is of type %s, but data %s is not of type %s" % (entity_type, field, type(item), sg_type, python_type))

                # TODO: add check for correct timezone

    def _validate_entity_fields(self, entity_type, fields):
        self._validate_entity_type(entity_type)
        if fields is not None:
            valid_fields = set(self._schema[entity_type].keys())
            for field in fields:
                try:
                    field2, entity_type2, field3 = field.split(".", 2)
                    self._validate_entity_fields(entity_type2, [field3])
                except ValueError:
                    if field not in valid_fields and field not in ("type", "id"):
                        raise ShotgunError("%s is not a valid field for entity %s" % (field, entity_type))
            
    def _get_default_value(self, entity_type, field):
        field_info = self._schema[entity_type][field]
        if field_info["data_type"]["value"] == "multi_entity":
            default_value = []
        else:
            default_value = field_info["properties"]["default_value"]["value"]
        return default_value

    def _get_new_row(self, entity_type):
        row = {"type": entity_type, "__retired": False}
        for field in self._schema[entity_type]:
            field_info = self._schema[entity_type][field]
            if field_info["data_type"]["value"] == "multi_entity":
                default_value = []
            else:
                default_value = field_info["properties"]["default_value"]["value"]
            row[field] = default_value
        return row

    def _compare(self, field_type, lval, operator, rval):
        if field_type == "checkbox":
            if operator == "is":
                return lval == rval
            elif operator == "is_not":
                return lval != rval
        elif field_type in ("float", "number", "date", "date_time"):
            if operator == "is":
                return lval == rval
            elif operator == "is_not":
                return lval != rval
            elif operator == "less_than":
                return lval < rval
            elif operator == "greater_than":
                return lval > rval
            elif operator == "between":
                return lval >= rval[0] and lval <= rval[1]
            elif operator == "not_between":
                return lval < rval[0] or lval > rval[1]
            elif operator == "in":
                return lval in rval
        elif field_type == "text":
            if operator == "is":
                return lval == rval
            elif operator == "is_not":
                return lval != rval
            elif operator == "contains":
                return lval in rval
            elif operator == "not_contains":
                return lval not in rval
            elif operator == "starts_with":
                return lval.startswith(rval)
            elif operator == "ends_with":
                return lval.endswith(rval)
        elif field_type == "entity":
            if operator == "is":
                return lval["type"] == rval["type"] and lval["id"] == rval["id"]
            elif operator == "is_not":
                return lval["type"] != rval["type"] or lval["id"] != rval["id"]
            elif operator == "in":
                return all((lval["type"] == sub_rval["type"] and lval["id"] == sub_rval["id"]) for sub_rval in rval)
            elif operator == "type_is":
                return lval["type"] == rval
            elif operator == "type_is_not":
                return lval["type"] != rval
            elif operator == "name_contains":
                return rval in lval["name"]
            elif operator == "name_not_contains":
                return rval not in lval["name"]
            elif operator == "name_starts_with":
                return lval["name"].startswith(rval)
            elif operator == "name_ends_with":
                return lval["name"].endswith(rval)
        elif field_type == "multi_entity":
            if operator == "is":
                return rval["id"] in (sub_lval["id"] for sub_lval in lval)
            elif operator == "is_not":
                return rval["id"] not in (sub_lval["id"] for sub_lval in lval)

        raise ShotgunError("The %s operator is not supported on the %s type" % (operator, field_type))

    def _get_field_from_row(self, entity_type, row, field):
        # split dotted form fields
        try:
            field2, entity_type2, field3 = field.split(".", 2)
            if field2 in row:
                row2 = row[field2]
                if "type" in row2 and "id" in row2:
                    return self._get_field_from_row(entity_type2, self._db[row2["type"]][row2["id"]], field3)
                else:
                    return self._get_field_from_row(entity_type2, row2, field3)
            else:
                return None
        except ValueError:
            if field in row:
                return row[field]
            elif "type" in row and "id" in row:
                return self._db[row["type"]][row["id"]]
            else:
                return None

    def _get_field_type(self, entity_type, field):
        # split dotted form fields
        try:
            field2, entity_type2, field3 = field.split(".", 2)
            return self._get_field_type(entity_type2, field3)
        except ValueError:
            return self._schema[entity_type][field]["data_type"]["value"]

    def _row_matches_filter(self, entity_type, row, filter):
        try:
            field, operator, rval = filter
        except ValueError:
            raise ShotgunError("Filters must be in the form [lval, operator, rval]")
        lval = self._get_field_from_row(entity_type, row, field)
        field_type = self._get_field_type(entity_type, field)
        # if we're operating on an entity, we'll need to grab the name from the lval's row
        if field_type == "entity":
            lval_row = self._db[lval["type"]][lval["id"]]
            if "name" in lval_row:
                lval["name"] = lval_row["name"]
            elif "code" in lval_row:
                lval["name"] = lval_row["code"]
        return self._compare(field_type, lval, operator, rval)

    def _row_matches_filters(self, entity_type, row, filters, filter_operator, retired_only):
        if retired_only and not row["__retired"] or not retired_only and row["__retired"]:
            # ignore retired rows unless the retired_only flag is set
            # ignore live rows if the retired_only flag is set
            return False
        elif filter_operator in ("all", None):
            return all(self._row_matches_filter(entity_type, row, filter) for filter in filters)
        elif filter_operator == "any":
            return any(self._row_matches_filter(entity_type, row, filter) for filter in filters)
        else:
            raise ShotgunError("%s is not a valid filter operator" % filter_operator)

    def find(self, entity_type, filters, fields=None, order=None, filter_operator=None, limit=0, retired_only=False, page=0):
        self._validate_entity_type(entity_type)
        self._validate_entity_fields(entity_type, fields)
        
        results = [row for row in self._db[entity_type].values() if self._row_matches_filters(entity_type, row, filters, filter_operator, retired_only)]
        
        if fields is None:
            fields = set(["type", "id"])
        else:
            fields = set(fields) | set(["type", "id"])
        
        return [dict((field, self._get_field_from_row(entity_type, row, field)) for field in fields) for row in results]
    
    def find_one(self, entity_type, filters, fields=None, order=None, filter_operator=None, retired_only=False):
        results = self.find(entity_type, filters, fields=fields, order=order, filter_operator=filter_operator, retired_only=retired_only)
        return results[0] if results else None
    
    def batch(self, requests):
        results = []
        for request in requests:
            if request["request_type"] == "create":
                results.append(self.create(request["entity_type"], request["data"]))
            elif request["request_type"] == "update":
                # note: Shotgun.update returns a list of a single item
                results.append(self.update(request["entity_type"], request["entity_id"], request["data"])[0])
            elif request["request_type"] == "delete":
                results.append(self.delete(request["entity_type"], request["entity_id"]))
            else:
                raise ShotgunError("Invalid request type %s in request %s" % (request["request_type"], request))
        return results

    def _update_row(self, entity_type, row, data):
        for field in data:
            field_type = self._get_field_type(entity_type, field)
            if field_type == "entity":
                row[field] = {"type": data[field]["type"], "id": data[field]["id"]}
            elif field_type == "multi_entity":
                row[field] = [{"type": item["type"], "id": item["id"]} for item in data[field]]
            else:
                row[field] = data[field]
            
    def create(self, entity_type, data, return_fields=None):
        self._validate_entity_type(entity_type)
        self._validate_entity_data(entity_type, data)
        self._validate_entity_fields(entity_type, return_fields)
        
        try:
            # get next id in this table
            next_id = max(self._db[entity_type]) + 1
        except ValueError:
            next_id = 1

        row = self._get_new_row(entity_type)

        self._update_row(entity_type, row, data)        
        row["id"] = next_id
        
        self._db[entity_type][next_id] = row

        if return_fields is None:
            result = dict((field, self._get_field_from_row(entity_type, row, field)) for field in data)
        else:
            result = dict((field, self._get_field_from_row(entity_type, row, field)) for field in return_fields)

        result["type"] = row["type"]
        result["id"] = row["id"]
        
        return result

    def _validate_entity_exists(self, entity_type, entity_id):
        if entity_id not in self._db[entity_type]:
            raise ShotgunError("No entity of type %s exists with id %s" % (entity_type, entity_id))

    def update(self, entity_type, entity_id, data):
        self._validate_entity_type(entity_type)
        self._validate_entity_data(entity_type, data)
        self._validate_entity_exists(entity_type, entity_id)

        row = self._db[entity_type][entity_id]
        self._update_row(entity_type, row, data)

        return [dict((field, item) for field, item in row.items() if field in data or field in ("type", "id"))]

    def delete(self, entity_type, entity_id):
        self._validate_entity_type(entity_type)
        self._validate_entity_exists(entity_type, entity_id)
        
        row = self._db[entity_type][entity_id]
        if not row["__retired"]:
            row["__retired"] = True
            return True
        else:
            return False
    
    def revive(self, entity_type, entity_id):
        self._validate_entity_type(entity_type)
        self._validate_entity_exists(entity_type, entity_id)
        
        row = self._db[entity_type][entity_id]
        if row["__retired"]:
            row["__retired"] = False
            return True
        else:
            return False
    
    def upload(self, entity_type, entity_id, path, field_name=None, display_name=None, tag_list=None):
        raise NotImplementedError
    
    def upload_thumbnail(self, entity_type, entity_id, path, **kwargs):
        pass