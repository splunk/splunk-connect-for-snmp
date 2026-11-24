import json
import tempfile
import urllib.request
from importlib.metadata import version
from pathlib import Path


def fresh_mib_builder(directory):
    from pysnmp.smi import builder

    mib_builder = builder.MibBuilder()
    mib_builder.loadTexts = True
    mib_builder.set_mib_sources(
        builder.DirMibSource(str(directory)),
        builder.ZipMibSource("pysnmp.smi.mibs"),
    )
    return mib_builder


def compiling_mib_builder(output, base_url):
    from pysnmp.smi import compiler

    empty_borrower = output / "borrower"
    empty_borrower.mkdir()
    mib_builder = fresh_mib_builder(output)
    compiler.add_mib_compiler(
        mib_builder,
        destination=str(output),
        sources=[f"{base_url}/asn1/@mib@"],
        borrowers=[empty_borrower.as_uri()],
    )
    return mib_builder


def compile_mib_status(base_url, name):
    with tempfile.TemporaryDirectory(prefix="sc4snmp-mib-status-") as directory:
        output = Path(directory)
        mib_builder = compiling_mib_builder(output, base_url)
        statuses = mib_builder.get_mib_compiler().compile(name)
        return {
            "has_artifact": (output / f"{name}.py").exists(),
            "statuses": {
                module: {
                    "status": str(status),
                    "error_type": type(getattr(status, "error", None)).__name__,
                }
                for module, status in statuses.items()
            },
        }


def compile_served_mibs(
    base_url, sources, valid_modules, invalid_modules, known_failure_modules=()
):
    """Compile served sources with fresh output and an empty local borrower."""
    for name, expected_source in sources.items():
        with urllib.request.urlopen(f"{base_url}/asn1/{name}", timeout=10) as response:
            assert (
                response.read().decode() == expected_source
            ), f"Stale source for {name}"

    with tempfile.TemporaryDirectory(prefix="sc4snmp-mib-compiler-") as directory:
        output = Path(directory)
        mib_builder = compiling_mib_builder(output, base_url)
        # Loading the dependent module first requires automatic local imports.
        mib_builder.load_modules(*valid_modules)
        for name in valid_modules:
            assert (output / f"{name}.py").is_file(), f"No fresh output for {name}"
        artifacts = {path.name: path.read_text() for path in output.glob("*.py")}

    failures = {}
    for name in invalid_modules:
        result = compile_mib_status(base_url, name)
        assert not result["has_artifact"], f"Invalid MIB compiled: {name}"
        failures[name] = result["statuses"]
    return {
        "artifacts": artifacts,
        "failures": failures,
        "known_failures": {
            name: compile_mib_status(base_url, name) for name in known_failure_modules
        },
        "versions": {package: version(package) for package in ("pysmi", "pysnmp")},
    }


def check_mibserver_outputs(valid_modules, invalid_modules):
    """Read both mibdump outputs and the JSON used to build the index."""
    output = Path("/app/new_mibs/output")
    result = {}
    for variant in ("notexts", "texts"):
        for name in valid_modules:
            assert (
                output / variant / f"{name}.py"
            ).is_file(), f"Missing {variant}/{name}"
        for name in invalid_modules:
            assert not (
                output / variant / f"{name}.py"
            ).exists(), f"Invalid {variant}/{name}"
        result[variant] = {
            path.name: path.read_text() for path in (output / variant).glob("*.py")
        }
    result["json"] = {
        name: json.loads((output / "json" / f"{name}.json").read_text())
        for name in valid_modules
    }
    for name in invalid_modules:
        assert not (
            output / "json" / f"{name}.json"
        ).exists(), f"Invalid JSON for {name}"
    return result
