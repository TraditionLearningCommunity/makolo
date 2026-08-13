from events.activity_bridge import sync_event_core


def seed_activity_core(ctx):
    projected = 0
    for event in ctx.events:
        sync_event_core(event)
        projected += 1
    ctx.add("activity_core_projections", projected)
