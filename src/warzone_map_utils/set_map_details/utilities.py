import xml.etree.ElementTree as ET

from warzone_map_utils.constants import svg


def get_layers(map_path):
    map_xml = ET.parse(map_path)
    root = map_xml.getroot()
    layers: dict[str, ET.Element] = {
        node.get(get_uri(svg.LABEL_ATTRIBUTE)): node
        for node in root.findall(f"./*[@{svg.LABEL_ATTRIBUTE}]", svg.NAMESPACES)
    }
    return layers


def get_uri(key: str) -> str:
    if ':' in key:
        namespace, key = key.split(':')
        key = f'{{{svg.NAMESPACES[namespace]}}}{key}'
    return key


def get_bonus_link_id(bonus_name: str) -> str:
    return svg.BONUS_LINK_IDENTIFIER + ''.join(filter(str.isalnum, bonus_name))

