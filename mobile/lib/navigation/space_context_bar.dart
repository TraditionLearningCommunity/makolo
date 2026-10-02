import 'package:flutter/material.dart';

import '../app/providers.dart';
import '../app/runtime/actor_context.dart';
import '../data/local/profile_store.dart';
import '../design/behavior_primitives.dart';
import '../design/makolo_theme.dart';
import '../features/space/space_repository.dart';
import 'actor_selector.dart';

class MakoloSpaceContextBar extends StatelessWidget {
  const MakoloSpaceContextBar({
    super.key,
    required this.runtime,
    required this.actor,
  });

  final AppRuntime runtime;
  final SpaceActorContext actor;

  @override
  Widget build(BuildContext context) {
    final repository = runtime.space;
    if (repository == null) return const SizedBox.shrink();

    return StreamBuilder<List<SpaceSummary>>(
      stream: repository.watchInventory(),
      builder: (context, inventorySnapshot) => StreamBuilder<StoredProjection?>(
        stream: repository.watchWorkspace(actor.space),
        builder: (context, workspaceSnapshot) {
          final spaces = inventorySnapshot.data ?? const <SpaceSummary>[];
          final bootstrap = _bootstrap(workspaceSnapshot.data);
          final spaceName = _spaceName(spaces, bootstrap);
          final perspectiveLabel = _perspectiveLabel(bootstrap);

          return Material(
            color: Theme.of(context).colorScheme.surface,
            child: Padding(
              padding: const EdgeInsets.fromLTRB(
                MakoloSpacing.md,
                MakoloSpacing.xs,
                MakoloSpacing.md,
                MakoloSpacing.sm,
              ),
              child: LayoutBuilder(
                builder: (context, constraints) {
                  final width = (constraints.maxWidth - MakoloSpacing.sm) / 2;
                  return Wrap(
                    spacing: MakoloSpacing.sm,
                    runSpacing: MakoloSpacing.xs,
                    children: [
                      SizedBox(
                        width: width,
                        child: Semantics(
                          button: true,
                          label: 'Changer d’Espace. Acteur actuel : $spaceName',
                          child: _ContextButton(
                            icon: Icons.groups_outlined,
                            label: spaceName,
                            onPressed: () => showMakoloActorPicker(
                              context,
                              runtime: runtime,
                            ),
                          ),
                        ),
                      ),
                      SizedBox(
                        width: width,
                        child: Semantics(
                          button: true,
                          label:
                              'Changer de responsabilité. Sélection actuelle : $perspectiveLabel',
                          child: _ContextButton(
                            icon: Icons.filter_alt_outlined,
                            label: perspectiveLabel,
                            onPressed: () => _showPerspectivePicker(
                              context,
                              bootstrap: bootstrap,
                            ),
                          ),
                        ),
                      ),
                    ],
                  );
                },
              ),
            ),
          );
        },
      ),
    );
  }

  SpaceBootstrap? _bootstrap(StoredProjection? projection) {
    if (projection == null) return null;
    try {
      return SpaceBootstrap.fromPayload(projection.payload);
    } on FormatException {
      return null;
    }
  }

  String _spaceName(List<SpaceSummary> spaces, SpaceBootstrap? bootstrap) {
    for (final item in spaces) {
      if (item.identity.id == actor.space.id) return item.name;
    }
    final payloadSpace = bootstrap?.payload['space'];
    if (payloadSpace is Map && payloadSpace['name'] is String) {
      final name = (payloadSpace['name'] as String).trim();
      if (name.isNotEmpty) return name;
    }
    return actor.space.slug;
  }

  String _perspectiveLabel(SpaceBootstrap? bootstrap) {
    final key = SpaceSyncKeys.perspectiveKey(actor.perspective);
    for (final item
        in bootstrap?.responsibilities ??
            const <SpaceResponsibilitySummary>[]) {
      if (item.key == key) return item.label;
    }
    return actor.perspective.isAll
        ? 'Toutes mes responsabilités'
        : 'Responsabilité sélectionnée';
  }

  Future<void> _showPerspectivePicker(
    BuildContext context, {
    required SpaceBootstrap? bootstrap,
  }) async {
    final controller = runtime.actorContext;
    if (controller == null) return;
    final current = controller.value;
    if (current is! SpaceActorContext || current.space.id != actor.space.id) {
      return;
    }

    final responsibilities = bootstrap?.responsibilities;
    final options = responsibilities == null || responsibilities.isEmpty
        ? const <SpaceResponsibilitySummary>[
            SpaceResponsibilitySummary(
              key: 'all',
              label: 'Toutes mes responsabilités',
              scope: 'space',
              combined: true,
            ),
          ]
        : responsibilities;

    await showMakoloBottomSheet<void>(
      context,
      builder: (sheetContext) => SafeArea(
        top: false,
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(
            MakoloSpacing.lg,
            MakoloSpacing.sm,
            MakoloSpacing.lg,
            MakoloSpacing.lg,
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(
                'Responsabilité',
                style: Theme.of(sheetContext).textTheme.titleLarge,
              ),
              const SizedBox(height: MakoloSpacing.md),
              for (final responsibility in options)
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  minVerticalPadding: MakoloSpacing.sm,
                  title: Text(
                    responsibility.label,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                  selected:
                      responsibility.key ==
                      SpaceSyncKeys.perspectiveKey(current.perspective),
                  trailing:
                      responsibility.key ==
                          SpaceSyncKeys.perspectiveKey(current.perspective)
                      ? const Icon(Icons.check)
                      : null,
                  onTap: () async {
                    final perspective = responsibility.key == 'all'
                        ? const ActorPerspective.all()
                        : ActorPerspective.opaque(responsibility.key);
                    await controller.selectPerspective(perspective);
                    if (sheetContext.mounted) {
                      Navigator.of(sheetContext).pop();
                    }
                  },
                ),
            ],
          ),
        ),
      ),
    );
  }
}

class _ContextButton extends StatelessWidget {
  const _ContextButton({
    required this.icon,
    required this.label,
    required this.onPressed,
  });

  final IconData icon;
  final String label;
  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    return OutlinedButton.icon(
      onPressed: onPressed,
      icon: Icon(icon, size: 18),
      label: Align(
        alignment: Alignment.centerLeft,
        child: Text(label, maxLines: 1, overflow: TextOverflow.ellipsis),
      ),
      style: OutlinedButton.styleFrom(
        minimumSize: const Size.fromHeight(48),
        padding: const EdgeInsets.symmetric(
          horizontal: MakoloSpacing.sm,
          vertical: MakoloSpacing.xs,
        ),
      ),
    );
  }
}
