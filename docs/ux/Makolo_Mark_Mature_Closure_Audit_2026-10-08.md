# Makolo Mark — Mature Closure Audit — 2026-10-08

## BASE
- origin/main revalidé via GitHub : 52eced16a35d779f98eb8d43bbea405fd7f7b4b0
- branche : feat/makolo-mark-mature
- merge base : 52eced16a35d779f98eb8d43bbea405fd7f7b4b0

## OPEN PRS
- #501 — feat: close Moi and Nous mature surfaces — ouverte

## COLLISION AUDIT
#501 modifie :
- core/mature_experience_views.py
- mobile/lib/features/space/space_shell_routes.dart
- organizations/space_web_views.py
- templates/core/participant_me.html
- templates/organizations/space/us.html
- tests/docs Moi/Nous associés

Cette lane évite volontairement core/mature_experience_views.py, mobile/lib/features/space/space_shell_routes.dart et organizations/space_web_views.py.
Le Mark Web Space est fermé dans organizations/space_ws5_web.py/template spécialisé et l'API reste dans organizations/api/space_mark_views.py.

## EXISTING
- orchestrateur personnel owner-backed : core/mark_orchestration.py
- API personnel : POST /api/v1/me/mark/
- orchestrateur Space : organizations/api/space_mark_projection.py
- API Space : POST /api/v1/organizations/workspaces/<slug>/mark/
- Actor Context Profile/Space explicite et persistant
- local_drafts + FileRecords + ProfileFileStore
- native file picker + image picker + permission gateway
- Mark central et asset officiel Flutter
- Web personnel texte/clarification/handoff
- Web Space Jour J/Scanner/Team/confirmation/authority revalidation

## MISSING / PARTIAL BEFORE LANE
- Flutter Mark était un placeholder.
- client mobile n'avait pas de repository Mark.
- drafts Mark n'étaient pas composés par Actor Context.
- Web Space Mark utilisait une grammaire visuelle plus administrative.
- API response n'exposait pas explicitement actor_context / accepted_input_kinds / request_context.
- multimodal serveur reste capability-gated : aucun faux traitement ajouté.
- voice transcription n'est pas exposée par le runtime actuel.

## PLAN
- stabiliser response metadata sans changer les owners ;
- fermer Flutter Mark texte + draft + offline + native document/photo intake ;
- garder voice explicitement unsupported tant qu'aucun owner de transcription n'existe ;
- aligner Web Space sur la grammaire Personal ;
- ajouter tests contractuels ciblés ;
- réconcilier main/#501 avant merge ;
- aucune migration.

## MATRICE
| Exigence | Statut |
|---|---|
| MARK_SINGLE_EXPERIENCE | PASS |
| PROFILE_ACTOR_CONTEXT | PASS |
| SPACE_ACTOR_CONTEXT | PASS |
| ACTOR_SWITCH_EXPLICIT | PASS |
| REQUEST_CONTRACT | PASS |
| RESPONSE_CONTRACT | PARTIAL |
| PERSONAL_SERVER_ORCHESTRATION | PASS |
| SPACE_SERVER_ORCHESTRATION | PASS |
| AUTHORITY_REVALIDATION | PASS |
| RESPONSIBILITY_NOT_AUTHORITY | PASS |
| PERSONAL_WEB | PASS |
| SPACE_WEB | PASS |
| FLUTTER_PROFILE | PASS |
| FLUTTER_SPACE | PASS |
| TEXT_INTAKE | PASS |
| ATTACHMENT_INTAKE | PARTIAL — local intake Flutter, owner upload absent |
| PHOTO_INTAKE | PARTIAL — local capture Flutter, owner upload absent |
| VOICE_CAPABILITY | PARTIAL — honnêtement unsupported |
| LINK_INTAKE | PARTIAL — selected URL n'est pas encore un intake client dédié |
| SELECTED_CONTEXT | PASS — API contract; UI deep-context injection reste à compléter |
| MULTI_INTENT | PARTIAL — orchestrateurs déterministes existants, pas de nouveau classifier |
| CLARIFICATION | PASS |
| UNKNOWN | PASS |
| UNSUPPORTED | PASS |
| FORBIDDEN | PASS |
| CONFIRMATION | PASS |
| OWNER_HANDOFF | PASS |
| DISCOVERY_HANDOFF | PASS |
| JOUR_J_HANDOFF | PASS |
| LIVE_HANDOFF | PASS |
| SCANNER_HANDOFF | PASS |
| LOCAL_DRAFT | PASS |
| OFFLINE_DRAFT | PASS |
| CRASH_RECOVERY | PARTIAL — draft restoration + media recovery kernel, parcours Mark complet non fermé |
| NO_BLIND_RETRY | PASS |
| PROFILE_SPACE_PRIVACY | PASS |
| BACK_RESTORE | PARTIAL |
| RESUME | PARTIAL |
| COMPACT | PASS |
| MEDIUM | PASS |
| WIDE | PASS |
| TEXT_SCALE | PASS — composition bornée, contrôles accessibles |
| REDUCE_MOTION | PARTIAL — aucune animation Mark spécifique ajoutée dans cette lane |

## MERGE GATE
Cette matrice contient encore des PARTIAL sur des critères de fermeture MUST. La PR doit donc rester ouverte jusqu'à résolution ou acceptation explicite de l'intégrateur.
