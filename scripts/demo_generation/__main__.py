"""Generation de demonstration Makolo : une seule interface transverse.

Exemples:
  python -m scripts.demo_generation inventory
  python -m scripts.demo_generation plan --domains all --count 100
  python -m scripts.demo_generation generate --domains all --count 100 --grant-roles
"""
import argparse

VERTICALS=("opportunities","services","obtention","funding")
CROSS=("journeys","access","operations","scanner","commerce")
COMMUNITY=("groups","objectives","notifications","trust","contributions","sharing")
ENGAGEMENT=("forms","crm")
LIVE=("placement","incidents")
PERSONAL=("discovery","goals","space")
ECOSYSTEM=("spaces","loyalty","automation")
DOMAINS=("activities","mandates",*CROSS,"transport",*VERTICALS,"media",*COMMUNITY,*ENGAGEMENT,*LIVE,*PERSONAL,*ECOSYSTEM,"content")
DEFAULT=tuple(domain for domain in DOMAINS if domain!="content")


def parse_domains(value):
    selected=DEFAULT if value=="all" else tuple(part.strip() for part in value.split(",") if part.strip())
    unknown=set(selected)-set(DOMAINS)
    if not selected or unknown:
        raise ValueError("Domaines inconnus: "+",".join(sorted(unknown or {"(vide)"})))
    return set(selected)


def build_parser():
    p=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawTextHelpFormatter)
    sub=p.add_subparsers(dest="action",required=True)
    sub.add_parser("inventory",help="Inventaire Django et couverture contenu (lecture seule)")
    audit=sub.add_parser("audit",help="Lecture seule : verifier la couverture a une date donnee")
    audit.add_argument("--at",help="Date/heure ISO-8601 avec fuseau")
    for action in ("plan","generate"):
        s=sub.add_parser(action,help="Apercu sans ecriture" if action=="plan" else "Ecriture SQLite demo explicite")
        s.add_argument("--domains",default="all",help="all ou liste: "+",".join(DOMAINS))
        s.add_argument("--count",type=int,default=50,help="Budget de scenarios par module")
        s.add_argument("--profiles",type=int,default=30,help="Profils world_* candidats")
        s.add_argument("--scans",type=int,default=None)
        s.add_argument("--orders",type=int,default=None)
        s.add_argument("--grant-roles",action="store_true",help="Concession explicite des Mandates demo")
        s.add_argument("--max-db-mb",type=int,default=450)
    t=sub.add_parser("timeline",help="Recalage temporel independant (jamais automatique)")
    t.add_argument("--database",default="db.sqlite3")
    t.add_argument("--demo-live",action="store_true")
    t.add_argument("--limit",type=int,default=0)
    t.add_argument("--apply",action="store_true")
    return p


def run(a):
    from . import scale, transport, verticals, mandates, content, clock, media, community, audit, engagement, live, foundations, catalog, personal, ecosystem
    if a.action=="inventory":
        catalog.main([])
        return
    if a.action=="audit":
        audit.main(["--at",a.at] if a.at else [])
        return
    if a.action=="timeline":
        options=["--database",a.database]
        if a.demo_live: options.append("--demo-live")
        if a.limit: options.extend(["--limit",str(a.limit)])
        if a.apply: options.append("--apply")
        clock.main(options)
        return

    try:
        domains=parse_domains(a.domains)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    if not 1<=a.count<=100000 or not 1<=a.profiles<=100:
        raise SystemExit("--count 1..100000 ; --profiles 1..100")
    scans=min(a.count,200) if a.scans is None else a.scans
    orders=min(a.count,200) if a.orders is None else a.orders
    if not 0<=scans<=100000 or not 0<=orders<=100000:
        raise SystemExit("--scans et --orders 0..100000")
    apply=a.action=="generate"
    if apply and "mandates" in domains and not a.grant_roles:
        raise SystemExit("Le domaine mandates exige --grant-roles pour generate.")
    print("MODE:","GENERATE" if apply else "PLAN","DOMAINES:",",".join(sorted(domains)))
    if "activities" in domains:
        print("ACTIVITIES: reutilisation des objets demo existants; creation par verticale explicite.")
    ecosystem_selected=set(ECOSYSTEM)&domains
    if ecosystem_selected:
        argv=["--domains",",".join(sorted(ecosystem_selected)),
              "--count",str(min(a.count,100)), "--profiles",str(a.profiles)]
        if apply: argv.append("--apply")
        ecosystem.main(argv)
    personal_selected=set(PERSONAL)&domains
    if personal_selected:
        argv=["--domains",",".join(sorted(personal_selected)),
              "--count",str(min(a.count,2000)), "--profiles",str(a.profiles)]
        if apply: argv.append("--apply")
        personal.main(argv)
    if "transport" in domains:
        argv=["--beneficiaries",str(a.profiles),"--scan-count",str(min(a.profiles,12))]
        if apply: argv.append("--apply")
        transport.main(argv)
    if "mandates" in domains:
        argv=["--limit",str(min(a.count,200))]
        if apply: argv.append("--apply")
        mandates.main(argv)
    verticals_selected=set(VERTICALS)&domains
    foundation_selected=verticals_selected&{"funding","services","obtention"}
    if foundation_selected:
        argv=["--domains",",".join(sorted(foundation_selected)),
              "--count",str(min(a.count,100))]
        if apply: argv.append("--apply")
        foundations.main(argv)
    if verticals_selected:
        argv=["--domains",",".join(sorted(verticals_selected)),
              "--per-domain",str(min(a.count,2000)),"--profiles",str(a.profiles)]
        if apply: argv.append("--apply")
        verticals.main(argv)
    cross_selected=set(CROSS)&domains
    if cross_selected:
        argv=[
            "--journeys",str(a.count if "journeys" in domains else 0),
            "--accesses",str(a.count if "access" in domains else 0),
            "--queues",str(min(a.count,100) if "operations" in domains else 0),
            "--scans",str(scans if "scanner" in domains else 0),
            "--orders",str(orders if "commerce" in domains else 0),
            "--profiles",str(a.profiles),
            "--max-db-mb",str(a.max_db_mb),
        ]
        if "operations" in domains: argv.extend(["--queue-advance","served"])
        if a.grant_roles: argv.append("--grant-demo-roles")
        if apply: argv.append("--apply")
        scale.main(argv)
    live_selected=set(LIVE)&domains
    if live_selected:
        argv=["--domains",",".join(sorted(live_selected)),
              "--count",str(min(a.count,200))]
        if apply: argv.append("--apply")
        live.main(argv)
    community_selected=set(COMMUNITY)&domains
    if community_selected:
        argv=["--domains",",".join(sorted(community_selected)),
              "--count",str(min(a.count,2000)),
              "--profiles",str(max(a.profiles,2))]
        if apply: argv.append("--apply")
        community.main(argv)
    engagement_selected=set(ENGAGEMENT)&domains
    if engagement_selected:
        argv=["--domains",",".join(sorted(engagement_selected)),
              "--count",str(min(a.count,2000))]
        if apply: argv.append("--apply")
        engagement.main(argv)
    if "media" in domains:
        argv=["--count",str(min(a.count,10000))]
        if apply: argv.append("--apply")
        media.main(argv)
    if "content" in domains:
        content.main()
    if not apply: print("PLAN en lecture seule : ajouter generate pour ecrire.")
    else: print("FIN : consulter les compteurs des modules, aucune copie de la base.")


def main(argv=None):
    args=build_parser().parse_args(argv)
    run(args)


if __name__=="__main__":
    main()
