NAMESPACES = {
    'svg': 'http://www.w3.org/2000/svg',
    'inkscape': 'http://www.inkscape.org/namespaces/inkscape',
    'xlink': 'http://www.w3.org/1999/xlink',
}


#################
# SVG CONSTANTS #
#################

class Svg:
    ID = 'id'
    GROUP = 'svg:g'
    PATH = 'svg:path'
    TITLE = 'svg:title'
    CLONE = 'svg:use'

    STYLE = 'style'
    FILL = 'fill'


######################
# INKSCAPE CONSTANTS #
######################

class Inkscape:
    LABEL = 'inkscape:label'


###################
# COLOR CONSTANTS #
###################

class Color:
    BLACK = '#000000'


###################
# XLINK CONSTANTS #
###################

class XLink:
    HREF = 'xlink:href'

#####################
# WARZONE CONSTANTS #
#####################


class Warzone:
    TERRITORY_IDENTIFIER = 'Territory_'
    BONUS_LINK_IDENTIFIER = 'BonusLink_'

###################
# LAYER CONSTANTS #
###################


class Map:
    BONUS_LINKS_LAYER = 'WZ:BonusLinks'
    TERRITORIES_LAYER = 'WZ:Territories'
    BACKGROUND_LAYER = 'Background'

    METADATA_LAYER = 'WZ:Metadata'
    BONUSES_LAYER = 'WZ:Bonuses'
    DISTRIBUTION_MODES_LAYER = 'WZ:DistributionModes'
