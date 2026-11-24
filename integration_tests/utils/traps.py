import logging

from pysnmp.hlapi.v3arch.asyncio import (
    CommunityData,
    ContextData,
    NotificationType,
    ObjectIdentity,
    SnmpEngine,
    UdpTransportTarget,
    send_notification,
)

logger = logging.getLogger(__name__)


async def send_trap(
    host, port, object_identity, mib_to_load, community, mp_model, *var_binds
):
    error_indication, error_status, error_index, _ = await send_notification(
        SnmpEngine(),
        CommunityData(community, mpModel=mp_model),
        await UdpTransportTarget.create((host, port)),
        ContextData(),
        "trap",
        NotificationType(ObjectIdentity(object_identity))
        .add_varbinds(*var_binds)
        .load_mibs(mib_to_load),
    )

    if error_indication:
        logger.error(f"{error_indication}")
