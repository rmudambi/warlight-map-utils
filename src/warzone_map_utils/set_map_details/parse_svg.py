from lxml import etree

from warzone_map_utils.constants import svg, types
from warzone_map_utils.set_map_details import utilities


def get_set_map_details_commands(map_path: str) -> list[types.Command]:
    layers = utilities.get_layers(map_path)

    commands = (
        get_set_territory_name_commands(layers[svg.TERRITORIES_LAYER])
        + get_add_bonus_commands(layers[svg.BONUS_LINKS_LAYER], layers[svg.METADATA_LAYER])
        + get_add_territory_to_bonus_commands(layers[svg.METADATA_LAYER])
        + get_add_distribution_mode_commands(layers[svg.METADATA_LAYER])
        + get_add_territory_to_distribution_commands(layers[svg.METADATA_LAYER])
    )
    return commands


def get_set_territory_name_commands(territory_layer_node: etree.Element) -> list[types.Command]:
    territory_nodes = [
        node for node in territory_layer_node.xpath(f"./{svg.PATH_TAG}", namespaces=svg.NAMESPACES)
        if svg.TERRITORY_IDENTIFIER in node.get(svg.ID_ATTRIBUTE)
    ]

    def get_set_territory_name_command(territory_node: etree.Element) -> types.Command:
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
        bonus_link_layer_node: etree.Element, metadata_layer_node: etree.Element
) -> list[types.Command]:
    bonus_link_nodes = {
        node.get(svg.ID_ATTRIBUTE):
        node for node in bonus_link_layer_node.xpath(f"./{svg.PATH_TAG}", namespaces=svg.NAMESPACES)
        if svg.BONUS_LINK_IDENTIFIER in node.get(svg.ID_ATTRIBUTE)
    }
    bonus_layer_nodes = utilities.get_metadata_type_layers(metadata_layer_node, svg.BONUSES_LAYER)

    def get_add_bonus_command(node: etree.Element) -> types.Command:
        bonus_name, bonus_value = utilities.parse_bonus_layer_label(node)

        bonus_link_node = bonus_link_nodes.get(utilities.get_bonus_link_id(bonus_name))
        if bonus_link_node is not None:
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


def get_add_territory_to_bonus_commands(metadata_layer_node: etree.Element) -> list[types.Command]:
    bonus_layer_nodes = utilities.get_metadata_type_layers(metadata_layer_node, svg.BONUSES_LAYER)

    def get_add_territory_to_bonus_command(
            territory_node: etree.Element, bonus_node: etree.Element
    ) -> types.Command:
        territory_id = utilities.get_territory_id_from_clone(territory_node)
        bonus_name, _ = utilities.parse_bonus_layer_label(bonus_node)

        command = {
            'command': 'addTerritoryToBonus',
            'id': territory_id,
            'bonusName': bonus_name
        }
        return command

    commands = [
        get_add_territory_to_bonus_command(territory_node, bonus_node)
        for bonus_node in bonus_layer_nodes
        for territory_node in bonus_node.findall(f"./{svg.CLONE_TAG}", svg.NAMESPACES)
    ]
    return commands


def get_add_distribution_mode_commands(metadata_layer_node: etree.Element) -> list[types.Command]:
    distribution_mode_layer_nodes = utilities.get_metadata_type_layers(
        metadata_layer_node, svg.DISTRIBUTION_MODES_LAYER, is_recursive=False
    )

    def get_add_distribution_mode_command(distribution_mode_node: etree.Element) -> types.Command:
        distribution_mode_name = distribution_mode_node.get(utilities.get_uri(svg.LABEL_ATTRIBUTE))
        # todo implement adding scenario distributions modes
        #  determine if scenario distribution mode
        #  get scenario names

        command = {
            'command': 'addDistributionMode',
            'name': distribution_mode_name,
        }
        return command

    commands = [get_add_distribution_mode_command(node) for node in distribution_mode_layer_nodes]
    return commands


def get_add_territory_to_distribution_commands(
        metadata_layer_node: etree.Element
) -> list[types.Command]:
    distribution_mode_layer_nodes = utilities.get_metadata_type_layers(
        metadata_layer_node, svg.DISTRIBUTION_MODES_LAYER, is_recursive=False
    )

    def get_add_territory_to_distribution_command(
            territory_node: etree.Element, distribution_mode_node: etree.Element
    ) -> types.Command:
        territory_id = utilities.get_territory_id_from_clone(territory_node)
        distribution_mode_name = distribution_mode_node.get(utilities.get_uri(svg.LABEL_ATTRIBUTE))
        # todo implement adding scenario distributions modes
        #  determine if scenario distribution mode
        #  get scenario names

        command = {
            'command': 'addTerritoryToDistribution',
            'id': territory_id,
            'distributionName': distribution_mode_name
        }
        return command

    commands = [
        get_add_territory_to_distribution_command(territory_node, distribution_mode_node)
        for distribution_mode_node in distribution_mode_layer_nodes
        for territory_node in distribution_mode_node.xpath(
            f"./{svg.CLONE_TAG}", namespaces=svg.NAMESPACES
        )
    ]
    return commands
