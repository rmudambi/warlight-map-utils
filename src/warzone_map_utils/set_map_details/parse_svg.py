from typing import Dict, List
import xml.etree.ElementTree as ET

from warzone_map_utils.constants import svg, types
from warzone_map_utils.set_map_details import utilities


def get_set_map_details_commands(map_path: str) -> List[types.Command]:
    layers = get_layers(map_path)

    commands = (
        get_set_territory_name_commands(layers[svg.TERRITORIES_LAYER])
        + get_add_bonus_commands(layers[svg.BONUS_LINKS_LAYER], layers[svg.METADATA_LAYER])
    )
    return commands


def get_layers(map_path):
    map_xml = ET.parse(map_path)
    root = map_xml.getroot()
    layers: Dict[str, ET.Element] = {
        node.get(utilities.get_uri(svg.LABEL_ATTRIBUTE)): node
        for node in root.findall(f"./*[@{svg.LABEL_ATTRIBUTE}]", svg.NAMESPACES)
    }
    return layers


def get_set_territory_name_commands(territory_layer_node: ET.Element) -> List[types.Command]:
    territory_nodes = [
        node for node in territory_layer_node.findall(f"./{svg.PATH_TAG}", svg.NAMESPACES)
        if svg.TERRITORY_IDENTIFIER in node.get(svg.ID_ATTRIBUTE)
    ]

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

    commands = [
        get_set_territory_name_command(territory_node) for territory_node in territory_nodes
        if territory_node.find(svg.TITLE_TAG, svg.NAMESPACES) is not None
    ]
    return commands


def get_add_bonus_commands(
        bonus_link_layer_node: ET.Element, metadata_layer_node: ET.Element
) -> List[types.Command]:
    bonus_link_nodes = {
        node.get(svg.ID_ATTRIBUTE):
        node for node in bonus_link_layer_node.findall(f"./{svg.PATH_TAG}", svg.NAMESPACES)
        if svg.BONUS_LINK_IDENTIFIER in node.get(svg.ID_ATTRIBUTE)
    }
    bonus_layer_nodes = (
        metadata_layer_node.findall(
            f"./{svg.GROUP_TAG}[@{svg.LABEL_ATTRIBUTE}='{svg.BONUSES_LAYER}']"
            f"//{svg.GROUP_TAG}[@{svg.LABEL_ATTRIBUTE}]", svg.NAMESPACES)
    )

    def get_add_bonus_command(node: ET.Element) -> types.Command:
        bonus_name, bonus_value = node.get(utilities.get_uri(svg.LABEL_ATTRIBUTE)).split(': ')

        if bonus_link_node := bonus_link_nodes.get(utilities.get_bonus_link_id(bonus_name)):
            node_style = {
                key: value for key, value in (
                    field.split(':') for field in bonus_link_node.get('style').split(';')
                )
            }
            bonus_color = node_style['fill'].upper()
        else:
            bonus_color = '#000000'

        command = {
            'command': 'addBonus',
            'name': bonus_name,
            'armies': bonus_value,
            'color': bonus_color
        }
        return command

    commands = [get_add_bonus_command(node) for node in bonus_layer_nodes]
    return commands
