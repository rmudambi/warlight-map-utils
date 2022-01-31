#!/usr/bin/env python

from argparse import ArgumentParser
import json
import re
import requests
from typing import Dict, List, Tuple, Union

import inkex
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
    GROUP_MODE = 'inkscape:groupmode'
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


class WZMapBuilder(inkex.EffectExtension):
    def add_arguments(self, pars: ArgumentParser) -> None:
        pars.add_argument("--tab", type=str, default='')
        pars.add_argument("--email", type=str, default='')
        pars.add_argument("--api_token", type=str, default='')
        pars.add_argument("--map_id", type=int)
        pars.add_argument("--territory_names", type=inkex.Boolean, default=False)
        pars.add_argument("--territory_center_points", type=inkex.Boolean, default=False)
        pars.add_argument("--connections", type=inkex.Boolean, default=False)
        pars.add_argument("--bonuses", type=inkex.Boolean, default=False)
        pars.add_argument("--territory_bonuses", type=inkex.Boolean, default=False)
        pars.add_argument("--distribution_modes", type=inkex.Boolean, default=False)
        pars.add_argument("--territory_distribution_modes", type=inkex.Boolean, default=False)

    def effect(self) -> None:
        {
            'territory-ids': self._set_territory_ids,
            'upload': self._upload_metadata,
        }[self.options.tab]()
        return

    ###########
    # EFFECTS #
    ###########

    def _set_territory_ids(self) -> None:
        """
        Sets the id of all selected paths to a Warzone Territory ID and moves them to the
        Territories layer. If move existing territories checkbox is checked, move all existing
        territories to the Territories layer.
        :return:
        """
        if not self.svg.selected:
            raise inkex.AbortExtension("There are no territories selected.")

        territory_layer = self._get_territory_layer()
        if territory_layer is None:
            territory_layer = inkex.Group.new(MapLayers.TERRITORIES, **{Inkscape.GROUP_MODE: 'layer'})
            self.svg.add(territory_layer)

        # todo check for territories in wrong layer
        territories: List[inkex.PathElement] = territory_layer.xpath(
            f"./{Svg.PATH}[contains(@{Svg.ID}, '{Warzone.TERRITORY_IDENTIFIER}')]",
            namespaces=NAMESPACES
        )
        max_id = max([0] + [self._get_territory_id(territory) for territory in territories])

        for territory in self.svg.selection.filter(inkex.PathElement):
            if Warzone.TERRITORY_IDENTIFIER not in territory.get_id():
                max_id += 1
                territory.set_id(f"{Warzone.TERRITORY_IDENTIFIER}{max_id}")
            if territory.getparent() != territory_layer:
                territory.getparent().remove(territory)
                territory_layer.append(territory)

    def _upload_metadata(self) -> None:
        commands = self._get_commands()
        self._post_map_details(commands)

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
        if self.options.territory_center_points:
            commands += self._get_set_territory_center_point_commands()
        if self.options.connections:
            commands += self._get_add_territory_connections_commands()
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

        A command is created for each path whose ID signifies it is a Warzone Territory (i.e. starts
        with the Warzone.TERRITORY_IDENTIFIER) and also has a title.

        :return:
        List of setTerritoryName commands
        """
        territories = self.svg.xpath(
            # todo look only in territory layer
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

    def _get_set_territory_center_point_commands(self) -> List[Command]:
        """
        Parses svg and sets territory center points.

        A command is created for each group that has a territory and an ellipse in it.
        :return:
        List of setTerritoryCenterPoint commands
        """
        groups = self.svg.xpath(
            f".//{Svg.GROUP}["
            f"  {Svg.PATH}[contains(@{Svg.ID}, '{Warzone.TERRITORY_IDENTIFIER}')]"
            f"  and .//{Svg.ELLIPSE}"
            f"]",
            namespaces=NAMESPACES
        )

        # todo use https://blog.mapbox.com/a-new-algorithm-for-finding-a-visual-center-of-a-polygon-7c77e6492fbc
        #  to set a default center point

        commands = []
        for group in groups:
            territory = group.find(f"./{Svg.PATH}", namespaces=NAMESPACES)
            territory_id = self._get_territory_id(territory)
            # todo account for matrix transformations in getting center point
            center_ellipse: inkex.Ellipse = group.find(f"./{Svg.ELLIPSE}", namespaces=NAMESPACES)
            x, y = center_ellipse.center
            command = {
                'command': 'setTerritoryCenterPoint',
                'id': territory_id,
                'x': x,
                'y': y
            }
            commands.append(command)

        return commands

    def _get_add_territory_connections_commands(self) -> List[Command]:
        """
        Parses svg and creates addTerritoryConnection commands

        A command is created for each diagram connector that connects two groups containing a
        territory.
        :return:
        List of addTerritoryConnection commands
        """
        connection_type_layers = self._get_metadata_type_layers(MapLayers.CONNECTIONS)

        commands = []
        for connection_type_layer in connection_type_layers:
            for connection_layer in connection_type_layer:
                def get_territory_id(attribute: str) -> int:
                    link_id = connection_layer.get(get_uri(attribute))[1:]
                    # todo handle top-level territories
                    #  - currently only works if territory node is one layer below linked node
                    #  - probably want to separate center point from group and key on that
                    #  - possible solution (likely most user friendly) is to automatically detect
                    #       which territory a center point corresponds with
                    territory = self.svg.xpath(
                        f".//*[@{Svg.ID}='{link_id}']"
                        f"/{Svg.PATH}[contains(@{Svg.ID}, '{Warzone.TERRITORY_IDENTIFIER}')]",
                        namespaces=NAMESPACES
                    )[0]
                    return self._get_territory_id(territory.get(Svg.ID))

                command = {
                    'command': 'addTerritoryConnection',
                    'id1': get_territory_id(Inkscape.CONNECTION_START),
                    'id2': get_territory_id(Inkscape.CONNECTION_END),
                    'wrap': connection_type_layer.get(get_uri(Inkscape.LABEL))
                }
                commands.append(command)

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
        bonus_links: Dict[str, inkex.PathElement] = {
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
        # todo implement adding scenario distributions modes
        #  determine if scenario distribution mode
        #  get scenario names

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
        # todo implement adding scenario distributions modes
        #  determine if scenario distribution mode
        #  get scenario names

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

    def _get_territory_layer(self) -> inkex.Group:
        return self.svg.find(
            f"./{Svg.GROUP}[@{Inkscape.LABEL}='{MapLayers.TERRITORIES}']", NAMESPACES
        )

    @staticmethod
    def _get_territory_id(territory: Union[str,  inkex.PathElement, inkex.Use]) -> int:
        """
        Returns the id of the territory. If the argument is a string it must be of the form
        'Territory_X'. If the argument is a territory, it gets the int part of the element's id. If
        it is a clone, it get the int part of the id of the linked element.
        :param territory:
        :return:
        territory id as required by the Warzone API
        """
        if isinstance(territory, str):
            territory_id = territory.split(Warzone.TERRITORY_IDENTIFIER)[-1]
        elif isinstance(territory, inkex.PathElement):
            territory_id = WZMapBuilder._get_territory_id(territory.get(Svg.ID))
        elif isinstance(territory, inkex.Use):
            territory_id = WZMapBuilder._get_territory_id(territory.get(get_uri(XLink.HREF)))
        else:
            raise ValueError(f'Element {territory} is not a valid territory element. It must be a'
                             f' path or a clone.')
        return int(territory_id)

    @staticmethod
    def _get_territory_name(territory: inkex.PathElement) -> str:
        """
        Get the name of the territory from its child title element. If no title, returns
        Warzone.UNNAMED_TERRITORY_NAME
        :param territory:
        :return:
        territory name
        """
        title = territory.find(Svg.TITLE, NAMESPACES)
        if title is not None:
            territory_name = title.text
        else:
            territory_name = Warzone.UNNAMED_TERRITORY_NAME
        return territory_name

    def _get_metadata_type_layers(
            self, metadata_type: str, is_recursive: bool = True
    ) -> List[inkex.Group]:
        """
        Returns all layers of the input type. If not recursive only retrieves top-level layers
        :param metadata_type:
        :param is_recursive:
        :return:
        metadata layers
        """
        slash = '//' if is_recursive else '/'
        bonus_layers = self.svg.xpath(
            f"./{Svg.GROUP}[@{Inkscape.LABEL}='{MapLayers.METADATA}']"
            f"/{Svg.GROUP}[@{Inkscape.LABEL}='{metadata_type}']"
            f"{slash}{Svg.GROUP}[@{Inkscape.LABEL}]",
            namespaces=NAMESPACES
        )
        return bonus_layers

    @staticmethod
    def _parse_bonus_layer_label(bonus_layer: inkex.Group) -> Tuple[str, int]:
        """
        Parses a bonus layer's label to get the bonus name and value.
        :param bonus_layer:
        :return:
        tuple of bonus name and bonus value
        """
        bonus_name, bonus_value = bonus_layer.get(get_uri(Inkscape.LABEL)).split(': ')
        return bonus_name, int(bonus_value)

    @staticmethod
    def _get_bonus_link_id(bonus_name: str) -> str:
        """
        Converts a bonus name to the corresponding ID for its bonus link
        :param bonus_name:
        :return:
        bonus link id
        """
        return Warzone.BONUS_LINK_IDENTIFIER + re.sub(r'[^a-zA-Z0-9]+', '', bonus_name)


WZMapBuilder().run()
