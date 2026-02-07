from typing import Any

from pygfa.graph_element.parser import field_validator as fv
from pygfa.graph_element.parser import line

SERIALIZATION_ERROR_MESSAGGE = "Couldn't serialize object identified by: "


def _format_exception(identifier: str, exception: Exception) -> str:
    return SERIALIZATION_ERROR_MESSAGGE + identifier + "\n\t" + repr(exception)


def _remove_common_edge_fields(edge_dict: dict[str, Any]) -> None:
    edge_dict.pop("eid")
    edge_dict.pop("from_node")
    edge_dict.pop("from_orn")
    edge_dict.pop("to_node")
    edge_dict.pop("to_orn")
    edge_dict.pop("from_positions")
    edge_dict.pop("to_positions")
    edge_dict.pop("alignment")
    edge_dict.pop("distance")
    edge_dict.pop("variance")


def _serialize_opt_fields(opt_fields: dict[str, line.OptField]) -> list[str]:
    fields = []
    for _key, opt_field in opt_fields.items():
        if line.is_optfield(opt_field):
            fields.append(str(opt_field))
    return fields


def _are_fields_defined(fields: Any) -> bool:
    try:
        for field in fields:
            if field is None:
                return False
    except Exception:
        return False
    return True


def _check_fields(fields: Any, required_fields: list[str]) -> bool:
    """Check if each field has the correct format as
    stated from the specification.

    :param fields: The fields to check.
    :param required_fields: The list of required field names.
    :return: True if all fields are valid, False otherwise.
    """
    try:
        for field in range(0, len(required_fields)):
            if not fv.is_valid(fields[field], required_fields[field]):
                return False
        return True
    except Exception:
        return False


def _check_identifier(identifier: str | Any) -> str:
    if not isinstance(identifier, str):
        identifier = f"'{identifier!s}' - id of type {type(identifier)}."
    return identifier
