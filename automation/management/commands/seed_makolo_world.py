from __future__ import annotations

import hashlib
import os
import uuid
from datetime import datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from access.models import Access, AccessCredential, AccessStatus, AccessUse, AccessUseResult, CredentialStatus, CredentialType
from accounts.models import NotificationPreference, User, UserProfile
from activities.models import Activity, ActivityStatus, ActivityVisibility, Occurrence, OccurrencePlace, OccurrencePlaceRole, OccurrenceStatus, OccurrenceTimingKind
from authorization.constants import SystemRoleCode
from authorization.services import ensure_platform_admin_mandate, grant_space_role
from capacity.models import CapacityPool, CapacityReservation, CapacityReservationStatus
from commerce.models import CommerceOrder, CommerceOrderItem, CommerceOrderStatus, Offer, OfferStatus, PaymentMode
from conversations.models import Conversation, ConversationContext, ConversationContextKind, ConversationDiscoverability, ConversationEntryMode, ConversationHistoryPolicy, ConversationLifecycle, ConversationModePreset, ConversationParticipation, ConversationParticipationSource, ConversationParticipationStatus, ConversationPoint, ConversationPointKind, ConversationPointLifecycle, ConversationPointResponse, ConversationPointResponseMode, ConversationPointResponseStatus, ConversationPointResolutionPolicy, ConversationPolicy
from events.models import Event, EventCategory, EventVenue, VenueKind
from geography.models import Place, Zone, ZoneType
from journeys.models import Journey, JourneyStatus, WorkflowKind
from opportunities.models import Opportunity, OpportunityKind, OpportunityPublicationStatus, OpportunityRequirement, OpportunityRequirementKind, OpportunityRevision, OpportunitySave, OpportunitySource, OpportunitySourceCheck, OpportunitySourceCheckResult, OpportunitySourceStatus, OpportunitySourceType
from opportunities.services import publish_opportunity_revision
from organizations.models import Organization, OrganizationFollow, ProfileFollow, Team, TeamMembership, TeamMembershipStatus
from payments.models import Payment, PaymentMethod, PaymentProvider, PaymentStatus
from services.models import CompletionPolicy, IntakePolicy, OpportunityPolicy, ServiceDetails, ServiceKind
from social.models import ActionNeed, ActionNeedCandidateKind, ActionNeedIntakePolicy, ActionNeedStatus, ActionNeedVisibility, ActionProposal, ActionProposalDirection, ActionProposalStatus, Contribution, ContributionKind, ContributionStatus, ContributionVisibility
from topics.models import ActionMatchKind, ActivityTopic, ProfileInterest, ProfileOpenTo, Topic

SEED = "makolo-world-2025-2026-v1"
NS = uuid.UUID("1e5dff5c-9ae2-45ea-92c8-a26887d1f08e")
TZ = ZoneInfo("Africa/Lubumbashi")

SCALES = {
    "smoke": dict(users=8, spaces=4, activities=24, opportunities=18, journeys=30, conversations=8, contributions=60, saves=30, needs=12),
    "full": dict(users=100, spaces=30, activities=420, opportunities=360, journeys=800, conversations=160, contributions=1500, saves=600, needs=200),
}

FIRST = "Amina Grace Sarah Naomi Esther Chantal Mireille Prisca Joelle Nadia Divine Blandine Ruth Deborah Gloria Fatou Aissatou Mariama Khadija Ndeye Patrick Junior Christian Jonathan David Samuel Michel Olivier Arnaud Cedric Fabrice Kevin Yannick Blaise Gael Ibrahim Moussa Ousmane Abdoulaye Cheikh Jean Alain Thierry Emmanuel Joseph Daniel Eric Marc Freddy Tresor".split()
LAST = "Mukendi Ilunga Kabongo Kasongo Tshibangu Mbuyi Kabasele Mutombo Kalala Mulumba Katumbi Mwamba Lukusa Ngoy Banza Kanku Mputu Kalonji Tshiala Lusamba Diallo Traore Keita Cisse Diop Ba Ndiaye Faye Sow Kone Mensah Boateng Owusu Agyeman Okafor Adeyemi Nwosu Kamau Mwangi Njoroge Mbeki Dlamini Ndlovu Moyo Kagame Habimana Mugisha Niyonsaba ElAmrani Benali".split()
PROFESSIONS = ["Développeuse logiciel", "Ingénieur data", "Responsable opérations", "Entrepreneure", "Chargé de programme", "Consultant finance", "Designer produit", "Ingénieur mines", "Spécialiste climat", "Responsable logistique", "Juriste", "Chef de projet", "Étudiante", "Chercheur", "Responsable RH", "Comptable", "Journaliste", "Photographe", "Formateur", "Coach carrière", "Ingénieur énergie", "Agronome", "Médecin", "Infirmière", "Spécialiste WASH", "Analyste politique", "Community manager", "Architecte", "Urbaniste", "Product manager"]
PLACES = [
    ("Lubumbashi", "Haut-Katanga", "CD", "-11.664677", "27.479553", "Africa/Lubumbashi"),
    ("Kinshasa", "Kinshasa", "CD", "-4.325000", "15.322200", "Africa/Kinshasa"),
    ("Kolwezi", "Lualaba", "CD", "-10.714840", "25.466740", "Africa/Lubumbashi"),
    ("Goma", "Nord-Kivu", "CD", "-1.658500", "29.220700", "Africa/Lubumbashi"),
    ("Kigali", "Kigali", "RW", "-1.944100", "30.061900", "Africa/Kigali"),
    ("Nairobi", "Nairobi County", "KE", "-1.267600", "36.810800", "Africa/Nairobi"),
    ("Kampala", "Central", "UG", "0.347600", "32.582500", "Africa/Kampala"),
    ("Dar es Salaam", "Dar es Salaam", "TZ", "-6.792400", "39.208300", "Africa/Dar_es_Salaam"),
    ("Lusaka", "Lusaka", "ZM", "-15.387500", "28.322800", "Africa/Lusaka"),
    ("Johannesburg", "Gauteng", "ZA", "-26.107600", "28.056700", "Africa/Johannesburg"),
    ("Cape Town", "Western Cape", "ZA", "-33.924900", "18.424100", "Africa/Johannesburg"),
    ("Accra", "Greater Accra", "GH", "5.603700", "-0.187000", "Africa/Accra"),
    ("Lagos", "Lagos", "NG", "6.428100", "3.421900", "Africa/Lagos"),
    ("Abidjan", "Abidjan", "CI", "5.359952", "-4.008256", "Africa/Abidjan"),
    ("Dakar", "Dakar", "SN", "14.716700", "-17.467700", "Africa/Dakar"),
    ("Addis Ababa", "Addis Ababa", "ET", "8.980600", "38.757800", "Africa/Addis_Ababa"),
    ("Yaounde", "Centre", "CM", "3.848000", "11.502100", "Africa/Douala"),
    ("Casablanca", "Casablanca-Settat", "MA", "33.573100", "-7.589800", "Africa/Casablanca"),
    ("Luanda", "Luanda", "AO", "-8.838300", "13.234400", "Africa/Luanda"),
    ("Brussels", "Brussels-Capital", "BE", "50.850300", "4.351700", "Europe/Brussels"),
]
SPACE_NAMES = ["Copperbelt Innovation Hub", "Kivu Digital Lab", "Kinshasa Creative House", "Lualaba Skills Center", "Green Cities Africa", "Women Build Tech", "Africa Career Bridge", "Health Access Network", "AgriFuture Cooperative", "Cobalt Responsible Forum", "Youth Policy Lab", "Makers Lubumbashi", "Clean Energy Circle", "Francophone Data Society", "Arts & Culture Commons", "Sport Impact Africa", "Climate Action Studio", "Logistics East Africa", "Education Pathways", "SME Finance Lab", "Public Service Academy", "Mining Safety Institute", "Digital Rights Forum", "Open Science Africa", "Tourism Experience Lab", "Urban Mobility Collective", "Social Enterprise Foundry", "Community Health Alliance", "Pan-African Research Network", "Makolo Community Commons"]
ACTIVITY_TEMPLATES = [
    ("event", "technologie", "Sommet tech & innovation", Decimal("35"), 500, "https://www.gitexafrica.com/"),
    ("event", "emploi", "Salon emplois & carrières", Decimal("0"), 1200, "https://www.afdb.org/en/about-us/careers"),
    ("event", "mines", "Forum mines responsables", Decimal("80"), 700, "https://miningindaba.com/"),
    ("event", "climat", "Forum climat & résilience", Decimal("15"), 400, "https://au.int/"),
    ("event", "sante", "Conférence santé communautaire", Decimal("10"), 450, "https://www.who.int/"),
    ("event", "agriculture", "Expo agriculture & food systems", Decimal("5"), 800, "https://www.fao.org/"),
    ("event", "energie", "Forum énergie propre", Decimal("20"), 500, "https://www.afdb.org/en/topics-and-sectors/sectors/energy-power"),
    ("event", "culture", "Festival industries créatives", Decimal("12"), 900, "https://en.unesco.org/creativity"),
    ("event", "finance", "Forum financement PME", Decimal("20"), 400, "https://www.ifc.org/"),
    ("event", "formation", "Sommet éducation & compétences", Decimal("0"), 650, "https://www.unesco.org/en/education"),
    ("general", "formation", "Bootcamp Python pratique", Decimal("40"), 40, "https://www.python.org/"),
    ("general", "data", "Bootcamp Data & BI", Decimal("60"), 35, "https://www.kaggle.com/learn"),
    ("general", "technologie", "Atelier cybersécurité", Decimal("30"), 30, "https://www.cisa.gov/"),
    ("general", "entrepreneuriat", "Demo Day startups", Decimal("0"), 250, "https://www.afdb.org/"),
    ("general", "climat", "Journée plantation", Decimal("0"), 150, "https://www.unep.org/"),
    ("general", "sante", "Formation premiers secours", Decimal("20"), 30, "https://www.ifrc.org/"),
    ("general", "mines", "Formation sécurité minière", Decimal("50"), 45, "https://www.ilo.org/"),
    ("general", "energie", "Formation installation solaire", Decimal("75"), 24, "https://www.irena.org/"),
    ("general", "agriculture", "Formation agri-business", Decimal("30"), 40, "https://www.fao.org/"),
    ("general", "emploi", "Freelance Lab", Decimal("10"), 40, "https://www.ilo.org/"),
    ("service", "emploi", "Clinique CV & candidature", Decimal("10"), 20, "https://www.afdb.org/en/about-us/careers"),
    ("service", "emploi", "Préparation entretien", Decimal("15"), 12, "https://careers.un.org/"),
    ("service", "formation", "Accompagnement bourses", Decimal("20"), 15, "https://www.chevening.org/scholarships/"),
    ("service", "entrepreneuriat", "Clinique entrepreneuriale", Decimal("25"), 18, "https://www.ifc.org/"),
]
OPP_TEMPLATES = [
    (OpportunityKind.JOB, "Ingénieur logiciel", "Digital Africa Labs", "Développement backend, APIs et fiabilité.", True, "https://careers.un.org/"),
    (OpportunityKind.JOB, "Data analyst", "Insight Works", "Analyse, BI et aide à la décision.", True, "https://www.afdb.org/en/about-us/careers"),
    (OpportunityKind.JOB, "Responsable logistique", "Relief Supply Network", "Achats, stocks et transport.", False, "https://jobs.unicef.org/"),
    (OpportunityKind.INTERNSHIP, "Stage data & analytics", "Pan-African Research Network", "Stage en analyse de données.", True, "https://www.afdb.org/en/about-us/careers/internship-programme/overview"),
    (OpportunityKind.INTERNSHIP, "Stage communication", "Creative Impact Studio", "Stage contenu et communication.", True, "https://au.int/en/internships"),
    (OpportunityKind.SCHOLARSHIP, "Bourse master leadership", "Global Scholars Africa", "Financement de master.", True, "https://www.chevening.org/scholarships/"),
    (OpportunityKind.SCHOLARSHIP, "Bourse sciences & technologies", "STEM Futures Fund", "Bourse STEM.", True, "https://erasmus-plus.ec.europa.eu/opportunities/opportunities-for-individuals/students/erasmus-mundus-joint-masters"),
    (OpportunityKind.EDUCATION, "Master data science", "African Institute of Data", "Admissions master data science.", False, "https://www.unesco.org/en/education"),
    (OpportunityKind.EDUCATION, "Certification supply chain", "Logistics East Africa", "Certification courte supply chain.", True, "https://www.worldbank.org/"),
    (OpportunityKind.GRANT, "Fonds innovation PME", "SME Growth Fund", "Financement compétitif pour PME.", False, "https://www.afdb.org/"),
    (OpportunityKind.GRANT, "Fonds solutions climat locales", "Green Cities Africa", "Petites subventions climat.", False, "https://www.undp.org/"),
    (OpportunityKind.COMPETITION, "Challenge startups impact", "Social Enterprise Foundry", "Compétition startups à impact.", True, "https://www.afdb.org/"),
    (OpportunityKind.COMPETITION, "Hackathon civic tech", "Open Data Community", "Challenge numérique services publics.", True, "https://data.worldbank.org/"),
    (OpportunityKind.PROGRAM, "Fellowship leadership africain", "Leadership Africa Network", "Leadership, mentorat et réseau.", True, "https://au.int/"),
    (OpportunityKind.PROGRAM, "Programme accélération startups", "Venture Builder Africa", "Accélération et mentorat.", True, "https://www.ifc.org/"),
    (OpportunityKind.VOLUNTEERING, "Volontariat éducation numérique", "Digital Inclusion Corps", "Animer des ateliers numériques.", False, "https://www.unv.org/"),
    (OpportunityKind.VOLUNTEERING, "Volontariat action climat", "Climate Action Studio", "Mobilisation et actions terrain.", False, "https://www.unv.org/"),
    (OpportunityKind.OTHER, "Résidence industries créatives", "Arts & Culture Commons", "Résidence de création.", False, "https://en.unesco.org/creativity"),
]
TOPIC_LABELS = [("technologie", "Technologie"), ("entrepreneuriat", "Entrepreneuriat"), ("culture", "Culture"), ("sport", "Sport"), ("formation", "Formation"), ("emploi", "Emploi"), ("voyage", "Voyage"), ("mines", "Mines"), ("energie", "Énergie"), ("climat", "Climat"), ("sante", "Santé"), ("agriculture", "Agriculture"), ("finance", "Finance"), ("logistique", "Logistique"), ("recherche", "Recherche"), ("data", "Data"), ("design", "Design"), ("leadership", "Leadership"), ("developpement", "Développement"), ("communication", "Communication")]
MATCHES = [v for v, _ in ActionMatchKind.choices]


def sid(key):
    return uuid.uuid5(NS, f"{SEED}:{key}")


def spread(index):
    m = index % 24
    return datetime(2025 + m // 12, m % 12 + 1, 3 + ((index * 7) % 22), tzinfo=TZ).date()


def aware(day, hour, tz_name="Africa/Lubumbashi"):
    return datetime.combine(day, time(hour), tzinfo=ZoneInfo(tz_name))


def bulk(model, rows):
    if rows:
        model.objects.bulk_create(rows, ignore_conflicts=True, batch_size=500)


def seed_world(scale, as_of, password):
    cfg = SCALES[scale]
    at = datetime.strptime(as_of, "%Y-%m-%d").replace(tzinfo=TZ)
    stats = {}
    for code, label in TOPIC_LABELS:
        Topic.objects.update_or_create(code=code, defaults={"label": label, "is_active": True})
    topics = list(Topic.objects.filter(code__in=[x[0] for x in TOPIC_LABELS]).order_by("code"))

    users = []
    for i in range(cfg["users"]):
        first, last = FIRST[i % len(FIRST)], LAST[(i * 7) % len(LAST)]
        city, _, country, _, _, tz = PLACES[i % len(PLACES)]
        email = f"{first.lower()}.{last.lower()}{i+1:03d}@makolo.demo"
        user = User.objects.filter(pk=sid(f"user:{i}")).first() or User(pk=sid(f"user:{i}"))
        user.email = email; user.username = f"world_{i+1:03d}_{first.lower()}"; user.first_name = first; user.last_name = last
        user.gender = "female" if i % 2 == 0 else "male"; user.bio = f"{PROFESSIONS[i % len(PROFESSIONS)]} basé(e) à {city}. Profil synthétique de démonstration."
        user.language = "fr"; user.timezone = tz; user.email_verified = True; user.onboarding_completed = True; user.onboarding_step = 5
        user.is_active = True; user.is_staff = i == 0; user.is_superuser = i == 0
        user.metadata = {"seed": SEED, "synthetic": True, "avatar_url": f"https://api.dicebear.com/9.x/notionists/png?seed=makolo-{i+1:03d}&size=256"}
        user.preferences = {"demo_world": True}; user.set_password(password); user.save()
        User.objects.filter(pk=user.pk).update(created_at=datetime(2025, 1, 15, 9, tzinfo=TZ) + timedelta(days=i * 4))
        UserProfile.objects.update_or_create(user=user, defaults={"profession": PROFESSIONS[i % len(PROFESSIONS)], "country": country, "city": city, "public_profile": i % 5 != 0, "searchable": i % 4 != 0})
        NotificationPreference.objects.update_or_create(user=user, defaults={"email_notifications": False, "sms_notifications": False, "push_notifications": False, "marketing_notifications": False, "security_notifications": True, "event_notifications": True, "service_notifications": True, "opportunity_notifications": True})
        users.append(user)
    ensure_platform_admin_mandate(profile=users[0], source=SEED)
    bulk(ProfileInterest, [ProfileInterest(id=sid(f"interest:{i}:{j}"), profile=u, topic=topics[(i*3+j)%len(topics)], is_public=j < 2) for i,u in enumerate(users) for j in range(3)])
    bulk(ProfileOpenTo, [ProfileOpenTo(id=sid(f"open:{i}:{j}"), profile=u, kind=MATCHES[(i+j)%len(MATCHES)], topic=topics[(i*5+j)%len(topics)], is_active=True, is_public=j==0, is_searchable=j==0) for i,u in enumerate(users) for j in range(2)])
    stats["users"] = len(users)

    places=[]; zones=[]
    for i,(city,area,country,lat,lon,tz) in enumerate(PLACES):
        p,_=Place.objects.get_or_create(pk=sid(f"place:{i}"), defaults={"name":f"World Demo — {city}","address_line":f"Centre-ville, {city}","locality":city,"administrative_area":area,"country_code":country,"latitude":Decimal(lat),"longitude":Decimal(lon),"timezone":tz,"is_active":True,"created_by":users[0]})
        z,_=Zone.objects.get_or_create(pk=sid(f"zone:{i}"), defaults={"name":f"World Demo — {city}","zone_type":ZoneType.ADMINISTRATIVE,"country_code":country,"administrative_area":area,"locality":city,"is_active":True,"created_by":users[0]})
        places.append(p); zones.append(z)

    spaces=[]
    for i in range(cfg["spaces"]):
        city,_,country,*_=PLACES[(i*2)%len(PLACES)]; creator=users[i%len(users)]
        space,_=Organization.objects.update_or_create(pk=sid(f"space:{i}"), defaults={"name":SPACE_NAMES[i],"slug":f"world-{i+1:02d}-space","description":f"Espace synthétique de démonstration actif à {city}.","contact_email":f"space{i+1:02d}@makolo.demo","country":country,"city":city,"public_profile":True,"verification_status":"verified","created_by":creator})
        team,_=Team.objects.update_or_create(pk=sid(f"team:{i}"), defaults={"organization":space,"name":"Équipe principale","is_default":True,"is_active":True})
        for j in range(min(5,len(users))):
            TeamMembership.objects.update_or_create(team=team,user=users[(i*3+j)%len(users)],defaults={"status":TeamMembershipStatus.ACTIVE,"invited_by":creator,"joined_at":at-timedelta(days=120)})
        grant_space_role(profile=creator,space=space,role=SystemRoleCode.SPACE_OWNER,granted_by=users[0],source=SEED)
        spaces.append(space)
    stats["spaces"] = len(spaces)
    bulk(OrganizationFollow,[OrganizationFollow(id=sid(f"orgfollow:{i}:{j}"),organization=spaces[(i+j*7)%len(spaces)],user=u,notify_new_events=True,notify_announcements=True) for i,u in enumerate(users) for j in range(min(3,len(spaces)))])
    bulk(ProfileFollow,[ProfileFollow(id=sid(f"profilefollow:{i}"),organizer_profile=users[(i+7)%len(users)],user=u,notify_new_activities=True) for i,u in enumerate(users) if users[(i+7)%len(users)].pk != u.pk])

    venues={}
    for i,p in enumerate(places):
        venues[p.pk],_=EventVenue.objects.get_or_create(pk=sid(f"venue:{i}"),defaults={"name":p.locality,"kind":VenueKind.PHYSICAL,"place":p,"is_active":True})
    categories={}
    for _,topic,_,_,_,_ in ACTIVITY_TEMPLATES:
        categories.setdefault(topic,EventCategory.objects.get_or_create(name=f"World Demo — {topic.title()}")[0])

    activities=[]; occs=[]; links=[]; pools=[]; offers=[]; atops=[]; events=[]; services=[]
    for i in range(cfg["activities"]):
        vertical,topic,title_base,price,capacity,source=ACTIVITY_TEMPLATES[i%len(ACTIVITY_TEMPLATES)]
        space=spaces[i%len(spaces)]; place=places[(i*5+1)%len(places)]; d1=spread(i); d2=d1+timedelta(days=14)
        activity=Activity(id=sid(f"activity:{i}"),space=space,created_by=space.created_by,title=f"{title_base} {place.locality} — {i+1:03d}",slug=f"world-{i+1:04d}-{topic}",short_description=f"{title_base}: expérience synthétique ancrée dans les réalités 2025–2026.",description=f"Donnée synthétique. Référence de calibration publique: {source}",status=ActivityStatus.PUBLISHED if d2>=at.date() else ActivityStatus.COMPLETED,visibility=ActivityVisibility.PUBLIC)
        activities.append(activity)
        for n,day in enumerate((d1,d2),1):
            start=aware(day,9+(i%7),place.timezone or "Africa/Lubumbashi"); end=start+timedelta(hours=6 if vertical=="event" else 3)
            occ=Occurrence(id=sid(f"occ:{i}:{n}"),activity=activity,label=f"Session {n}",start_date=day,start_time=start.timetz().replace(tzinfo=None),end_date=day,end_time=end.timetz().replace(tzinfo=None),timing_kind=OccurrenceTimingKind.EXACT,start_at=start,end_at=end,timezone=place.timezone or "Africa/Lubumbashi",status=OccurrenceStatus.SCHEDULED if day>=at.date() else OccurrenceStatus.COMPLETED)
            occs.append(occ); links.append(OccurrencePlace(id=sid(f"oplace:{i}:{n}"),occurrence=occ,place=place,role=OccurrencePlaceRole.PRIMARY,position=0))
            if n==1:
                pool=CapacityPool(id=sid(f"pool:{i}"),activity=activity,occurrence=occ,label="Places",total_quantity=capacity,is_active=True,source_key=f"world:activity:{i}:capacity")
                pools.append(pool); offers.append(Offer(id=sid(f"offer:{i}"),activity=activity,occurrence=occ,capacity_pool=pool,name="Accès standard",unit_price=price,currency="USD",payment_mode=PaymentMode.NONE if price==0 else PaymentMode.UPFRONT,available_from=start-timedelta(days=90),available_until=start-timedelta(hours=1),min_quantity=1,max_quantity=4,status=OfferStatus.ACTIVE,source_key=f"world:activity:{i}:offer"))
        t=next((x for x in topics if x.code==topic),topics[i%len(topics)]); atops.append(ActivityTopic(id=sid(f"atop:{i}:1"),activity=activity,topic=t)); atops.append(ActivityTopic(id=sid(f"atop:{i}:2"),activity=activity,topic=topics[(i+5)%len(topics)]))
        if vertical=="event":
            events.append(Event(id=sid(f"event:{i}"),activity=activity,category=categories[topic],venue=venues[place.pk],slug=f"world-event-{i+1:04d}",registration_start_at=aware(d1,9,place.timezone)-timedelta(days=75),registration_end_at=aware(d1,8,place.timezone),published_at=aware(d1,9,place.timezone)-timedelta(days=90),metadata={"seed":SEED,"synthetic":True,"cover_url":f"https://picsum.photos/seed/makolo-world-{i+1:04d}/1200/675","calibration_url":source}))
        elif vertical=="service":
            services.append(ServiceDetails(id=sid(f"service:{i}"),activity=activity,service_kind=ServiceKind.CAREER_SUPPORT if topic=="emploi" else ServiceKind.ORIENTATION,opportunity_policy=OpportunityPolicy.OPTIONAL,intake_policy=IntakePolicy.AUTO_CONFIRM,allows_external_beneficiary=True,completion_policy=CompletionPolicy.REQUIRED_STEPS))
    for model,rows in ((Activity,activities),(Occurrence,occs),(OccurrencePlace,links),(CapacityPool,pools),(Offer,offers),(ActivityTopic,atops),(Event,events),(ServiceDetails,services)): bulk(model,rows)
    activities=list(Activity.objects.filter(pk__in=[a.pk for a in activities]).order_by("slug")); occs=list(Occurrence.objects.filter(pk__in=[o.pk for o in occs]).select_related("activity").order_by("start_date","id")); poolmap={x.activity_id:x for x in CapacityPool.objects.filter(source_key__startswith="world:activity:")}; offermap={x.activity_id:x for x in Offer.objects.filter(source_key__startswith="world:activity:")}
    stats.update(activities=len(activities),occurrences=len(occs),events=len(events),services=len(services))

    firstocc={}
    for o in occs:firstocc.setdefault(o.activity_id,o)
    journeys=[]; reservations=[]; accesses=[]; creds=[]; uses=[]; orders=[]; items=[]; payments=[]
    for i in range(cfg["journeys"]):
        a=activities[i%len(activities)]; o=firstocc[a.pk]; u=users[(i*7+3)%len(users)]; offer=offermap.get(a.pk)
        status=JourneyStatus.FULFILLED if o.start_date<at.date() else (JourneyStatus.PENDING_PAYMENT if offer and offer.unit_price>0 and i%7==0 else (JourneyStatus.DRAFT if i%11==0 else JourneyStatus.CONFIRMED))
        try:a.service_details; workflow=WorkflowKind.SERVICE
        except ServiceDetails.DoesNotExist:workflow=WorkflowKind.PURCHASE if offer and offer.unit_price>0 else WorkflowKind.REGISTRATION
        j=Journey(id=sid(f"journey:{i}"),initiated_by=u,beneficiary=u,activity=a,occurrence=o,workflow=workflow,status=status,submitted_at=o.start_at-timedelta(days=30) if status!=JourneyStatus.DRAFT else None,confirmed_at=o.start_at-timedelta(days=20) if status in {JourneyStatus.CONFIRMED,JourneyStatus.FULFILLED} else None,fulfilled_at=o.end_at+timedelta(hours=1) if status==JourneyStatus.FULFILLED else None,expires_at=o.start_at-timedelta(days=2) if status in {JourneyStatus.DRAFT,JourneyStatus.PENDING_PAYMENT} else None); journeys.append(j)
        pool=poolmap.get(a.pk)
        if pool and status!=JourneyStatus.DRAFT:reservations.append(CapacityReservation(id=sid(f"res:{i}"),pool=pool,journey=j,quantity=1,status=CapacityReservationStatus.COMMITTED if status!=JourneyStatus.PENDING_PAYMENT else CapacityReservationStatus.HELD,committed_at=o.start_at-timedelta(days=10) if status!=JourneyStatus.PENDING_PAYMENT else None,expires_at=at+timedelta(hours=2) if status==JourneyStatus.PENDING_PAYMENT else None,source_key=f"world:{i}"))
        if status in {JourneyStatus.CONFIRMED,JourneyStatus.FULFILLED}:
            ac=Access(id=sid(f"access:{i}"),beneficiary=u,activity=a,occurrence=o,journey=j,status=AccessStatus.USED if status==JourneyStatus.FULFILLED else AccessStatus.VALID,single_use=True,source_key=f"world:{i}",valid_from=o.start_at-timedelta(hours=2),valid_until=o.end_at+timedelta(hours=2)); accesses.append(ac)
            cr=AccessCredential(id=sid(f"cred:{i}"),access=ac,credential_type=CredentialType.QR,status=CredentialStatus.ACTIVE,public_id=sid(f"pubcred:{i}"),version=1,issued_at=o.start_at-timedelta(days=5)); creds.append(cr)
            if status==JourneyStatus.FULFILLED:uses.append(AccessUse(id=sid(f"use:{i}"),access=ac,credential=cr,occurrence=o,result=AccessUseResult.ACCEPTED,source="world-demo",client_reference=f"world-use-{i}",used_at=o.start_at+timedelta(minutes=15)))
        if offer and offer.unit_price>0 and status in {JourneyStatus.CONFIRMED,JourneyStatus.FULFILLED}:
            order=CommerceOrder(id=sid(f"order:{i}"),reference=f"WRLD-{i+1:08d}",journey=j,buyer=u,payee_space=a.space,status=CommerceOrderStatus.CONFIRMED,currency="USD",payment_mode=PaymentMode.UPFRONT,subtotal=offer.unit_price,discount_total=Decimal("0"),total=offer.unit_price,expected_payee_amount=Decimal("0"),makolo_amount=Decimal("0"),financial_snapshot={},confirmed_at=o.start_at-timedelta(days=15),idempotency_key=f"world-order:{i}",source_key=f"world-order:{i}"); orders.append(order); items.append(CommerceOrderItem(id=sid(f"item:{i}"),order=order,offer=offer,beneficiary=u,quantity=1,label_snapshot=offer.name,unit_price=offer.unit_price,line_subtotal=offer.unit_price,discount_total=Decimal("0"),line_total=offer.unit_price))
            if i%5!=0:payments.append(Payment(id=sid(f"pay:{i}"),reference=f"PAYW-{i+1:08d}",commerce_order=order,initiated_by=u,provider=PaymentProvider.SANDBOX,method=PaymentMethod.MOBILE_MONEY,status=PaymentStatus.SUCCEEDED,amount=offer.unit_price,currency="USD",payer_name=u.full_name,payer_email=u.email,provider_reference=f"sandbox-world-{i}",idempotency_key=f"world-payment:{i}",metadata={"seed":SEED},processed_at=o.start_at-timedelta(days=14),succeeded_at=o.start_at-timedelta(days=14)))
    for model,rows in ((Journey,journeys),(CapacityReservation,reservations),(Access,accesses),(AccessCredential,creds),(AccessUse,uses),(CommerceOrder,orders),(CommerceOrderItem,items),(Payment,payments)):bulk(model,rows)
    stats.update(journeys=len(journeys),accesses=len(accesses),payments=len(payments))

    opps=[]; revs=[]; sources=[]; checks=[]; reqs=[]
    for i in range(cfg["opportunities"]):
        kind,title,issuer,summary,remote,cal=OPP_TEMPLATES[i%len(OPP_TEMPLATES)]; p=places[(i*3+2)%len(places)]; deadline=aware(spread(i+5),23,p.timezone or "Africa/Lubumbashi"); opens=deadline-timedelta(days=60)
        opp=Opportunity(id=sid(f"opp:{i}"),kind=kind,created_by=users[0]); rev=OpportunityRevision(id=sid(f"rev:{i}"),opportunity=opp,version=1,title=f"{title} {p.locality} — {i+1:03d}",summary=summary,issuer_name=issuer,opens_at=opens,deadline_at=deadline,timezone=p.timezone or "Africa/Lubumbashi",application_instructions="Opportunity entièrement synthétique de démonstration; vérifier toute opportunité réelle auprès de sa source officielle.",remote_allowed=remote,created_by=users[0]); src=OpportunitySource(id=sid(f"src:{i}"),opportunity=opp,source_type=OpportunitySourceType.AGGREGATOR,source_name="Source synthétique Makolo Demo",url=f"https://example.org/makolo-world/opportunities/{i+1:04d}",external_reference=f"WORLD-{i+1:05d}",is_primary=True,status=OpportunitySourceStatus.ACTIVE,discovered_at=opens,last_checked_at=min(at,deadline)); chk=OpportunitySourceCheck(id=sid(f"chk:{i}"),source=src,result=OpportunitySourceCheckResult.UNCHANGED,checked_at=min(at,deadline),checked_by=users[0],fingerprint=hashlib.sha256(f"world-{i}".encode()).hexdigest()[:32],note=f"Référence de calibration publique: {cal}")
        opps.append(opp);revs.append(rev);sources.append(src);checks.append(chk);reqs.append(OpportunityRequirement(id=sid(f"req:{i}:1"),revision=rev,kind=OpportunityRequirementKind.DOCUMENT,title="CV / dossier à jour",description="Requirement synthétique.",is_mandatory=True,position=10));reqs.append(OpportunityRequirement(id=sid(f"req:{i}:2"),revision=rev,kind=OpportunityRequirementKind.EXPERIENCE if kind in {OpportunityKind.JOB,OpportunityKind.INTERNSHIP} else OpportunityRequirementKind.ELIGIBILITY,title="Critère principal d'éligibilité",description="Requirement synthétique.",is_mandatory=True,position=20))
    for model,rows in ((Opportunity,opps),(OpportunityRevision,revs),(OpportunitySource,sources),(OpportunitySourceCheck,checks),(OpportunityRequirement,reqs)):bulk(model,rows)
    omap={x.pk:x for x in Opportunity.objects.filter(pk__in=[o.pk for o in opps])};rmap={x.pk:x for x in OpportunityRevision.objects.filter(pk__in=[r.pk for r in revs])}
    for i in range(cfg["opportunities"]):
        opp=omap[sid(f"opp:{i}")];rev=rmap[sid(f"rev:{i}")]
        if rev.published_at is None:publish_opportunity_revision(opportunity=opp,revision=rev,actor=users[0])
        elif opp.publication_status!=OpportunityPublicationStatus.PUBLISHED or opp.current_revision_id!=rev.pk:Opportunity.objects.filter(pk=opp.pk).update(publication_status=OpportunityPublicationStatus.PUBLISHED,current_revision=rev,published_at=rev.published_at)
    published=list(Opportunity.objects.filter(sources__external_reference__startswith="WORLD-").distinct())
    bulk(OpportunitySave,[OpportunitySave(id=sid(f"save:{i}"),profile=users[i%len(users)],opportunity=published[(i*7+3)%len(published)]) for i in range(cfg["saves"])])
    stats["opportunities"]=len(opps)

    needs=[];proposals=[]
    for i in range(cfg["needs"]):
        owner=users[i%len(users)];candidate=users[(i*11+7)%len(users)];candidate=users[(i+1)%len(users)] if candidate.pk==owner.pk else candidate;a=activities[(i*3)%len(activities)];day=spread(i+2);past=day<at.date();need=ActionNeed(id=sid(f"need:{i}"),owner_profile=owner,created_by=owner,title=f"[Demo] {MATCHES[i%len(MATCHES)].replace('_',' ').title()} — {a.title[:100]}",description="Besoin synthétique ancré dans une action Makolo.",match_kind=MATCHES[i%len(MATCHES)],candidate_kind=ActionNeedCandidateKind.PROFILE,activity=a,visibility=ActionNeedVisibility.PUBLIC if i%3 else ActionNeedVisibility.MATCHED,intake_policy=ActionNeedIntakePolicy.OPEN if i%2 else ActionNeedIntakePolicy.MATCHED,target_count=1+(i%4),opens_at=aware(day,8),closes_at=aware(day,20)+timedelta(days=30),needed_from=aware(day,9),needed_until=aware(day,18)+timedelta(days=45),status=ActionNeedStatus.FILLED if past else ActionNeedStatus.OPEN);needs.append(need);proposals.append(ActionProposal(id=sid(f"proposal:{i}"),need=need,candidate_profile=candidate,initiated_by=owner,direction=ActionProposalDirection.OWNER_TO_CANDIDATE,status=ActionProposalStatus.ACCEPTED if past else ActionProposalStatus.PENDING,message="Proposition synthétique pour coordonner une action réelle.",response_message="D'accord, coordonnons." if past else "",responded_by=candidate if past else None,responded_at=aware(day,12) if past else None,expires_at=aware(day,20)+timedelta(days=30),client_reference=f"world-proposal-{i}"))
    bulk(ActionNeed,needs);bulk(ActionProposal,proposals);proposals=list(ActionProposal.objects.filter(client_reference__startswith="world-proposal-").order_by("client_reference"));stats["action_needs"]=len(needs)

    convs=[];contexts=[];policies=[];parts=[];points=[];responses=[]
    for i in range(cfg["conversations"]):
        creator=users[i%len(users)];other=users[(i*9+5)%len(users)];other=users[(i+1)%len(users)] if other.pk==creator.pk else other;opened=aware(spread(i+1),9);c=Conversation(id=sid(f"conv:{i}"),title_override=f"Coordination Makolo — {i+1:03d}",purpose="Conversation synthétique orientée vers une action concrète.",lifecycle=ConversationLifecycle.OPEN,mode_preset=ConversationModePreset.MIXED,entry_mode=ConversationEntryMode.DERIVED,discoverability=ConversationDiscoverability.HIDDEN,history_policy=ConversationHistoryPolicy.CONTEXT_HISTORY,client_reference=f"world-conversation-{i}",created_by=creator,opened_at=opened);convs.append(c)
        if i<min(len(users),cfg["conversations"]//2):
            a,b=sorted((creator,other),key=lambda u:str(u.pk));contexts.append(ConversationContext(id=sid(f"ctx:{i}"),conversation=c,kind=ConversationContextKind.DIRECT,direct_profile_a=a,direct_profile_b=b,purpose_key="coordination"))
        elif proposals and i%3==0:contexts.append(ConversationContext(id=sid(f"ctx:{i}"),conversation=c,kind=ConversationContextKind.ACTION_PROPOSAL,action_proposal=proposals[i%len(proposals)],purpose_key="coordination"))
        else:contexts.append(ConversationContext(id=sid(f"ctx:{i}"),conversation=c,kind=ConversationContextKind.ACTIVITY,activity=activities[i%len(activities)],purpose_key="coordination"))
        policies.append(ConversationPolicy(conversation=c,preset=ConversationModePreset.MIXED,allow_information=True,allow_questions=True,allow_confirmations=True,allow_polls=True,allow_requests=True,allow_form_requests=True,allow_free_exchange=True,allow_voice=True,allow_images=True,allow_video=False,allow_documents=True,allow_links=True))
        for k,u in enumerate((creator,other)):parts.append(ConversationParticipation(id=sid(f"part:{i}:{k}"),conversation=c,profile=u,source=ConversationParticipationSource.MANUAL,status=ConversationParticipationStatus.ACTIVE,joined_at=opened,created_by=creator))
        specs=((ConversationPointKind.INFORMATION,ConversationPointResponseMode.NONE,"Information pratique",False),(ConversationPointKind.QUESTION,ConversationPointResponseMode.FREE_TEXT,"Question à clarifier",True),(ConversationPointKind.CONFIRMATION,ConversationPointResponseMode.BOOLEAN,"Confirmation attendue",True),(ConversationPointKind.EXCHANGE,ConversationPointResponseMode.FREE_TEXT,"Échange de coordination",True))
        for k,(kind,mode,title,expects) in enumerate(specs):
            pt=ConversationPoint(id=sid(f"point:{i}:{k}"),conversation=c,kind=kind,response_mode=mode,resolution_policy=ConversationPointResolutionPolicy.MANUAL,title=title,body="Point synthétique pour faire avancer la coordination.",lifecycle=ConversationPointLifecycle.OPEN,requires_acknowledgement=kind==ConversationPointKind.INFORMATION,opens_at=opened,deadline_at=opened+timedelta(days=14) if expects else None,response_visibility="respondent_and_authorities",allow_response_change=True,published_by=creator,client_reference=f"world-point-{i}-{k}",published_at=opened);points.append(pt)
            if expects:responses.append(ConversationPointResponse(id=sid(f"response:{i}:{k}"),point=pt,actor=other,value=True if mode==ConversationPointResponseMode.BOOLEAN else "Réponse synthétique de coordination.",status=ConversationPointResponseStatus.ACTIVE,client_reference=f"world-response-{i}-{k}",submitted_at=opened+timedelta(hours=6)))
    for model,rows in ((Conversation,convs),(ConversationContext,contexts),(ConversationPolicy,policies),(ConversationParticipation,parts),(ConversationPoint,points),(ConversationPointResponse,responses)):bulk(model,rows)
    stats["conversations"]=len(convs)

    kinds=[ContributionKind.UPDATE,ContributionKind.TIP,ContributionKind.FIELD_NOTE,ContributionKind.DISCUSSION];messages=["Les inscriptions sont ouvertes; vérifiez votre préparation.","Conseil terrain: préparez vos documents et votre accès.","Retour d'expérience: la coordination en amont réduit les blocages.","Qui souhaite coordonner le déplacement ou partager les points pratiques ?"]
    bulk(Contribution,[Contribution(id=sid(f"contrib:{i}"),author_profile=users[(i*7+1)%len(users)],kind=kinds[i%len(kinds)],body=messages[i%len(messages)],activity=activities[(i*13+2)%len(activities)],visibility=ContributionVisibility.PUBLIC if i%4 else ContributionVisibility.CONTEXT,status=ContributionStatus.PUBLISHED) for i in range(cfg["contributions"])])
    stats["contributions"]=cfg["contributions"]
    return stats, users[:5]


def counts():
    wu=User.objects.filter(email__endswith="@makolo.demo"); wa=Activity.objects.filter(slug__startswith="world-"); wo=Opportunity.objects.filter(sources__external_reference__startswith="WORLD-").distinct(); wc=Conversation.objects.filter(client_reference__startswith="world-conversation-"); wp=ConversationPoint.objects.filter(client_reference__startswith="world-point-")
    c={"users":wu.count(),"profiles":UserProfile.objects.filter(user__in=wu).count(),"interests":ProfileInterest.objects.filter(profile__in=wu).count(),"open_to":ProfileOpenTo.objects.filter(profile__in=wu).count(),"spaces":Organization.objects.filter(slug__startswith="world-").count(),"teams":Team.objects.filter(organization__slug__startswith="world-").count(),"memberships":TeamMembership.objects.filter(team__organization__slug__startswith="world-").count(),"org_follows":OrganizationFollow.objects.filter(organization__slug__startswith="world-").count(),"profile_follows":ProfileFollow.objects.filter(user__in=wu).count(),"places":Place.objects.filter(name__startswith="World Demo —").count(),"zones":Zone.objects.filter(name__startswith="World Demo —").count(),"activities":wa.count(),"activity_topics":ActivityTopic.objects.filter(activity__in=wa).count(),"occurrences":Occurrence.objects.filter(activity__in=wa).count(),"occurrence_places":OccurrencePlace.objects.filter(occurrence__activity__in=wa).count(),"events":Event.objects.filter(activity__in=wa).count(),"services":ServiceDetails.objects.filter(activity__in=wa).count(),"pools":CapacityPool.objects.filter(source_key__startswith="world:activity:").count(),"offers":Offer.objects.filter(source_key__startswith="world:activity:").count(),"journeys":Journey.objects.filter(activity__in=wa,beneficiary__in=wu).count(),"reservations":CapacityReservation.objects.filter(source_key__startswith="world:").count(),"accesses":Access.objects.filter(source_key__startswith="world:").count(),"credentials":AccessCredential.objects.filter(access__source_key__startswith="world:").count(),"uses":AccessUse.objects.filter(source="world-demo").count(),"orders":CommerceOrder.objects.filter(source_key__startswith="world-order:").count(),"order_items":CommerceOrderItem.objects.filter(order__source_key__startswith="world-order:").count(),"payments":Payment.objects.filter(idempotency_key__startswith="world-payment:").count(),"opportunities":wo.count(),"revisions":OpportunityRevision.objects.filter(opportunity__in=wo).count(),"sources":OpportunitySource.objects.filter(external_reference__startswith="WORLD-").count(),"checks":OpportunitySourceCheck.objects.filter(source__external_reference__startswith="WORLD-").count(),"requirements":OpportunityRequirement.objects.filter(revision__opportunity__in=wo).count(),"saves":OpportunitySave.objects.filter(opportunity__in=wo,profile__in=wu).count(),"needs":ActionNeed.objects.filter(title__startswith="[Demo]").count(),"proposals":ActionProposal.objects.filter(client_reference__startswith="world-proposal-").count(),"conversations":wc.count(),"contexts":ConversationContext.objects.filter(conversation__in=wc).count(),"policies":ConversationPolicy.objects.filter(conversation__in=wc).count(),"participants":ConversationParticipation.objects.filter(conversation__in=wc).count(),"points":wp.count(),"responses":ConversationPointResponse.objects.filter(point__in=wp).count(),"contributions":Contribution.objects.filter(activity__in=wa).count()};c["total_records"]=sum(c.values());return c


class Command(BaseCommand):
    help="Seed a deterministic, explicitly synthetic Makolo world spanning Jan 2025-Dec 2026. Demo/beta only."
    def add_arguments(self,p):
        p.add_argument("--profile",choices=sorted(SCALES),default="full");p.add_argument("--as-of",required=True);p.add_argument("--demo-password",default=None)
    def handle(self,*args,**o):
        password=o["demo_password"] or os.environ.get("MAKOLO_DEMO_PASSWORD")
        if not password:raise CommandError("Set MAKOLO_DEMO_PASSWORD or pass --demo-password.")
        try:
            with transaction.atomic():stats,users=seed_world(o["profile"],o["as_of"],password)
        except Exception as exc:raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS("Makolo realistic synthetic world seed complete"));self.stdout.write(f"Profile: {o['profile']} | As of: {o['as_of']}")
        for k,v in sorted(stats.items()):self.stdout.write(f"{k}: {v}")
        self.stdout.write("Login examples:")
        for u in users:self.stdout.write(f"  {u.email}")
        self.stdout.write("Password accepted from runtime input; value intentionally not printed.")
