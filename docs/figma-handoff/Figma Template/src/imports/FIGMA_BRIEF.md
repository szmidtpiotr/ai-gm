# AI-GM UI Brief for Figma

Project:
- AI-GM RPG web app with two primary surfaces:
  - Player frontend (`frontend/index.html`, `frontend/styles.css`, `frontend/js/*`)
  - Admin frontend (`frontend/admin.html`, `frontend/admin.css`, `frontend/js/admin.js`)

Design goals:
- Chat-first UX for player.
- Data-dense but readable admin CRUD UI.
- Component consistency between player and admin views.
- Mainly for mobile, but good lookin on desktop

Hard UX constraints (already implemented in app logic):
1. Player must log in before app content is visible.
2. LLM settings panel is collapsed by default but always accessible.
3. Admin panel uses tabbed sections and inline table editing.
4. Lock-aware editing flow exists (`locked_at` + force override).

Current admin sections:
- Stats
- Skills
- DC
- Weapons
- Enemies
- Conditions
- Accounts
- User LLM

Visual direction:
- Crisp, utility-forward sci-fi/fantasy operator panel.
- Avoid decorative noise; prioritize scanability and action clarity.
- Distinguish normal action vs destructive action clearly.

Deliverables expected from Figma:
1. Desktop layout for Player view.
2. Desktop layout for Admin view with all tabs.
3. Reusable components:
   - Button (primary/secondary/danger/disabled)
   - Input / Select / Textarea
   - Tab button
   - Card / Panel
   - Table row with inline actions
   - Lock badge
4. States:
   - hover / focus / disabled / error / loading
5. Spacing + typography tokens.

Token guidance:
- Prefer an 8px spacing scale.
- Define color tokens with semantic names:
  - bg/surface/border/text-muted/text-primary/accent/success/warning/danger
- Radius scale:
  - sm / md / lg

Implementation note for Codex:
- Keep generated styles compatible with existing `styles.css` and `admin.css`.
- Favor incremental migration, not full rewrite in one step.
