# UI Data Contract Examples

Use these examples to design realistic table rows and form states in Figma.

## Stats row
- key: `STR`
- label: `Strength`
- description: `Physical power and melee force`
- sort_order: `1`
- locked_at: `2026-04-14T00:00:00Z` (shows lock badge)

## Skill row
- key: `athletics`
- label: `Athletics`
- linked_stat: `STR`
- rank_ceiling: `5`
- description: `Climbing, jumping, lifting, sprinting`
- sort_order: `2`

## DC row
- key: `hard`
- label: `Hard`
- value: `16`
- description: `Demanding attempt with meaningful failure risk`
- sort_order: `3`

## Weapon row
- key: `shortsword`
- label: `Short Sword`
- damage_die: `d6`
- linked_stat: `STR`
- allowed_classes: `warrior,ranger`
- is_active: `1`

## Enemy row
- key: `goblin`
- label: `Goblin`
- hp_base: `8`
- ac_base: `11`
- attack_bonus: `2`
- damage_die: `d6`
- description: `Fast and opportunistic skirmisher`
- is_active: `1`

## Condition row
- key: `poisoned`
- label: `Poisoned`
- effect_json: `{"stat_mods":{"STR":-2},"duration":"3 turns"}`
- description: `Temporary STR penalty`
- is_active: `1`

## User LLM form example
- provider: `openai`
- base_url: `https://api.llmapi.ai`
- model: `gpt-4o`
- api_key: masked input

## Error/validation examples (for UI states)
- invalid `damage_die` -> show inline error under field
- invalid `linked_stat` -> show inline error + red border
- locked row save without force -> show warning dialog
- referenced weapon delete -> show conflict message
