from datetime import datetime
from typing import List, Type, Optional
import xml.etree.ElementTree as ET  # nosec
import os

from flask import request, Response
from sqlalchemy.inspection import inspect
from ivr_gateway.models.enums import Partner

def try_cast_to_date(datetime_str):
    try:
        date_obj = datetime.fromisoformat(datetime_str).date()
        return date_obj
    except (TypeError, ValueError):
        return None


def try_cast_to_time(time_str):
    try:
        time_obj = datetime.strptime(time_str, '%H:%M').time()
        return time_obj
    except (TypeError, ValueError):
        return None


def returns_twiml(f):
    def decorated_function(*args, **kwargs):
        r = f(*args, **kwargs)
        return Response(str(r), content_type='text/xml; charset=utf-8')

    return decorated_function


def returns_xml(f):
    def decorated_function(*args, **kwargs):
        r = f(*args, **kwargs)
        xml = ET.tostring(r).decode('utf-8')
        xml_string = '<?xml version="1.0" encoding="UTF-8"?>{}'.format(xml)
        return Response(xml_string, content_type='text/xml; charset=utf-8')

    return decorated_function


def log_request_info(logger):
    logger.debug('Headers: %s', request.headers)
    logger.debug('Body: %s', request.get_data())


def modify_object_with_dict(object_to_update, update_dict: dict):
    for key, value in update_dict.items():
        setattr(object_to_update, key, value)


def dynamic_class_loader(name) -> Type:
    components = name.split('.')
    mod = __import__(components[0])
    for comp in components[1:]:
        mod = getattr(mod, comp)
    return mod


def without(d, key):
    new_d = d.copy()
    try:
        new_d.pop(key)
    except KeyError:
        pass
    return new_d


def recursive_dict_fetch(container: dict, keys: List[str]):
    """
    Extracts a key from a nested container object, extraction is performed by traversing the list of keys
    until we resolve the object or error

    :param container:
    :param keys:
    :return:
    :raises KeyError if key does not exist
    """
    if len(keys) > 1:
        return recursive_dict_fetch(container[keys[0]], keys[1:])
    elif len(keys) == 1:
        return container[keys[0]]
    else:
        return container


def get_model_changes(model):
    """
    Return a dictionary containing changes made to the model since it was
    fetched from the database.

    The dictionary is of the form {'property_name': [old_value, new_value]}

    https://stackoverflow.com/a/56351576

    modified to exclude initial setting of fields
    """
    state = inspect(model)
    changes = {}
    for attr in state.attrs:
        hist = state.get_history(attr.key, True)

        if not hist.has_changes():
            continue

        old_value = hist.deleted[0] if hist.deleted else None
        new_value = hist.added[0] if hist.added else None
        if old_value is not None and old_value != new_value:
            changes[attr.key] = [old_value, new_value]

    return changes


def get_partner_namespaced_environment_variable(field: str, service: str = None, partner: Partner = None,
                                                raise_if_none: bool = True) -> Optional[str]:
    """
    Return the value of a partner namespaced environment variable formatted as SERVICE_PARTNER_FIELD, e.g.

    service = telco
    partner = Partner.IVR
    field   = api_key
    TELCO_IVR_API_KEY
    """

    if field is None:
        raise TypeError
    if partner is None and service is None:
        raise ValueError("Either partner or service must be specified.")

    if partner is None:
        var_name = f"{service.upper()}_{field.upper()}"
    elif service is None:
        var_name = f"{partner.value.upper()}_{field.upper()}"
    else:
        var_name = f"{service.upper()}_{partner.value.upper()}_{field.upper()}"

    var = os.getenv(var_name)
    if raise_if_none and not var:
        raise TypeError(f"Environment variable {var_name} not found.")
    return var


def format_as_sentence(msg: str) -> str:
    if msg == "":
        return msg

    if msg[0].isalpha():
        first_char = msg[0].upper()
    else:
        first_char = msg[0]

    if msg[-1] != ".":
        last_char = "."
    else:
        last_char = ""
    return first_char + msg[1:] + last_char


def trailing_digits(s: str):
    return s[len(s.rstrip('0123456789')):]
