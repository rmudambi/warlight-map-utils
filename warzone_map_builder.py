#!/usr/bin/env python

from argparse import ArgumentParser
import json
import re
import requests
from typing import Dict, List, Tuple, Union

from inkex import Boolean, EffectExtension, Group, PathElement, Use
from inkex.utils import debug


Command = Dict[str, Union[str, int]]

SET_MAP_DETAILS_URL = 'https://www.warzone.com/API/SetMapDetails'
NAMESPACES = {
    'svg': 'http://www.w3.org/2000/svg',
    'inkscape': 'http://www.inkscape.org/namespaces/inkscape',
    'xlink': 'http://www.w3.org/1999/xlink',
}


def get_uri(key: str) -> str:
    if ':' in key:
        namespace, key = key.split(':')
        key = f'{{{NAMESPACES[namespace]}}}{key}'
    return key


class Svg:
    ID = 'id'
    GROUP = 'svg:g'
    PATH = 'svg:path'
    TITLE = 'svg:title'
    CLONE = 'svg:use'
    ELLIPSE = 'svg:ellipse'

    STYLE = 'style'
    FILL = 'fill'


class Inkscape:
    LABEL = 'inkscape:label'
    CONNECTION_START = 'inkscape:connection-start'
    CONNECTION_END = 'inkscape:connection-end'


class XLink:
    HREF = 'xlink:href'


class MapLayers:
    BONUS_LINKS = 'WZ:BonusLinks'
    TERRITORIES = 'WZ:Territories'
    BACKGROUND = 'Background'

    METADATA = 'WZ:Metadata'
    BONUSES = 'WZ:Bonuses'
    DISTRIBUTION_MODES = 'WZ:DistributionModes'
    CONNECTIONS = 'WZ:Connections'
    NORMAL_CONNECTIONS = 'Normal'
    WRAP_HORIZONTAL = 'WrapHorizontally'
    WRAP_VERTICAL = 'WrapVertically'


class Color:
    BLACK = '#000000'


class Warzone:
    TERRITORY_IDENTIFIER = 'Territory_'
    BONUS_LINK_IDENTIFIER = 'BonusLink_'

    UNNAMED_TERRITORY_NAME = 'Unnamed'


class WZMapBuilder(EffectExtension):
    def add_arguments(self, pars: ArgumentParser) -> None:
        pars.add_argument("--email", type=str, default='')
        pars.add_argument("--api_token", type=str, default='')
        pars.add_argument("--map_id", type=int)
        pars.add_argument("--territory_names", type=Boolean, default=False)
        pars.add_argument("--territory_center_points", type=Boolean, default=False)
        pars.add_argument("--connections", type=Boolean, default=False)
        pars.add_argument("--bonuses", type=Boolean, default=False)
        pars.add_argument("--territory_bonuses", type=Boolean, default=False)
        pars.add_argument("--distribution_modes", type=Boolean, default=False)
        pars.add_argument("--territory_distribution_modes", type=Boolean, default=False)

    def effect(self):
        commands = self._get_commands()
        self._post_map_details(commands)
        return

    ##################
    # HELPER METHODS #
    ##################

    def _post_map_details(self, commands: List[Command]) -> None:
        response = requests.post(
            url=SET_MAP_DETAILS_URL,
            json={
                'email': self.options.email,
                'APIToken': self.options.api_token,
                'mapID': self.options.map_id,
                'commands': commands,
            }
        )

        debug(json.loads(response.text))

    def _get_commands(self) -> List[Command]:
        commands = []
        if self.options.territory_names:
            commands += self._get_set_territory_name_commands()
        # todo add set center points
        # todo add connections
        if self.options.bonuses:
            commands += self._get_add_bonus_commands()
        if self.options.territory_bonuses:
            commands += self._get_add_territory_to_bonus_commands()
        if self.options.distribution_modes:
            commands += self._get_add_distribution_mode_commands()
        if self.options.territory_distribution_modes:
            commands += self._get_add_territory_to_distribution_commands()
        return commands

    ###################
    # COMMAND GETTERS #
    ###################

    def _get_set_territory_name_commands(self) -> List[Command]:
        """
        Parses svg and creates setTerritoryName commands.

        A command for each path whose ID signifies it is a Warzone Territory (i.e. starts with the
        Warzone.TERRITORY_IDENTIFIER) and also has a title.

        :return:
        List of setTerritoryNameCommands
        """
        territories = self.svg.xpath(
            f".//{Svg.PATH}[contains(@{Svg.ID}, '{Warzone.TERRITORY_IDENTIFIER}') and {Svg.TITLE}]",
            namespaces=NAMESPACES
        )

        commands = [
            {
                'command': 'setTerritoryName',
                'id': self._get_territory_id(territory),
                'name': self._get_territory_name(territory)
            } for territory in territories
        ]
        return commands

    def _get_add_bonus_commands(self) -> List[Command]:
        """
        Parses svg and creates addBonus commands.

        A command is created for each sub-layer of the WZ:Bonuses layer. Each of these sub-layers is
        assumed to have a name of the form `bonus_name: bonus_value`. If a path node exists with the
        id f"{Warzone.BONUS_IDENTIFIER}bonus_name" the fill color of that path is used as the bonus
        color, otherwise the bonus color is black.

        :return:
        List of addBonus commands
        """
        bonus_links: Dict[str, PathElement] = {
            bonus_link.get(Svg.ID): bonus_link
            for bonus_link in self.svg.xpath(
                f".//{Svg.PATH}[contains(@{Svg.ID}, '{Warzone.BONUS_LINK_IDENTIFIER}')]",
                namespaces=NAMESPACES
            )
        }
        bonus_layer_nodes = self._get_metadata_type_layers(MapLayers.BONUSES)

        commands = []
        for bonus_layer in bonus_layer_nodes:
            bonus_name, bonus_value = self._parse_bonus_layer_label(bonus_layer)
            bonus_link_node = bonus_links.get(self._get_bonus_link_id(bonus_name))
            if bonus_link_node is not None:
                node_style = bonus_link_node.composed_style()
                bonus_color = node_style[Svg.FILL].upper()
            else:
                bonus_color = Color.BLACK

            command = {
                'command': 'addBonus',
                'name': bonus_name,
                'armies': bonus_value,
                'color': bonus_color
            }
            commands.append(command)

        return commands

    def _get_add_territory_to_bonus_commands(self) -> List[Command]:
        """
        Parses svg and creates addTerritoryToBonus commands.

        Each sub-layer of the WZ:Bonuses layer is assumed to contain clones of Territory nodes (i.e.
        path nodes whose id starts with Warzone.TERRITORY_IDENTIFIER). A command is created for the
        linked territory of each clone in each of these sub-layers adding that territory to the
        bonus of the layer it is in.

        :return:
        List of addTerritoryToBonus commands
        """
        bonus_layers = self._get_metadata_type_layers(MapLayers.BONUSES)
        commands = [
            {
                'command': 'addTerritoryToBonus',
                'id': self._get_territory_id(territory),
                'bonusName': self._parse_bonus_layer_label(bonus_layer)[0]
            } for bonus_layer in bonus_layers
            for territory in bonus_layer.xpath(f"./{Svg.CLONE}", namespaces=NAMESPACES)
        ]
        return commands

    def _get_add_distribution_mode_commands(self) -> List[Command]:
        """
        Parses svg and creates addDistributionMode commands.

        A command is created for each sub-layer of the WZ:DistributionModes layer. Each of these
        sub-layers should be named with the name of the distribution mode.

        :return:
        List of addDistributionMode commands
        """
        distribution_mode_layers = self._get_metadata_type_layers(
            MapLayers.DISTRIBUTION_MODES, is_recursive=False
        )

        commands = [
            {
                'command': 'addDistributionMode',
                'name': distribution_mode_layer.get(get_uri(Inkscape.LABEL)),
            } for distribution_mode_layer in distribution_mode_layers
        ]
        return commands

    def _get_add_territory_to_distribution_commands(self) -> List[Command]:
        """
        Parses svg and creates addTerritoryToDistribution commands.

        Each sub-layer of the WZ:DistributionModes layer is assumed to contain clones of Territory
        nodes (i.e. path nodes whose id starts with Warzone.TERRITORY_IDENTIFIER). A command is
        created for the linked territory of each clone in each of these sub-layers adding that
        territory to the distribution mode of the layer it is in.

        :return:
        List of addTerritoryToDistribution commands
        """
        distribution_mode_layers = self._get_metadata_type_layers(
            MapLayers.DISTRIBUTION_MODES, is_recursive=False
        )

        commands = [
            {
                'command': 'addTerritoryToDistribution',
                'id': self._get_territory_id(territory),
                'distributionName': distribution_mode_layer.get(get_uri(Inkscape.LABEL))
            } for distribution_mode_layer in distribution_mode_layers
            for territory in distribution_mode_layer.xpath(f"./{Svg.CLONE}", namespaces=NAMESPACES)
        ]
        return commands

    #################
    # PARSING UTILS #
    #################

    @staticmethod
    def _get_territory_id(territory: Union[str,  PathElement, Use]) -> int:
        if isinstance(territory, str):
            territory_id = territory.split(Warzone.TERRITORY_IDENTIFIER)[-1]
        elif isinstance(territory, PathElement):
            territory_id = WZMapBuilder._get_territory_id(territory.get(Svg.ID))
        elif isinstance(territory, Use):
            territory_id = WZMapBuilder._get_territory_id(territory.get(get_uri(XLink.HREF)))
        else:
            raise ValueError(f'Element {territory} is not a valid territory element. It must be a'
                             f' path or a clone.')
        return int(territory_id)

    @staticmethod
    def _get_territory_name(territory: PathElement) -> str:
        title = territory.find(Svg.TITLE, NAMESPACES)
        if title is not None:
            territory_name = title.text
        else:
            territory_name = Warzone.UNNAMED_TERRITORY_NAME
        return territory_name

    def _get_metadata_type_layers(
            self, metadata_type: str, is_recursive: bool = True
    ) -> List[Group]:
        slash = '//' if is_recursive else '/'
        bonus_layers = self.svg.xpath(
            f"./{Svg.GROUP}[@{Inkscape.LABEL}='{MapLayers.METADATA}']"
            f"/{Svg.GROUP}[@{Inkscape.LABEL}='{metadata_type}']"
            f"{slash}{Svg.GROUP}[@{Inkscape.LABEL}]",
            namespaces=NAMESPACES
        )
        return bonus_layers

    @staticmethod
    def _parse_bonus_layer_label(bonus_layer: Group) -> Tuple[str, int]:
        bonus_name, bonus_value = bonus_layer.get(get_uri(Inkscape.LABEL)).split(': ')
        return bonus_name, int(bonus_value)

    @staticmethod
    def _get_bonus_link_id(bonus_name: str) -> str:
        return Warzone.BONUS_LINK_IDENTIFIER + re.sub(r'[^a-zA-Z0-9]+', '', bonus_name)


WZMapBuilder().run()
