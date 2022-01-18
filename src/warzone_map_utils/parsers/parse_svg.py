from xml.dom.minidom import parse


def parse_map_svg(map_path: str) -> None:
    # map_path = Path('/home/sklempt/warzone/warlight-maps/earthsea/small-map/earthsea-small.svg')

    parser = parse(str(map_path))
    paths = parser.getElementsByTagName('path')
    territories = [path for path in paths if 'Territory_' in path.getAttribute('id')]
    for territory in territories:
        print(territory.getAttribute('name'))
