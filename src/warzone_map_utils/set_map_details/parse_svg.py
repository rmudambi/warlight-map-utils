from typing import Dict, List
from xml.dom.minidom import parse, Document, Element

from warzone_map_utils.constants import svg, types


def get_set_map_details_commands(map_path: str) -> List[types.Command]:

    map_xml: Document = parse(str(map_path))
    root_node = map_xml.childNodes[0]
    layers: Dict[str, Element] = {
        node.getAttribute(svg.LABEL_ATTRIBUTE): node
        for node in root_node.childNodes if node.nodeName == svg.GROUP_TAG
    }

    commands = []
    commands += get_set_territory_name_commands(layers[svg.TERRITORIES_LAYER])
    return commands


def get_set_territory_name_commands(territory_layer_node: Element) -> List[types.Command]:
    territory_nodes = [
        node for node in territory_layer_node.getElementsByTagName(svg.PATH_TAG)
        if svg.TERRITORY_IDENTIFIER in node.getAttribute(svg.ID_ATTRIBUTE)
    ]

    commands = []
    for territory_node in territory_nodes:
        command = get_set_territory_name_command(territory_node)
        if command:
            commands.append(command)

    return commands


def get_set_territory_name_command(territory_node: Element) -> types.Command:
    territory_id = int(
        territory_node.getAttribute(svg.ID_ATTRIBUTE)
        .replace(svg.TERRITORY_IDENTIFIER, '')
    )

    title_nodes = territory_node.getElementsByTagName('title')

    command = {}
    if len(title_nodes) > 1:
        print(f'Territory {territory_id} has more than 1 title node')
    elif title_nodes:
        territory_name = (
            title_nodes[0]
            .childNodes[0]
            .data
        )
        command = {
            'command': 'setTerritoryName',
            'id': territory_id,
            'name': territory_name
        }
    return command
