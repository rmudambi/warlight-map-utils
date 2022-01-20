import json
import requests
import sys
from typing import Dict, List

from warzone_map_utils.constants.types import Command
from warzone_map_utils.set_map_details import get_set_map_details_commands

SET_MAP_DETAILS_URL = 'https://www.warzone.com/API/SetMapDetails'


def set_map_details(map_id: str, auth_file_path: str, map_svg_path: str) -> None:
    authentication_details = get_authentication_details(auth_file_path)
    map_id = int(map_id)
    commands = get_set_map_details_commands(map_svg_path)
    post_map_details(map_id, authentication_details, commands)


def get_authentication_details(auth_file_path: str) -> Dict[str, str]:
    with open(auth_file_path) as auth_file:
        authentication_details = json.load(auth_file)
    return authentication_details


def post_map_details(map_id: int, auth_details: Dict[str, str], commands: List[Command]) -> None:
    json_body = (
        auth_details
        | {'mapID': map_id}
        | {'commands': commands}
    )

    response = requests.post(
        url=SET_MAP_DETAILS_URL,
        json=json_body
    )

    data = json.loads(response.text)
    print(data)


if __name__ == "__main__":
    args = sys.argv[1:]
    set_map_details(*args)
