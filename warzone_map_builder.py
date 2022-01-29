#!/usr/bin/env python

from argparse import ArgumentParser
import json
import requests
from typing import Dict, List, Union

from inkex import BaseElement, EffectExtension, PathElement
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


class Warzone:
    TERRITORY_IDENTIFIER = 'Territory_'
    BONUS_LINK_IDENTIFIER = 'BonusLink_'

    UNNAMED_TERRITORY_NAME = 'Unnamed'


class WZMapBuilder(EffectExtension):
    def add_arguments(self, pars: ArgumentParser) -> None:
        pars.add_argument("--email", type=str, default='')
        pars.add_argument("--api_token", type=str, default='')
        pars.add_argument("--map_id", type=int)
        # TODO add checkboxes for each type of set details command

    def effect(self):
        # selected_object = self.svg.selected[self.options.ids[0]]
        # # 2 get type of the selected object
        # typeOfSelectedObject = selected_object.tag
        # # 3 Display the type
        # inkex.utils.debug("I am a: ")
        # inkex.utils.debug(typeOfSelectedObject)
        # inkex.utils.debug(" !\n")

        commands = self._get_commands()
        # todo uncomment when ready to POST
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

        # todo add check for whether to include this command type
        if True:
            commands += self._get_set_territory_name_commands()
        # todo add the rest of the commands
        return commands

    def _get_set_territory_name_commands(self) -> List[Command]:
        """
        Parses svg and creates a setTerritoryNameCommand for each path whose ID signifies it is a
        Warzone Territory (i.e. starts with the Warzone.TERRITORY_IDENTIFIER) and also has a title.
        :return:
        List of setTerritoryNameCommands
        """
        territory_nodes = self.svg.xpath(
            f".//{Svg.PATH}[contains(@{Svg.ID}, '{Warzone.TERRITORY_IDENTIFIER}') and {Svg.TITLE}]",
            namespaces=NAMESPACES
        )

        commands = [
            {
                'command': 'setTerritoryName',
                'id': self._get_territory_id(territory_node),
                'name': self._get_territory_name(territory_node)
            } for territory_node in territory_nodes
        ]
        return commands

    #################
    # PARSING UTILS #
    #################

    @staticmethod
    def _get_territory_id(territory: Union[str,  BaseElement]) -> int:
        if isinstance(territory, str):
            territory_id = territory.split(Warzone.TERRITORY_IDENTIFIER)[-1]
        elif isinstance(territory, PathElement):
            territory_id = WZMapBuilder._get_territory_id(territory.get(Svg.ID))
        elif territory.tag == get_uri(Svg.CLONE):
            territory_id = WZMapBuilder._get_territory_id(territory.get(get_uri(XLink.HREF)))
        else:
            raise ValueError(f'Element {territory} is not a valid territory element. It must be a'
                             f' path or a clone.')
        return int(territory_id)

    @staticmethod
    def _get_territory_name(territory_node: PathElement) -> str:
        title_node = territory_node.find(Svg.TITLE, NAMESPACES)
        if title_node is not None:
            territory_name = title_node.text
        else:
            territory_name = Warzone.UNNAMED_TERRITORY_NAME
        return territory_name


WZMapBuilder().run()
