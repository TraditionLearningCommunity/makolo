import 'dart:async';

import 'package:flutter/material.dart';

import '../app/providers.dart';
import '../app/runtime/actor_context.dart';
import '../design/behavior_primitives.dart';
import '../design/makolo_theme.dart';
import '../features/space/space_repository.dart';

Future<void> showMakoloActorPicker(
  BuildContext context, {
  required AppRuntime runtime,
}) async {
  await showMakoloBottomSheet<void>(
    context,
    builder: (_) => _MakoloActorPicker(runtime: runtime),
  );
}

class MakoloActorSelectorTile extends StatelessWidget {
  const MakoloActorSelectorTile({super.key, required this.runtime, this.onTap});

  final AppRuntime runtime;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final controller = runtime.actorContext;
    final repository = runtime.space;
    if (controller == null || repository == null) {
      return const ListTile(
        contentPadding: EdgeInsets.zero,
        leading: Icon(Icons.person_pin_circle_outlined),
        title: Text('Agir comme'),
        subtitle: Text('Moi'),
      );
    }

    return StreamBuilder<List<SpaceSummary>>(
      stream: repository.watchInventory(),
      builder: (context, snapshot) => ListenableBuilder(
        listenable: controller,
        builder: (context, _) {
          final spaces = snapshot.data ?? const <SpaceSummary>[];
          final actor = controller.value;
          final label = _actorLabel(actor, spaces);
          return ListTile(
            contentPadding: EdgeInsets.zero,
            minVerticalPadding: MakoloSpacing.sm,
            leading: const Icon(Icons.person_pin_circle_outlined),
            title: const Text('Agir comme'),
            subtitle: Text(
              actor is SpaceActorContext
                  ? 'Agit actuellement pour $label'
                  : 'Moi',
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
            trailing: const Icon(Icons.chevron_right),
            onTap:
                onTap ?? () => showMakoloActorPicker(context, runtime: runtime),
          );
        },
      ),
    );
  }
}

class _MakoloActorPicker extends StatefulWidget {
  const _MakoloActorPicker({required this.runtime});

  final AppRuntime runtime;

  @override
  State<_MakoloActorPicker> createState() => _MakoloActorPickerState();
}

class _MakoloActorPickerState extends State<_MakoloActorPicker> {
  @override
  void initState() {
    super.initState();
    final repository = widget.runtime.space;
    if (repository?.sync != null) {
      unawaited(_refreshInventory());
    }
  }

  Future<void> _refreshInventory() async {
    try {
      await widget.runtime.space?.refreshInventory();
    } on Object {
      // Cached actor contexts remain usable when refresh is unavailable.
    }
  }

  Future<void> _selectPersonal() async {
    final controller = widget.runtime.actorContext;
    if (controller == null) return;
    await controller.selectPersonal();
    if (mounted) Navigator.of(context).pop();
  }

  Future<void> _selectSpace(SpaceSummary summary) async {
    final controller = widget.runtime.actorContext;
    if (controller == null) return;

    final current = controller.value;
    if (current is SpaceActorContext &&
        current.space.id == summary.identity.id) {
      await controller.selectSpace(
        summary.identity,
        perspective: current.perspective,
      );
    } else {
      await controller.selectSpace(summary.identity);
    }

    final repository = widget.runtime.space;
    if (repository?.sync != null) {
      unawaited(_refreshWorkspace(summary.identity));
    }
    if (mounted) Navigator.of(context).pop();
  }

  Future<void> _refreshWorkspace(SpaceActorIdentity space) async {
    try {
      await widget.runtime.space?.refreshWorkspace(space);
    } on Object {
      // The shell keeps local context; server revalidation remains authoritative.
    }
  }

  @override
  Widget build(BuildContext context) {
    final controller = widget.runtime.actorContext;
    final repository = widget.runtime.space;
    if (controller == null || repository == null) {
      return const Padding(
        padding: EdgeInsets.all(MakoloSpacing.lg),
        child: Text('Moi'),
      );
    }

    return StreamBuilder<List<SpaceSummary>>(
      stream: repository.watchInventory(),
      builder: (context, snapshot) => ListenableBuilder(
        listenable: controller,
        builder: (context, _) {
          final actor = controller.value;
          final spaces = snapshot.data ?? const <SpaceSummary>[];
          return SafeArea(
            top: false,
            child: SingleChildScrollView(
              padding: const EdgeInsets.fromLTRB(
                MakoloSpacing.lg,
                MakoloSpacing.sm,
                MakoloSpacing.lg,
                MakoloSpacing.lg,
              ),
              child: Semantics(
                container: true,
                label: 'Choisir pour qui Makolo travaille',
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Text(
                      'Agir comme',
                      style: Theme.of(context).textTheme.titleLarge,
                    ),
                    const SizedBox(height: MakoloSpacing.md),
                    ListTile(
                      contentPadding: EdgeInsets.zero,
                      minVerticalPadding: MakoloSpacing.sm,
                      leading: const Icon(Icons.person_outline),
                      title: const Text('Moi'),
                      trailing: actor is PersonalActorContext
                          ? const Icon(Icons.check)
                          : null,
                      selected: actor is PersonalActorContext,
                      onTap: _selectPersonal,
                    ),
                    for (final space in spaces)
                      ListTile(
                        contentPadding: EdgeInsets.zero,
                        minVerticalPadding: MakoloSpacing.sm,
                        leading: const Icon(Icons.groups_outlined),
                        title: Text(
                          space.name,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                        trailing:
                            actor is SpaceActorContext &&
                                actor.space.id == space.identity.id
                            ? const Icon(Icons.check)
                            : null,
                        selected:
                            actor is SpaceActorContext &&
                            actor.space.id == space.identity.id,
                        onTap: () => _selectSpace(space),
                      ),
                  ],
                ),
              ),
            ),
          );
        },
      ),
    );
  }
}

String _actorLabel(ActorContext actor, List<SpaceSummary> spaces) {
  if (actor is! SpaceActorContext) return 'Moi';
  for (final space in spaces) {
    if (space.identity.id == actor.space.id) return space.name;
  }
  return actor.space.slug;
}
