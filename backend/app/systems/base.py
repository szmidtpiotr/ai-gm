from typing import Protocol

class SystemAdapter(Protocol):
    system_id: str

    def create_default_sheet(self, player_name: str) -> dict: ...
    def list_supported_commands(self) -> list[str]: ...
