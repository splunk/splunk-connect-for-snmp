import argparse
import os
from typing import Union

import ruamel.yaml

DOCKER_COMPOSE = "docker-compose.yaml"


def human_bool(flag: Union[str, bool], default: bool = False) -> bool:
    if flag is None:
        return False
    if isinstance(flag, bool):
        return flag
    if flag.lower() in [
        "true",
        "1",
        "t",
        "y",
        "yes",
    ]:
        return True
    elif flag.lower() in [
        "false",
        "0",
        "f",
        "n",
        "no",
    ]:
        return False
    else:
        return default


def read_var_from_env(path_to_compose_files: str) -> dict:
    logging_keys = [
        "SPLUNK_HEC_TOKEN",
        "SPLUNK_HEC_PROTOCOL",
        "SPLUNK_HEC_HOST",
        "SPLUNK_HEC_PORT",
        "SPLUNK_LOG_INDEX",
        "SPLUNK_HEC_INSECURESSL",
    ]
    environment = dict()
    try:
        with open(path_to_compose_files + "/.env") as env_file:
            for line in env_file.readlines():
                if any(k in line for k in logging_keys):
                    line = line.removesuffix("\n")
                    split_line = line.split("=", 1)
                    environment[split_line[0]] = split_line[1]
        return environment
    except Exception as e:
        print(f"Error occurred: {e}")
        raise Exception(f"Error occurred: {e}")


def load_template(environment: dict, service_name: str) -> dict:
    yaml = ruamel.yaml.YAML()
    template = f"""
    logging:
        driver: "splunk"
        options:
            splunk-token: "{environment['SPLUNK_HEC_TOKEN']}"
            splunk-url: "{environment['SPLUNK_HEC_PROTOCOL']}://{environment['SPLUNK_HEC_HOST']}:{environment['SPLUNK_HEC_PORT']}"
            splunk-index: "{environment['SPLUNK_LOG_INDEX']}"
            splunk-insecureskipverify: "{environment['SPLUNK_HEC_INSECURESSL']}"
            splunk-sourcetype: "docker:container:splunk-connect-for-snmp-{service_name}"
    """
    template_yaml = yaml.load(template)
    return template_yaml


def create_logs(environment, path_to_compose_files):
    try:
        yaml = ruamel.yaml.YAML()
        with open(os.path.join(path_to_compose_files, DOCKER_COMPOSE)) as file:
            yaml_file = yaml.load(file)

        for service_name in yaml_file["services"].keys():
            template_yaml = load_template(environment, service_name)
            yaml_file["services"][service_name].update(template_yaml)

        with open(os.path.join(path_to_compose_files, DOCKER_COMPOSE), "w") as file:
            yaml.dump(yaml_file, file)
    except Exception as e:
        print(f"Problem with editing docker-compose.yaml. Error: {e}")


def delete_logs(path_to_compose_files):
    try:
        yaml = ruamel.yaml.YAML()
        with open(os.path.join(path_to_compose_files, DOCKER_COMPOSE)) as file:
            yaml_file = yaml.load(file)

        for service_name in yaml_file["services"].keys():
            yaml_file["services"][service_name]["logging"]["driver"] = "json-file"
            yaml_file["services"][service_name]["logging"].pop("options")

        with open(os.path.join(path_to_compose_files, DOCKER_COMPOSE), "w") as file:
            yaml.dump(yaml_file, file)
    except Exception as e:
        print(f"Problem with editing docker-compose.yaml. Error: {e}")


def main():
    parser = argparse.ArgumentParser(description="Manage logs in docker compose")
    parser.add_argument(
        "-e", "--enable_logs", action="store_true", help="Enables the logs"
    )
    parser.add_argument(
        "-p", "--path_to_compose", required=True, help="Path to dockerfiles"
    )
    parser.add_argument(
        "-d", "--disable_logs", action="store_true", help="Disables the logs"
    )

    args = parser.parse_args()

    # Assign inputs from command line to variables
    enable_logs = human_bool(args.enable_logs)
    path_to_compose_files = args.path_to_compose
    disable_logs = human_bool(args.disable_logs)

    if not os.path.exists(path_to_compose_files):
        print("Path to compose files doesn't exist")
        return

    env = read_var_from_env(path_to_compose_files)

    if enable_logs:
        try:
            create_logs(env, path_to_compose_files)
        except ValueError as e:
            print(e)
    if disable_logs:
        try:
            delete_logs(path_to_compose_files)
        except ValueError as e:
            print(e)


if __name__ == "__main__":
    main()
