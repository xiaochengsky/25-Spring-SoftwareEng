import json
from borsh_construct import CStruct, U64, I64, U16, Vec, U8, String

# Map JSON types to borsh-construct types
type_mapping = {
    "u64": U64,
    "i64": I64,
    "u16": U16,
    "u8": U8,
    "string": String,
    "array": Vec
}

#Load an anchor schema froma an idl defined structure
def load_schema(schema_def: dict)->CStruct:
    # Ensure the schema defines a struct
    if schema_def["type"]["kind"] != "struct":
        raise ValueError("Only struct types are supported.")

    # Parse fields
    fields = {}
    for field in schema_def["type"]["fields"]:
        field_name = field["name"]
        field_type = field["type"]

        # Map field type to borsh-construct type
        if field_type in type_mapping:
            fields[field_name] = type_mapping[field_type]
        else:
            raise ValueError(f"Unsupported type: {field_type}")

    # Create the CStruct
    return schema_def["name"], CStruct(**fields)