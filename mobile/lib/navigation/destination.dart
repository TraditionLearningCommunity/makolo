import '../app/runtime/actor_context.dart';

enum MakoloPrimaryDoor { now, discover, continuity, identity }

enum MakoloDestination {
  personalNow(
    branchIndex: 0,
    path: '/now',
    label: 'Maintenant',
    door: MakoloPrimaryDoor.now,
    actorKind: ActorContextKind.personal,
  ),
  personalDiscover(
    branchIndex: 1,
    path: '/discover',
    label: 'Découvrir',
    door: MakoloPrimaryDoor.discover,
    actorKind: ActorContextKind.personal,
  ),
  personalContinuity(
    branchIndex: 2,
    path: '/ongoing',
    label: 'En cours',
    door: MakoloPrimaryDoor.continuity,
    actorKind: ActorContextKind.personal,
  ),
  personalIdentity(
    branchIndex: 3,
    path: '/me',
    label: 'Moi',
    door: MakoloPrimaryDoor.identity,
    actorKind: ActorContextKind.personal,
  ),
  spaceNow(
    branchIndex: 4,
    path: '/space/now',
    label: 'Maintenant',
    door: MakoloPrimaryDoor.now,
    actorKind: ActorContextKind.space,
  ),
  spaceDiscover(
    branchIndex: 5,
    path: '/space/discover',
    label: 'Découvrir',
    door: MakoloPrimaryDoor.discover,
    actorKind: ActorContextKind.space,
  ),
  spaceContinuity(
    branchIndex: 6,
    path: '/space/work',
    label: 'Métier',
    door: MakoloPrimaryDoor.continuity,
    actorKind: ActorContextKind.space,
  ),
  spaceIdentity(
    branchIndex: 7,
    path: '/space/us',
    label: 'Nous',
    door: MakoloPrimaryDoor.identity,
    actorKind: ActorContextKind.space,
  );

  const MakoloDestination({
    required this.branchIndex,
    required this.path,
    required this.label,
    required this.door,
    required this.actorKind,
  });

  final int branchIndex;
  final String path;
  final String label;
  final MakoloPrimaryDoor door;
  final ActorContextKind actorKind;

  bool get isSpace => actorKind == ActorContextKind.space;

  static MakoloDestination forBranchIndex(int index) {
    for (final destination in values) {
      if (destination.branchIndex == index) return destination;
    }
    return personalNow;
  }

  static MakoloDestination? forPath(String path) {
    for (final destination in values) {
      if (destination.path == path) return destination;
    }
    return null;
  }

  static MakoloDestination forActor(
    ActorContext actor,
    MakoloPrimaryDoor door,
  ) {
    final kind = actor.kind;
    for (final destination in values) {
      if (destination.actorKind == kind && destination.door == door) {
        return destination;
      }
    }
    return kind == ActorContextKind.space ? spaceNow : personalNow;
  }

  static List<MakoloDestination> primaryForActor(ActorContext actor) {
    final kind = actor.kind;
    return values
        .where((destination) => destination.actorKind == kind)
        .toList(growable: false);
  }
}

class StructuredDestination {
  const StructuredDestination({
    required this.kind,
    required this.id,
    this.link,
  });

  final String kind;
  final String id;
  final String? link;
}
