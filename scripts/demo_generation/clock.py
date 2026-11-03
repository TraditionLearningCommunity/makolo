#!/usr/bin/env python3
"""Recaler les dates metier d'une SQLite de demonstration Makolo.

Sans dependance externe. Aucun CREATE/DROP. --apply modifie en place sans copie.
Une copie (--output) ou une sauvegarde (--backup) sont exclusivement optionnelles.
Les dates d'audit (created_at/updated_at) ne sont jamais modifiees.
"""
import argparse
import datetime as dt
import hashlib
import os
from pathlib import Path
import shutil
import sqlite3
import sys
from zoneinfo import ZoneInfo

UTC = dt.timezone.utc
FIELDS = {
    'activities_occurrence': ('start_at','end_at','start_date','end_date','schedule_local_date'),
    'access_access': ('valid_from','valid_until'),
    'access_accesscredential': ('issued_at','revoked_at','expired_at'),
    'access_accessuse': ('used_at',),
    'journeys_journey': ('expires_at','submitted_at','confirmed_at','fulfilled_at','cancelled_at','started_at'),
}

# Audit-safe, closed SQL vocabulary. Identifiers are fixed in source and never
# assembled from external input; all row identifiers and values are parameters.
FIELD_QUERIES = {
    ('activities_occurrence', 'start_at'): ('SELECT "start_at" FROM "activities_occurrence" WHERE id=?', 'UPDATE "activities_occurrence" SET "start_at"=? WHERE id=?'),
    ('activities_occurrence', 'end_at'): ('SELECT "end_at" FROM "activities_occurrence" WHERE id=?', 'UPDATE "activities_occurrence" SET "end_at"=? WHERE id=?'),
    ('activities_occurrence', 'start_date'): ('SELECT "start_date" FROM "activities_occurrence" WHERE id=?', 'UPDATE "activities_occurrence" SET "start_date"=? WHERE id=?'),
    ('activities_occurrence', 'end_date'): ('SELECT "end_date" FROM "activities_occurrence" WHERE id=?', 'UPDATE "activities_occurrence" SET "end_date"=? WHERE id=?'),
    ('activities_occurrence', 'schedule_local_date'): ('SELECT "schedule_local_date" FROM "activities_occurrence" WHERE id=?', 'UPDATE "activities_occurrence" SET "schedule_local_date"=? WHERE id=?'),
    ('access_access', 'valid_from'): ('SELECT "valid_from" FROM "access_access" WHERE id=?', 'UPDATE "access_access" SET "valid_from"=? WHERE id=?'),
    ('access_access', 'valid_until'): ('SELECT "valid_until" FROM "access_access" WHERE id=?', 'UPDATE "access_access" SET "valid_until"=? WHERE id=?'),
    ('access_accesscredential', 'issued_at'): ('SELECT "issued_at" FROM "access_accesscredential" WHERE id=?', 'UPDATE "access_accesscredential" SET "issued_at"=? WHERE id=?'),
    ('access_accesscredential', 'revoked_at'): ('SELECT "revoked_at" FROM "access_accesscredential" WHERE id=?', 'UPDATE "access_accesscredential" SET "revoked_at"=? WHERE id=?'),
    ('access_accesscredential', 'expired_at'): ('SELECT "expired_at" FROM "access_accesscredential" WHERE id=?', 'UPDATE "access_accesscredential" SET "expired_at"=? WHERE id=?'),
    ('access_accessuse', 'used_at'): ('SELECT "used_at" FROM "access_accessuse" WHERE id=?', 'UPDATE "access_accessuse" SET "used_at"=? WHERE id=?'),
    ('journeys_journey', 'expires_at'): ('SELECT "expires_at" FROM "journeys_journey" WHERE id=?', 'UPDATE "journeys_journey" SET "expires_at"=? WHERE id=?'),
    ('journeys_journey', 'submitted_at'): ('SELECT "submitted_at" FROM "journeys_journey" WHERE id=?', 'UPDATE "journeys_journey" SET "submitted_at"=? WHERE id=?'),
    ('journeys_journey', 'confirmed_at'): ('SELECT "confirmed_at" FROM "journeys_journey" WHERE id=?', 'UPDATE "journeys_journey" SET "confirmed_at"=? WHERE id=?'),
    ('journeys_journey', 'fulfilled_at'): ('SELECT "fulfilled_at" FROM "journeys_journey" WHERE id=?', 'UPDATE "journeys_journey" SET "fulfilled_at"=? WHERE id=?'),
    ('journeys_journey', 'cancelled_at'): ('SELECT "cancelled_at" FROM "journeys_journey" WHERE id=?', 'UPDATE "journeys_journey" SET "cancelled_at"=? WHERE id=?'),
    ('journeys_journey', 'started_at'): ('SELECT "started_at" FROM "journeys_journey" WHERE id=?', 'UPDATE "journeys_journey" SET "started_at"=? WHERE id=?'),
}
RELATION_QUERIES = {
    ('access_access', 'occurrence_id'): 'SELECT id FROM "access_access" WHERE "occurrence_id"=?',
    ('access_accesscredential', 'access_id'): 'SELECT id FROM "access_accesscredential" WHERE "access_id"=?',
    ('access_accessuse', 'occurrence_id'): 'SELECT id FROM "access_accessuse" WHERE "occurrence_id"=?',
    ('access_accessuse', 'access_id'): 'SELECT id FROM "access_accessuse" WHERE "access_id"=?',
    ('journeys_journey', 'occurrence_id'): 'SELECT id FROM "journeys_journey" WHERE "occurrence_id"=?',
}
OPERATION_COUNT_QUERIES = {
    'operations_occurrencecheckpoint': 'SELECT COUNT(DISTINCT occurrence_id) FROM "operations_occurrencecheckpoint" WHERE occurrence_id IS NOT NULL',
    'operations_occurrencequeue': 'SELECT COUNT(DISTINCT occurrence_id) FROM "operations_occurrencequeue" WHERE occurrence_id IS NOT NULL',
    'scanner_scannerassignment': 'SELECT COUNT(DISTINCT occurrence_id) FROM "scanner_scannerassignment" WHERE occurrence_id IS NOT NULL',
    'access_access': 'SELECT COUNT(DISTINCT occurrence_id) FROM "access_access" WHERE occurrence_id IS NOT NULL',
}
OPERATION_ACTIVE_QUERIES = {
    'operations_occurrencecheckpoint': 'SELECT 1 FROM "operations_occurrencecheckpoint" WHERE occurrence_id=? LIMIT 1',
    'operations_occurrencequeue': 'SELECT 1 FROM "operations_occurrencequeue" WHERE occurrence_id=? LIMIT 1',
    'scanner_scannerassignment': 'SELECT 1 FROM "scanner_scannerassignment" WHERE occurrence_id=? LIMIT 1',
    'access_access': 'SELECT 1 FROM "access_access" WHERE occurrence_id=? LIMIT 1',
}

def parsed(value):
    if not value:
        return None
    try:
        p=dt.datetime.fromisoformat(str(value).replace('Z','+00:00'))
        return p.replace(tzinfo=UTC) if p.tzinfo is None else p.astimezone(UTC)
    except ValueError:
        return None

def shift_text(value, delta, kind):
    if value is None:
        return None
    if kind=='date':
        try: return (dt.date.fromisoformat(str(value)[:10])+delta).isoformat()
        except ValueError: return value
    p=parsed(value)
    if p is None: return value
    moved=p+delta
    # SQLite / Django DateTime storage: keep naive UTC if original was naive.
    if dt.datetime.fromisoformat(str(value).replace('Z','+00:00')).tzinfo is None:
        moved=moved.replace(tzinfo=None)
    return moved.isoformat(sep=' ')

def table_columns(db, table):
    # SQLite's table-valued pragma accepts the table name as a bound value.
    return {row[0] for row in db.execute('SELECT name FROM pragma_table_info(?)', (table,))}

def update_by_id(db, table, identifier, fields, delta):
    cols = table_columns(db, table)
    changed = False
    for field in fields:
        if field not in cols:
            continue
        select_sql, update_sql = FIELD_QUERIES[(table, field)]
        row = db.execute(select_sql, (identifier,)).fetchone()
        if row is None:
            return int(changed)
        previous = row[0]
        kind = 'date' if field.endswith('_date') or field == 'schedule_local_date' else 'datetime'
        next_value = shift_text(previous, delta, kind)
        if previous != next_value:
            db.execute(update_sql, (next_value, identifier))
            changed = True
    return int(changed)

def ids(db, table, foreign_key, identifier):
    if foreign_key not in table_columns(db, table):
        return []
    return [row[0] for row in db.execute(RELATION_QUERIES[(table, foreign_key)], (identifier,))]

def move_occurrence(db, occ_id, delta):
    counts={t:0 for t in FIELDS}
    counts['activities_occurrence']+=update_by_id(db,'activities_occurrence',occ_id,FIELDS['activities_occurrence'],delta)
    accesses=ids(db,'access_access','occurrence_id',occ_id)
    for aid in accesses:
        counts['access_access']+=update_by_id(db,'access_access',aid,FIELDS['access_access'],delta)
        for cred in ids(db,'access_accesscredential','access_id',aid):
            counts['access_accesscredential']+=update_by_id(db,'access_accesscredential',cred,FIELDS['access_accesscredential'],delta)
    uses=set(ids(db,'access_accessuse','occurrence_id',occ_id))
    for aid in accesses: uses.update(ids(db,'access_accessuse','access_id',aid))
    for uid in uses: counts['access_accessuse']+=update_by_id(db,'access_accessuse',uid,FIELDS['access_accessuse'],delta)
    for jid in ids(db,'journeys_journey','occurrence_id',occ_id):
        counts['journeys_journey']+=update_by_id(db,'journeys_journey',jid,FIELDS['journeys_journey'],delta)
    return counts

def target_for(occ_id, now, duration):
    # Reproductible par identifiant: environ 15 % en cours, 15 % imminentes,
    # 45 % prochaines semaines, 25 % passe recent.
    h=int(hashlib.sha256(str(occ_id).encode()).hexdigest()[:12],16)
    band=h%100
    if band<15: return now-dt.timedelta(minutes=30+(h//100)%90)
    if band<30: return now+dt.timedelta(minutes=5+(h//100)%175)
    if band<75: return now+dt.timedelta(days=1+(h//100)%63,hours=(h//10000)%24)
    return now-dt.timedelta(days=1+(h//100)%21,hours=(h//10000)%24)


def demo_slot(occ_id, index, now, timezone):
    """Horaires garantis pour les premiers candidats; repartition stable entre executions."""
    local=now.astimezone(timezone)
    today=local.date()
    tomorrow=today+dt.timedelta(days=1)
    def wall(day,hour,minute=0):
        return dt.datetime.combine(day,dt.time(hour,minute),tzinfo=timezone).astimezone(UTC)
    slot=index%12
    options=[
        now-dt.timedelta(minutes=35),               # en cours, si duree >= 35 min
        now-dt.timedelta(minutes=15),
        now+dt.timedelta(minutes=15),
        now+dt.timedelta(minutes=45),
        wall(today,14),
        wall(today,16),
        wall(today,19),
        wall(today,21),
        wall(tomorrow,8),
        wall(tomorrow,10),
        wall(tomorrow,15),
        wall(tomorrow,19),
    ]
    # Pas de slots "ce soir" dans le passe apres 19h: ils passent au soir suivant.
    result=options[slot]
    if slot in (4,5,6,7) and result<now:
        result=result+dt.timedelta(days=1)
    return result


def live_coverage(db, now, timezone):
    """Etat observable, sans inventer de permissions ni de donnees operationnelles."""
    cols=table_columns(db,'activities_occurrence')
    if not {'start_at','end_at'} <= cols:
        return {'error':'schema occurrence incompatible'}
    entries=db.execute('SELECT id,start_at,end_at FROM activities_occurrence WHERE start_at IS NOT NULL AND end_at IS NOT NULL').fetchall()
    today=now.astimezone(timezone).date()
    windows={'now':0,'next_2h':0,'today_later':0,'tonight':0,'tomorrow':0}
    active_ids=[]
    for ident,raw_start,raw_end in entries:
        start,end=parsed(raw_start),parsed(raw_end)
        if not start or not end: continue
        local=start.astimezone(timezone)
        if start<=now<end:
            windows['now']+=1
            active_ids.append(ident)
        if now<start<=now+dt.timedelta(hours=2): windows['next_2h']+=1
        if local.date()==today and start>now: windows['today_later']+=1
        if local.date()==today and local.hour>=18 and start>now: windows['tonight']+=1
        if local.date()==today+dt.timedelta(days=1): windows['tomorrow']+=1
    operational={}
    for table in ('operations_occurrencecheckpoint','operations_occurrencequeue','scanner_scannerassignment','access_access'):
        if 'occurrence_id' in table_columns(db,table):
            operational[table]=db.execute(OPERATION_COUNT_QUERIES[table]).fetchone()[0]
    if active_ids:
        for table in ('operations_occurrencecheckpoint','operations_occurrencequeue','scanner_scannerassignment','access_access'):
            if 'occurrence_id' in table_columns(db,table):
                # Each occurrence ID is unique; count those present via a bound query.
                sql = OPERATION_ACTIVE_QUERIES[table]
                total = sum(db.execute(sql, (ident,)).fetchone() is not None for ident in active_ids)
                operational[table+'_active']=total
    return {'temporal':windows,'operational':operational}

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--database',required=True,help='SQLite source')
    p.add_argument('--apply',action='store_true',help='Effectuer les changements (sinon apercu)')
    p.add_argument('--in-place',action='store_true',help='Alias historique: modifier la source (deja le comportement par defaut)')
    p.add_argument('--backup',action='store_true',help='Creer une sauvegarde avant modification (option explicite)')
    p.add_argument('--output',help='Creer explicitement une copie de travail a ce chemin (non utilise par defaut)')
    p.add_argument('--now',help='Date/heure ISO, ex. 2026-10-27T18:00:00+01:00; defaut=maintenant')
    p.add_argument('--timezone',default='Africa/Kinshasa',help='Fuseau de reference, defaut Africa/Kinshasa')
    p.add_argument('--limit',type=int,default=0,help='Limiter le nombre d\'occurrences traitees (essai)')
    p.add_argument('--include-existing',action='store_true',help='Inclure aussi les Occurrences non synthetiques')
    p.add_argument('--demo-live',action='store_true',help='Garantir des creneaux temporels autour de maintenant, aujourd hui et demain; auditer la couverture operationnelle')
    p.add_argument('--demo-slots',type=int,default=120,help='Nombre de candidats affectes aux creneaux garantis (defaut 120)')
    a=p.parse_args(argv)
    source=Path(a.database).resolve()
    if not source.is_file(): p.error('Base introuvable: '+str(source))
    if a.in_place and a.output: p.error('--in-place et --output sont incompatibles')
    if a.backup and not a.apply: p.error('--backup exige --apply')
    tz=ZoneInfo(a.timezone)
    now=dt.datetime.fromisoformat(a.now.replace('Z','+00:00')) if a.now else dt.datetime.now(tz)
    if now.tzinfo is None: now=now.replace(tzinfo=tz)
    now=now.astimezone(UTC)
    target=Path(a.output).resolve() if a.output else source
    if a.output and target==source: p.error('--output doit etre different de --database')
    if target!=source and target.exists() and a.apply: p.error('Fichier de sortie existant; choisir un autre --output')
    if a.apply:
        if a.backup:
            backup=source.with_name(source.name+'.backup-'+dt.datetime.now().strftime('%Y%m%d-%H%M%S'))
            if backup.exists(): p.error('Sauvegarde deja existante')
            with sqlite3.connect(source) as src, sqlite3.connect(backup) as dst: src.backup(dst)
            print('Sauvegarde:',backup)
        if target!=source:
            with sqlite3.connect(source) as src, sqlite3.connect(target) as dst: src.backup(dst)
    db=sqlite3.connect(target if a.apply else source)
    try:
        cols=table_columns(db,'activities_occurrence')
        if not {'id','start_at','end_at'}<=cols: p.error('Schema Occurrence incompatible')
        # Les donnees ajoutees dans le premier lot sont identifiees par Activity.slug demo-2026-q4-.
        # En l'absence de cette signature, selection volontairement vide par defaut.
        acols=table_columns(db,'activities_activity')
        if not a.include_existing and not {'slug','id'}<=acols:
            p.error('Activity.slug introuvable; utiliser --include-existing seulement si voulu')
        rows=db.execute(
            'SELECT o.id,o.start_at,o.end_at FROM activities_occurrence o '
            'JOIN activities_activity a ON a.id=o.activity_id '
            'WHERE o.start_at IS NOT NULL AND (? OR a.slug LIKE ?) ORDER BY o.id LIMIT ?',
            (int(a.include_existing), 'demo-2026-q4-%', a.limit if a.limit>0 else -1),
        ).fetchall()
        # Autres lots synthetiques peuvent utiliser un prefixe different : voir --include-existing.
        print('Occurrences selectionnees:',len(rows),'| mode:', 'MODIFICATION' if a.apply else 'APERCU')
        print('Reference UTC:',now.isoformat(),'| base:',source)
        if a.apply:
            db.execute('PRAGMA foreign_keys=ON')
            db.execute('BEGIN IMMEDIATE')
        totals={t:0 for t in FIELDS}
        for index,(occ_id,start,end) in enumerate(rows):
            old=parsed(start)
            if not old: continue
            duration=(parsed(end)-old) if parsed(end) else dt.timedelta(hours=2)
            if duration.total_seconds()<0: continue
            new_start=(demo_slot(occ_id,index,now,tz) if a.demo_live and index<a.demo_slots else target_for(occ_id,now,duration))
            delta=new_start-old
            if a.apply:
                result=move_occurrence(db,occ_id,delta)
                for k,n in result.items(): totals[k]+=n
        if a.apply:
            failures=db.execute('PRAGMA foreign_key_check').fetchmany(3)
            if failures: raise RuntimeError('Foreign key check echec: '+str(failures))
            db.commit()
            print('Lignes modifiees par table:',totals)
            if a.demo_live:
                coverage=live_coverage(db,now,tz)
                print('COUVERTURE LIVE/JOUR J:',coverage)
                print('NOTE: creneaux temporels garantis, mais droits, statuts et operations existantes non crees. Verifier les compteurs operationnels et les permissions du viewer.')
            print('Fichier:',target)
        else:
            print('Aucun changement effectue. Relancer avec --apply pour modifier directement la base (sans copie).')
            if rows: print('Exemple occurrence:',rows[0][0], 'ancien debut:',rows[0][1], 'nouveau debut:',(demo_slot(rows[0][0],0,now,tz) if a.demo_live else target_for(rows[0][0],now,dt.timedelta(hours=2))).isoformat())
            if a.demo_live: print('COUVERTURE ACTUELLE LIVE/JOUR J:',live_coverage(db,now,tz))
    except Exception:
        db.rollback()
        raise
    finally: db.close()

if __name__=='__main__': main()
