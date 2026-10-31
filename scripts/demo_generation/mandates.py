"""Mandates Activity non-admin sur les seules occurrences de demonstration actives."""
import argparse
import unicodedata

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--grantor",default="beta_staff")
    p.add_argument("--limit",type=int,default=20)
    p.add_argument("--apply",action="store_true")
    a=p.parse_args(argv)
    if not 1<=a.limit<=200: p.error("--limit doit etre entre 1 et 200")
    import django
    django.setup()
    from django.contrib.auth import get_user_model
    from django.db import connection, transaction
    from django.utils import timezone
    from activities.models import Activity, ActivityStatus, Occurrence, OccurrenceStatus
    from authorization.constants import SystemRoleCode
    from authorization.services import grant_activity_role
    from operations.permissions import user_can_manage_activity_operations
    if connection.vendor!="sqlite": p.error("SQLite de demonstration seulement")
    User=get_user_model()
    grantor=User.objects.filter(username=a.grantor,is_active=True).first()
    if grantor is None: p.error("Grantor inconnu ou inactif")
    now=timezone.now()
    live_occurrences=(Occurrence.objects.select_related("activity").filter(
        activity__slug__startswith="demo-",
        activity__status=ActivityStatus.PUBLISHED,
        start_at__lte=now,end_at__gt=now,
    ).exclude(status__in=[OccurrenceStatus.CANCELLED,OccurrenceStatus.COMPLETED])
     .order_by("start_at","id"))
    # Use the same earliest-active-first order as scale.py: a mandate must
    # actually cover Journeys seeded in the current Live time window.
    candidates=[]
    seen=set()
    for occurrence in live_occurrences:
        if occurrence.activity_id in seen:
            continue
        seen.add(occurrence.activity_id)
        candidates.append(occurrence.activity)
    def normalized(text):
        return "".join(c for c in unicodedata.normalize("NFKD",(text or "").lower())
                       if not unicodedata.combining(c))
    def transport(activity):
        name=normalized((activity.title or "")+" "+(activity.slug or ""))
        return any(word in name for word in ("transport","voyage","bus","navette","trajet"))
    for username,expected_transport in (("beta_transport_operator",True),("beta_event_manager",False)):
        user=User.objects.filter(username=username,is_active=True,is_staff=False,is_superuser=False).first()
        if user is None:
            print(username,": compte beta non administrateur indisponible")
            continue
        matches=[activity for activity in candidates
            if transport(activity)==expected_transport
            and user_can_manage_activity_operations(grantor,activity)][:a.limit]
        print(username,":",len(matches),"Activity eligibles")
        for activity in matches:
            print(" ",str(activity.pk),activity.title)
        if a.apply:
            with transaction.atomic():
                for activity in matches:
                    grant_activity_role(profile=user,activity=activity,
                        role_code=SystemRoleCode.ACTIVITY_OPERATIONS_MANAGER,
                        granted_by=grantor,source="makolo-demo-generation")
            print("Mandates verifies/attribues:",len(matches))
