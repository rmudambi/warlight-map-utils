from warzone_map_utils.constants import svg


def get_uri(key: str) -> str:
    if ':' in key:
        namespace, key = key.split(':')
        key = f'{{{svg.NAMESPACES[namespace]}}}{key}'
    return key


def get_bonus_link_id(bonus_name: str) -> str:
    return svg.BONUS_LINK_IDENTIFIER + ''.join(filter(str.isalnum, bonus_name))

