from .fantasy import FantasySystem

SYSTEMS = {
    "fantasy": FantasySystem(),
}

def get_system(system_id: str):
    return SYSTEMS.get(system_id)
