import re

from lxml import etree

from warzone_map_utils.constants.svg import Inkscape, Svg, Warzone, XLink, NAMESPACES


def get_layers(map_path: str) -> dict[str, etree.Element]:
    root = etree.parse(map_path)
    layers = {
        node.get(get_uri(Inkscape.LABEL)): node
        for node in root.xpath(f"./*[@{Inkscape.LABEL}]", namespaces=NAMESPACES)
    }
    return layers


def get_metadata_type_nodes(
        metadata_layer_node: etree.Element, metadata_type: str, is_recursive: bool = True
) -> list[etree.Element]:
    slash = '//' if is_recursive else '/'
    bonus_layer_nodes = (
        metadata_layer_node.xpath(
            f"./{Svg.GROUP}[@{Inkscape.LABEL}='{metadata_type}']"
            f"{slash}{Svg.GROUP}[@{Inkscape.LABEL}]",
            namespaces=NAMESPACES
        )
    )
    return bonus_layer_nodes


def get_territory_id(territory_node: etree.Element) -> int:
    if territory_node.tag == get_uri(Svg.PATH):
        territory_id = territory_node.get(Svg.ID).replace(Warzone.TERRITORY_IDENTIFIER, '')
    elif territory_node.tag == get_uri(Svg.CLONE):
        territory_id = (
            territory_node
            .get(get_uri(XLink.HREF))
            .split(Warzone.TERRITORY_IDENTIFIER)
            [-1]
        )
    else:
        raise ValueError(f'Element {territory_node} is not a valid territory element. It must be a'
                         f' path or a clone.')
    return int(territory_id)


def get_territory_name(territory_node: etree.Element) -> str:
    title_node = territory_node.find(Svg.TITLE, NAMESPACES)
    if title_node is not None:
        territory_name = title_node.text
    else:
        territory_name = Warzone.UNNAMED_TERRITORY_NAME
    return territory_name


def parse_bonus_layer_label(node: etree.Element) -> tuple[str, int]:
    bonus_name, bonus_value = node.get(get_uri(Inkscape.LABEL)).split(': ')
    return bonus_name, int(bonus_value)


def get_uri(key: str) -> str:
    if ':' in key:
        namespace, key = key.split(':')
        key = f'{{{NAMESPACES[namespace]}}}{key}'
    return key


def get_bonus_link_id(bonus_name: str) -> str:
    return Warzone.BONUS_LINK_IDENTIFIER + re.sub(r'[^a-zA-Z0-9]+', '', bonus_name)
