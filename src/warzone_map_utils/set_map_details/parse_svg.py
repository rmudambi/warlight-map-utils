from typing import Dict, List
import xml.etree.ElementTree as ET

from warzone_map_utils.constants import svg, types


def get_uri(key: str) -> str:
    if ':' in key:
        namespace, key = key.split(':')
        key = f'{{{svg.NAMESPACES[namespace]}}}{key}'
    return key


def get_set_map_details_commands(map_path: str) -> List[types.Command]:

    map_xml = ET.parse(map_path)
    root = map_xml.getroot()
    layers: Dict[str, ET.Element] = {
        node.get(get_uri(svg.LABEL_ATTRIBUTE)): node
        for node in root.findall(f"./*[@{svg.LABEL_ATTRIBUTE}]", svg.NAMESPACES)
    }

    commands = []
    commands += get_set_territory_name_commands(layers[svg.TERRITORIES_LAYER])
    return commands


def get_set_territory_name_commands(territory_layer_node: ET.Element) -> List[types.Command]:
    territory_nodes = [
        node for node in territory_layer_node.findall(f"./{svg.PATH_TAG}", svg.NAMESPACES)
        if svg.TERRITORY_IDENTIFIER in node.get('id')
    ]

    commands = [
        get_set_territory_name_command(territory_node) for territory_node in territory_nodes
        if territory_node.find(svg.TITLE_TAG, svg.NAMESPACES) is not None
    ]
    return commands


def get_set_territory_name_command(territory_node: ET.Element) -> types.Command:
    territory_id = int(
        territory_node.get(svg.ID_ATTRIBUTE)
        .replace(svg.TERRITORY_IDENTIFIER, '')
    )

    title_node = territory_node.find(svg.TITLE_TAG, svg.NAMESPACES)
    territory_name = title_node.text
    command = {
        'command': 'setTerritoryName',
        'id': territory_id,
        'name': territory_name
    }
    return command
