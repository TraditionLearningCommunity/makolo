import 'dart:async';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

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
  bool _switching = false;
  String? _error;
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
    if (_switching) return;
    final controller = widget.runtime.actorContext;
    if (controller == null) return;
    await controller.selectPersonal();
    if (mounted) Navigator.of(context).pop();
  }

  Future<void> _selectSpace(SpaceSummary summary) async {
    if (_switching) return;
    final controller = widget.runtime.actorContext;
    final repository = widget.runtime.space;
    if (controller == null || repository?.sync == null) {
      setState(
        () => _error = 'Une connexion est nécessaire pour vérifier cet Espace.',
      );
      return;
    }
    setState(() {
      _switching = true;
      _error = null;
    });
    try {
      await repository!.refreshInventory();
      final inventoryState = await repository.readSource(
        repository.inventorySource(),
      );
      if (inventoryState.lastSuccessAt == null ||
          inventoryState.invalidated ||
          inventoryState.lastErrorCode != null) {
        throw StateError('Inventaire non vérifié.');
      }
      final authorized = (await repository.readInventory()).any(
        (space) =>
            space.identity.id == summary.identity.id &&
            space.identity.slug == summary.identity.slug,
      );
      if (!authorized) {
        throw StateError(
          'Cet Espace ne figure plus parmi vos accès autorisés.',
        );
      }
      await repository.refreshWorkspace(summary.identity);
      final workspaceState = await repository.readSource(
        repository.workspaceSource(summary.identity),
      );
      if (workspaceState.lastSuccessAt == null ||
          workspaceState.invalidated ||
          workspaceState.lastErrorCode != null) {
        throw StateError('Contexte Space non vérifié.');
      }
      final current = controller.value;
      await controller.selectSpace(
        summary.identity,
        perspective:
            current is SpaceActorContext &&
                current.space.id == summary.identity.id
            ? current.perspective
            : const ActorPerspective.all(),
      );
      if (mounted) Navigator.of(context).pop();
    } on Object {
      if (mounted) {
        setState(
          () => _error = 'Impossible de vérifier cet Espace. Votre contexte n’a pas changé.',
        );
      }
    } finally {
      if (mounted) setState(() => _switching = false);
    }
  }

  void _openCreateSpace() {
    final router = GoRouter.of(context);
    Navigator.of(context).pop();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      router.push('/space/create');
    });
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
                      onTap: _switching ? null : _selectPersonal,
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
                        onTap: _switching ? null : () => _selectSpace(space),
                      ),
                    if (spaces.isEmpty)
                      const Padding(
                        padding: EdgeInsets.symmetric(
                          vertical: MakoloSpacing.md,
                        ),
                        child: Text(
                          'Aucun Espace autorisé connu pour le moment.',
                        ),
                      ),
                    if (_error != null)
                      Padding(
                        padding: const EdgeInsets.symmetric(
                          vertical: MakoloSpacing.sm,
                        ),
                        child: Text(
                          _error!,
                          style: TextStyle(
                            color: Theme.of(context).colorScheme.error,
                          ),
                        ),
                      ),
                    if (_switching) const LinearProgressIndicator(),
                    const SizedBox(height: MakoloSpacing.md),
                    if (widget.runtime.api != null && repository.sync != null)
                      OutlinedButton.icon(
                        onPressed: _switching ? null : _openCreateSpace,
                        icon: const Icon(Icons.add),
                        label: const Text('Créer un Espace'),
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
