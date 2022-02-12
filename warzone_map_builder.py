#!/usr/bin/env python

from argparse import ArgumentParser
import json
import re
import requests
from typing import Dict, List, Optional, Tuple, Union

import inkex
from inkex.utils import debug


Command = Dict[str, Union[str, int]]

SET_MAP_DETAILS_URL = 'https://www.warzone.com/API/SetMapDetails'
NAMESPACES = {
    'svg': 'http://www.w3.org/2000/svg',
    'inkscape': 'http://www.inkscape.org/namespaces/inkscape',
    'xlink': 'http://www.w3.org/1999/xlink',
}


class WarzoneMapBuilderException(ValueError):
    """specify exception raised by"""


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
    RECTANGLE = 'svg:rect'
    TEXT = 'svg:text'
    TSPAN = 'svg:tspan'

    STYLE = 'style'
    FILL = 'fill'
    STROKE = 'stroke'
    STROKE_WIDTH = 'stroke-width'


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
    WHITE = '#FFFFFF'
    TERRITORY_FILL = '#FFFFFF'
    BONUS_LINK_STROKE = '#FFFF00'


class Warzone:
    TERRITORY_IDENTIFIER = 'Territory_'
    BONUS_LINK_IDENTIFIER = 'BonusLink_'

    UNNAMED_TERRITORY_NAME = 'Unnamed'

    BONUS_LINK_SIDE = 20

    RECT_WIDTH = 20
    RECT_HEIGHT = 15
    RECT_ROUNDING = 4

    ARMY_FONT_SIZE = 13     # px


class WZMapBuilder(inkex.EffectExtension):
    def add_arguments(self, ap: ArgumentParser) -> None:
        ap.add_argument("--tab", type=str, default='about')

        # arguments for set territories
        ap.add_argument("--territories_territory_layer", type=inkex.Boolean, default=True)

        # arguments for set territory name
        ap.add_argument("--territory_name", type=str, default=Warzone.UNNAMED_TERRITORY_NAME)
        ap.add_argument("--territory_name_territory_layer", type=inkex.Boolean, default=True)

        # arguments for set bonus
        ap.add_argument("--bonus_name", type=str, default='')
        ap.add_argument("--bonus_value", type=str, default='')
        ap.add_argument("--bonus_color", type=str, default=Color.BLACK)
        ap.add_argument("--bonus_link_visible", type=inkex.Boolean, default=True)
        ap.add_argument("--bonus_replace", type=inkex.Boolean, default=True)

        # arguments for metadata upload
        ap.add_argument("--upload_email", type=str, default='')
        ap.add_argument("--upload_api_token", type=str, default='')
        ap.add_argument("--upload_map_id", type=int)
        ap.add_argument("--upload_territory_names", type=inkex.Boolean, default=False)
        ap.add_argument("--upload_territory_center_points", type=inkex.Boolean, default=False)
        ap.add_argument("--upload_connections", type=inkex.Boolean, default=False)
        ap.add_argument("--upload_bonuses", type=inkex.Boolean, default=False)
        ap.add_argument("--upload_territory_bonuses", type=inkex.Boolean, default=False)
        ap.add_argument("--upload_distribution_modes", type=inkex.Boolean, default=False)
        ap.add_argument("--upload_territory_distribution_modes", type=inkex.Boolean, default=False)

    def effect(self) -> None:
        try:
            {
                'about': (lambda: ''),
                'territories': self._set_territories,
                'territory-name': self._set_territory_name,
                'bonus': self._set_bonus,
                'upload': self._upload_metadata,
            }[self.options.tab]()
        except WarzoneMapBuilderException as e:
            debug(e)
        return

    ###########
    # EFFECTS #
    ###########

    def _set_territories(self) -> None:
        """
        Converts all selected paths to a Warzone Territories by setting a Warzone Territory ID and
        creating a territory group. If territory-layer checkbox is checked, move all existing
        territories to the Territories layer.
        :return:
        """

        territory_layer = (
            self._get_or_create_territory_layer()
            if self.options.territories_territory_layer else None
        )
        territories = self._get_territories(self.svg)
        max_id = self.get_max_territory_id(territories)
        territories += [selected for selected in self.svg.selection.filter(inkex.PathElement)]
        for territory in territories:
            max_id = self.create_territory(territory, max_id, territory_layer)
        if not self.svg.selected:
            debug("There are no territories selected. Territories must be paths.")
        if self.options.territories_territory_layer:
            debug(f"All existing paths with valid Warzone Territory IDs were moved to the "
                  f"{MapLayers.TERRITORIES} layer.")

    def _set_territory_name(self) -> None:
        """
        Sets the title of the selected path to the input name. If path isn't a Warzone Territory,
        converts it into one. If territory-layer checkbox is checked, move to the Territories layer.
        :return:
        """
        selected_paths = self.svg.selection.filter(inkex.PathElement)
        if len(selected_paths) != 1:
            debug("There must be exactly one selected path element.")
            return

        territory_layer = (
            self._get_or_create_territory_layer()
            if self.options.territory_name_territory_layer else None
        )
        territory = selected_paths.pop()
        territory.add(inkex.Title.new(self.options.territory_name))
        self.create_territory(territory, self.get_max_territory_id(), territory_layer)

    def _set_bonus(self) -> None:
        """
        Creates a bonus layer if it doesn't exist and adds the selected territories to it. If the
        bonus previously existed, either adds the territories to the bonus or replaces existing
        territories depending on bonus_replace option. Creates a bonus-link if necessary.
        :return:
        """
        # todo allow bonus to be selected if bonus link is in selection
        territories = [
            self._get_territories(group)[0] for group in self.svg.selection.filter(inkex.Group)
            if self._is_territory_group(group)
        ]
        self.svg.selection.set(*territories)

        # todo remove argument
        bonus_layer = self._get_or_create_bonus_layer('sdfkjl')

        if self.options.bonus_link_visible:
            bonus_link = self._set_bonus_link()
        else:
            bonus_link = None

        bonus_territories = []
        for territory in territories:
            bonus_territories.append(
                self._create_bonus_territory(territory, bonus_layer)
            )

        if self.options.bonus_replace:
            bonus_layer.remove_all()

        # bonus_layer.add(bonus_territories)
        # todo set stroke color of all territories
        # todo reselect original selection
        pass

    def _upload_metadata(self) -> None:
        commands = self._get_set_metadata_commands()
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

    def _get_set_metadata_commands(self) -> List[Command]:
        commands = []
        if self.options.upload_territory_names:
            commands += self._get_set_territory_name_commands()
        if self.options.upload_territory_center_points:
            commands += self._get_set_territory_center_point_commands()
        if self.options.upload_connections:
            commands += self._get_add_territory_connections_commands()
        if self.options.upload_bonuses:
            commands += self._get_add_bonus_commands()
        if self.options.upload_territory_bonuses:
            commands += self._get_add_territory_to_bonus_commands()
        if self.options.upload_distribution_modes:
            commands += self._get_add_distribution_mode_commands()
        if self.options.upload_territory_distribution_modes:
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

        commands = []
        for group in groups:
            territory = group.find(f"./{Svg.PATH}", NAMESPACES)
            territory_id = self._get_territory_id(territory)
            # todo account for matrix transformations in getting center point
            center_ellipse: inkex.Ellipse = group.find(f"./{Svg.ELLIPSE}", NAMESPACES)
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

    def find(self, xpath: str, root: inkex.BaseElement = None) -> inkex.BaseElement:
        if root is None:
            root = self.svg
        if 'contains(' in xpath:
            if target := root.xpath(xpath, NAMESPACES):
                target = target[0]
            else:
                target = None
        else:
            target = root.find(xpath, NAMESPACES)
        return target

    def _get_or_create_territory_layer(self) -> Optional[inkex.Layer]:
        """
        Returns the territory layer. Creates it if it doesn't exist.
        :return:
        territory_layer
        """
        territory_layer = self.find(f"./{Svg.GROUP}[@{Inkscape.LABEL}='{MapLayers.TERRITORIES}']")

        if territory_layer is None:
            territory_layer = inkex.Layer.new(MapLayers.TERRITORIES)
            self.svg.add(territory_layer)
        return territory_layer

    @staticmethod
    def _is_territory_group(group: inkex.ShapeElement) -> bool:
        """
        Checks if element is a territory group. It is a territory group if it is a non-layer Group
        and has two children, one of which is a territory, the other of which is a center point
        group.
        :param group:
        :return:
        """
        return (
            isinstance(group, inkex.Group)
            and not isinstance(group, inkex.Layer)
            and len(group.getchildren()) == 2
            and len(WZMapBuilder._get_territories(group, is_recursive=False)) == 1
            and len(group.xpath(f"./{Svg.GROUP}[{Svg.RECTANGLE} and {Svg.TEXT}]")) == 1
        )

    @staticmethod
    def _get_territories(
            root: inkex.BaseElement, is_recursive: bool = True
    ) -> List[inkex.PathElement]:
        """
        Gets all territory elements that are children of the root node. If not is_recursive, gets
        only direct children.
        :param root:
        :param is_recursive:
        :return:
        """
        slash = '//' if is_recursive else '/'
        return root.xpath(
            f".{slash}{Svg.PATH}[contains(@{Svg.ID}, '{Warzone.TERRITORY_IDENTIFIER}')]",
            # todo see if we can remove this argument
            namespaces=NAMESPACES
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
        # todo support territory group?
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

    def get_max_territory_id(self, territories: List[inkex.PathElement] = None) -> int:
        """
        Gets the maximum territory id as an int in the territories. If territories is None, searches
        the whole svg.
        :return:
        maximum int id
        """
        territories = self._get_territories(self.svg) if territories is None else territories
        max_id = max([0] + [self._get_territory_id(territory) for territory in territories])
        return max_id

    def _get_metadata_type_layers(
            self, metadata_type: str, is_recursive: bool = True
    ) -> List[inkex.Layer]:
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
    def _parse_bonus_layer_label(bonus_layer: inkex.Layer) -> Tuple[str, int]:
        """
        Parses a bonus layer's label to get the bonus name and value.
        :param bonus_layer:
        :return:
        tuple of bonus name and bonus value
        """
        bonus_name, bonus_value = bonus_layer.get(get_uri(Inkscape.LABEL)).split(': ')
        return bonus_name, int(bonus_value)

    def _get_or_create_bonus_link_layer(self) -> inkex.Layer:
        """Gets the bonus link layer"""
        layer = self.find(f"./{Svg.GROUP}[{Inkscape.LABEL}='{MapLayers.BONUS_LINKS}']")
        if layer is None:
            layer = inkex.Layer.new(MapLayers.BONUS_LINKS)
            self.svg.add(layer)
        return layer

    @staticmethod
    def _get_bonus_link_id(bonus_name: str) -> str:
        """
        Converts a bonus name to the corresponding ID for its bonus link
        :param bonus_name:
        :return:
        bonus link id
        """
        return Warzone.BONUS_LINK_IDENTIFIER + re.sub(r'[^a-zA-Z0-9]+', '', bonus_name)

    @staticmethod
    def _is_bonus_link_group(group: inkex.ShapeElement) -> bool:
        """
        Checks if element is a bonus link group. It is a bonus link group if it is a non-layer Group
        and has two children, one of which is a bonus link, the other of which is a text element.
        :param group:
        :return:
        """
        return (
            isinstance(group, inkex.Group)
            and not isinstance(group, inkex.Layer)
            and len(group.getchildren()) == 2
            and (len(group.xpath(
                    f"./{Svg.PATH}[contains(@{Svg.ID}, '{Warzone.BONUS_LINK_IDENTIFIER}')]",
                    NAMESPACES
                )) == 1)
            and (group.find(f"./{Svg.TEXT}") is not None)
        )

    ####################
    # METADATA SETTERS #
    ####################

    def _get_metadata_layer(self, metadata_type: str = None, create: bool = False) -> inkex.Layer:
        """
        Returns the specified metadata layer node. If no metadata type provided returns the base
        metadata mode. If create, will create node if it doesn't exist.
        :param metadata_type:
        :param create:
        :return:
        """
        metadata_layer = self.find(f"./{Svg.GROUP}[@{Inkscape.LABEL}='{MapLayers.METADATA}']")
        if metadata_layer is None:
            metadata_layer = inkex.Layer.new(MapLayers.METADATA)
            self.svg.add(metadata_layer)

        if metadata_type:
            layer = self.find(f"./{Svg.GROUP}[@{Inkscape.LABEL}='{metadata_type}']", metadata_layer)
            if layer is None and create:
                layer = inkex.Layer.new(metadata_type)
                metadata_layer.add(layer)
        else:
            layer = metadata_layer
        return layer



    def create_territory(
            self, territory: inkex.PathElement, max_id: int, territory_layer: inkex.Layer = None
    ) -> int:
        """
        Converts territory path into a Warzone Territory.

        Sets the id of territory to the next Warzone Territory ID after the current maximum and
        creates a territory group containing a center-point and display army numbers. If
        territory_layer argument is passed, move territory group to the Territories layer.

        :param max_id:
        :param territory:
        :param territory_layer:
        :return maximum territory id as int
        """
        if Warzone.TERRITORY_IDENTIFIER not in territory.get_id():
            max_id += 1
            territory.set_id(f"{Warzone.TERRITORY_IDENTIFIER}{max_id}")
        parent: inkex.Group = territory.getparent()
        if not self._is_territory_group(parent):
            territory_group = inkex.Group.new(
                territory.get_id(),
                territory,
                self._create_center_point_group(territory),
            )
        else:
            territory_group = parent
            parent = territory_group.getparent()
        territory_style = territory.effective_style()
        territory_style[Svg.STROKE_WIDTH] = 1
        if territory_style.get_color() != Color.TERRITORY_FILL:
            territory_style.set_color(Color.TERRITORY_FILL)
        destination = territory_layer if self.options.territories_territory_layer else parent
        if territory_group not in destination:
            destination.add(territory_group)
        return max_id

    @staticmethod
    def _create_center_point_group(territory: Union[inkex.Group, inkex.PathElement]) -> inkex.Group:
        """
        Creates a group containing a rounded rectangle and sample army numbers centered at the
        territory's center-point
        :param territory:
        :return:
        center point group
        """
        # todo use https://blog.mapbox.com/a-new-algorithm-for-finding-a-visual-center-of-a-polygon-7c77e6492fbc
        #  to set a default center point
        center = territory.bounding_box().center
        return inkex.Group.new(
            territory.get_id(),
            inkex.Rectangle.new(
                left=center.x - Warzone.RECT_WIDTH / 2,
                top=center.y - Warzone.RECT_HEIGHT / 2,
                width=Warzone.RECT_WIDTH,
                height=Warzone.RECT_HEIGHT,
                ry=Warzone.RECT_ROUNDING,
                rx=Warzone.RECT_ROUNDING,
                style=inkex.Style(
                    fill='none',
                    stroke=Color.TERRITORY_FILL,
                    stroke_width=1.0,
                    stroke_linecap='round',
                    stroke_linejoin='round',
                ),
            ),
            inkex.TextElement.new(
                WZMapBuilder.create_tspan('88', font_color=Color.BLACK),
                x=center.x,
                y=center.y + Warzone.ARMY_FONT_SIZE * 3/8,
            ),
        )

    def _set_bonus_link(self) -> inkex.Group:
        """
        Creates a bonus link if it doesn't exist and adds it to the bonus link layer. Updates any
        properties of bonus link it if already exists.

        :return:
        bonus link
        """
        # todo account for already selected bonus link and name changes
        # Get bonus link path if it exists
        bonus_link_id = self._get_bonus_link_id(self.options.bonus_name)
        bonus_link_path = self.find(f".//{Svg.PATH}[{Svg.ID}='{bonus_link_id}']")
        location = self.svg.selection.bounding_box().center

        # Create bonus link path if it does not exist
        if new_link := bonus_link_path is None:
            bonus_link_path = inkex.Rectangle.new(
                left=location.x - Warzone.BONUS_LINK_SIDE / 2,
                top=location.y - Warzone.BONUS_LINK_SIDE / 2,
                width=Warzone.BONUS_LINK_SIDE,
                height=Warzone.BONUS_LINK_SIDE,
                ry=Warzone.RECT_ROUNDING,
                rx=Warzone.RECT_ROUNDING,
            ).to_path_element()
            bonus_link_path.set_id(bonus_link_id)

        # Set bonus link fill and stroke
        bonus_link_style = bonus_link_path.effective_style()
        bonus_link_style.set_color(Color.BONUS_LINK_STROKE, name=Svg.STROKE)
        try:
            bonus_link_style.set_color(self.options.bonus_color)
        except inkex.colors.ColorError:
            error_message = (
                f"If creating a new bonus with a bonus link, a bonus color must be provided as an"
                f" RGB string in the form '#00EE33'. Provided {self.options.bonus_color}"
                if new_link else
                f"If a bonus color is provided if must be an RGB string in the form '#00EE33'."
                f" Provided {self.options.bonus_color}"
            )
            raise WarzoneMapBuilderException(error_message)

        # Get bonus link group
        parent = bonus_link_path.getparent()
        if self._is_bonus_link_group(parent):
            bonus_link = parent
        else:
            # Create bonus link group if it doesn't exist
            bonus_link = inkex.Group.new(
                bonus_link_id,
                bonus_link_path,
                inkex.TextElement.new(
                    self.create_tspan(self.options.bonus_value, font_color=Color.WHITE),
                    x=location.x,
                    y=location.y + Warzone.ARMY_FONT_SIZE * 3 / 8,
                ),
            )

        # Set bonus link font color
        tspan = self.find(f"./{Svg.TEXT}/{Svg.TSPAN}", bonus_link)
        tspan.effective_style().set_color(
            Color.WHITE if bonus_link_style.get_color().to_rgb().to_hsl().lightness < 128
            else Color.BLACK
        )
        # Set bonus link value
        if tspan.text != self.options.bonus_value:
            tspan.text = self.options.bonus_value

        # Add bonus link to bonus link layer
        bonus_link_layer = self._get_or_create_bonus_link_layer()
        if bonus_link.getparent() != bonus_link_layer:
            bonus_link_layer.add(bonus_link)
        return bonus_link

    def _get_or_create_bonus_layer(self, old_bonus_name: str) -> inkex.Layer:
        """
        Finds the bonus layer corresponding to the old bonus name. Updates the bonus name and value
        if needed. Creates a new bonus layer if no bonus exists for that name.
        :param old_bonus_name:
        :return:
        bonus layer
        """
        # get bonuses layer and create if not exists
        bonuses_layer = self._get_metadata_layer(MapLayers.BONUSES, create=True)

        # get bonus layer for old bonus name and create if not exists
        bonus_layer = self.find(f"./{Svg.GROUP}[contains(@{Inkscape.LABEL}, '{old_bonus_name}: ')]")
        if bonus_layer is None:
            try:
                bonus_value = int(self.options.bonus_value)
            except ValueError:
                raise WarzoneMapBuilderException(
                    f"If creating a new bonus, a bonus value must be provided as an integer."
                    f" Provided '{self.options.bonus_value}'"
                )
            if not self.options.bonus_name:
                raise WarzoneMapBuilderException(
                    "If no bonus link is selected, a bonus name must be provided."
                )
            bonus_layer = inkex.Layer.new(f'{self.options.bonus_name}: {bonus_value}')
            bonuses_layer.add(bonus_layer)
        else:
            try:
                bonus_value = int(
                    self.options.bonus_value if self.options.bonus_value != ''
                    else bonus_layer[{Inkscape.LABEL}].split(': ')[-1]
                )
                self.options.bonus_value = str(bonus_value)
            except ValueError:
                raise WarzoneMapBuilderException(
                    f"If a bonus value is provided it must be an integer."
                    f" Provided {self.options.bonus_value}"
                )

            # update bonus name if name or value has changed
            new_bonus_name = self.options.bonus_name if self.options.bonus_name else old_bonus_name
            bonus_layer[{Inkscape.LABEL}] = f'{new_bonus_name}: {bonus_value}'

        return bonus_layer

    @staticmethod
    def _create_bonus_territory(
            territory: inkex.PathElement, bonus_layer: inkex.Layer
    ) -> inkex.PathElement:
        """

        :param territory:
        :param bonus_layer:
        :return:
        """
        # todo create clone
        return None

    @staticmethod
    def create_tspan(bonus_value, font_color: str):
        return inkex.Tspan.new(
            bonus_value,
            style=inkex.Style(
                fill=font_color,
                font_weight='bold',
                font_size=f'{Warzone.ARMY_FONT_SIZE}px',
                text_align='center',
                text_anchor='middle',
            )
        )


WZMapBuilder().run()
