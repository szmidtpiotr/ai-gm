# AI-GM UI Brief for Figma

Project surfaces:
- Player frontend (`frontend/index.html`, `frontend/styles.css`, `frontend/js/*`)
- Admin frontend (`frontend/admin.html`, `frontend/admin.css`, `frontend/js/admin.js`)

Design goals:
- Chat-first UX for player.
- Data-dense but readable admin CRUD UI.
- Consistent components across player and admin surfaces.
- Mobile-first behavior with desktop-ready layout.

Current UX constraints implemented in code:
1. Player login gate must block app content before authentication.
2. LLM settings panel is collapsed by default but always accessible.
3. Admin panel is tab-based with inline table editing.
4. Lock-aware editing exists (`locked_at` + force override).

Current admin tabs:
- Stats
- Skills
- DC
- Weapons
- Enemies
- Conditions
- Accounts
- User LLM

Visual direction:
- Clean, high-contrast, operator-style dark UI.
- Strong hierarchy and scanability.
- Clear distinction between secondary and destructive actions.

Expected Figma deliverables:
1. Player desktop layout.
2. Admin desktop layout including all tabs.
3. Reusable components:
   - Buttons (primary/secondary/danger/disabled)
   - Inputs/selects/textarea
   - Tabs
   - Panels/cards
   - Table rows with inline actions
   - Lock badge
4. State variants:
   - hover/focus/disabled/error/loading
5. Tokenized spacing/typography/colors.

Token guidance:
- 8px spacing scale.
- Semantic color tokens: background/surface/border/text/accent/success/warning/danger.
- Radius tokens: small/medium/large.

Implementation guidance:
- Keep design compatible with current `styles.css` and `admin.css`.
- Prefer incremental migration over full one-shot rewrite.
