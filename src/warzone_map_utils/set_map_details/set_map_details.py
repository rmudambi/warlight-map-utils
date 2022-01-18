import json
import requests
import sys
from typing import Dict, List, Union

SET_MAP_DETAILS_URL = 'https://www.warzone.com/API/SetMapDetails'

Command = Dict[str, Union[str, int]]


def get_set_territory_name_command(territory_id: int, name: str) -> Command:
    return {
        'command': 'setTerritoryName',
        'id': territory_id,
        'name': name
    }


def set_map_details(map_id: str, auth_details: Dict[str, str]) -> None:
    json_body = (
        auth_details
        | {'mapID': map_id}
        | {'commands': get_commands()}
    )

    response = requests.post(
        url=SET_MAP_DETAILS_URL,
        json=json_body
    )

    data = json.loads(response.text)
    print(data)


def get_commands() -> List[Command]:
    # todo
    return [get_set_territory_name_command(1156, 'Paln')]


if __name__ == "__main__":
    args = sys.argv[1:]
    wz_map_id = args[0]
    with open(args[1]) as auth_file:
        authentication_details = json.load(auth_file)
    set_map_details(wz_map_id, authentication_details)
