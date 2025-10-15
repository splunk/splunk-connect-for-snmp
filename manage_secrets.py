import json
import os
import shutil
import sys

BASE_DIR = "/app/secrets/snmpv3"
SECRETS_JSON = "/app/secrets/tmp/secrets.json"


def create_secret_files(secrets):
    file_map = {
        "username": "userName",
        "authkey": "authKey",
        "authprotocol": "authProtocol",
        "privkey": "privKey",
        "privprotocol": "privProtocol",
        "contextengineid": "contextEngineId",
    }
    secret_names = []
    for secretname, details in secrets.items():
        secret_dir = os.path.join(BASE_DIR, secretname)
        skip = False
        for key, value in details.items():
            if key.lower() != "contextengineid" and not value:
                print(f"Skipping {secretname} as value {key} is not set.")
                skip = True
        if not skip:
            os.makedirs(secret_dir, exist_ok=True)
            for key, value in details.items():
                file_name = file_map.get(key.lower())
                if file_name:
                    file_path = os.path.join(secret_dir, file_name)
                    with open(file_path, "w") as f:
                        f.write(str(value))
            print(f"Created secret: {secretname}")
            secret_names.append(secretname)
    return secret_names


def delete_secret_files(secret_names):
    new_secret_names = set(secret_names)
    existing_secret_dirs = set(os.listdir(BASE_DIR))

    # Remove directories of the secrets that are not provided
    for secret_dir in existing_secret_dirs - new_secret_names:
        shutil.rmtree(os.path.join(BASE_DIR, secret_dir))
        print(f"Deleted secret: {secret_dir}")


if __name__ == "__main__":
    if not os.path.isfile(SECRETS_JSON):
        print("Path to secret Json files doesn't exist")
    else:
        with open(SECRETS_JSON) as f:
            secrets = json.load(f)

        secret_names = create_secret_files(secrets)
        delete_secret_files(secret_names)