import json
import math
import sys
from typing import Dict, List, Set
from pathlib import Path

from warzone_map_utils.constants import game_feed, paths


class Territory:
    def __init__(self, territory_id: int, name: str, connection_ids: Set[int] = None):
        self.territory_id = territory_id
        self.name = name
        self.connection_ids = connection_ids

    # noinspection PyShadowingBuiltins,PyPep8Naming
    @staticmethod
    def parse_territory_from_api(id: str, name: str, connectedTo: List[int]) -> 'Territory':
        return Territory(int(id), name, set(connectedTo))


class Bonus:

    # noinspection PyShadowingBuiltins
    def __init__(self, bonus_id: int, name: str, value: int, territory_ids: Set[int]):
        self.bonus_id = bonus_id
        self.name = name
        self.value = value
        self.territory_ids = territory_ids

    def __len__(self) -> int:
        return len(self.territory_ids)

    def validate(self) -> bool:
        return True

    # noinspection PyShadowingBuiltins,PyPep8Naming
    @staticmethod
    def parse_bonus_from_api(id: str, name: str, value: int, territoryIDs: List[int]) -> 'Bonus':
        return Bonus(bonus_id=int(id), name=name, value=int(value), territory_ids=set(territoryIDs))


class SubBonus(Bonus):

    INTENDED_VALUE_BY_SIZE: Dict[int, int] = {
        2: 1,
        3: -1,
        4: 2,
        5: -4,
        6: 8,
    }

    INTENDED_VALUE_BY_SIZE_FULL: Dict[int, int] = {
        2: 1,
        3: -2,
        4: 0,
        5: -6,
        6: 5,
    }

    def __init__(self, bonus_id: int, name: str, value: int, territory_ids: Set[int], base_bonus: 'BaseBonus'):
        super().__init__(bonus_id, name, value, territory_ids)
        self.base_bonus = base_bonus

    @property
    def intended_size(self) -> int:
        return int(self.name.split(' ')[-1][0]) + 1

    @property
    def intended_value(self) -> int:
        value_map = (
            SubBonus.INTENDED_VALUE_BY_SIZE_FULL if len(self) == len(self.base_bonus)
            else SubBonus.INTENDED_VALUE_BY_SIZE
        )
        return value_map[self.intended_size]

    def validate(self) -> bool:
        validates = True
        correct_size = len(self) == self.intended_size
        if not correct_size:
            print(f'Bonus {self.name} should have {self.intended_size} territories. It has {len(self)} territories.')
            validates = False

        correct_value = self.value == self.intended_value
        if not correct_value:
            print(f'Bonus {self.name} should have value {self.intended_value}. Value is {self.value}.')
            validates = False

        subset = not self.territory_ids - self.base_bonus.territory_ids
        if not subset:
            print(f'Bonus {self.name} should have no territories that are not in base bonus {self.base_bonus.name}.')
            validates = False

        return validates

    @staticmethod
    def get_base_bonus_name(sub_bonus_name: str) -> str:
        return ' '.join(sub_bonus_name[1:].split(' ')[:-1])

    @staticmethod
    def get_sub_bonus_size(sub_bonus_name: str) -> int:
        return int(sub_bonus_name.split(' ')[-1][0]) + 1


class BaseBonus(Bonus):

    INTENDED_VALUE_BY_SIZE: Dict[int, int] = {
        2: 0,
        3: 1,
        4: 2,
        5: 2,
        6: 3,
    }

    def __init__(self, bonus_id: int, name: str, value: int, territory_ids: Set[int], base_territory_id: int,
                 sub_bonuses: Dict[int, Set[SubBonus]] = None):
        super().__init__(bonus_id, name, value, territory_ids)
        self.base_territory_id = base_territory_id
        self.sub_bonuses = sub_bonuses if sub_bonuses else {i: set() for i in range(2, len(self) + 1)}

    @property
    def intended_value(self) -> int:
        return BaseBonus.INTENDED_VALUE_BY_SIZE[len(self)]

    @property
    def sea_territory_ids(self) -> Set[int]:
        return self.territory_ids - {self.base_territory_id}

    def validate(self) -> bool:
        # bonus has the correct value
        validates = True
        correct_value = self.value == self.intended_value
        if not correct_value:
            print(f'Bonus {self.name} should have value {self.intended_value}. Value is {self.value}.')
            validates = False

        for i, sub_bonuses in self.sub_bonuses.items():
            # bonus has the correct number of sub-bonuses
            correct_sub_bonus_count = len(sub_bonuses) == math.comb(len(self) - 1, i - 1)
            if not correct_sub_bonus_count:
                print(f'Bonus {self.name} should have {math.comb(len(self), i)} sub-bonuses of size {i}.'
                      f'There are {len(sub_bonuses)} sub-bonuses.')
                validates = False
            # all sub-bonuses have distinct subsets of territories
            distinct = len({tuple(sub_bonus.territory_ids) for sub_bonus in sub_bonuses}) == len(sub_bonuses)
            if not distinct:
                print(f'Bonus {self.name} should have no overlapping sub-bonuses of size {i}.')
                validates = False

            for sub_bonus in sub_bonuses:
                validates &= sub_bonus.validate()

        return validates


class Map:
    def __init__(self, map_id: int, name: str, territories: Dict[int, Territory], bonuses: Dict[int, Bonus]):
        self.map_id = map_id
        self.name = name
        self.territories = territories
        self.bonuses = bonuses

    @classmethod
    def parse_territories_from_api(cls, territories: List[Dict]) -> Dict[int, Territory]:
        return {int(territory['id']): Territory.parse_territory_from_api(**territory) for territory in territories}

    @classmethod
    def parse_bonuses_from_api(cls, bonuses: List[Dict]) -> Dict[int, Bonus]:
        return {int(bonus['id']): Bonus.parse_bonus_from_api(**bonus) for bonus in bonuses}

    # noinspection PyShadowingBuiltins
    @classmethod
    def parse_map_from_api(cls, id: str, name: str, territories: List[Dict], bonuses: List[Dict], **kwargs) -> 'Map':
        territories = cls.parse_territories_from_api(territories)
        bonuses = cls.parse_bonuses_from_api(bonuses)
        return Map(int(id), name, territories, bonuses)


class EarthseaMap(Map):
    OCEAN_BONUS_ID = 1

    @property
    def ocean_bonus(self) -> Bonus:
        return self.bonuses[self.OCEAN_BONUS_ID]

    # noinspection PyShadowingBuiltins
    @classmethod
    def parse_map_from_api(cls, id: str, name: str, territories: List[Dict], bonuses: List[Dict],
                           **kwargs) -> 'EarthseaMap':
        territories = cls.parse_territories_from_api(territories)
        all_bonuses = cls.parse_bonuses_from_api(bonuses)

        territory_name_map: Dict[str, Territory] = {territory.name: territory for territory in territories.values()}

        ocean_bonus = all_bonuses[EarthseaMap.OCEAN_BONUS_ID]
        bonuses = {ocean_bonus.name: ocean_bonus}
        for bonus in all_bonuses.values():
            if '~' not in bonus.name and bonus != ocean_bonus:
                base_territory_id = territory_name_map[bonus.name].territory_id
                bonuses[bonus.name] = BaseBonus(**vars(bonus), base_territory_id=base_territory_id)

        for bonus in all_bonuses.values():
            if '~' in bonus.name:
                base_bonus_name = SubBonus.get_base_bonus_name(bonus.name)
                sub_bonus_size = SubBonus.get_sub_bonus_size(bonus.name)
                base_bonus = bonuses[base_bonus_name]

                sub_bonus = SubBonus(**vars(bonus), base_bonus=base_bonus)
                base_bonus.sub_bonuses[sub_bonus_size].add(sub_bonus)

        bonuses = {bonus.bonus_id: bonus for bonus in bonuses.values()}
        return EarthseaMap(int(id), name, territories, bonuses)

    def validate_ocean_bonus(self) -> bool:
        base_bonuses = {bonus for bonus in self.bonuses.values() if type(bonus) == BaseBonus}
        base_territory_ids = {bonus.base_territory_id for bonus in base_bonuses}

        overlap = base_territory_ids & self.ocean_bonus.territory_ids
        if overlap:
            print(f'The ocean and the base territories should be disjoint sets. {overlap} are in both sets.')

        incomplete = (
                {territory_id for territory_id in self.territories.keys()}
                - base_territory_ids | self.ocean_bonus.territory_ids
        )
        if incomplete:
            print(f'The ocean and base territories should contain all territories. {incomplete} are in neither set.')

        return not overlap and not incomplete

    def validate_base_bonus(self, base_bonus: BaseBonus) -> bool:
        base_territory = self.territories[base_bonus.base_territory_id]

        expected_sea_territory_ids = base_territory.connection_ids & self.ocean_bonus.territory_ids
        correct_territories = expected_sea_territory_ids == base_bonus.sea_territory_ids
        if not correct_territories:
            print(f'Bonus {base_bonus.name} should include all sea territories that border {base_territory.name}.')

        return correct_territories & base_bonus.validate()

    def validate(self) -> bool:
        validates = self.validate_ocean_bonus()
        for bonus in self.bonuses.values():
            validates &= bonus.validate()
        return validates


def validate_earthsea_map(game_json_path: Path) -> None:
    with open(paths.BASE_DIR / game_json_path) as f:
        game_data = json.load(f)

    earthsea_map = EarthseaMap.parse_map_from_api(**game_data[game_feed.MAP_NODE_NAME])
    if earthsea_map.validate():
        print('All bonuses validate.')


if __name__ == "__main__":
    validate_earthsea_map(*sys.argv[1:])
