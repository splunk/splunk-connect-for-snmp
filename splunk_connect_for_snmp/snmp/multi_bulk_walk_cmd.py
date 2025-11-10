from typing import AsyncGenerator

from pysnmp.entity.engine import SnmpEngine
from pysnmp.hlapi import varbinds
from pysnmp.hlapi.v3arch.asyncio.auth import CommunityData, UsmUserData
from pysnmp.hlapi.v3arch.asyncio.cmdgen import bulk_cmd
from pysnmp.hlapi.v3arch.asyncio.context import ContextData
from pysnmp.hlapi.v3arch.asyncio.lcd import CommandGeneratorLcdConfigurator
from pysnmp.hlapi.v3arch.asyncio.transport import AbstractTransportTarget
from pysnmp.proto import errind
from pysnmp.proto.rfc1902 import Integer32, Null
from pysnmp.proto.rfc1905 import EndOfMibView, endOfMibView
from pysnmp.smi.rfc1902 import ObjectIdentity, ObjectType

VB_PROCESSOR = varbinds.CommandGeneratorVarBinds()
LCD = CommandGeneratorLcdConfigurator()
is_end_of_mib = varbinds.is_end_of_mib


async def multi_bulk_walk_cmd(
    snmpEngine: SnmpEngine,
    authData: "CommunityData | UsmUserData",
    transportTarget: AbstractTransportTarget,
    contextData: ContextData,
    nonRepeaters: int,
    maxRepetitions: int,
    *varBinds: ObjectType,
    **options,
) -> AsyncGenerator[
    "tuple[errind.ErrorIndication | None, Integer32 | str | int | None, Integer32 | int | None, tuple[ObjectType, ...]]",
    None,
]:
    r"""Creates a generator to perform SNMP GETBULK queries with multiple OID trees.

    This function extends the bulk_walk_cmd functionality to support walking multiple
    OID trees simultaneously while respecting lexicographic mode for each varbind
    independently. Each varbind is tracked separately and will stop iteration when
    it reaches its natural boundary or goes out of scope.

    On each iteration, new SNMP GETBULK request is sent (:RFC:`1905#section-4.2.3`).
    The iterator blocks waiting for response to arrive or error to occur. Unlike
    bulk_walk_cmd which only handles a single varbind, this function can handle
    multiple varbinds in parallel, applying lexicographic mode filtering to each.

    Parameters
    ----------
    snmpEngine : :py:class:`~pysnmp.hlapi.v3arch.asyncio.SnmpEngine`
        Class instance representing SNMP engine.

    authData : :py:class:`~pysnmp.hlapi.v3arch.asyncio.CommunityData` or :py:class:`~pysnmp.hlapi.v3arch.asyncio.UsmUserData`
        Class instance representing SNMP credentials.

    transportTarget : :py:class:`~pysnmp.hlapi.v3arch.asyncio.UdpTransportTarget` or :py:class:`~pysnmp.hlapi.v3arch.asyncio.Udp6TransportTarget`
        Class instance representing transport type along with SNMP peer address.

    contextData : :py:class:`~pysnmp.hlapi.v3arch.asyncio.ContextData`
        Class instance representing SNMP ContextEngineId and ContextName values.

    nonRepeaters : int
        One MIB variable is requested in response for the first
        `nonRepeaters` MIB variables in request.

    maxRepetitions : int
        `maxRepetitions` MIB variables are requested in response for each
        of the remaining MIB variables in the request (e.g. excluding
        `nonRepeaters`). Remote SNMP engine may choose lesser value than
        requested.

    *varBinds : :py:class:`~pysnmp.smi.rfc1902.ObjectType`
        One or more class instances representing MIB variables to place
        into SNMP request. Each varbind represents a separate OID tree to walk.

    Other Parameters
    ----------------
    \*\*options :
        Request options:

            * `lookupMib` - load MIB and resolve response MIB variables at
              the cost of slightly reduced performance. Default is `True`.
            * `lexicographicMode` - walk SNMP agent's MIB till the end (if `True`),
              otherwise (if `False`) stop iteration when all response MIB
              variables leave the scope of initial MIB variables in
              `varBinds`. Default is `True`.
            * `ignoreNonIncreasingOid` - continue iteration even if response
              MIB variables (OIDs) are not greater then request MIB variables.
              Be aware that setting it to `True` may cause infinite loop between
              SNMP management and agent applications. Default is `False`.
            * `maxRows` - stop iteration once this generator instance processed
              `maxRows` of SNMP conceptual table. Default is `0` (no limit).
            * `maxCalls` - stop iteration once this generator instance processed
              `maxCalls` responses. Default is 0 (no limit).

    Yields
    ------
    errorIndication : str
        True value indicates SNMP engine error.
    errorStatus : str
        True value indicates SNMP PDU error.
    errorIndex : int
        Non-zero value refers to varBinds[errorIndex-1]
    varBinds : tuple
        A sequence of :py:class:`~pysnmp.smi.rfc1902.ObjectType` class
        instances representing MIB variables returned in SNMP response.
        Contains all valid OIDs from the current GETBULK response batch.

    Raises
    ------
    PySnmpError
        Or its derivative indicating that an error occurred while
        performing SNMP operation.

    Notes
    -----
    Key Behavioral Differences from bulk_walk_cmd:

     - Supports multiple varbinds simultaneously: the generator can walk multiple
      OID subtrees in parallel within a single SNMP session.
     - Each varbind is independently tracked: completion, last OID, and
      lexicographic boundaries are maintained per varbind.
     - lexicographicMode is applied per-varbind: a varbind stops only when its
      own scope is exhausted if lexicographicMode=False. Other varbinds continue.
     - Can optionally ignore non-increasing OIDs: if ignoreNonIncreasingOid=True,
      the generator continues even when the agent returns OIDs that are not
      greater than previous ones.
     - Returns all valid responses from each GETBULK call in a single yield: all
      active varbinds' results are grouped together in the same batch.
     - Respects maxRows and maxCalls limits across all varbinds combined.
     - Handles timeouts gracefully: the generator continues unless the error
      is non-recoverable.

    Examples
    --------
    >>> from pysnmp.hlapi.v3arch.asyncio import *
    >>> objects = await multi_bulk_walk_cmd(
    ...     SnmpEngine(),
    ...     CommunityData('public'),
    ...     await UdpTransportTarget.create(('demo.pysnmp.com', 161)),
    ...     ContextData(),
    ...     0, 25,
    ...     ObjectType(ObjectIdentity('SNMPv2-MIB', 'sysDescr'))
    ... )
    >>> g = [item async for item in objects]
    >>> next(g)
    (None, 0, 0, [ObjectType(ObjectIdentity(ObjectName('1.3.6.1.2.1.1.1.0')), DisplayString('SunOS zeus.pysnmp.com 4.1.3_U1 1 sun4m'))])
    >>> g.send( [ ObjectType(ObjectIdentity('IF-MIB', 'ifInOctets')) ] )
    (None, 0, 0, [(ObjectName('1.3.6.1.2.1.2.2.1.10.1'), Counter32(284817787))])
    """
    lexicographicMode = options.get("lexicographicMode", True)
    ignoreNonIncreasingOid = options.get("ignoreNonIncreasingOid", False)
    maxRows = options.get("maxRows", 0)
    maxCalls = options.get("maxCalls", 0)

    initialVars = [x[0] for x in VB_PROCESSOR.make_varbinds(snmpEngine.cache, varBinds)]
    num_varbinds = len(initialVars)

    # Track state for each varbind independently
    completed = [False] * num_varbinds

    # Track last seen OID per varbind (used for next bulk_cmd request)
    last_oids = [
        vb[0] if isinstance(vb[0], ObjectIdentity) else ObjectIdentity(vb[0])
        for vb in varBinds
    ]

    totalRows = 0
    totalCalls = 0

    while True:

        # Used to keep valid varbinds to yield.
        valid_results = []
        if varBinds:
            if maxRows and totalRows < maxRows:
                maxRepetitions = min(maxRepetitions, maxRows - totalRows)

            # Build request varbinds from currently active (non-completed) varbinds
            active_indices = [i for i in range(num_varbinds) if not completed[i]]

            if not active_indices:
                return

            # Create request varbinds using last known OIDs for active varbinds
            request_varbinds = [
                ObjectType(
                    (
                        last_oids[i]
                        if isinstance(last_oids[i], ObjectIdentity)
                        else ObjectIdentity(last_oids[i])
                    ),
                    Null(""),
                )
                for i in active_indices
            ]

            errorIndication, errorStatus, errorIndex, varBindTable = await bulk_cmd(
                snmpEngine,
                authData,
                transportTarget,
                contextData,
                nonRepeaters,
                maxRepetitions,
                *request_varbinds,
                **dict(lookupMib=options.get("lookupMib", True)),
            )

            if (
                ignoreNonIncreasingOid
                and errorIndication
                and isinstance(errorIndication, errind.OidNotIncreasing)
            ):
                errorIndication = None

            if errorIndication:
                yield (
                    errorIndication,
                    errorStatus,
                    errorIndex,
                    varBindTable and tuple(varBindTable) or (),
                )
                if errorIndication != errind.requestTimedOut:
                    return
            elif errorStatus:
                # SNMP PDU errors from agent
                if errorStatus == 2:
                    # Hide SNMPv1 noSuchName error which leaks in here
                    # from SNMPv1 Agent through internal pysnmp proxy
                    errorStatus = 0
                    errorIndex = 0

                yield (
                    errorIndication,
                    errorStatus,
                    errorIndex,
                    tuple(ObjectType(last_oids[i], Null("")) for i in active_indices),
                )
                return
            else:
                if not varBindTable:
                    return

                num_active = len(active_indices)
                stopFlag = True

                for idx, response_vb in enumerate(varBindTable):
                    active_vb_idx = idx % num_active
                    original_idx = active_indices[active_vb_idx]
                    name, val = response_vb

                    # Check if beyond initial scope (when lexicographicMode=False)
                    foundEnding = isinstance(val, (Null, EndOfMibView))
                    foundBeyond = not lexicographicMode and not initialVars[
                        original_idx
                    ].isPrefixOf(name)

                    is_end_of_mib_val = val is endOfMibView

                    if foundEnding or foundBeyond or is_end_of_mib_val:
                        completed[original_idx] = True
                        continue

                    # Valid response - add to results
                    valid_results.append(response_vb)
                    last_oids[original_idx] = name
                    stopFlag = False

                totalRows += len(valid_results)
                totalCalls += 1

                # If stopFlag is True, all varbinds have completed
                if stopFlag:
                    # Check if we have any final results to yield
                    if valid_results:
                        yield (
                            errorIndication,
                            errorStatus,
                            errorIndex,
                            tuple(valid_results),
                        )
                    return

                # If no valid results, stop walking
                if not valid_results:
                    return

                if maxRows and totalRows > maxRows:
                    excess = totalRows - maxRows
                    keep_count = len(valid_results) - excess

                    if keep_count > 0:
                        valid_results = valid_results[:keep_count]
                        totalRows = maxRows
                    else:
                        # This entire batch exceeds the limit
                        return

        else:
            errorIndication = None
            errorStatus = None
            errorIndex = None
            varBinds = ()

        # Yield all collected valid varBinds for this batch
        initialVarBinds: "tuple[ObjectType, ...]|None" = (
            yield errorIndication,
            errorStatus,
            errorIndex,
            tuple(valid_results),
        )

        if initialVarBinds:
            num_new = len(initialVarBinds)

            new_initial_vars = [
                x[0]
                for x in VB_PROCESSOR.make_varbinds(snmpEngine.cache, initialVarBinds)
            ]

            initialVars = new_initial_vars
            num_varbinds = num_new
            completed = [False] * num_varbinds
            last_oids = [vb[0] for vb in initialVarBinds]

        if maxRows and totalRows >= maxRows:
            return

        if maxCalls and totalCalls >= maxCalls:
            return

        if all(completed):
            return
