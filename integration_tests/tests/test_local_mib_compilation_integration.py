import json
import logging
from importlib.metadata import version
from pathlib import Path

import pytest
from packaging.version import Version
from pyasn1.error import PyAsn1Error
from pysnmp.proto import rfc1902
from pysnmp.smi import view
from pysnmp.smi.rfc1902 import ObjectIdentity

from integration_tests.utils import mib_compilation
from integration_tests.utils.mibserver import (
    LOCAL_MIB_INDEX_ROWS,
    MIBSERVER_FIXTURES_DIR,
    get_mibserver_url,
    prepare_local_mib_environment,
    restart_mibserver,
    run_mib_python,
)
from integration_tests.utils.splunk_test_utils import (
    _wait_for_mib_refresh_index,
    get_mibserver_logs_compose,
    get_mibserver_logs_microk8s,
)

logger = logging.getLogger(__name__)

CUSTOM_MIB_NAME = "SC4SNMP-TEST-MIB"
VALID_MODULES = (
    "SC4SNMP-TEST-EXT-MIB",
    CUSTOM_MIB_NAME,
    "SC4SNMP-TEST-TC",
    "SC4SNMP-TEST-V1-MIB",
)
INVALID_SYNTAX_MODULES = (
    "SC4SNMP-TEST-BROKEN-MIB",
    "SC4SNMP-TEST-BAD-MODULE-NAME-MIB",
    "SC4SNMP-TEST-BAD-DESCRIPTOR-MIB",
    "SC4SNMP-TEST-LEADING-UNDERSCORE-MIB",
    "SC4SNMP-TEST-BAD-ENUM-MIB",
)
INVALID_MODULES = (*INVALID_SYNTAX_MODULES, "SC4SNMP-TEST-MISSING-MIB")
LEGACY_ENUM_MODULES = (
    "SC4SNMP-TEST-LEGACY-ENUM-MIB",
    "SC4SNMP-TEST-LEGACY-ATTRIBUTE-MIB",
    "SC4SNMP-TEST-LEGACY-OBJECT-MIB",
)
EXPECTED_ROWS = LOCAL_MIB_INDEX_ROWS


class LegacyEnumNameAccepted(AssertionError):
    """The compiler accepted an enum label that violates SMI naming rules."""


def _run_compilation_check(deployment, expression, *, mibserver=False):
    script = Path(mib_compilation.__file__).read_text()
    script += f"\nprint(json.dumps({expression}))\n"
    return json.loads(run_mib_python(deployment, script, mibserver=mibserver))


@pytest.fixture(scope="module")
def local_mib_environment(request):
    deployment = request.config.getoption("sc4snmp_deployment")
    return deployment, prepare_local_mib_environment(deployment)


@pytest.fixture(scope="module")
def compilation_report(local_mib_environment):
    deployment, _ = local_mib_environment
    base_url = get_mibserver_url(deployment)
    sources = {
        path.name: path.read_text()
        for vendor in ("TESTVENDOR", "INVALIDVENDOR", "LEGACYVENDOR")
        for path in (MIBSERVER_FIXTURES_DIR / vendor).iterdir()
    }
    report = _run_compilation_check(
        deployment,
        f"compile_served_mibs({base_url!r}, "
        f"{sources!r}, {VALID_MODULES!r}, {INVALID_MODULES!r}, {LEGACY_ENUM_MODULES!r})",
    )
    for package in ("pysmi", "pysnmp"):
        assert report["versions"][package] == version(
            package
        ), f"Deployed {package} differs from the repository test environment"
    return report


@pytest.fixture(scope="module")
def compiled_mibs(compilation_report, tmp_path_factory):
    output = tmp_path_factory.mktemp("compiled-local-mibs")
    for name, source in compilation_report["artifacts"].items():
        (output / name).write_text(source)
    mib_builder = mib_compilation.fresh_mib_builder(output)
    mib_builder.load_modules(*VALID_MODULES)
    return mib_builder, compilation_report["failures"]


def _symbol(compiled_mibs, name, module=CUSTOM_MIB_NAME):
    mib_builder, _ = compiled_mibs
    return mib_builder.import_symbols(module, name)[0]


@pytest.mark.part9
class TestLocalMibs:
    def test_local_mibs_remain_available_after_mibserver_restart(
        self, local_mib_environment
    ):
        deployment, original_index = local_mib_environment
        identity_script = "import socket\nprint(socket.gethostname())\n"
        original_container = (
            run_mib_python(deployment, identity_script, mibserver=True)
            if deployment == "docker-compose"
            else None
        )
        restart_mibserver(deployment)
        restarted_index = _wait_for_mib_refresh_index(deployment)
        assert sorted(restarted_index.splitlines()) == sorted(
            original_index.splitlines()
        )
        if original_container is not None:
            assert (
                run_mib_python(deployment, identity_script, mibserver=True)
                == original_container
            ), "Adding local MIBs must preserve the Compose container"

    def test_local_mib_loaded_without_permission_error(self, local_mib_environment):
        deployment, index = local_mib_environment
        logs = (
            get_mibserver_logs_microk8s()
            if deployment == "microk8s"
            else get_mibserver_logs_compose()
        )
        logger.info(f"mibserver index.csv snippet: {index[:500]}")
        assert EXPECTED_ROWS <= set(index.splitlines())
        for marker in ("Permission denied", "Errno 13"):
            assert marker not in logs, f"Local MIB compilation reported {marker!r}"

    def test_mibserver_generates_loadable_python_and_json(
        self, local_mib_environment, tmp_path
    ):
        deployment, _ = local_mib_environment
        report = _run_compilation_check(
            deployment,
            f"check_mibserver_outputs({VALID_MODULES!r}, {INVALID_MODULES!r})",
            mibserver=True,
        )
        for variant in ("notexts", "texts"):
            output = tmp_path / variant
            output.mkdir()
            for name, source in report[variant].items():
                (output / name).write_text(source)
            mib_builder = mib_compilation.fresh_mib_builder(output)
            mib_builder.load_modules(*VALID_MODULES)
            assert set(VALID_MODULES) <= mib_builder.mibSymbols.keys()
        objects = report["json"][CUSTOM_MIB_NAME]
        assert objects["sc4snmpTest"]["oid"] == "1.3.6.1.4.1.99999"
        assert objects["sc4snmpTestNotification"]["class"] == "notificationtype"

    @pytest.mark.parametrize("module", VALID_MODULES)
    def test_consumer_compiles_and_loads_each_local_module(self, compiled_mibs, module):
        mib_builder, _ = compiled_mibs
        assert module in mib_builder.mibSymbols

    @pytest.mark.parametrize(
        "name, suffix",
        [
            ("sc4snmpTestObject", (1,)),
            ("sc4snmpTestIdentity", (100,)),
            ("sc4snmp-test-hyphen", (101,)),
            ("sc4snmpTestValue", (20, 1, 3)),
            ("sc4snmpTestNotification", (0, 1)),
        ],
    )
    def test_symbolic_and_numeric_oid_resolution(self, compiled_mibs, name, suffix):
        mib_builder, _ = compiled_mibs
        mib_view = view.MibViewController(mib_builder)
        expected = (1, 3, 6, 1, 4, 1, 99999) + suffix
        symbolic = ObjectIdentity(CUSTOM_MIB_NAME, name).resolve_with_mib(mib_view)
        numeric = ObjectIdentity(expected).resolve_with_mib(mib_view)
        assert tuple(symbolic.get_oid()) == expected
        assert numeric.get_mib_symbol()[:2] == (CUSTOM_MIB_NAME, name)

    @pytest.mark.parametrize(
        "name, expected_type, value",
        [
            ("sc4snmpTestCounter", rfc1902.Counter32, 2**32 - 1),
            ("sc4snmpTestLargeCounter", rfc1902.Counter64, 2**64 - 1),
            ("sc4snmpTestGauge", rfc1902.Gauge32, 2**32 - 1),
            ("sc4snmpTestTicks", rfc1902.TimeTicks, 12345),
            ("sc4snmpTestUnsigned", rfc1902.Unsigned32, 100),
            ("sc4snmpTestOid", rfc1902.ObjectIdentifier, (1, 3, 6, 1)),
            ("sc4snmpTestAddress", rfc1902.IpAddress, bytes((192, 0, 2, 1))),
        ],
    )
    def test_scalar_syntax_and_values(self, compiled_mibs, name, expected_type, value):
        syntax = _symbol(compiled_mibs, name).getSyntax()
        assert syntax.tagSet == expected_type.tagSet
        assert syntax.clone(value).isValue

    @pytest.mark.parametrize("value", [-10, -1, 1, 10])
    def test_imported_integer_ranges(self, compiled_mibs, value):
        assert (
            int(_symbol(compiled_mibs, "sc4snmpTestLevel").getSyntax().clone(value))
            == value
        )

    @pytest.mark.parametrize(
        "name, value",
        [
            ("sc4snmpTestLevel", -11),
            ("sc4snmpTestLevel", 0),
            ("sc4snmpTestLevel", 11),
            ("sc4snmpTestObject", ""),
            ("sc4snmpTestObject", "x" * 33),
            ("sc4snmpTestUnsigned", -1),
            ("sc4snmpTestUnsigned", 101),
            ("sc4snmpTestCounter", 2**32),
            ("sc4snmpTestLargeCounter", 2**64),
            ("sc4snmpTestHex", b"x"),
        ],
    )
    def test_compiled_constraints_reject_invalid_values(
        self, compiled_mibs, name, value
    ):
        with pytest.raises(PyAsn1Error):
            _symbol(compiled_mibs, name).getSyntax().clone(value)

    @pytest.mark.parametrize("value", ["x", "x" * 32])
    def test_imported_string_size_and_display_hint(self, compiled_mibs, value):
        syntax = _symbol(compiled_mibs, "sc4snmpTestObject").getSyntax()
        assert syntax.clone(value).asOctets() == value.encode()
        assert syntax.displayHint == "32a"

    @pytest.mark.parametrize(
        "label, value",
        [
            ("down", 0),
            ("up", 1),
            ("ready-state", 5),
        ],
    )
    def test_valid_enum_labels(self, compiled_mibs, label, value):
        syntax = _symbol(compiled_mibs, "sc4snmpTestState").getSyntax()
        assert int(syntax.clone(label)) == value
        assert syntax.clone(value).prettyPrint() == label

    @pytest.mark.xfail(
        Version(version("pysmi")) < Version("2.0.0"),
        reason=(
            "Known failure: PySMI before 2.0.0 accepts invalid underscore enum names "
            "https://github.com/lextudio/pysnmp/issues/257"
        ),
        strict=True,
        raises=LegacyEnumNameAccepted,
    )
    @pytest.mark.parametrize("module", LEGACY_ENUM_MODULES)
    def test_consumer_rejects_underscore_enum_names(self, compilation_report, module):
        result = compilation_report["known_failures"][module]
        status = result["statuses"][module]
        assert status["status"] in {"compiled", "failed"}, status
        if status["status"] == "compiled":
            assert result["has_artifact"], "Compilation reported success without output"
            raise LegacyEnumNameAccepted(
                f"{module} accepted an invalid underscore enum"
            )
        assert status["error_type"] in {"PySmiLexerError", "PySmiParserError"}
        assert not result["has_artifact"]

    def test_bits_positions_and_defaults(self, compiled_mibs):
        syntax = _symbol(compiled_mibs, "sc4snmpTestBits").getSyntax()
        assert syntax.asOctets() == bytes((128, 128))
        assert syntax.clone(("fourth", "ninth")).asOctets() == bytes((16, 128))

    def test_defaults_and_descriptive_metadata(self, compiled_mibs):
        assert (
            _symbol(compiled_mibs, "sc4snmpTestObject").getSyntax().asOctets()
            == b"ready"
        )
        assert int(_symbol(compiled_mibs, "sc4snmpTestState").getSyntax()) == 1
        assert _symbol(
            compiled_mibs, "sc4snmpTestHex"
        ).getSyntax().asOctets() == bytes.fromhex("abcd")
        assert _symbol(
            compiled_mibs, "sc4snmpTestBinary"
        ).getSyntax().asOctets() == bytes((170,))
        assert tuple(_symbol(compiled_mibs, "sc4snmpTestOid").getSyntax()) == (
            1,
            3,
            6,
            1,
            4,
            1,
            99999,
            100,
        )
        assert _symbol(compiled_mibs, "sc4snmpTestLevel").getUnits() == "percent"
        assert (
            "description parsing"
            in _symbol(compiled_mibs, "sc4snmpTest").getDescription()
        )

    def test_composite_and_implied_table_index(self, compiled_mibs):
        row = _symbol(compiled_mibs, "sc4snmpTestEntry")
        assert row.getIndexNames() == (
            (0, CUSTOM_MIB_NAME, "sc4snmpTestIndex"),
            (1, CUSTOM_MIB_NAME, "sc4snmpTestLabel"),
        )
        assert row.getInstIdFromIndices(7, "ab") == (7, 97, 98)
        index, label = row.getIndicesFromInstId((7, 97, 98))
        assert int(index) == 7
        assert label.asOctets() == b"ab"

    def test_cross_module_table_augmentation(self, compiled_mibs):
        base = _symbol(compiled_mibs, "sc4snmpTestEntry")
        augmented = _symbol(
            compiled_mibs, "sc4snmpTestExtEntry", "SC4SNMP-TEST-EXT-MIB"
        )
        assert augmented.getIndexNames() == base.getIndexNames()
        assert augmented.getInstIdFromIndices(7, "ab") == (7, 97, 98)
        assert ("SC4SNMP-TEST-EXT-MIB", "sc4snmpTestExtEntry") in base.augmentingRows

    def test_notification_and_conformance_references(self, compiled_mibs):
        notification = _symbol(compiled_mibs, "sc4snmpTestNotification")
        assert notification.getObjects() == (
            (CUSTOM_MIB_NAME, "sc4snmpTestObject"),
            (CUSTOM_MIB_NAME, "sc4snmpTestState"),
        )
        group = _symbol(compiled_mibs, "sc4snmpTestGroup")
        assert (CUSTOM_MIB_NAME, "sc4snmpTestLevel") in group.getObjects()
        group = _symbol(compiled_mibs, "sc4snmpTestNotificationGroup")
        assert group.getObjects() == ((CUSTOM_MIB_NAME, "sc4snmpTestNotification"),)
        assert _symbol(compiled_mibs, "sc4snmpTestCompliance").getName()[-1] == 32

    def test_smiv1_types_and_trap_conversion(self, compiled_mibs):
        module = "SC4SNMP-TEST-V1-MIB"
        counter = _symbol(compiled_mibs, "sc4snmpTestV1Counter", module)
        assert counter.getSyntax().tagSet == rfc1902.Counter32.tagSet
        assert counter.getMaxAccess() == "read-only"
        trap = _symbol(compiled_mibs, "sc4snmpTestV1Trap", module)
        assert trap.getName() == (1, 3, 6, 1, 4, 1, 99997, 0, 7)
        assert trap.getObjects() == (
            (module, "sc4snmpTestV1Counter"),
            (module, "sc4snmpTestV1Gauge"),
        )

    @pytest.mark.parametrize("module", INVALID_MODULES)
    def test_invalid_local_mib_is_not_indexed(self, local_mib_environment, module):
        _, index = local_mib_environment
        assert all(row.split(",")[0] != module for row in index.splitlines())

    @pytest.mark.parametrize("module", INVALID_SYNTAX_MODULES)
    def test_invalid_syntax_or_name_fails_compilation(self, compiled_mibs, module):
        _, failures = compiled_mibs
        assert failures[module][module]["status"] == "failed"
        assert failures[module][module]["error_type"] in {
            "PySmiLexerError",
            "PySmiParserError",
        }

    def test_missing_import_fails_compilation(self, compiled_mibs):
        _, failures = compiled_mibs
        assert (
            failures["SC4SNMP-TEST-MISSING-MIB"]["SC4SNMP-TEST-ABSENT-MIB"]["status"]
            == "missing"
        )
