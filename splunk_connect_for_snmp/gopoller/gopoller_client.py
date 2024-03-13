import requests


def main():
    post_json = {
        "userName": "",
        "authenticationProtocol": "",
        "authenticationPassphrase": "",
        "privacyProtocol": "",
        "privacyPassphrase": "",
        "authoritativeEngineID": "",
        "target": "",
        "port": 161,
        "community": "",
        "oids": ["1.3.6.1.2.1.2"],
        "ignoreNonIncreasingOid": True,
        "version": "3",
    }

    response = requests.post("http://localhost:9000/walk", json=post_json)

    try:
        print(response.json())
    except:
        print(response.status_code)


if __name__ == "__main__":
    main()
