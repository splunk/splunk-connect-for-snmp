import argparse
import os
from typing import Union
import yaml


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


def remove_variables_from_env(file_path, variables_to_remove):
    try:
        with open(file_path, 'r') as env_file:
            lines = env_file.readlines()

        with open(file_path, 'w') as env_file:
            for line in lines:
                key = line.split('=')[0].strip()
                if key not in variables_to_remove:
                    env_file.write(line)

        print("Variables removed successfully from .env file.")
    except Exception as e:
        print(f"Error: {e}")


def create_secrets(variables, path_to_compose_files, secret_name, worker_poller, traps):
    for k, v in variables.items():
        if k != "contextEngineId" and not v:
            raise ValueError(f"Value {k} is not set")

    new_secrets = []
    new_secrets_in_workers = []

    for k, v in variables.items():
        if v:
            new_secrets.append(
                {"secret_name": f"{secret_name}_{k}", "secret_config": {"environment": f"{secret_name}_{k}"}})
            new_secrets_in_workers.append(
                {"source": f"{secret_name}_{k}", "target": f"/app/secrets/snmpv3/{secret_name}/{k}"})

    # Open secrets file
    try:
        with open(os.path.join(path_to_compose_files, "docker-compose-secrets.yaml"), 'r') as file:
            secrets_file = yaml.load(file, Loader=yaml.FullLoader)
        if secrets_file["secrets"] is None:
            secrets_file["secrets"] = {}
        for new_secret in new_secrets:
            if new_secret["secret_name"] in secrets_file["secrets"]:
                print(f"Secret {secret_name} already configured. New secret not added.")
                return
            secrets_file["secrets"][new_secret["secret_name"]] = new_secret["secret_config"]
        secrets_file_ready = True
    except:
        print("Problem with editing docker-compose-secrets.yaml. Secret not added.")
        secrets_file_ready = False

    if worker_poller:
        try:
            # Open poller configuration
            with open(os.path.join(path_to_compose_files, "docker-compose-worker-poller.yaml"), 'r') as file:
                worker_poller_file = yaml.load(file, Loader=yaml.FullLoader)
            if 'secrets' not in worker_poller_file['services']['worker-poller']:
                worker_poller_file['services']['worker-poller']["secrets"] = []
            worker_poller_file['services']['worker-poller']["secrets"].extend(new_secrets_in_workers)
            worker_poller_file_ready = True
        except:
            print("Problem with editing docker-compose-worker-poller.yaml. Secret not added.")
            worker_poller_file_ready = False
    else:
        worker_poller_file_ready = True

    if traps:
        try:
            # Open traps configuration
            with open(os.path.join(path_to_compose_files, "docker-compose-traps.yaml"), 'r') as file:
                traps_file = yaml.load(file, Loader=yaml.FullLoader)
            if 'secrets' not in traps_file['services']['traps']:
                traps_file['services']['traps']["secrets"] = []
            traps_file['services']['traps']["secrets"].extend(new_secrets_in_workers)
            traps_file_ready = True
        except:
            print("Problem with editing docker-compose-traps.yaml. Secret not added.")
            traps_file_ready = False
    else:
        traps_file_ready = True

    if secrets_file_ready and worker_poller_file_ready and traps_file_ready:
        with open(os.path.join(path_to_compose_files, "docker-compose-secrets.yaml"), 'w') as file:
            yaml.dump(secrets_file, file, default_flow_style=False)
        with open(os.path.join(path_to_compose_files, ".env"), 'a') as file:
            for k, v in variables.items():
                if v:
                    file.write(f'\n{secret_name}_{k}={v}')
        if worker_poller:
            with open(os.path.join(path_to_compose_files, "docker-compose-worker-poller.yaml"), 'w') as file:
                yaml.dump(worker_poller_file, file, default_flow_style=False)
        if traps:
            with open(os.path.join(path_to_compose_files, "docker-compose-traps.yaml"), 'w') as file:
                yaml.dump(traps_file, file, default_flow_style=False)


def delete_secrets(variables, path_to_compose_files, secret_name, worker_poller, traps):
    secrets = []
    for key in variables.keys():
        secrets.append(f"{secret_name}_{key}")

    # Open secrets file
    with open(os.path.join(path_to_compose_files, "docker-compose-secrets.yaml"), 'r') as file:
        secrets_file = yaml.load(file, Loader=yaml.FullLoader)
    for secret in secrets:
        if secret in secrets_file["secrets"]:
            del secrets_file["secrets"][secret]
    with open(os.path.join(path_to_compose_files, "docker-compose-secrets.yaml"), 'w') as file:
        yaml.dump(secrets_file, file, default_flow_style=False)

    # Delete secrets from .env
    try:
        with open(os.path.join(path_to_compose_files, ".env"), 'r') as env_file:
            lines = env_file.readlines()
        with open(os.path.join(path_to_compose_files, ".env"), 'w') as env_file:
            lines_to_write = []
            for line in lines:
                key = line.split('=')[0].strip()
                if key not in secrets:
                    lines_to_write.append(line.strip())
            for i, line in enumerate(lines_to_write):
                if i < len(lines_to_write) - 1:
                    env_file.write(f"{line}\n")
                else:
                    env_file.write(line)
    except Exception as e:
        print(f"Error: {e}")

    if worker_poller:
        # Open poller configuration
        with open(os.path.join(path_to_compose_files, "docker-compose-worker-poller.yaml"), 'r') as file:
            worker_poller_file = yaml.load(file, Loader=yaml.FullLoader)
        worker_poller_file['services']['worker-poller']["secrets"] = list(
            filter(lambda el: el["source"] not in secrets,
                   worker_poller_file['services']['worker-poller']["secrets"]))
        with open(os.path.join(path_to_compose_files, "docker-compose-worker-poller.yaml"), 'w') as file:
            yaml.dump(worker_poller_file, file, default_flow_style=False)
    if traps:
        # Open traps configuration
        with open(os.path.join(path_to_compose_files, "docker-compose-traps.yaml"), 'r') as file:
            traps_file = yaml.load(file, Loader=yaml.FullLoader)
        traps_file['services']['traps']["secrets"] = list(
            filter(lambda el: el["source"] not in secrets,
                   traps_file['services']['traps']["secrets"]))
        with open(os.path.join(path_to_compose_files, "docker-compose-traps.yaml"), 'w') as file:
            yaml.dump(traps_file, file, default_flow_style=False)


def main():
    parser = argparse.ArgumentParser(description='Manage secrets in docker compose')
    parser.add_argument('--delete', default='false', help='If true, delete the secret')
    parser.add_argument('--secret_name', help='Secret name')
    parser.add_argument('--path_to_compose', help='Path to dockerfiles')
    parser.add_argument('--worker_poller', default='true', help='Add secret to worker poller')
    parser.add_argument('--traps', default='true', help='Add secret to traps')
    parser.add_argument('--userName', default='', help='SNMPV3 username')
    parser.add_argument('--privProtocol', default='', help='SNMPV3 privProtocol')
    parser.add_argument('--privKey', default='', help='SNMPV3 privKey')
    parser.add_argument('--authProtocol', default='', help='SNMPV3 authProtocol')
    parser.add_argument('--authKey', default='', help='SNMPV3 authKey')
    parser.add_argument('--contextEngineId', default='', help='SNMPV3 contextEngineId')

    args = parser.parse_args()

    delete_secret = human_bool(args.delete)
    secret_name = args.secret_name
    path_to_compose_files = args.path_to_compose
    worker_poller = human_bool(args.worker_poller)
    traps = human_bool(args.traps)
    variables = {
        "userName": args.userName,
        "privProtocol": args.privProtocol,
        "privKey": args.privKey,
        "authProtocol": args.authProtocol,
        "authKey": args.authKey,
        "contextEngineId": args.contextEngineId
    }

    if not os.path.exists(path_to_compose_files):
        print("Path to compose files doesn't exist")
        return
    if not secret_name:
        print("Secret name not specified")
        return

    if not delete_secret:
        try:
            create_secrets(variables, path_to_compose_files, secret_name, worker_poller, traps)
        except ValueError as e:
            print(e)
    else:
        delete_secrets(variables, path_to_compose_files, secret_name, worker_poller, traps)


if __name__ == "__main__":
    main()
