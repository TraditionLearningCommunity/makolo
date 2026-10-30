# Donnees de demonstration Makolo — volume et operations

## But

Tester de vrais parcours de bout en bout avec des faits **synthetiques** en restant sur une seule base SQLite, sans copie ni backup automatique : profils, Activity/Occurrence, Journey, Access/AccessCredential/AccessUse, Operations (Checkpoint et Queue), Scanner, Event/Ticket/Commerce et Payment sandbox.

La demo ne remplace ni les permissions serveur, ni les transitions de statut, ni les preuves de paiement reelles. Les actions sont executees par les services canoniques. **Ne jamais executer sur production.**

## Modules et couverture

| Module | Script / option | Contrat |
| --- | --- | --- |
| Calendrier maintenant/soir/demain | `scripts/makolo_demo_clock.py --demo-live` | Repositionnement temporel |
| Journey massives | `scripts/makolo_demo_scale.py --journeys N` | create/submit/confirm, selection `world_*` |
| Access et credentials | `--accesses N` | issue_access |
| Checkpoints et files Live | `--queues N --queue-advance served` | open_checkpoint, enter_queue, call_next, serve_entry |
| Mandates demo scopes | `--grant-demo-roles` | grant_activity_role, Activity seulement |
| Scanner Event | `--scans N` | scan_ticket, doublon et token invalide |
| Ticket / Offer / Capacity | `--orders N` | configure_ticket_type, create_order |
| Payment | `--orders N` | initiate_payment / complete_sandbox_payment, seulement si sandbox active |
| Transport | `scripts/makolo_demo_transport.py` | Activity, Occurrence, reservation, AccessUse, queue |
| Inventaire des modeles | `--inventory` | Comptage en lecture seule de tous les modeles Django |

**Les autres domaines (Trust, Resources, CRM, Automation, Proof, Notifications, etc.) ne sont pas generes artificiellement par ce premier lot.** Le rapport d'inventaire sert a mesurer precisement les lacunes; chaque domaine requiert son propre contrat et des services de production/adaptation demo, et non une insertion SQL aveugle.

## Commandes Windows PowerShell (racine du depot)

```powershell
git pull --ff-only
python -m py_compile scripts/makolo_demo_scale.py scripts/makolo_demo_transport.py
python manage.py check
python scripts/makolo_demo_scale.py --journeys 10000 --accesses 10000 --queues 30 --queue-advance served --scans 500 --orders 100 --grant-demo-roles
python scripts/makolo_demo_transport.py
```

Lorsque les apercus sont corrects :

```powershell
python scripts/makolo_demo_scale.py --journeys 10000 --accesses 10000 --queues 30 --scans 500 --orders 100 --grant-demo-roles --apply
python scripts/makolo_demo_transport.py --apply
python scripts/makolo_demo_scale.py --inventory
```

**Ordre logique:** les Journeys sont preparees avant les Access; les Access avant les scans; les roles de Scanner et Operations restent distincts. Si `PAYMENTS_SANDBOX_ENABLED` est faux, les commandes payantes restent en attente, aucune confirmation n'est inventee.

Le volume 10 000 represente jusqu'a 10 000 paires distinctes Occurrence/Profile eligibles et jusqu'a 10 000 Journey equipees d'un Access selon la presence de Journey; ce n'est pas une promesse de 10 000 scans acceptes le meme jour. Le nombre effectif et les causes de refus figurent dans les compteurs.

Le script impose un seuil de taille SQLite par defaut (450 MiB) pour limiter le risque de remplir les 512 Mo de PythonAnywhere. Ce seuil ne remplace pas une verification des quotas, fichiers journaux et autres usages du disque. Aucun fichier `.backup` ni clone de base n'est genere.

## Verification fonctionnelle

- Comparer les compteurs du script a la projection Live du Profil connecte, puis a celle de l'operateur.
- Tester un scan accepte, un deuxieme scan du meme credential (duplicate), et un QR invalide.
- Verifier que `beta_scanner` / `beta_transport_operator` restent non-staff et non-superuser.
- Verifier qu'une Activity non-demo ne recoit aucun nouveau Mandate.
- Le script transport cree des **AccessUse** pour ses voyages; un **ScanLog** n'est produit que sur le domaine Event par `scan_ticket`.
- Controler `python manage.py check` puis les tests cibles des domaines touches avant tout merge.

## Limites

Une Activity synthétique ne constitue pas un service reel du monde physique. Les scans et paiements sandbox sont des faits de simulation techniques, marques dans leurs metadata/source. Certains modeles Django doivent rester vides sans contexte source; ne pas remplir les tables par seul objectif statistique.

Aucune migration n'est requise pour ces scripts. Les scripts ne modifient pas `main` et ne suppriment aucune ligne metier.
