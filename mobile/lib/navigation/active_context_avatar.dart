import 'package:flutter/material.dart';

import '../app/runtime/actor_context.dart';
import '../app/runtime/app_runtime.dart';
import '../design/makolo_theme.dart';
import '../features/space/space_repository.dart';
import 'profile_avatar_image.dart';

/// The header visual identifies the active working context, not the
/// authenticated account. A Space is NEVER rendered from ProfilePortraitStore.
class ActiveContextAvatar extends StatelessWidget {
  const ActiveContextAvatar({
    super.key,
    required this.runtime,
    required this.actor,
    required this.size,
    this.personalLetter,
    this.personalUrl,
    this.personalRevision,
  });

  final AppRuntime runtime;
  final ActorContext actor;
  final double size;
  final String? personalLetter;
  final String? personalUrl;
  final Object? personalRevision;

  @override
  Widget build(BuildContext context) {
    if (actor case SpaceActorContext(:final space)) {
      return StreamBuilder<List<SpaceSummary>>(
        stream: runtime.space?.watchInventory(),
        builder: (context, snapshot) {
          final name = activeSpaceName(space, snapshot.data);
          final label = spaceMonogram(name);
          return ColoredBox(
            color: MakoloColors.indigo,
            child: SizedBox.square(
              dimension: size,
              child: Center(
                child: Text(
                  label,
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    fontSize: size * (label.length > 1 ? 0.30 : 0.43),
                    fontWeight: FontWeight.w800,
                    color: Colors.white,
                  ),
                ),
              ),
            ),
          );
        },
      );
    }
    return ProfileAvatarImage(
      profileId: runtime.personal?.store.profileId,
      api: runtime.api,
      url: personalUrl,
      revision: personalRevision,
      size: size,
      fallback: Center(
        child: Text(
          personalLetter ?? '?',
          style: TextStyle(
            fontWeight: FontWeight.w700,
            color: Theme.of(context).colorScheme.onPrimaryContainer,
          ),
        ),
      ),
    );
  }
}

/// Presentation-only lookup. Space name is sourced from the owner inventory;
/// the slug is an offline fallback, never a copied identity fact.
String activeSpaceName(
  SpaceActorIdentity space,
  List<SpaceSummary>? inventory,
) {
  for (final item in inventory ?? const <SpaceSummary>[]) {
    if (item.identity.id == space.id) return item.name;
  }
  return space.slug;
}

String spaceMonogram(String name) {
  final words = name.trim().split(RegExp(r'\s+')).where((w) => w.isNotEmpty);
  if (words.isEmpty) return 'E';
  final letters = words.take(2).map((w) => w.substring(0, 1)).join();
  return letters.toUpperCase();
}
