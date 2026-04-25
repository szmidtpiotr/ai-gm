"""Slash command keys + default descriptions — shared by turns dispatcher and client_ui_config (no circular imports)."""

# Used by /help and the command dispatcher; admin-editable copy lives in client_ui_config / game_config_meta.
COMMAND_REGISTRY: dict[str, str] = {
    "/help": "Show this list of available commands",
    "/sheet": "Display your full character sheet",
    "/roll": "Roll d20 + modifier for the last GM-requested roll",
    "/name <new name>": "Rename your character",
    "/history": "Show the last 10 turns of the session",
    "/atak": "Stan aktywnej walki (wrogowie, HP, czyja tura) albo informacja, że walka nie trwa",
    "/mem [pytanie]": "Pytanie o przeszłość z podsumowań — bez wpływu na narrację (żółte dymki)",
    "/helpme [pytanie]": "Doradca OOC — wskazówki bez zmiany fabuły (czerwone dymki); nie wpływa na kontekst narracji",
    "/move [lokacja]": "Próba przejścia do wskazanej lokalizacji z walidacją integralności świata",
    "/export": "Export the full session to a text file on the server (/data/exports/)",
}
