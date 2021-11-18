from collections import namedtuple

from celery.utils.log import get_task_logger
from pysnmp.smi import builder, view
from pysnmp.smi.rfc1902 import ObjectType, ObjectIdentity

from splunk_connect_for_snmp.snmp.tasks import MIB_SOURCES

logger = get_task_logger(__name__)


class VarbindCollection(namedtuple("VarbindCollection", "get, bulk")):
    def __add__(self, other):
        return VarbindCollection(bulk=self.bulk + other.bulk, get=self.get + other.get)


def translate_list_to_oid(varbind):
    oid = ObjectType(
        ObjectIdentity(
            *varbind
        ).addAsn1MibSource(
            MIB_SOURCES,
        )
    ).loadMibs()
    return oid


def mib_string_handler(mib_list: list) -> VarbindCollection:
    """
    Perform the SNMP Get for mib-name/string, where mib string is a list
    1) case 1: with mib index - consider it as a single oid -> snmpget
    e.g. ['SNMPv2-MIB', 'sysUpTime',0] (syntax -> [<mib_file_name>, <mib_name/string>, <min_index>])

    2) case 2: without mib index - consider it as a oid with * -> snmpbulkwalk
    . ['SNMPv2-MIB', 'sysORUpTime'] (syntax -> [<mib_file_name>, <mib_name/string>)
    """
    if not mib_list:
        return VarbindCollection(get=[], bulk=[])
    get_list, bulk_list = [], []
    for mib_string in mib_list:
        try:
            oid = translate_list_to_oid(mib_string)
            logger.debug(f"[-] oid: {oid}")
            mib_string_length = len(mib_string)
            if mib_string_length == 3:
                get_list.append(ObjectType(oid))
            elif mib_string_length < 3:
                bulk_list.append(ObjectType(oid))
            else:
                raise Exception(
                    f"Invalid mib string - {mib_string}."
                    f"\nPlease provide a valid mib string in the correct format. "
                    f"Learn more about the format at https://bit.ly/3qtqzQc"
                )
        except Exception as e:
            logger.error(
                f"Error happened while polling for mib string: {mib_string}: {e}"
            )
    return VarbindCollection(get=get_list, bulk=bulk_list)


def _any_failure_happened(
    error_indication, error_status, error_index, var_binds: list
) -> bool:
    """
    This function checks if any failure happened during GET or BULK operation.
    @param error_indication:
    @param error_status:
    @param error_index: index of varbind where error appeared
    @param var_binds: list of varbinds
    @return: if any failure happened
    """
    if error_indication:
        result = f"error: {error_indication}"
        logger.error(result)
    elif error_status:
        result = "error: {} at {}".format(
            error_status.prettyPrint(),
            error_index and var_binds[int(error_index) - 1][0] or "?",
        )
        logger.error(result)
    else:
        return False
    return True

