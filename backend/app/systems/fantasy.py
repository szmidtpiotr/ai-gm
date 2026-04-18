class FantasySystem:
    system_id = "fantasy"

    def create_default_sheet(self, player_name: str) -> dict:
        might = 2
        agility = 1
        wits = 1
        will = 0

        return {
            "name": player_name,
            "class": "adventurer",
            "level": 1,
            "xp": 0,
            "attributes": {
                "might": might,
                "agility": agility,
                "wits": wits,
                "will": will
            },
            "skills": {
                "melee": 2,
                "ranged": 0,
                "athletics": 2,
                "stealth": 0,
                "lore": 0,
                "notice": 2,
                "survival": 0,
                "persuasion": 0,
                "intimidation": 0,
                "craft": 0,
                "magic": 0,
                "healing": 0
            },
            "resources": {
                "health": {
                    "current": 10 + might,
                    "max": 10 + might
                },
                "focus": {
                    "current": 5 + will,
                    "max": 5 + will
                },
                "defense": 10 + agility
            },
            "inventory": {
                "slots_max": 8 + might,
                "coins": 10
            },
            "conditions": [],
            "equipped": {
                "weapon": "rusty sword",
                "armor": "leather jack"
            },
            "notes": [],
            "identity": {
                "appearance": "",
                "personality": "",
                "flaw": "",
                "bonds": [{"text": "", "strength": "strong", "origin": "creation"}],
                "secret": "",
            },
        }

    def list_supported_commands(self) -> list[str]:
        return ["/help", "/name", "/sheet", "/inv", "/roll", "/say", "/do", "/ooc", "/mem", "/helpme"]