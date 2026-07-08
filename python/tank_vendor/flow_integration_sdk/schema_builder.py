# Copyright (c) 2026 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""Schema builder utilities for creating and managing Flow pipeline schemas."""

from __future__ import annotations  # needed for python 3.9 support

from typing import Any

from tank_vendor.flow_data_sdk.base import model as flow_model
from tank_vendor.flow_data_sdk.base.exceptions import (
    FlowConnectionError,
    GQLAPIError,
    ValidationError,
)

from .exceptions import (
    FlowSchemaBuilderError,
    FlowSchemaDisplayDataError,
    FlowSchemaError,
    FlowSchemaLibraryError,
)
from .globals import KIND_BASE_TYPE_ID, get_client
from .objects import FlowProject
from . import schema
from .schema import get_schema_id
from .utils import get_logger


# Constant for Flow Toolkit Library schema library ID
FLOW_TOOLKIT_LIBRARY_ID = "FlowToolkitLibrary"


class SchemaBuilder:
    """Utility class to build and validate schemas from a dictionary.

    This class provides methods to validate schema definitions, build new schemas,
    update schema display names, and retrieve existing schemas from a schema library.
    """

    def __init__(
        self,
        schema_dict: dict,
        schema_kind: flow_model.SchemaKind,
        project_id: str,
        schema_library_id: str,
    ):
        """Initialize the SchemaBuilder.

        Args:
            schema_dict: The dictionary containing the schema definition.
            schema_kind: The kind of Schema to create (type, component, or property).
            project_id: The Flow AM project ID.
            schema_library_id: The ID of the schema library where the schema
                will be created.
        """
        self.schema_dict = schema_dict
        self.schema_kind = schema_kind
        self.project_id = project_id
        self.schema_library_id = schema_library_id
        self.schema: flow_model.Schema | None = None

        # Validate schema dictionary on initialization
        self.__validate_schema_dict()

    def __validate_schema_dict(self) -> None:
        """Validate the incoming schema dictionary.

        Raises:
            KeyError: If required keys are missing or invalid.
            ValueError: If key types or values are invalid.
        """

        # Define a dictionary mapping keys to their expected types
        key_type_dict = {
            "name": str,
            "version": str,
            "display_name": str,
            "kind": str,
            "description": str,
            "inherits": list,
            "properties": list,
        }

        # Check for mandatory keys
        for key in ["name", "version", "kind"]:
            if key not in self.schema_dict:
                raise KeyError(
                    f"The schema definition must contain a '{key}' key of type string."
                )

        # Validate keys and types
        for key, value in self.schema_dict.items():
            if key not in key_type_dict:
                raise KeyError(f"Invalid key '{key}' in custom type schema.")
            if not isinstance(value, key_type_dict[key]):
                raise ValueError(
                    f"The '{key}' key must be of type {key_type_dict[key].__name__}."
                )
            if key == "kind":
                # Validate against flow_model.SchemaKind enum
                valid_kinds = [kind.value for kind in flow_model.SchemaKind]
                if value not in valid_kinds:
                    raise ValueError(
                        f"Invalid kind '{value}' in custom type schema. "
                        f"Must be one of {', '.join(valid_kinds)}"
                    )
            if key == "properties":
                for property_dict in value:
                    self.__validate_property_dict(property_dict)

    def __validate_property_dict(self, property_dict: dict) -> None:
        """Validate a schema 'property' dictionary.

        Args:
            property_dict (dict): The property dictionary to validate.

        Raises:
            KeyError: If required keys are missing or invalid.
            ValueError: If key types or values are invalid.
        """

        # Define a dictionary mapping keys to their expected types
        key_type_dict = {
            "name": str,
            "data_type": str,
            "properties": list,
            "default_value": Any,
            "context": str,
            "length": int,
        }

        # Check for mandatory keys
        for key in ["name", "data_type"]:
            if key not in property_dict:
                raise KeyError(f"The property schema must contain a '{key}' key.")

        # Validate keys and types
        for key, value in property_dict.items():
            if key not in key_type_dict:
                raise KeyError(f"Invalid key '{key}' in property schema.")

            if key_type_dict[key] is not Any:
                if not isinstance(value, key_type_dict[key]):  # type: ignore
                    raise ValueError(
                        f"The '{key}' key must be of type "
                        f"{key_type_dict[key].__name__}."  # type: ignore
                    )

            if key == "data_type":
                # Validate that referenced schema exists in config
                if "$ref:" in value:
                    referenced_schema = value.split(":")[1]
                    referenced_schema_id = get_schema_id(referenced_schema)
                    if not referenced_schema_id:
                        raise ValueError(
                            f"Referenced schema '{referenced_schema}' not found "
                            "in config.json."
                        )

            if key == "properties":
                for sub_property_dict in value:
                    self.__validate_property_dict(sub_property_dict)

    def _create_property_type_input(
        self, data_type: str
    ) -> flow_model.PropertyTypeInput:
        """Create a PropertyTypeInput from a data type string.

        Args:
            data_type: Either a primitive type name (e.g., "String") or a
                custom schema type ID

        Returns:
            PropertyTypeInput with either primitive_type or custom_type set
        """
        primitive_types = [member.value for member in flow_model.PrimitiveType]

        if data_type in primitive_types:
            primitive_enum = flow_model.PrimitiveType(data_type)
            return flow_model.PropertyTypeInput(primitive_type=primitive_enum.value)

        return flow_model.PropertyTypeInput(custom_type=data_type)

    def _create_properties_definition_input(
        self, property_dict: dict
    ) -> flow_model.PropertiesDefinitionInput:
        """Recursively create a PropertiesDefinitionInput from a property dictionary."""
        # Resolve references in data type
        data_type = property_dict["data_type"]

        if "$ref:" in data_type:
            # Resolve referenced schema id
            referenced_schema_name = property_dict["data_type"].split(":")[1]
            referenced_schema_id = get_schema_id(referenced_schema_name)
            if not referenced_schema_id:
                raise ValueError(
                    f"Referenced schema '{referenced_schema_name}' not found "
                    "in config.json."
                )
            data_type = referenced_schema_id

        if "$id:" in data_type:
            data_type = ":".join(data_type.split(":")[1:])

        # Create PropertyTypeInput
        property_type_input = self._create_property_type_input(data_type)

        # Recursively handle nested properties
        nested_properties = []
        if property_dict.get("properties"):
            for nested_property in property_dict["properties"]:
                nested_properties.append(
                    self._create_properties_definition_input(nested_property)
                )

        # Create PropertiesDefinitionInput
        properties_definition_input = flow_model.PropertiesDefinitionInput(
            name=property_dict["name"],
            type=property_type_input,
            properties=nested_properties if nested_properties else None,
        )

        # Add optional fields if present
        if "default_value" in property_dict:
            properties_definition_input.value = property_dict["default_value"]
        if "context" in property_dict:
            properties_definition_input.context = property_dict["context"]
        if "length" in property_dict:
            properties_definition_input.length = property_dict["length"]

        return properties_definition_input

    def build(self) -> flow_model.Schema:
        """Build and commit the custom private Schema.

        Returns:
            Schema: The created or existing Schema instance.

        Raises:
            FlowSchemaError: If schema creation or commit fails due to a client error.
            ValueError: If referenced schemas in 'inherits' or 'properties' are
                not found.
        """

        logger = get_logger(__name__)
        client = get_client()

        # Build inherits list for CreateSchemaInput
        inherits = []
        if self.schema_dict.get("inherits"):
            for inherited_schema in self.schema_dict["inherits"]:
                # If current schema inherits from another schema
                if "$ref:" in inherited_schema:
                    # Resolve referenced schema id
                    inherited_schema_name = inherited_schema.split(":")[1]
                    inherited_schema_id = get_schema_id(inherited_schema_name)
                    if not inherited_schema_id:
                        raise ValueError(
                            f"Inherited schema '{inherited_schema_name}' not found "
                            "in config.json."
                        )
                    inherits.append(inherited_schema_id)
                else:
                    inherits.append(inherited_schema)

        # Build property list for CreateSchemaInput
        properties = []
        for property_dict in self.schema_dict.get("properties", []):
            properties.append(
                self._create_properties_definition_input(property_dict)
            )

        try:
            # Create CreateSchemaInput for the mutation
            create_schema_input = flow_model.CreateSchemaInput(
                kind=self.schema_kind.value,
                name=self.schema_dict["name"],
                project_id=self.project_id,
                schema_library_id=self.schema_library_id,
                version=self.schema_dict["version"],
                description=self.schema_dict.get("description", ""),
                inherits=inherits if inherits else None,
                properties=properties if properties else None,
            )
            # Create and call the schema mutation
            create_schema_query = client.service_schema.create_schema(
                variables=create_schema_input
            )
            query_response = create_schema_query.call()
            self.schema = query_response.schema
            logger.info(f"Created new schema: {self.schema.name}")
        except (GQLAPIError, FlowConnectionError, ValidationError) as e:
            raise FlowSchemaError(
                details=(
                    f"Failed to create schema '{self.schema_dict['name']}' "
                    f"version '{self.schema_dict['version']}': {e}"
                )
            ) from e

        return self.schema

    def get_display_data(self) -> flow_model.SchemaDisplayData | None:
        """Retrieve the display data object for the current schema.

        This method attempts to fetch the SchemaDisplayData associated with the
        schema instance. If the schema has not been built, a FlowSchemaBuilderError
        is raised. If no display data exists for the schema, None is returned.

        Returns:
            SchemaDisplayData | None: The display data instance if found,
                otherwise None.

        Raises:
            FlowSchemaBuilderError: If the schema instance has not been built.
        """

        if not self.schema:
            raise FlowSchemaBuilderError(details="Schema instance has not been built yet.")

        client = get_client()
        schema_display_data = None
        try:
            # Create GetSchemaDisplayDataInput for the query
            input_data = flow_model.GetSchemaDisplayDataInput(
                schema_type_id=self.schema.type_id
            )
            # Create and call the schema query
            schema_query = client.service_schema.schema_display_data(
                variables=input_data
            )
            query_response = schema_query.call()
            schema_display_data = query_response.schema_display_data
        except (GQLAPIError, FlowConnectionError, ValidationError):
            # TODO: Verify get display data for new created schema's behavior
            # Two possible scenarios:
            # 1. Schema type doesn't exist (shouldn't happen if schema was just created)
            # 2. No display data exists yet (expected for newly created schemas)
            pass

        return schema_display_data

    def update_display_name(self) -> str | None:
        """Update the display name of the schema to match the value in the schema
        definition.

        This method retrieves the current schema's display data and updates its
        display name if it differs from the desired value. If the display name is
        successfully updated, the new value is returned. If the display name
        already matches, it is returned.

        Returns:
            str | None: The updated display name if successful, or the current
                display name if it already matches the desired value.

        Raises:
            FlowSchemaBuilderError: If the schema instance has not been built or the
                schema definition does not specify a display name.
            FlowSchemaDisplayDataError: If updating the display name fails due to an
                error (such as an API failure).
        """

        logger = get_logger(__name__)
        client = get_client()
        display_name = self.schema_dict.get("display_name")

        if not self.schema:
            raise FlowSchemaBuilderError(details="Schema instance has not been built yet.")

        if not display_name:
            raise FlowSchemaBuilderError(
                details="No display name specified in schema definition."
            )

        if (
            self.schema.display_data
            and self.schema.display_data.display_name == display_name
        ):
            return display_name

        schema_display_data = self.get_display_data()

        try:
            if schema_display_data:
                # Display data exists
                # Create UpdateSchemaDisplayDataInput for update display name
                # mutation and call it
                input_data = flow_model.UpdateSchemaDisplayDataInput(
                    schema_type_id=self.schema.type_id, display_name=display_name
                )
                client.service_schema.update_schema_display_data(
                    variables=input_data,
                ).call()
            else:
                # Display data doesn't exist
                # Create CreateSchemaDisplayDataInput for create display name
                # mutation and call it
                input_data = flow_model.CreateSchemaDisplayDataInput(
                    schema_type_id=self.schema.type_id, display_name=display_name
                )
                client.service_schema.create_schema_display_data(
                    variables=input_data,
                ).call()

            logger.debug(
                "updated display name of schema %s to '%s'",
                self.schema.name,
                display_name,
            )
            return display_name
        except (GQLAPIError, FlowConnectionError, ValidationError) as e:
            raise FlowSchemaDisplayDataError(
                details=(
                    f"Could not update display data for schema "
                    f"'{self.schema.name}': {e}."
                )
            ) from e


def _get_schema_library(
    library_id: str, collection_id: str
) -> flow_model.SchemaLibrary | None:
    """Retrieve a schema library by its unique name (ID) if it exists, or None
    if not found.

    Raises:
        FlowSchemaLibraryError: If retrieving schema libraries fails due to a client
            error.
    """

    logger = get_logger(__name__)
    client = get_client()

    try:
        # Create SchemaLibrariesByCollectionIdInput for the query
        input_data = flow_model.SchemaLibrariesByCollectionIdInput(
            collection_id=collection_id
        )
        # Create and call the schema query
        schema_query = client.service_schema.schema_libraries_by_collection_id(
            variables=input_data
        )
        schema_libraries = list(schema_query.libraries_iterator or [])
    except (GQLAPIError, FlowConnectionError, ValidationError) as e:
        raise FlowSchemaLibraryError(
            details=f"Failed to retrieve all schema libraries: {e}"
        ) from e

    for schema_library in schema_libraries:
        if schema_library.name == library_id:
            logger.info("Found existing schema library %s", library_id)
            return schema_library

    logger.info("Schema Library %s not found.", library_id)
    return None


def _create_schema_library(
    library_id: str,
    title: str,
    description: str,
    project_id: str,
    collection_id: str,
) -> flow_model.SchemaLibrary:
    """Create a schema library if it does not exist, or return the existing one.

    Raises:
        FlowSchemaLibraryError: If retrieving or creating the schema library fails
            due to a client error.
    """

    logger = get_logger(__name__)
    schema_library = _get_schema_library(library_id, collection_id)

    if schema_library is not None:
        logger.info("Schema Library %s found. Skipping creation.", library_id)
        return schema_library

    client = get_client()

    try:
        # Create CreateSchemaLibraryInput for the mutation
        input_data = flow_model.CreateSchemaLibraryInput(
            name=library_id,
            title=title,
            description=description,
            project_id=project_id,
        )
        # Create and call the schema mutation
        schema_query = client.service_schema.create_schema_library(
            variables=input_data
        )
        query_response = schema_query.call()
        # Extract the created schema library from the response
        schema_library = query_response.schema_library
        logger.info("Successfully created a new Schema Library %s", library_id)
        return schema_library

    except (GQLAPIError, FlowConnectionError, ValidationError) as e:
        raise FlowSchemaLibraryError(
            details=f"Failed to create SchemaLibrary '{library_id}': {e}"
        ) from e


def create_pipeline_schemas(project_id: str, config_path: str):
    """Create pipeline schemas under the schema library 'Flow Toolkit Library'
    for a CPA collection.

    This utility is only applicable to CPA (provisioned) collections. It is
    designed to create or use the 'Flow Toolkit Library' and its associated
    schemas.

    The function performs the following steps:
        1. Loads and validates the config.json file.
        2. Queries existing schema type ids for the target collection.
        3. Creates the schema library if any configured schemas are missing.
        4. Creates any missing schemas and sets their display names.

    Args:
        project_id: The Flow AM project ID.
        config_path: Path to the schema config json file.
    Raises:
        RuntimeError: If schema library creation fails.
        FileNotFoundError: If the config file does not exist.
        json.JSONDecodeError: If the config file contains invalid JSON.
        KeyError: If the config file does not contain a 'schemas' key,
            or if required keys are missing in the schema definition.
        ValueError: If schema definition or property values are invalid.
        FlowSchemaError: If schema creation or retrieval fails.
        FlowSchemaBuilderError: If schema building fails.
        FlowSchemaDisplayDataError: If updating display data fails.
        FlowSchemaLibraryError: If schema library operations fail.
    """
    logger = get_logger(__name__)

    config = schema._read_schema_config(config_path)
    if "schemas" not in config:
        raise KeyError("The schema config file must contain a 'schemas' key with a list of schemas to create.")
    client = get_client()
    collection_id = FlowProject.get_collection_id(project_id)

    # Collect distinct schema kinds present in config, then query existing
    # schemas per kind. This avoids querying for kinds not used in the config.
    kinds_in_config = {s["kind"] for s in config.get("schemas", []) if "kind" in s}

    existing_schema_types = set()
    try:
        for kind in kinds_in_config:
            base_type_id = KIND_BASE_TYPE_ID[kind]
            schemas_by_supertype_input = flow_model.SchemasBySuperTypeInput(
                collection_id=collection_id,
                type_id=base_type_id,
                include_sub_sub_classes=True,
            )
            schema_query = client.service_schema.schemas_by_super_type(
                variables=schemas_by_supertype_input
            )
            existing_schema_types.update(schema_query.schema_types_iterator)
        logger.info(
            f"Retrieved {len(existing_schema_types)} existing schemas for "
            f'collection "{collection_id}".'
        )
    except (GQLAPIError, FlowConnectionError, ValidationError) as e:
        raise RuntimeError(f"Failed to retrieve existing schemas: {e}") from e

    # Check if schema listed in config.json already exists
    # If not, add it to need_to_create list
    need_to_create = []
    for schema_dict in config.get("schemas", []):
        # Get the schema type id for the schema and check if it already exists
        schema_type_id = get_schema_id(schema_dict["name"])
        if schema_type_id not in existing_schema_types:
            logger.info(
                f'Schema "{schema_type_id}" not found. Adding to list to be created.'
            )
            need_to_create.append(schema_dict)

    # Check if need_to_create is not empty
    # and proceed to create schema library and schemas
    if len(need_to_create) > 0:
        logger.info("Attempting to create missing schemas...")
        library_id = FLOW_TOOLKIT_LIBRARY_ID
        _create_schema_library(
            library_id=library_id,
            title="Flow Toolkit Library",
            description="Schemas for Flow Toolkit pipelines.",
            project_id=project_id,
            collection_id=collection_id,
        )

        schemas = []
        # Create schemas if not exist
        for schema_dict in need_to_create:
            schema_builder = SchemaBuilder(
                schema_dict=schema_dict,
                schema_kind=flow_model.SchemaKind(schema_dict["kind"]),
                project_id=project_id,
                schema_library_id=library_id,
            )
            schema_builder.build()

            if schema_builder.schema:
                # NOTE: We need to explicitly pass the display name back because
                # in newly created schemas, the 'display_name' property is not
                # updated, therefore can not be reliably used to determine
                # display name of the schema.
                display_name = schema_builder.update_display_name()
                schemas.append((schema_builder.schema, display_name))
    else:
        logger.info("All required schemas already exist.")
