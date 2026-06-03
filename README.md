# Autoresearch PHP

Version PHP autonome d'Autoresearch pour organiser des projets de recherche, sources, notes, constats et taches.

## Prerequis

- PHP 8.1 ou plus recent
- Extension PDO SQLite activee

## Lancer en local

```powershell
php -S 127.0.0.1:8000 -t public
```

Puis ouvrir:

```text
http://127.0.0.1:8000
```

La base SQLite est creee automatiquement dans `data/autoresearch.sqlite`.

## Fonctionnalites

- Tableau de bord des projets
- Creation et edition de projets de recherche
- Gestion des sources par projet
- Notes, constats et taches
- Recherche transversale dans les projets, sources, notes et constats
- Export Markdown d'un projet
- Application sans dependance Composer

