Jesteś AI pomagającym w projekcie ai-gm (FastAPI + SQLite, Python).

⚠️ ZANIM cokolwiek zaimplementujesz — STOP i odpowiedz na pytania:
1. Czy tabele game_config_armor i game_config_shields już istnieją w DB? 
   (sprawdź przez: sqlite3 data/ai_gm.db ".tables")
2. Czy kolumny equipped i slot już istnieją w inventory_items?
3. Jak wygląda obecny system migracji? (sprawdź migrations_admin.py lub podobny plik)
4. Czy cokolwiek w istniejącym kodzie odwołuje się do inventory_items i może się 
   zepsuć po dodaniu kolumn?
5. Czy starter INSERT data nie koliduje z istniejącymi rekordami?

Jeśli znajdziesz JAKIKOLWIEK bloker lub ryzyko kolizji — opisz go i czekaj na moją decyzję.
Jeśli wszystko bezpieczne — napisz "✅ Brak blokerów, kontynuuję" i dopiero wtedy działaj.

---

Zadanie: Dodaj do bazy danych tabele pancerzy i tarcz.

Przeczytaj najpierw:
- backend/app/db.py
- backend/app/migrations_admin.py (lub plik migracji)
- data/ai_gm.db (sprawdź istniejące tabele)

Utwórz (lub uzupełnij) plik migracji o:

1. Tabelę game_config_armor:
   key TEXT UNIQUE, label TEXT, armor_type TEXT ('light'/'medium'/'heavy'),
   ac_bonus INTEGER, max_dex_bonus INTEGER DEFAULT 99,
   stealth_penalty INTEGER DEFAULT 0, weight INTEGER DEFAULT 0,
   description TEXT, is_active INTEGER DEFAULT 1

2. Tabelę game_config_shields:
   key TEXT UNIQUE, label TEXT, ac_bonus INTEGER,
   proficiency_required TEXT DEFAULT NULL,
   weight INTEGER DEFAULT 0, description TEXT, is_active INTEGER DEFAULT 1

3. Kolumny w inventory_items (jeśli nie istnieją):
   equipped INTEGER DEFAULT 0, slot TEXT ('armor'/'shield'/'weapon')

4. INSERT OR IGNORE starter danych:
   Pancerze: padded(+1), leather(+2), studded(+3), chain_shirt(+4,max_dex2),
             scale_mail(+4,max_dex2,stealth-2), breastplate(+5,max_dex2),
             chain_mail(+6,max_dex0,stealth-2), splint(+7,max_dex0,stealth-2),
             plate_mail(+8,max_dex0,stealth-2)
   Tarcze: wooden_shield(+2), steel_shield(+3,warrior), tower_shield(+4,warrior)

Migracja musi być idempotentna. Dodaj jej wywołanie do inicjalizacji DB.
Pokaż mi zmienione pliki przed zapisem.