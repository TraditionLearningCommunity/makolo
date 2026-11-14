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
AFTERCARE=("outcomes",)
SUBSCRIPTIONS=("subscriptions","subscription-catalog")
CONNECTIONS=("connections",)
CONVERSATIONS=("conversations",)
DOMAINS=("activities","mandates",*CROSS,"transport",*VERTICALS,"media",*COMMUNITY,*ENGAGEMENT,*LIVE,*PERSONAL,*ECOSYSTEM,*AFTERCARE,*SUBSCRIPTIONS,*CONNECTIONS,*CONVERSATIONS,"content")
DEFAULT=tuple(domain for domain in DOMAINS if domain not in {"content","subscriptions","subscription-catalog"})


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
    v=sub.add_parser("validate",help="Verifier les contrats sur une base de test Django isolee")
    v.add_argument("--quick",action="store_true",help="Tests CLI et integration ciblée")
    v.add_argument("--failfast",action="store_true")
    v.add_argument("--verbosity",type=int,default=1,choices=(0,1,2))
    audit=sub.add_parser("audit",help="Lecture seule : verifier la couverture a une date donnee")
    audit.add_argument("--at",help="Date/heure ISO-8601 avec fuseau")
    for action in ("plan","generate"):
        s=sub.add_parser(action,help="Apercu sans ecriture" if action=="plan" else "Ecriture SQLite demo explicite")
        s.add_argument("--domains",default="all",help="all ou liste: "+",".join(DOMAINS))
        s.add_argument("--count",type=int,default=50,help="Budget de scenarios par module")
        s.add_argument("--profiles",type=int,default=30,help="Profils world_* candidats")
        s.add_argument("--profile-username",default=None,help="Cibler explicitement un beneficiaire par username (aucun compte code en dur)")
        s.add_argument("--objectives-projects",type=int,default=4,help="Projets par profil pour objectives (1..8)")
        s.add_argument("--objectives-dossiers-per-project",type=int,default=3,help="Dossiers par Projet (1..6)")
        s.add_argument("--objectives-independent",type=int,default=2,help="Dossiers independants par profil (0..6)")
        s.add_argument("--objectives-journeys-per-dossier",type=int,default=2,help="Journeys canoniques liees par Dossier (0..4)")
        s.add_argument("--seed",type=int,default=2026,help="Graine de repartition stable (Conversations)")
        s.add_argument("--conversation-points",type=int,default=4,choices=(1,2,3,4))
        s.add_argument("--conversation-include-test-users",action="store_true",
                       help="Inclure les comptes existants beta_* et mobile_mature_*")
        s.add_argument("--conversation-usernames",default=None,
                       help="Liste de usernames principaux, separes par des virgules")
        s.add_argument("--conversation-selection",choices=("random","ordered"),default="random")
        s.add_argument("--conversation-max-participants",type=int,default=8)
        s.add_argument("--conversation-context-types",default="all")
        s.add_argument("--scans",type=int,default=None)
        s.add_argument("--orders",type=int,default=None)
        s.add_argument("--grant-roles",action="store_true",help="Concession explicite des Mandates demo")
        s.add_argument("--max-db-mb",type=int,default=450)
    def time_options(command):
        command.add_argument("--database", default="db.sqlite3")
        command.add_argument("--demo-live", action="store_true")
        command.add_argument("--limit", type=int, default=0)
        command.add_argument("--mode", choices=("safe", "full"), default="safe")
        command.add_argument("--activity-prefix", default="demo-")
        command.add_argument("--include-existing", action="store_true")
        command.add_argument("--backup", action="store_true")
        command.add_argument("--output")
        command.add_argument("--now")
        command.add_argument("--timezone", default="Africa/Kinshasa")
        command.add_argument("--demo-slots", type=int, default=120)
        command.add_argument("--apply", action="store_true")

    t=sub.add_parser("timeline",help="Recalage explicite des scenarios temporels")
    time_options(t)
    r=sub.add_parser("rebalance",help="Reequilibrer les relations ou les periodes demo")
    r.add_argument("--target",required=True,choices=("profiles","spaces","periods"))
    r.add_argument("--count",type=int,default=50)
    r.add_argument("--profiles",type=int,default=30)
    r.add_argument("--profile-username")
    r.add_argument("--space-id")
    r.add_argument("--per-profile",type=int,default=3)
    r.add_argument("--seed",type=int,default=2026)
    r.add_argument("--direction",choices=("add","trim"),default="add")
    time_options(r)
    res=sub.add_parser("resources",help="Documents, preuves et titres de Mes ressources")
    res.add_argument("--domains",default="all",help="all ou documents,proofs,credentials")
    res.add_argument("--count",type=int,default=4)
    res.add_argument("--profiles",type=int,default=30)
    res.add_argument("--profile-username")
    res.add_argument("--include-test-users",action="store_true")
    res.add_argument("--reuse-avatar",action="store_true",default=True)
    res.add_argument("--no-reuse-avatar",dest="reuse_avatar",action="store_false")
    res.add_argument("--apply",action="store_true")
    res.add_argument("--backup",action="store_true")
    m=sub.add_parser("maintain",help="Completer, rafraichir ou archiver des scenarios demo")
    m.add_argument("--action",dest="maintenance_action",required=True,choices=("complete","refresh","retire","restore"))
    m.add_argument("--domains",default="all")
    m.add_argument("--count",type=int,default=50)
    m.add_argument("--profiles",type=int,default=30)
    m.add_argument("--profile-username")
    m.add_argument("--space-id")
    m.add_argument("--activity-prefix",default="demo-")
    m.add_argument("--older-than-days",type=int,default=30)
    m.add_argument("--edition",type=int,default=1)
    m.add_argument("--grant-roles",action="store_true")
    m.add_argument("--apply",action="store_true")
    m.add_argument("--backup",action="store_true")
    return p


def run(a):
    from . import subscription_catalog, scale, transport, verticals, mandates, content, clock, media, community, audit, engagement, live, foundations, catalog, personal, ecosystem, aftercare, validate, subscriptions, connections, conversations, rebalance, maintenance, resources
    if a.action == "resources":
        options=["--domains",a.domains,"--count",str(a.count),
                 "--profiles",str(a.profiles)]
        if a.profile_username: options.extend(["--profile-username",a.profile_username])
        if a.include_test_users: options.append("--include-test-users")
        options.append("--reuse-avatar" if a.reuse_avatar else "--no-reuse-avatar")
        if a.backup: options.append("--backup")
        if a.apply: options.append("--apply")
        return resources.main(options)
    if a.action=="validate":
        options=["--verbosity",str(a.verbosity)]
        if a.quick: options.append("--quick")
        if a.failfast: options.append("--failfast")
        return validate.main(options)
    if a.action=="inventory":
        catalog.main([])
        return
    if a.action=="audit":
        audit.main(["--at",a.at] if a.at else [])
        return
    if a.action in ("timeline", "rebalance") and (
        a.action == "timeline" or a.target == "periods"
    ):
        if a.action == "rebalance":
            if (a.space_id or a.profile_username or a.direction != "add" or
                    a.per_profile != 3 or a.seed != 2026):
                raise SystemExit("Les options de relations ne concernent pas --target periods.")
            if a.count != 50 and a.limit == 0:
                a.limit = a.count
        options=["--database",a.database, "--mode",a.mode,
                 "--activity-prefix",a.activity_prefix,
                 "--timezone",a.timezone,"--demo-slots",str(a.demo_slots)]
        if a.now: options.extend(["--now",a.now])
        if a.output: options.extend(["--output",a.output])
        if a.backup: options.append("--backup")
        if a.include_existing: options.append("--include-existing")
        if a.demo_live: options.append("--demo-live")
        if a.limit: options.extend(["--limit",str(a.limit)])
        if a.apply: options.append("--apply")
        clock.main(options)
        return
    if a.action == "rebalance":
        if (a.database != "db.sqlite3" or a.demo_live or a.limit or
                a.mode != "safe" or a.include_existing or a.output or a.now or
                a.timezone != "Africa/Kinshasa" or a.demo_slots != 120):
            raise SystemExit("Les options temporelles exigent --target periods.")
        options=["--target",a.target,"--count",str(a.count),
                 "--profiles",str(a.profiles),"--per-profile",str(a.per_profile),
                 "--seed",str(a.seed),"--direction",a.direction,
                 "--activity-prefix",a.activity_prefix]
        if a.profile_username: options.extend(["--profile-username",a.profile_username])
        if a.space_id: options.extend(["--space-id",a.space_id])
        if a.backup: options.append("--backup")
        if a.apply: options.append("--apply")
        rebalance.main(options)
        return
    if a.action == "maintain":
        options=["--action",a.maintenance_action,
                 "--domains",a.domains,"--count",str(a.count),
                 "--profiles",str(a.profiles),"--activity-prefix",a.activity_prefix,
                 "--older-than-days",str(a.older_than_days),
                 "--edition",str(a.edition)]
        if a.profile_username: options.extend(["--profile-username",a.profile_username])
        if a.space_id: options.extend(["--space-id",a.space_id])
        if a.grant_roles: options.append("--grant-roles")
        if a.backup: options.append("--backup")
        if a.apply: options.append("--apply")
        maintenance.main(options)
        return

    try:
        domains=parse_domains(a.domains)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    if not 1<=a.count<=100000 or not 1<=a.profiles<=100:
        raise SystemExit("--count 1..100000 ; --profiles 1..100")
    if not (1<=a.objectives_projects<=8 and
            1<=a.objectives_dossiers_per_project<=6 and
            0<=a.objectives_independent<=6 and
            0<=a.objectives_journeys_per_dossier<=4):
        raise SystemExit("Objectives: --objectives-projects 1..8, --objectives-dossiers-per-project 1..6, --objectives-independent 0..6, --objectives-journeys-per-dossier 0..4")
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
    if "connections" in domains:
        connections.main((["--apply"] if apply else []) + ["--count", str(min(a.count,5000)), "--profiles", str(a.profiles)] + (["--profile-username", a.profile_username] if a.profile_username else []))
    if "subscription-catalog" in domains:
        subscription_catalog.main(["--apply"] if apply else [])
    if "subscriptions" in domains:
        argv=["--count",str(min(a.count,50)),"--profiles",str(a.profiles)]
        if a.profile_username: argv.extend(["--profile-username",a.profile_username])
        if apply: argv.append("--apply")
        subscriptions.main(argv)
    ecosystem_selected=set(ECOSYSTEM)&domains
    if ecosystem_selected:
        argv=["--domains",",".join(sorted(ecosystem_selected)),
              "--count",str(min(a.count,100)), "--profiles",str(a.profiles)]
        if apply: argv.append("--apply")
        if a.profile_username: argv.extend(["--profile-username",a.profile_username])
        ecosystem.main(argv)
    personal_selected=set(PERSONAL)&domains
    if personal_selected:
        argv=["--domains",",".join(sorted(personal_selected)),
              "--count",str(min(a.count,2000)), "--profiles",str(a.profiles)]
        if a.profile_username: argv.extend(["--profile-username",a.profile_username])
        if apply: argv.append("--apply")
        personal.main(argv)
    if "transport" in domains:
        argv=["--beneficiaries",str(a.profiles),"--scan-count",str(min(a.profiles,12))]
        if apply: argv.append("--apply")
        if a.profile_username: argv.extend(["--profile-username",a.profile_username])
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
        if a.profile_username: argv.extend(["--profile-username",a.profile_username])
        if apply: argv.append("--apply")
        foundations.main(argv)
    if verticals_selected:
        argv=["--domains",",".join(sorted(verticals_selected)),
              "--per-domain",str(min(a.count,2000)),"--profiles",str(a.profiles)]
        if apply: argv.append("--apply")
        if a.profile_username: argv.extend(["--profile-username",a.profile_username])
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
        if a.profile_username: argv.extend(["--profile-username",a.profile_username])
        if a.grant_roles: argv.append("--grant-demo-roles")
        if apply: argv.append("--apply")
        scale.main(argv)
    if "outcomes" in domains:
        argv=["--count",str(min(a.count,10000))]
        if apply: argv.append("--apply")
        if a.profile_username: argv.extend(["--profile-username",a.profile_username])
        aftercare.main(argv)
    live_selected=set(LIVE)&domains
    if live_selected:
        argv=["--domains",",".join(sorted(live_selected)),
              "--count",str(min(a.count,200))]
        if apply: argv.append("--apply")
        if a.profile_username: argv.extend(["--profile-username",a.profile_username])
        live.main(argv)
    community_selected=set(COMMUNITY)&domains
    if community_selected:
        argv=["--domains",",".join(sorted(community_selected)),
              "--count",str(min(a.count,2000)),
              "--profiles",str(max(a.profiles,2))]
        if "objectives" in community_selected:
            argv.extend([
                "--objectives-projects",str(a.objectives_projects),
                "--objectives-dossiers-per-project",str(a.objectives_dossiers_per_project),
                "--objectives-independent",str(a.objectives_independent),
                "--objectives-journeys-per-dossier",str(a.objectives_journeys_per_dossier),
            ])
        if apply: argv.append("--apply")
        if a.profile_username: argv.extend(["--profile-username",a.profile_username])
        community.main(argv)
    engagement_selected=set(ENGAGEMENT)&domains
    if engagement_selected:
        argv=["--domains",",".join(sorted(engagement_selected)),
              "--count",str(min(a.count,2000))]
        if apply: argv.append("--apply")
        if a.profile_username: argv.extend(["--profile-username",a.profile_username])
        engagement.main(argv)
    if "media" in domains:
        argv=["--count",str(min(a.count,10000))]
        if apply: argv.append("--apply")
        media.main(argv)
    # Contextual conversations depend on the Activity, Occurrence, Space,
    # Journey and Group rows materialized by the preceding generators.
    if "conversations" in domains:
        options=["--count",str(min(a.count,2000)), "--profiles",str(a.profiles),
                 "--seed",str(a.seed), "--points",str(a.conversation_points)]
        if a.profile_username: options.extend(["--profile-username",a.profile_username])
        if a.conversation_usernames: options.extend(["--profile-usernames",a.conversation_usernames])
        options.extend(["--selection",a.conversation_selection,
                        "--max-participants",str(a.conversation_max_participants),
                        "--context-types",a.conversation_context_types])
        if a.conversation_include_test_users: options.append("--include-test-users")
        if apply: options.append("--apply")
        conversations.main(options)
    if "content" in domains:
        content.main()
    if not apply: print("PLAN en lecture seule : ajouter generate pour ecrire.")
    else: print("FIN : consulter les compteurs des modules, aucune copie de la base.")


def main(argv=None):
    args=build_parser().parse_args(argv)
    run(args)


if __name__=="__main__":
    main()
