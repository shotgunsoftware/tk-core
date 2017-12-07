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
Handle migration of TankPublishedFile entities to PublishedFile entities
"""

import sys
import os
import shutil
from itertools import chain

from tank_vendor import yaml
from .action_base import Action
from . import update 
from ..errors import TankError
from . import constants
from .. import constants as constants_global
from ..util import shotgun
from ..util import ShotgunPath

class EntityMigrator(object):
    """
    Base class for performing migrations from a source entity type to a 
    destination entity type.
    
    This will attempt to copy entities allowing derived classes to map 
    fields and values where necessary
    
    It will also attempt to migrate any internal or external (from other
    types) entity links.
    """
    
    # common entity fields that shouldn't be touched/written to:
    READ_ONLY_FIELDS = ["id", "updated_by", "updated_at", "open_notes_count", "open_notes"]
    
    # Entity types that should not be modified:
    READ_ONLY_ENTITY_TYPES = ["EventLogEntry"]
    
    SHOTGUN_BATCH_SIZE = 50
    
    def __init__(self, log, sg, src_type, dst_type, sg_project):
        """
        Construction
        """
        self._log = log
        self._sg = sg
        self._src_type = src_type
        self._dst_type = dst_type

        # information determined from the schema:
        self._schema = None
        self._schema_errors_and_warnings = []
        self._tracking_field = None
        self._entity_field_details = {}
        self._dst_field_default_values = {}
        self._linked_entity_field_details = {}

        self._migration_errors = []

        # set up the project filter here:
        self._project_filter = ["project", "is", sg_project] if sg_project else []
        
    def set_schema(self, sg_schema):
        """
        Parse the shotgun schema and look for things to
        migrate, validating as we go...
        """
        # reset cached data:
        self._schema = sg_schema
        self._schema_errors_and_warnings = []
        self._entity_field_details = {}
        self._linked_entity_field_details = {}
        self._tracking_field = None
        
        # first, get the source and destination entity schemas and
        # check they are both valid
        src_schema = sg_schema.get(self._src_type)
        if not src_schema:
            self.__log_schema_error("Entity type '%s' is not a valid Shotgun entity!" % self._src_type)
        dst_schema = sg_schema.get(self._dst_type)
        if not dst_schema:
            self.__log_schema_error("Entity type '%s' is not a valid Shotgun entity!" % self._dst_type)
        if not src_schema or not dst_schema:
            return
        
        # ensure that the source entity contains a field to use when tracking
        # the migration.  This field will link from the old/source entity to
        # the new/destination entity.
        self._tracking_field = self.__find_migration_tracking_field(src_schema)
        if not self._tracking_field in src_schema:
            # re-read the source schema:
            src_schema = self._sg.schema_field_read(self._src_type)
            sg_schema[self._src_type] = src_schema
        
        # look at the source and destination schemas and find fields that
        # need to be copied between them
        for src_field, src_properties in src_schema.iteritems():

            if src_field == self._tracking_field:
                # special field that never gets migrated!
                continue 

            # exclude some base fields that are read-only and can't
            # be migrated
            if src_field in EntityMigrator.READ_ONLY_FIELDS:
                continue
        
            # get the destination field for this source field:
            dst_field = self._get_dst_field(src_field)
            if not dst_field:
                # we should skip this field!
                continue
            
            # check that we have a destination:
            if not dst_field in dst_schema:
                self.__log_schema_warning("Field '%s' on the '%s' entity does not exist on the '%s' entity.  Data for this field will not be migrated!" 
                                          % (src_field, self._src_type, self._dst_type))
                continue

            # get destination properties:
            dst_properties = dst_schema[dst_field]

            # compare details to ensure that the fields 
            # are compatible:
            src_field_data_type = src_properties["data_type"]["value"]
            dst_field_data_type = dst_properties["data_type"]["value"]
            
            if not self._are_fields_compatible(src_field, src_properties, dst_field, dst_properties):
                if src_field_data_type != dst_field_data_type:
                    # fields must be the same type
                    self.__log_schema_warning("Source field '%s.%s' (type: %s) is not compatible with '%s.%s' (type: %s).  Data for this field will not be migrated!" 
                                              % (self._src_type, src_field, src_field_data_type, self._dst_type, dst_field, dst_field_data_type))
                    continue
                
                if src_field_data_type in ["entity", "multi_entity"]:
                    # valid types for entity fields must be the same:
                    src_valid_types = src_properties["properties"]["valid_types"]["value"]
                    dst_valid_types = dst_properties["properties"]["valid_types"]["value"]
                    valid_types_match = (len(src_valid_types) == len(dst_valid_types))
                    if valid_types_match:
                        for st in src_valid_types:
                            # special case as we know that we are going to migrate entities
                            # of src_type to dst_type!
                            dt = self._dst_type if st == self._src_type else st
                            if not dt in dst_valid_types:
                                valid_types_match = False
                                break
                    if not valid_types_match:
                        self.__log_schema_warning("Source %s field '%s.%s' is not compatible with '%s.%s' as it accepts different valid entity types.  Data for this field will not be migrated!" 
                                              % (src_field_data_type, self._src_type, src_field, self._dst_type, dst_field))
                        continue
                    
                # if specific values are set then check they are consistent:
                src_valid_values = src_properties["properties"].get("valid_values", {}).get("value")
                dst_valid_values = dst_properties["properties"].get("valid_values", {}).get("value")
                if src_valid_values == None and dst_valid_values != None:
                    self.__log_schema_warning("Destination field '%s.%s' is restricted to specific values but the source field '%s.%s' is not.  Data for this field will not be migrated!" 
                                              % (self._dst_type, dst_field, self._src_type, src_field))
                    continue
                elif src_valid_values != None and dst_valid_values == None:
                    # this is probably ok as the destination is less restrictive than the source
                    pass
                elif src_valid_values != None and dst_valid_values != None:
                    # make sure the values are the same:
                    values_match = True
                    for sv in src_valid_values:
                        if not sv in dst_valid_values:
                            values_match = False
                            break
                    if not values_match:
                        self.__log_schema_warning("Destination field '%s.%s' is restricted to different specific values than the source field '%s.%s'.  Data for this field will not be migrated!" 
                                              % (self._dst_type, dst_field, self._src_type, src_field))
                        continue
                
            dst_default_value = dst_properties["properties"].get("default_value", {}).get("value")
                
            # add field to list of fields to migrate:
            #self._entity_field_details[src_field] = dst_field
            self._entity_field_details[src_field] = {"src_data_type":src_field_data_type,
                                                    "dst_field":dst_field,
                                                    "dst_data_type":dst_field_data_type}
            self._dst_field_default_values[dst_field] = dst_default_value
            
        # next, look for all fields on all entities that accept
        # entities of type 'src_type' and have a valid field to migrate
        # entities of type 'dst_type' to:
        for entity_type, entity_schema in sg_schema.iteritems():
            
            # skip fields on the source or destination types as these will be handled
            # in the entity migration
            if entity_type == self._src_type or entity_type == self._dst_type:
                continue

            # don't touch certain entity types!
            if entity_type in EntityMigrator.READ_ONLY_ENTITY_TYPES:
                continue
            
            # skip non-project entities - do we need to handle these?
            if not "project" in entity_schema:
                continue
            
            dst_field_map = {}
            for src_field, src_field_schema in entity_schema.iteritems():
                # only care if the data type is entity or multi_entity
                src_field_data_type = src_field_schema["data_type"]["value"]
                if src_field_data_type not in ("entity", "multi_entity"):
                    continue
                
                # only care if the source entity type is a valid type 
                # for this field    
                valid_types = src_field_schema["properties"]["valid_types"]["value"]
                if self._src_type not in valid_types:
                    continue
                
                # get the destination field:
                dst_field = self._get_external_entity_dst_field(entity_type, src_field)
                if not dst_field:
                    # if no destination field is provided then just skip it!
                    continue
                
                # ensure that the destination field isn't being used multiple times!
                if dst_field in dst_field_map:
                    self.__log_schema_error("Destination field %s.%s is already being used to migrate from source field '%s' and cannot be used again for source field '%s'"
                                    % (entity_type, dst_field, dst_field_map[dst_field], src_field))
                    continue
                
                # check this field is valid and get the schema:
                dst_field_schema = entity_schema.get(dst_field)
                if not dst_field_schema:
                    self.__log_schema_error("Destination field '%s' for migration of linked entities from '%s.%s' does not exist!" 
                                    % (dst_field, entity_type, src_field))
                    continue
                        
                # check the type for the destination field:
                dst_field_data_type = dst_field_schema["data_type"]["value"]
                if dst_field_data_type not in ("entity", "multi_entity"):
                    self.__log_schema_error("%s field '%s' on entity type '%s' is not a valid type - expected entity or multi-entity!" 
                                    % (dst_field_data_type, dst_field, entity_type))
                    continue
                
                # and ensure that it accepts the destination entity type:
                valid_types = dst_field_schema["properties"]["valid_types"]["value"]
                if self._dst_type not in valid_types:
                    self.__log_schema_warning("%s field '%s' on entity type '%s' does not accept entities of type '%s'" 
                                    % (dst_field_data_type, dst_field, entity_type, self._dst_type))
                    continue
                
                # store all this info in the fields dict:
                self._linked_entity_field_details.setdefault(entity_type, dict())[src_field] = {"src_data_type":src_field_data_type,
                                                                            "dst_field":dst_field,
                                                                            "dst_data_type":dst_field_data_type}
                dst_field_map[dst_field] = src_field
     
    def get_schema_errors(self):
        """
        """
        return [entry["msg"] for entry in self._schema_errors_and_warnings if entry["level"] == "error"]
    
    def get_migration_errors(self):
        """
        """
        return self._migration_errors
    
    def get_schema_warnings(self):
        """
        """
        return [entry["msg"] for entry in self._schema_errors_and_warnings if entry["level"] == "warning"]
     
    def calc_num_project_entities_to_migrate(self):
        """
        Find the number of entities for this project
        that have not been migrated yet
        """
        return self.__calc_num_entities_to_migrate(project_only=True)
    
    def calc_num_site_entities_to_migrate(self):
        """
        Find the number of entities for the whole site
        that have not been migrated yet
        """
        return self.__calc_num_entities_to_migrate(project_only=False)
    
    def migrate_entities(self, update_existing_entities=False):   
        """
        Do entity migration
        """
        
        if not self._schema or self.get_schema_errors():
            raise TankError("Unable to migrate entities without a valid schema!")
        
        # stop immediately if there is nothing to do!
        if not self._entity_field_details and not self._linked_entity_field_details:
            self._log.info("Nothing found to migrate!")
            return
        
        # migrate entities:
        self.__migrate(update_existing_entities)

    """
    ====================
    Protected Methods
    ====================
    """        
    def _get_dst_field(self, src_field):
        """
        Get the destination field to use for the specified source 
        field
        
        Return None to cause this field to be skipped

        The default implementation assumes destination field has 
        the same name as the source field
        """
        return src_field
    
    def _are_fields_compatible(self, src_field, src_properties, dst_field, dst_properties):
        """
        Check to see if the destination field is migratable from the
        source field
        
        Return False if not known!
        """
        return False
    
    def _migrate_field_value(self, src_field, src_value, src_data_type, dst_data_type):
        """
        Migrate the value for the source field if needed.  The
        default implementation just returns the source value
        
        The default implementation just returns the value unchanged 
        """
        return src_value
    
    def _find_migrated_entity_id(self, src_entity):
        """
        Find the entity id for the migrated version of the
        source entity.
        
        This allows derived classes to do a secondary lookup
        if needed rather than rely on the tracking field.
        """
        return None

    def _get_external_entity_dst_field(self, entity_type, src_field):
        """
        For the given entity type and source field, return a destination
        field that any links should be migrated to!
        
        Return None to cause this field to be skipped

        The default implementation assumes destination field has 
        the same name as the source field
        """
        return src_field

    def _pre_entity_migration(self):
        """
        Opportunity for derived classes to do any work 
        before entities are migrated
        
        Default implementation does nothing
        """
        pass

    def _post_entity_migration(self):
        """
        Opportunity for derived classes to do any work 
        immediately after entities are migrated
        
        Default implementation does nothing
        """
        pass
    
    """
    ====================
    Private Methods
    ====================
    """    
    def __log_schema_error(self, msg):
        """
        Log a schema error
        """
        self._schema_errors_and_warnings.append({"level":"error", "msg":msg})
        
    def __log_schema_warning(self, msg):
        """
        Log a schema warning
        """
        self._schema_errors_and_warnings.append({"level":"warning", "msg":msg})
    
    def __find_migration_tracking_field(self, src_schema=None, create_if_missing=True):
        """
        Find the field on the source type that is used to 
        track the migrated destination entity        
        """
        if not src_schema:
            try:
                src_schema = self._sg.schema_field_read(self._src_type)
            except:
                return None
        
        # construct field name:
        name = "Tank Migrated Entity %s" % self._dst_type
        
        self._log.debug("Looking up migration tracking field '%s' on source entity '%s'" % (name, self._src_type))
        
        # look through schema for a matching field:
        for field_name, properties in src_schema.iteritems():
            if (properties.get("name", {}).get("value") != name
                or properties.get("data_type", {}).get("value") != "entity" 
                or self._dst_type not in 
                    properties.get("properties", {}).get("valid_types", {}).get("value", [])):
                continue
            
            # found a matching field - lets use this!
            self._log.debug("Found migration tracking field '%s'/'%s'" % (name, field_name))
            return field_name
        
        if create_if_missing:
            # didn't find field so need to create it:
            self._log.debug("Adding migration tracking field '%s' on source entity '%s'" % (name, self._src_type))
            try:
                res = self._sg.schema_field_create(self._src_type, "entity", name, 
                                             properties={"valid_types":[self._dst_type]})
            except Exception as e:
                raise TankError("Failed to create migration tracking field: %s" % e)
            self._log.debug("Successfully created migration tracking field '%s'/'%s'" % (name, res))
            return res
        
        return None
        
    def __calc_num_entities_to_migrate(self, project_only=True):
        """
        Find the number of entities
        that have not been migrated yet
        """
        filters = []
        if project_only:
            if not self._project_filter:
                raise TankError("Missing project filter")
            filters.extend([self._project_filter])
        
        # see if entity schema has tracking field:
        if not self._tracking_field:
            self._tracking_field = self.__find_migration_tracking_field(None, False)
        if self._tracking_field:
            filters.extend([[self._tracking_field, "is", None]])
            
        entity_count = 0
        try:
            sg_summaries = self._sg.summarize(self._src_type, filters=filters, summary_fields=[{'field':'id', 'type':'count'}])
            entity_count = sg_summaries["summaries"]["id"]
        except:
            pass
        
        return entity_count
        
    def __migrate(self, update_existing_entities):
        """
        Migrate the entities for source type to destination
        type
        """

        # 1. Migrate entities:
        self._log.info("  Migrating entities...")
        cb = lambda entities, uee=update_existing_entities: self.__migrate_entities_block(entities, uee)
        migration_results = self.__process_entities(self._src_type, EntityMigrator.SHOTGUN_BATCH_SIZE, self._entity_field_details.keys() + [self._tracking_field], cb)
        
        # 2. build single src map from the results:
        src_map = {}
        for res in migration_results:
            src_map = dict(chain(src_map.iteritems(), res.iteritems()))
        
        # 3. Once all entities have been migrated, we can fix up links 
        # between entities of the same type:
        self._log.info("  Updating internal entity links...")
        self.__migrate_internal_links(src_map)
        
        # 4. Update all external links from other entity types:
        self._log.info("  Updating external links from other entity types...")
        self.__migrate_external_links(src_map)
            
    def __report_progress(self, percent, msg=None):
        """
        Simple stdout progress reporter
        """
        progress_len = 20
        percent_per_unit = 100/progress_len
        
        num_hashes = min(max(0, int(percent/percent_per_unit)), progress_len)
        num_spaces = progress_len-num_hashes
        
        to_write = "\r  [%s%s] %3d%%" % ("#"*num_hashes, " "*num_spaces, percent)
        if msg:
            to_write = "%s - %s" % (to_write, msg)
        if percent == 100:
            to_write += "\n"
        
        sys.stdout.write(to_write)
        sys.stdout.flush()

    def __process_entities(self, entity_type, block_size, fields, callback):
        """
        Process all entities of a specific type in blocks of the specified
        size.
        """
        
        # get the number of entities:
        filters = []
        if self._project_filter:
            filters.extend([self._project_filter])
        summaries = self._sg.summarize(entity_type=entity_type, filters = filters, summary_fields=[{'field':'id', 'type':'count'}])
        entity_count = summaries["summaries"]["id"]
        
        block_count = 0
        order = [{"field_name":"id", "direction":"asc"}]
        start_id = -1
        progress = 0.0
        
        results = []
        while True:
            # report some progress info:
            block_start = (block_count * block_size) + 1
            block_end = min((block_count+1) * block_size, entity_count)
            if block_end < block_start:
                break
            msg = "%d-%d of %d '%s' entities" % (block_start, block_end, entity_count, entity_type)
            progress = (float(block_count*block_size)/entity_count) * 100
            self.__report_progress(progress, msg)
            block_count += 1
            
            # filter to start at next block:
            filters = [["id", "greater_than", start_id]]
            if self._project_filter:
                filters.extend([self._project_filter])
                
            # find entities
            try:
                sg_entities = self._sg.find(entity_type, 
                                                 filters=filters, 
                                                 order=order, 
                                                 limit=block_size, 
                                                 fields=fields)
            except Exception as e:
                self._migration_errors.append("Failed to retrieve details for %d %s entities from Shotgun! - %s"
                                              % (block_size, entity_type, e))
                continue
                
            if not sg_entities:
                break

            # update start_id to max entity id:
            start_id = max([entity["id"] for entity in sg_entities])

            # process:
            res = callback(sg_entities)
            results.append(res)
            
        if progress != 100:
            self.__report_progress(100)
            
        return results    
        
    def __migrate_entities_block(self, src_entities, update_existing_entities):
        """
        Migrate the specified source entities to their destination type.
        """
        entities_to_create = []
        entities_to_update = []
        entities_to_link = []

        # sg.find("PublishedFile", filters=[["id", "between", 220, 250]], fields=[])
        
        entities_with_thumbnails = []
        src_map = {}
        
        # iterate through entities looking for ones that need creating
        for src_entity in src_entities:
            
            src_entity_id = src_entity["id"]
            src_map[src_entity_id] = {"entity_fields":{}, "multi_entity_fields":{}}
            
            # see if this entity has previously been migrated:
            dst_entity_id = None
            dst_entity = src_entity.get(self._tracking_field) or {}
            if dst_entity:
                # entity has already been migrated so keep track
                # of mapping between source and destination:
                dst_entity_id = dst_entity["id"]
                src_map[src_entity_id]["id"] = dst_entity_id
            else:
                # see if there is a matching destination entity that
                # isn't linked for some reason:
                dst_entity_id = self._find_migrated_entity_id(src_entity)
                if dst_entity_id is not None:
                    # found a match so keep track of mapping:
                    src_map[src_entity_id]["id"] = dst_entity_id

                    # and also add to entities to be linked so that
                    # the actual link is created for next time
                    entities_to_link.append((src_entity_id, dst_entity_id))

            if dst_entity_id is not None and not update_existing_entities:
                # don't worry about updating entities that have already been migrated!
                continue
            
            dst_entity = {}       
                           
            try:
                                
                # iterate through fields translating values where needed:
                image_field = None
                for src_field, value in src_entity.iteritems():
                    
                    if not value:
                        # don't bother migrating empty values!
                        continue
                    
                    if src_field == self._tracking_field:
                        # skip the tracking field
                        continue
                    
                    field_details = self._entity_field_details.get(src_field)
                    if not field_details: 
                        # skip this field as we don't have any info about it!
                        continue
                    
                    dst_field = field_details["dst_field"]
                    src_data_type = field_details["src_data_type"]
                    dst_data_type = field_details["dst_data_type"]
                    
                    # allow derived classes to modify value if they need to:
                    value = self._migrate_field_value(src_field, value, src_data_type, dst_data_type)
                    
                    # use the schema to determine how the value should be migrated:
                    if src_data_type == "image":
                        # thumbnails will be migrated afterwards using the share_thumbnail api
                        image_field = dst_field
                        continue
                    elif src_data_type == "entity":
                        # don't migrate links to entities of src type - this will be done later
                        if value["type"] == self._src_type:
                            src_map[src_entity_id]["entity_fields"][dst_field] = value
                            continue
                    elif src_data_type == "multi_entity":
                        migrate_field = True
                        for entity in value:
                            if entity["type"] == self._src_type:
                                # don't migrate links to entities of src type - this will be done later
                                migrate_field = False
                                break
                        if not migrate_field:
                            src_map[src_entity_id]["multi_entity_fields"][dst_field] = value
                            continue
                    elif src_data_type == "url":
                        # paths can be different types and need to be migrated
                        # accordingly:
                        link_type = value.get("link_type")
                        value_key = {"local":"local_path", "web":"url"}.get(link_type)
                        if not value_key:
                            raise TankError("Failed to find value for url field %s on entity %s" % (src_field, src_entity_id))
                        value = {value_key:value.get(value_key)}
                    
                    # add value to be migrated:
                    dst_entity[dst_field] = value
            
            except TankError as e:
                msg = ""
                if dst_entity_id is not None:
                    msg = ("Unable to update migrated %s entity %d (%s:%d) - %s" 
                            % (self._src_type, src_entity_id, self._dst_type, dst_entity_id, e))
                else:
                    msg = "Unable to migrate %s entity %d - %s" % (self._src_type, src_entity_id, e)
                self._migration_errors.append(msg)
                continue
            
            #self._migration_errors.append("A dummy error")
            #continue
            
            if dst_entity:
                if dst_entity_id is not None:
                    # add to entities to be updated:
                    entities_to_update.append((src_entity, dst_entity, dst_entity_id, image_field))
                else:
                    # add to entities to be created:
                    entities_to_create.append((src_entity, dst_entity))
                    if image_field:
                        entities_with_thumbnails.append(src_entity_id)
            else:
                self._migration_errors.append("Unable to migrate %s entity %d - none of the fields are migratable" % (self._src_type, src_entity_id))
                
            
        # build list of requests to create/update entities as required:    
        requests = []
        
        # add requests to create new entities:
        if entities_to_create:
            self._log.debug("Creating %d new entities" % len(entities_to_create))
            for _, dst_entity in entities_to_create:
                requests.append({"request_type":"create", "entity_type":self._dst_type, "data":dst_entity})
        
        # append requests to update existing entities:
        if entities_to_update:
            self._log.debug("Updating %d existing entities" % len(entities_to_update))
            
            # We need to get the existing data as we only 
            # want to update fields that are empty/non-default:
            dst_fields = set()
            dst_entity_ids = []
            for _, dst_entity, dst_entity_id, image_field in entities_to_update:
                for field in dst_entity.keys():
                    dst_fields.add(field)
                if image_field:
                    dst_fields.add(image_field)
                dst_entity_ids.append(dst_entity_id)
                
            range_start = min(dst_entity_ids)-1
            range_end = max(dst_entity_ids)

            # get data for existing entities:
            try:
                existing_entities = self._sg.find(self._dst_type, 
                                          filters = [["id", "between", range_start, range_end]], 
                                          fields=list(dst_fields))
            except Exception as e:
                self._migration_errors.append("Failed to query existing data for %d %s entities from Shotgun. These entities will no be updated! - %s"
                                              % (len(entities_to_update, self._dst_type, e)))
            else:
                existing_entities_by_id = dict((entity["id"], entity) for entity in existing_entities)

                # now, we only want to update empty fields for existing entities:
                for src_entity, dst_entity, dst_entity_id, image_field in entities_to_update:
                    existing_entity = existing_entities_by_id[dst_entity_id]
                    if not existing_entity:
                        self._migration_errors.append("Failed to retrieve existing data for %s entity %d from Shotgun.  It will not be updated - %s"
                                              % (self._dst_type, dst_entity_id, e))
                        continue
                    
                    update_data = {}
                    for field, value in dst_entity.iteritems():
                        
                        dst_default_value = self._dst_field_default_values[field]
                        if existing_entity.get(field) != dst_default_value:
                            # don't update fields that already have non-default data
                            continue

                        if field == image_field:
                            # images are updated later using the share_thumbnail api:
                            entities_with_thumbnails.append(src_entity["id"])
                            continue
    
                        # field needs updating:
                        update_data[field] = value
    
                    if update_data:
                        # we have something to update so add a request for it:
                        requests.append({"request_type":"update", "entity_type":self._dst_type, "entity_id":dst_entity_id, "data":update_data})
        
        # ok, so if we have any requests then lets execute them:
        if requests:
            
            # allow derived objects to do any preparation before migration:
            self._pre_entity_migration()
            try:
                created_entities = self._sg.batch(requests=requests)
            except Exception as e:
                self._migration_errors.append("Failed to create/update %d %s entities in Shotgun - %s"
                                              % (len(requests), self._dst_type, e))
            else:
                # result is garunteed to be returned in the same order the requests submitted
                # so we can easily match the new entities up to their original source entities
                for entity_idx, (src_entity, _) in enumerate(entities_to_create):
                    new_entity = created_entities[entity_idx]
                    src_entity_id = src_entity["id"]
                    new_entity_id = new_entity["id"]
                    
                    # update mapping info:
                    src_map[src_entity_id]["id"] = new_entity_id
                    
                    # and add entity to be linked:
                    entities_to_link.append((src_entity_id, new_entity_id))                
            finally:
                # allow derived objects to do any cleanup:
                self._post_entity_migration()
            
        # link source entities to destination entities
        # so that the migration can be tracked   
        if entities_to_link:
            self._log.debug("Linking source and destination entities together")
            
            requests = []
            for src_entity_id, dst_entity_id in entities_to_link:
                data = {self._tracking_field : {"id":dst_entity_id, "type":self._dst_type}}
                requests.append({"request_type":"update", "entity_type":self._src_type, "entity_id":src_entity_id, "data":data})

            try:
                self._sg.batch(requests=requests)
            except Exception as e:
                self._migration_errors.append("Failed to update migration tracking field for %d %s entities in Shotgun - %s"
                                              % (len(requests), self._src_type, e))
        
        # finally, migrate any thumbnails using the share_thumbnail api:
        if entities_with_thumbnails:
            self._log.debug("Updating %d thumbnails!" % len(entities_with_thumbnails))
            
            # Unfortunately we can't batch this and it can be really slow!
            for src_id in entities_with_thumbnails:
                dst_id = src_map[src_id].get("id")
                if dst_id == None:
                    continue
                
                src_entity = {"id":src_id, "type":self._src_type}
                dst_entity = {"id":dst_id, "type":self._dst_type}
                try:
                    self._sg.share_thumbnail(entities=[dst_entity], source_entity=src_entity)
                except Exception as e:
                    self._migration_errors.append("Failed to share thumbnail with %s entity %d in Shotgun - %s"
                                                  % (self._dst_type, dst_id, e))
                
        return src_map

    def __migrate_internal_links(self, src_map):
        """
        Migrate any linked entities within the source entity type to
        the equivelant field in the destination entity type
        """
        requests = []
        
        # iterate over every entity in the src map:
        for _, details in src_map.iteritems():
            
            entity_fields = details.get("entity_fields", {})
            multi_entity_fields = details.get("multi_entity_fields", {})
            if not entity_fields and not multi_entity_fields:
                continue
            
            dst_entity_id = details.get("id")
            if dst_entity_id == None:
                # this is probably as a result of an 
                # earlier problem so just skip it
                continue
            
            data = {}
            # process 'entity' fields for this entity:
            for field, entity in entity_fields.iteritems():
                
                # look for the migrated entity id in the source map:
                dst_entity_id = src_map[entity["id"]]["id"]
                
                # add migrated entity to data to be updated:
                data[field] = {"id":dst_entity_id, "type":self._dst_type}

            # process 'multi-entity' fields:
            for field, entities in multi_entity_fields.iteritems():
                new_entities = []
                for entity in entities:
                    # for entities that aren't source type, just copy them:
                    if entity["type"] != self._src_type:
                        new_entities.append(entity.copy())
                    
                    # look for the migrated entity id in the source map:
                    dst_entity_id = src_map[entity["id"]]["id"]
                
                    # add migrated entity to list of entities for this field:        
                    new_entities.append({"id":dst_entity_id, "type":self._dst_type})
                
                # if we have any entities to migrate then add to data to be updated:
                if new_entities:
                    data[field] = new_entities
                    
            # if we have any data to update for this entity then add to list of requests:
            if data:
                requests.append({"request_type":"update", "entity_type":self._dst_type, "entity_id":dst_entity_id, "data":data})
                
        # if we have any requests then process them:
        if requests:
            try:
                self._sg.batch(requests=requests)
            except Exception as e:
                self._migration_errors.append("Failed to update inter-entity links for %d %s entities in Shotgun - %s"
                                              % (len(requests), self._dst_type, e))
                

             
    def __migrate_external_links(self, entity_map):
        """
        Migrate entity or multi-entity fields on other entities
        that link to src_type entities:
        """
        # now find entities to migrate:
        for entity_type, fields_dict in self._linked_entity_field_details.iteritems():
            
            # will want to get all data for all fields - both source and destination:
            all_fields = list(set(sum([(src_field, details["dst_field"]) for src_field, details in fields_dict.iteritems()], ())))
            #filters = []
            
            cb = lambda entities, fd=fields_dict, em=entity_map: self.__migrate_external_links_block(entities, fd, em)
            self.__process_entities(entity_type, EntityMigrator.SHOTGUN_BATCH_SIZE, all_fields, cb)

             
    def __migrate_external_links_block(self, entities, field_details, entity_map):
        """
        Migrate any incoming links from a block of entities
        
        """
        requests = []
        for entity in entities:
            new_data = {}
            for src_field, details in field_details.iteritems():
                
                src_field_type = details["src_data_type"]
                dst_field = details["dst_field"]
                dst_field_type = details["dst_data_type"]
                
                dst_entities = []
                if src_field_type == "entity":
                    linked_entity = entity[src_field]
                    if not linked_entity or linked_entity["type"] != self._src_type:
                        # nothing to migrate so continue
                        continue
                        
                    dst_linked_entity_id = entity_map.get(linked_entity["id"], {}).get("id")
                    
                    if dst_linked_entity_id == None:
                        self._migration_errors.append("Couldn't find migrated entity for %s entity %d when migrating links for %s.%s (id: %d)"
                                                      % (self._src_type, linked_entity["id"], entity["type"], src_field, entity["id"]))
                        continue
                    
                    dst_entities.append({"type":self._dst_type, "id":dst_linked_entity_id})
                            
                elif src_field_type == "multi_entity":
                    linked_entities = entity[src_field]
                    linked_entity_lookup = [(e["type"], e["id"]) for e in linked_entities]
                    for linked_entity in linked_entities:
                        if linked_entity["type"] != self._src_type:
                            continue
                        
                        dst_linked_entity_id = entity_map.get(linked_entity["id"], {}).get("id") 
                        if dst_linked_entity_id == None:
                            self._migration_errors.append("Couldn't find migrated entity for %s entity %d when migrating links for %s.%s (id: %d)"
                                                          % (self._src_type, linked_entity["id"], entity["type"], src_field, entity["id"]))
                            continue
                            
                        if (self._dst_type, dst_linked_entity_id) in linked_entity_lookup:
                            # destination is already linked.
                            continue
                        
                        # add new entity to be linked:
                        dst_entities.append({"type":self._dst_type, "id":dst_linked_entity_id})

                if not dst_entities:
                    # nothing to migrate so skip
                    continue
                
                # handle special case where source and destination 
                # fields are the same:
                if src_field == dst_field:
                    if src_field_type == "multi_entity":
                        # include all original entities in the new value:
                        linked_entities = entity[src_field]
                        dst_entities.extend(linked_entities)
                        
                # now check that the destination field can accept the entities:
                if dst_field_type == "entity" and len(dst_entities) != 1:
                    # log an error!
                    continue
                
                new_data[dst_field] = dst_entities
                
            if not new_data:
                continue
                
            # Finally, have something we can migrate so add it to the requests:
            entity_id = entity["id"]
            entity_type = entity["type"]                
            requests.append({"request_type":"update", "entity_type":entity_type, "entity_id":entity_id, "data":new_data})
                        
        # now if we have any requests then process them:
        if requests:
            try:
                self._sg.batch(requests=requests)
            except Exception as e:
                self._migration_errors.append("Failed to update external entity links for %d %s entities in Shotgun - %s"
                                              % (len(requests), self._dst_type, e))            
                

class PublishedFileTypeEntityMigrator(EntityMigrator):
    """
    Handle entity migration for TankType->PublishedFileType
    """
    
    def __init__(self, log, sg, sg_project):
        """
        Construction
        """
        EntityMigrator.__init__(self, log, sg, "TankType", "PublishedFileType", sg_project)
        
        self._pft_name_to_id_map = None

    def _get_dst_field(self, src_field):
        """
        """
        # going from project-specific to non-project-specific so
        # no destination field for 'project' source field!
        if src_field == "project":
            return None
        
        return src_field
        
    def _find_migrated_entity_id(self, src_entity):
        """
        """
        # look for an existing entity with the same name
        # in case it was added for another project:
        src_code = src_entity.get("code")
        if src_code:
            # return the id of the PublishedFileType entity if
            # one already exists for this entity:
            return self.__get_name_to_id_map().get(src_code)

    def _get_external_entity_dst_field(self, entity_type, src_field):
        """
        """
        # ignore all fields on any of the published file entity types
        if entity_type in [ "TankPublishedFile", "TankType", "TankDependency",
                            "PublishedFile", "PublishedFileType", "PublishedFileDependency"]:
            return None
        
        # just return the source field:
        return src_field

    def __get_name_to_id_map(self):
        """
        Get current mapping from PublishedFileType name to id.
        """
        if self._pft_name_to_id_map == None:
            self._pft_name_to_id_map = {}
            
            # get all PublishedFileType entities:
            self._log.debug("Retrieving existing TankTypes from Shotgun")
            sg_entities = self._sg.find(self._dst_type, filters = [], fields=["id", "code"])
            
            # build a mapping from the name (code) to the entity id:
            for entity in sg_entities:
                self._pft_name_to_id_map[entity["code"]] = entity["id"]
            
        return self._pft_name_to_id_map



class PublishedFileEntityMigrator(EntityMigrator):
    """
    Handle entity migration for TankPublishedFile->PublishedFile
    """
    FIELD_MAPPINGS = {"downstream_tank_published_files":"downstream_published_files",
                      "upstream_tank_published_files":"upstream_published_files",
                      "tank_type": "published_file_type"}
    
    def __init__(self, log, sg, sg_project, migrate_tank_primary_storage=True):
        """
        Construction
        """
        EntityMigrator.__init__(self, log, sg, "TankPublishedFile", "PublishedFile", sg_project)
        self._publish_type_map = None
        
        self._migrate_tank_ps = migrate_tank_primary_storage
        self._entity_uses_tank_ls = False
        self._tls = None
        
        
    def _get_dst_field(self, src_field):
        """
        """
        # path_cache_storage field can't be migrated:
        if src_field == "path_cache_storage":
            return None
        
        # some fields have specific mappings:
        if src_field in PublishedFileEntityMigrator.FIELD_MAPPINGS:
            return PublishedFileEntityMigrator.FIELD_MAPPINGS[src_field] 
        
        return src_field
    
    def _get_external_entity_dst_field(self, entity_type, src_field):
        """
        """
        # ignore all fields on any of the published file entity types
        if entity_type in [ "TankPublishedFile", "TankType", "TankDependency",
                            "PublishedFile", "PublishedFileType", "PublishedFileDependency"]:
            return None
        
        if entity_type == "Version":
            if src_field == "tank_published_file":
                return "published_files"
            
        # just return the source field:
        return src_field

    def _are_fields_compatible(self, src_field, src_properties, dst_field, dst_properties):
        """
        """
        if src_field == "tank_type":
            # we know how to handle this field even though it
            # isn't the same type!
            return True
        return False
        
    def _migrate_field_value(self, src_field, src_value, src_data_type, dst_data_type):
        """
        """
        if src_field == "tank_type":
            # need to replace tank published file type with
            # published_file_type equivelant:
            tt_id = src_value["id"]
            
            # find the id of the PublishedFileType entity that the 
            # TankType entity is linked to
            pft_id = self.__get_publish_type_map().get(tt_id)
            if pft_id is None:
                raise TankError("Failed to find corresponding 'PublishedFileType' entity for 'TankType' entity (id: %d) - please ensure that one exists!" % (tt_id))
            return {"id":pft_id, "type":"PublishedFileType"}
        elif src_data_type == "url" and src_value.get("link_type") == "local":
            # need to handle local storages to attempt to replace 'Tank' with 'primary':
            ls_name = src_value.get("local_storage", {}).get("name")
            if ls_name == "Tank":
                # track that something uses 'Tank' local storage
                self._entity_uses_tank_ls = True
        
        # just return the value
        return src_value
    
    def _pre_entity_migration(self):
        """
        """
        if not self._migrate_tank_ps or not self._entity_uses_tank_ls:
            return
        
        # Ok, so some entities are using the 'Tank' local storage
        # and we want to migrate them over to use 'primary'
        # Because we can't specify this explicitly through the API
        # we need to trick Shotgun into using 'primary' by 
        # temporarily breaking the path for the 'Tank' storage so
        # that it no longer matches any paths we upload..
        tls = self.__get_tank_local_storage()
        if tls:
            # need to edit the storage so that entities don't match against it..
            tmp_path = "[___TANK_TO_PRIMARY_STORAGE_MIGRATION_TMP___]" + tls["path"]
            self._log.debug("Temporarily modifying the Tank LocalStorage %s field to '%s'" % (tls["path_field"], tmp_path))
            self._sg.update(entity_type = "LocalStorage", entity_id = tls["id"], data = {tls["path_field"]:tmp_path})

    def _post_entity_migration(self):
        """
        """
        # if we need to, restore the Tank local storage back to it's
        # previous 'valid' state:
        if not self._migrate_tank_ps or not self._entity_uses_tank_ls:
            return
        
        tls = self.__get_tank_local_storage()
        if tls:
            self._log.debug("Restoring the Tank LocalStorage %s field to '%s'" % (tls["path_field"], tls["path"]))
            # need to edit the storage so that entities don't match against it..
            self._sg.update(entity_type = "LocalStorage", entity_id = tls["id"], data = {tls["path_field"]:tls["path"]})
        
        # reset flag so we only do this next time it's needed:
        self._entity_uses_tank_ls = False
        
    def __get_tank_local_storage(self):
        """
        Get the tank local storage entity
        """
        if self._tls == None:
            # query shotgun for the 'Tank' LocalStorage entity
            self._tls = {}

            path_field = ShotgunPath.get_shotgun_storage_key()
            
            sg_entity = self._sg.find_one("LocalStorage", filters=[["code", "is", "Tank"]], fields=[path_field])
            if sg_entity:
                self._tls = {"id":sg_entity["id"], "path_field":path_field, "path":sg_entity[path_field]}
            
        return self._tls        
    
    
    def __get_publish_type_map(self):
        """
        Get the mapping between TankType and PublishedFileType entities.
        """
        if self._publish_type_map == None:
            self._publish_type_map = {}
            
            # query the types from shotgun:
            # (sg_tank_migrated_entity_publishedfiletype is currently hard coded!)
            self._log.debug("Retrieving TankType->PublishedFileType mapping from Shotgun")
            sg_entities = self._sg.find("TankType", 
                                  filters = [self._project_filter] if self._project_filter else [], 
                                  fields = ["sg_tank_migrated_entity_publishedfiletype"])
            for entity in sg_entities:
                mapped_entity = entity["sg_tank_migrated_entity_publishedfiletype"]
                self._publish_type_map[entity["id"]] = mapped_entity.get("id") if mapped_entity else None

        return self._publish_type_map
    

class MigratePublishedFileEntitiesAction(Action):
    """
    Command to migrate TankPublishedFile entities to PublishedFile 
    entities
    """
    
    def __init__(self):
        """
        Construction
        """
        Action.__init__(self, 
                        "migrate_published_file_entities", 
                        Action.GLOBAL, 
                        ("Migrates your publishes from TankPublishedFile to PublishedFile and "
                         "sets this configuration to use PublishedFile whenever publishing."), 
                        "Admin")
        
    def run_interactive(self, log, args):
        """
        Run this action with the given args
        """

        MIGRATE, BACKOUT = range(2)
        operation = None
        if len(args) == 0:
            # no arguments mean we're doing a migration
            operation = MIGRATE
        elif len(args) == 1 and args[0] == "--backout":
            operation = BACKOUT
        else:
            log.info("This command will migrate TankPublishedFile and associated entities to PublishedFile entities.")
            log.info("")
            log.info("Syntax:")
            log.info("migrate_published_file_entities [--backout]")
            log.info("")
            log.info("Flags:")
            log.info("--backout - Use this flag to backout of a current migration and switch back to using "
                     "'TankPublishedFile' and associated entities")
            log.info("")
            raise TankError("Invalid syntax for the command!")
        
        # get or create a shotgun connection to use and
        # get the details about the current project:
        sg_connection = None
        sg_project = {} 
        if self.tk:

            if self.tk.pipeline_configuration.is_site_configuration():
                raise TankError("You can't migrate entities for the site configuration.")

            # running for a specific project/pc:
            sg_connection = self.tk.shotgun
            sg_project = {"id":self.tk.pipeline_configuration.get_project_id(), "type":"Project"}
            
            # get the project name from shotgun:
            sg_res = sg_connection.find_one("Project", filters = [["id", "is", sg_project["id"]]], fields = ["name"])
            if sg_res:
                sg_project = sg_res
        else:
            # running 'globally' on all projects so need to create a new connection:
            sg_connection = shotgun.get_sg_connection() 
            
        if operation == MIGRATE:
            self._run_migration(log, sg_connection, sg_project)
        elif operation == BACKOUT:
            self._backout_migration(log, sg_connection, sg_project)
            
    def _backout_migration(self, log, sg_connection, sg_project):
        """
        Backout of the current entity migration and switch configs back to using
        TankPublishedFile entities 
        """
        log.info("Backout of Published File Entity Migration")
        log.info("------------------------------------------")
        if sg_project:
            log.info("This will switch ALL pipeline configurations for this "
                     "project back to using the 'TankPublishedFile' and associated "
                     "entities instead of the new 'PublishedFile' entities.")
        else:
            log.info("This will switch ALL pipeline configurations for ALL "
                     "projects back to using the 'TankPublishedFile' and associated "
                     "entities instead of the new 'PublishedFile' entities.")
        log.info("")
        log.info("This command WILL NOT:")
        log.info(" - Undo the previous migration - any migrated entities WILL NOT "
                 "be retired.")
        log.info(" - Migrate new PublishedFile entities back to the old TankPublishedFile "
                 "entity type.")
        log.info("")
        log.info("WARNING: If you have custom fields on any entities that link to both 'TankPublishedFile' "
                 "and their equivelant 'PublishedFile' entities then this may lead to problems.  If this "
                 "is the case, please contact support for advice.")

        log.info("")
        response = raw_input("Would you like to switch ALL configurations back now? [Yes]/No: ")
        if response and not response.lower().startswith("y"):
            raise TankError("Aborted by User.")
        
        # read the shotgun schema:
        sg_schema = sg_connection.schema_read()
        
        if (not "TankPublishedFile" in sg_schema
            or not "TankType" in sg_schema
            or not "TankDependency" in sg_schema):
            log.info("Please ensure that the 'TankPublishedFile', 'TankType' and 'TankDependency' entity "
                     "types are enabled in Shotgun before running this command.")
            raise TankError("Unable to continue because of missing entity types.")        
        
        log.info("")
        log.info("Updating pipeline configurations")
        log.info("--------------------------------")
        
        # run the update
        _, pc_warnings = self.__update_pipeline_configurations(log, sg_connection, sg_project, False, "TankPublishedFile")
        
        # report success/failure:
        log.info("")        
        if pc_warnings:
            for warning in pc_warnings:
                log.warning(warning)
            log.info("%d warnings were reported whilst updating pipeline configurations!" % len(pc_warnings))
            
            log.info("")
            log.info("The command has completed with warnings!  You should now check that all " 
                     "pipeline configurations have been updated by running this command for any "
                     "that failed to update!")
        else:
            log.info("You have successfully backed out of the Published File entity migration "
                     "for all configurations.  New Publishes will now use the TankPublishedFile "
                     "and associated entities until the migration command is run again!")
    
            
    def _run_migration(self, log, sg_connection, sg_project):
        """
        Run the entity migration to migrate all TankPublishedFile, TankType & TankDependency entities
        to PublishedFile, PublishedFileType & PublishedFileDependency entities respectively.
        """
            
        # create the migrators that we need for the migration:
        pf_migrator = PublishedFileEntityMigrator(log, sg_connection, sg_project)
        pft_migrator = PublishedFileTypeEntityMigrator(log, sg_connection, sg_project)
        
        # lets tell the user what this command is going to do:
        log.info("Migrate Tank Published File Entities")
        log.info("------------------------------------")
        if sg_project:
            log.info("This command will migrate all 'TankPublishedFile' entities within the '%s' project " 
                     "to the new 'PublishedFile' entity type by executing the following steps:" % sg_project["name"])
        else:
            log.info("This command will migrate all 'TankPublishedFile' entities for ALL PROJECTS " 
                     "to the new 'PublishedFile' entity type by executing the following steps:")
        log.info("")
        
        log.info("1. Migrate all 'TankType' entity records to the new 'PublishedFileType' entity type. "
                 "Note that 'PublishedFileType' is a *non-project* entity, whereas 'TankType' was "
                 "project-specific.  As a result, the migration script will consolidate 'TankType' "
                 "entities across projects if they share the same name.")
        log.info("2. Migrate all 'TankPublishedFile' entity records to the new 'PublishedFile' entity type.")
        if sg_project:
            log.info("3. Update all Pipeline Configurations for this project to use the new "
                     "'PublishedFile' entity types.")
        else:
            log.info("3. Update all Pipeline Configurations to use the new 'PublishedFile' "
                     "entity types.")
            log.info("")
            log.info("If you would prefer to run this migration on a single project, please run it "
                     "from within that project.")
        
        log.info("")
        log.info("For further information please see the documentation which can be found here: "
                 "https://support.shotgunsoftware.com/entries/95442888")
        log.info("")        
        log.info("The migration can take a long time to run depending on the number of entities " 
                 "that need migrating.  Therefore, we advise running it outside of working "
                 "hours if possible.")
        
        # it's quite a big change so lets warn them as well!
        log.info("")
        log.info("WARNING")
        log.info("-------")
        log.info("You should only continue if you are ready to switch to the 'PublishedFile' entity "
                 "types.  Before you begin, please be sure to do the following:")
        log.info("")
        log.info("- Enable the 'PublishedFile' entity types in the Shotgun Site Preferences.")
        log.info("- Update any custom apps or hooks you are using to support the new 'PublishedFile' "
                 "entity types.")
        log.info("")
        log.info("If you are unsure about any of this, please contact %s." % (constants_global.SUPPORT_EMAIL,))
        
        # now, after all that are they ready to start?
        num_entities_to_migrate = 0
        if sg_project:
            num_entities_to_migrate = (pf_migrator.calc_num_project_entities_to_migrate() 
                                        + pft_migrator.calc_num_project_entities_to_migrate())
        else:
            num_entities_to_migrate = (pf_migrator.calc_num_site_entities_to_migrate() 
                                        + pft_migrator.calc_num_site_entities_to_migrate())
            
        log.info("")
        log.info("NOTE")
        log.info("----")
        if num_entities_to_migrate == 0:
            log.info("It looks like all entities have already been migrated.  You can still continue "
                     "if you are fixing problems from a previous migration or are running this command "
                     "in a different project or Pipeline Configuration.")
        else:
            log.info("Found %d entities to migrate" % num_entities_to_migrate)
        log.info("")
        response = raw_input("Would you like to continue with the migration? [Yes]/No: ")
        if response and not response.lower().startswith("y"):
            raise TankError("Aborted by User.")
        
        log.info("")
        log.info("Validating the Shotgun schema, please wait...")
        log.info("---------------------------------------------")
        
        # read the shotgun schema:
        sg_schema = sg_connection.schema_read()
        
        # check that all the entity types we are interested in exist in the
        # Shotgun schema
        if (not "PublishedFile" in sg_schema
            or not "PublishedFileType" in sg_schema
            or not "PublishedFileDependency" in sg_schema):
            log.info("The 'PublishedFile', 'PublishedFileType' and 'PublishedFileDependency' entity "
                     "types are not enabled in Shotgun.  Please enable them and then run this "
                     "command again")
            raise TankError("Unable to continue because of missing entity types!")
        
        if (not "TankPublishedFile" in sg_schema
            or not "TankType" in sg_schema
            or not "TankDependency" in sg_schema):
            log.info("The 'TankPublishedFile', 'TankType' and 'TankDependency' entity "
                     "types are not enabled in Shotgun.  This probably means that you "
                     "are not using them and don't need to run this migration command!")
            raise TankError("Unable to continue because of missing entity types!")

        # parse the schemas
        pft_migrator.set_schema(sg_schema)
        pf_migrator.set_schema(sg_schema)
        
        # collate errors and warnings:
        errors = pft_migrator.get_schema_errors() + pf_migrator.get_schema_errors() 
        warnings = pft_migrator.get_schema_warnings() + pf_migrator.get_schema_warnings()
        if errors:
            log.info("")
            for error in errors:
                log.error(error)
        if warnings:
            log.info("")
            for warning in warnings:
                log.warning(warning)
        if errors or warnings:
            log.info("")
            log.info("%d errors and %d warnings were reported whilst validating the schema!" % (len(errors), len(warnings)))
        if errors:
            # can't continue if there were any errors found!
            log.info("")
            log.info("Please fix all errors and then try running this command again")
            raise TankError("Aborting due to problems found with the Shotgun schema")
        if warnings:
            # warnings aren't great but it's up to the user to continue or not...
            log.info("")
            response = raw_input("Would you like to ignore these warnings and continue with the migration? [Yes]/No: ")
            if response and not response.lower().startswith("y"):
                raise TankError("Aborted by User.")
            log.info("")
            log.warning("Ignoring schema warnings - some fields may not be migrated to the new entity types!")
        else:
            log.info("Shotgun schema is valid for migration")        
        
        # Check to see if we should do an app update - this is recommended!
        app_update_skipped = False
        log.info("")
        log.info("Update apps before migration?")
        log.info("-----------------------------")
        
        log.info("It is recommended that you update all of the apps in your Pipeline Configurations "
                 "before migrating entities to ensure they are ready to support the new 'PublishedFile' "
                 "entity types.")
        log.info("")

        if sg_project:
            response = raw_input("Would you like to update all apps now? [Yes]/No: ")
            if response and not response.lower().startswith("y"):
                app_update_skipped = True
            else:
                # run the app update:
                try:
                    update.check_for_updates(
                        log,
                        self.tk,
                        env_name=None,
                        engine_instance_name=None,
                        app_instance_name=None
                    )
                    log.info("App update completed successfully.")
                except TankError as e:
                    raise TankError("App update failed with the following error: %s" % e)
        else:
            response = raw_input("Would you like to exit now so that you can run app updates "
                                 "for each pipeline configuration? [Yes]/No: ")
            if response and not response.lower().startswith("y"):
                app_update_skipped = True
            else:
                log.info("")
                log.info("NOTE: Each project's engines and apps must be updated individually.  To do "
                         "this, run 'tank updates' on each.")
                raise TankError("Aborted by User.")
    
        if app_update_skipped:
            log.info("")            
            log.warning("App update skipped!  Please ensure all apps are updated once the migration "
                        "has completed to avoid unexpected problems.")

        # We now always update existing migrated entities as it is now non-destructive
        update_existing_entities = True
    
        log.info("")
        response = raw_input("Migration is now ready to begin - continue? [Yes]/No: ")
        if response and not response.lower().startswith("y"):
            raise TankError("Aborted by User.")
    
        log.info("")
        log.info("----------------------------------------------------------------------------")
        log.info("                           STARTING THE MIGRATION                           ")
        log.info("----------------------------------------------------------------------------")
            
        # we'll keep track of migration warnings as we go and present them at the end:
        # any errors would be thrown as exceptions so we don't worry about them!
        migration_warnings = []
            
        # migrate published file type entities
        log.info("")
        log.info("Step 1. Migrating entities of type 'TankType'")
        log.info("---------------------------------------------")
        try:
            pft_migrator.migrate_entities(update_existing_entities)
        except TankError as e:
            raise TankError("Migration of 'TankType' entities failed with the following error: %s" % e)
        migration_warnings.extend(pft_migrator.get_migration_errors())
        
        # migrate published file entities:
        log.info("")
        log.info("Step 2. Migrating entities of type 'TankPublishedFile'")
        log.info("------------------------------------------------------")
        log.info("")
        try:
            pf_migrator.migrate_entities(update_existing_entities)
        except TankError as e:
            raise TankError("Migration of 'TankPublishedFile' entities failed with the following error: %s" % e)
        migration_warnings.extend(pf_migrator.get_migration_errors())
        
        # report success/failure:
        log.info("")
        if migration_warnings:
            for warning in migration_warnings:
                log.warning(warning)
            log.info("")                
            log.info("%d warnings were reported whilst migrating entities!" % len(migration_warnings))
        else:
            log.info("All entities migrated successfully.")
            
        # update pipeline configurations:
        log.info("")
        log.info("Step 3. Updating pipeline configurations")
        log.info("----------------------------------------")
        
        all_pipeline_configs_updated = False
        pc_warnings =[]
        log.info("")
        if sg_project:
            log.info("In order to fully switch to the new entity types, all Pipeline Configurations for "
                     "the '%s' project need to be updated." % sg_project["name"])
        else:
            log.info("In order to fully switch to the new entity types, all Pipeline Configurations for "
                     "all projects need to be updated.")
        
        pc_update_skipped = False
        if self.tk:
            # have a pipeline config so can choose just to update this one!
            log.info("If you are still testing the migration then you can choose to only update the "
                     "current Pipeline Configuration.")
            log.info("")
            response = raw_input("Which Pipeline Configurations would you like to update? [All]/Current/None: ")
            
            if not response or response.lower().startswith("a") or response.lower().startswith("c"):
                update_current_pc_only = response and response.lower().startswith("c")
            
                # update
                all_pipeline_configs_updated, pc_warnings = self.__update_pipeline_configurations(log, sg_connection, sg_project, update_current_pc_only)                    
            else:
                pc_update_skipped = True
        else:
            log.info("")
            response = raw_input("Would you like to update all Pipeline Configurations? [Yes]/No: ")
            if not response or response.lower().startswith("y"):
                # update
                all_pipeline_configs_updated, pc_warnings = self.__update_pipeline_configurations(log, sg_connection, sg_project, False)
            else:
                pc_update_skipped = True
            
        if pc_update_skipped:
            all_pipeline_configs_updated = False
            pc_warnings.append("Pipeline Configuration update skipped!  Even though the migration has "
                               "completed, the 'TankPublishedFile' entity type will still be used when "
                               "publishing.  Re-run this command again to update your Pipeline Configurations "
                               "when you are ready to use the new entity types.")
            
        # report success/failure:
        log.info("")
        if pc_warnings:
            for warning in pc_warnings:
                log.warning(warning)
            log.info("")
            log.info("%d warnings were reported whilst updating Pipeline Configurations!" % len(pc_warnings))
        else:
            log.info("All Pipeline Configurations were updated successfully.")
        
        # finally, describe what needs to happen next.
        log.info("")
        if migration_warnings or pc_warnings:
            log.info("----------------------------------------------------------------------------")
            log.info("                     Migration completed with warnings!                     ")
            log.info("----------------------------------------------------------------------------")            
            log.info("There are some potential issue with your migration.  It is recommended that "
                     "you address the problems listed below and run this command again.  Some of "
                     "the warnings might be safe to ignore, but please review this summary to be certain:")
            log.info("")
            
            # output first 10 warnings:
            all_warnings = []
            if migration_warnings:
                all_warnings.extend(migration_warnings)
            if pc_warnings:
                all_warnings.extend(pc_warnings)
            for wi, warning in enumerate(all_warnings[:10]):
                log.warning("(%s) %s" % (wi+1, warning))
            if len(all_warnings) > 10:
                log.info("...")
            log.info("")
            log.info(" - %d warnings were reported during migration!" % len(all_warnings))
            log.info("")
                        
        else:
            log.info("----------------------------------------------------------------------------")
            log.info("                     Migration completed successfully.                      ")
            log.info("----------------------------------------------------------------------------")  

        log.info("The next steps you should take are:")

        # detail next steps:
        all_entities_migrated = (pf_migrator.calc_num_site_entities_to_migrate() + pft_migrator.calc_num_site_entities_to_migrate()) == 0

        class AutoCounter(object):
            def __init__(self, initial_val):
                self._val = initial_val
            @property
            def value(self):
                current_val = self._val
                self._val += 1
                return current_val

        step_num = AutoCounter(1)
        if app_update_skipped:
            log.info(("%d. Run the 'tank updates' command to update your apps - you "
                     "skipped this step at the beginning!") % step_num.value)
        log.info(("%d. Update any of your own apps or hooks that explicitly use the old 'TankPublishedFile', "
                  "'TankType' or 'TankDependency' entity types") % step_num.value)
        if not all_pipeline_configs_updated:
            log.info(("%d. Update any Pipeline Configurations that were not updated by "
                      "this command by running this command again from within those configurations") % step_num.value)            
        if not all_entities_migrated:
            log.info(("%d. Migrate entities for all other projects that have not been "
                      "migrated yet") % step_num.value)
        log.info("%d. Update any details pages on your Shotgun site to reference the new entities." % step_num.value)
        log.info("%d. Ensure everything works as expected." % step_num.value)

        # this command can be run again!
        log.info("")
        log.info("NOTE")
        log.info("----")
        log.info("You can safely run this migration command again if needed.  It will only "
                 "create new entities where they weren't migrated previously, otherwise it will "
                 "just update the existing ones.")
        
        if all_entities_migrated:
            # special case if all entities have been migrated across all projects!
            log.info("")
            log.info("Migration of all entities is now complete!")
            log.info("------------------------------------------")
            log.info("All 'TankPublishedFile' entities on your site have now been migrated!  "
                     "If you are happy that everything is now working correctly across all "
                     "projects then you should disable the 'TankPublishedFile' entities within "
                     "your site preferences.")
            log.info("")
            log.info("If you are not ready to disable 'TankPublishedFile' entities yet then be "
                     "sure to check that no new entities have been created when you do.  To do " 
                     "this, just run this comand again.")
        
        log.info("")
        log.info("Finally, if you have any problems with this migration, please contact "
                 "%s." % (constants_global.SUPPORT_EMAIL,))
        log.info("")
        

    def __update_pipeline_configurations(self, log, sg_connection, sg_project, current_only, pf_entity_type="PublishedFile"):
        """
        Update all pipeline configurations for this project if we 
        have access.
        
        Returns an array of warnings generated during the migration
        """
        warnings = []
        all_updated = True
        
        # first, get all pipeline configs:
        pcs = sg_connection.find(
            constants.PIPELINE_CONFIGURATION_ENTITY,
            filters = [["project", "is", sg_project]] if sg_project else [],
            fields = ["code", "mac_path", "windows_path", "linux_path", "project"]
        )
        
        # now iterate through them, updating as we go
        for pc_i, pc in enumerate(pcs):
            project_name = pc.get("project", {}).get("name", "")
            pc_name = pc["code"]
            
            if current_only:
                if not self.tk or pc["id"] != self.tk.pipeline_configuration.get_shotgun_id():
                    all_updated = False
                    continue
            
            log.info("")
            log.info("Updating pipeline configuration '%s' for project '%s' (%d of %d)" % (pc_name, project_name, pc_i+1, len(pcs)))
            
            # check that pipeline config is accessible:
            local_path = pc.get(ShotgunPath.get_shotgun_storage_key())
            if local_path is None or not os.path.exists(local_path):
                all_updated = False
                warnings.append("Pipeline configuration '%s' for project '%s' is not accessible from this computer and can't be migrated!" 
                                % (pc_name, project_name))
                continue
                
            # find the pipeline_config.yml path:
            pc_path = os.path.join(
                local_path,
                "config",
                "core",
                constants.PIPELINECONFIG_FILE
            )

            
            if not os.path.exists(pc_path):
                all_updated = False
                warnings.append("The settings file '%s' for the pipeline configuration '%s' in project '%s' could not be found to update!" 
                                % (pc_path, pc_name, project_name))
                continue
            
            # update file to use the new entity type:
            log.info(" - Updating published entity type in '%s'" % pc_path)
            old_umask = os.umask(0)
            try:
                pc_data = {}
                
                # read the file first
                fh = open(pc_path, "rt")
                try:
                    pc_data = yaml.load(fh)
                finally:
                    fh.close()

                # update the entity type:            
                pc_data["published_file_entity_type"] = pf_entity_type

                # and write back to the file:
                os.chmod(pc_path, 0o666)
                try:
                    # and write the new file
                    fh = open(pc_path, "wt")
                    # using safe_dump instead of dump ensures that we
                    # don't serialize any non-std yaml content. In particular,
                    # this causes issues if a unicode object containing a 7-bit
                    # ascii string is passed as part of the data. in this case, 
                    # dump will write out a special format which is later on 
                    # *loaded in* as a unicode object, even if the content doesn't  
                    # need unicode handling. And this causes issues down the line
                    # in toolkit code, assuming strings:
                    #
                    # >>> yaml.dump({"foo": u"bar"})
                    # "{foo: !!python/unicode 'bar'}\n"
                    # >>> yaml.safe_dump({"foo": u"bar"})
                    # '{foo: bar}\n'
                    #                    
                    yaml.safe_dump(pc_data, fh)
                finally:
                    fh.close()
        
                log.debug("Successfully updated pipeline configuration '%s'" % pc_name)
        
            except Exception as e:
                all_updated = False
                warnings.append("Failed to update the settings file '%s' for pipeline configuration '%s', project '%s': %s" 
                                % (pc_path, pc_name, project_name, e))
                continue
            finally:
                os.umask(old_umask)
            
            if pf_entity_type == "PublishedFile":
                # now look for the shotgun_TankPublishedFile.yml environment 
                # file and copy if necessary
                env_path = os.path.join(local_path, "config", "env", "shotgun_tankpublishedfile.yml")
                if os.path.exists(env_path):
                    log.info(" - Processing environment file '%s'" % env_path)
                    
                    # copy to new environment:
                    dst_env_path = os.path.join(local_path, "config", "env", "shotgun_publishedfile.yml")
                    if os.path.exists(dst_env_path):
                        log.debug("Environment file '%s' already exists, skipping" % dst_env_path)
                        continue
    
                    log.debug("Copying environment configuration from '%s' to '%s'" % (env_path, dst_env_path))
                    try:
                        shutil.copyfile(env_path, dst_env_path)
                    except IOError as e:
                        warnings.append("Failed to copy environment file '%s' to '%s': %s" % (env_path, dst_env_path, e))
                
            
        return (all_updated, warnings)
