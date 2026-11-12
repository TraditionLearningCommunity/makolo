import 'dart:async';

import 'package:flutter/material.dart';

import '../../app/runtime/actor_context.dart';
import '../../app/runtime/actor_context_controller.dart';
import '../../data/local/profile_store.dart';
import '../../sync/owner_source_state.dart';
import 'objective_repository.dart';

Map<String, dynamic> _object(Object? raw) => raw is Map
    ? raw.map((key, value) => MapEntry('$key', value))
    : <String, dynamic>{};

List<Map<String, dynamic>> _items(Object? raw) => raw is List
    ? raw.map(_object).where((entry) => entry.isNotEmpty).toList()
    : <Map<String, dynamic>>[];

/// Read-only continuation of the canonical Dossier projection.
/// Assignments are never interpreted as Mandates.
class DossierPeopleScreen extends StatefulWidget {
  const DossierPeopleScreen({
    super.key,
    required this.id,
    required this.repository,
    required this.onOpenPerson,
    this.actorContext,
  });

  final String id;
  final ObjectiveRepository repository;
  final ValueChanged<String> onOpenPerson;
  final ActorContextController? actorContext;

  @override
  State<DossierPeopleScreen> createState() => _DossierPeopleScreenState();
}

class _DossierPeopleScreenState extends State<DossierPeopleScreen> {
  bool _refreshing = false;
  bool _refreshFailed = false;
  int _revision = 0;

  String? get _spaceSlug {
    final context = widget.actorContext?.value;
    return context is SpaceActorContext ? context.space.slug : null;
  }

  @override
  void initState() {
    super.initState();
    widget.actorContext?.addListener(_actorChanged);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) unawaited(_refresh());
    });
  }

  @override
  void didUpdateWidget(covariant DossierPeopleScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.actorContext != widget.actorContext) {
      oldWidget.actorContext?.removeListener(_actorChanged);
      widget.actorContext?.addListener(_actorChanged);
    }
    if (oldWidget.id != widget.id ||
        oldWidget.repository != widget.repository ||
        oldWidget.actorContext != widget.actorContext) {
      _revision++;
      _refreshing = false;
      _refreshFailed = false;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) unawaited(_refresh());
      });
    }
  }

  void _actorChanged() {
    if (!mounted) return;
    _revision++;
    setState(() {
      _refreshing = false;
      _refreshFailed = false;
    });
    unawaited(_refresh());
  }

  @override
  void dispose() {
    widget.actorContext?.removeListener(_actorChanged);
    super.dispose();
  }

  Future<void> _refresh() async {
    if (_refreshing) return;
    final revision = _revision;
    final slug = _spaceSlug;
    setState(() {
      _refreshing = true;
      _refreshFailed = false;
    });
    try {
      await widget.repository.refresh(
        ObjectiveDepth.dossier,
        widget.id,
        spaceSlug: slug,
      );
    } on Object {
      // A local snapshot remains readable, but is not a permission grant.
      if (mounted && revision == _revision) {
        setState(() => _refreshFailed = true);
      }
    } finally {
      if (mounted && revision == _revision) {
        setState(() => _refreshing = false);
      }
    }
  }

  Widget _personTile(Map<String, dynamic> row, String key, String subtitle) {
    final name = (row[key]?.toString() ?? '').trim();
    final id = row['profile_id']?.toString() ?? '';
    final scheme = Theme.of(context).colorScheme;
    return ListTile(
      leading: CircleAvatar(
        backgroundColor: scheme.primaryContainer,
        child: Text(
          name.isEmpty ? '•' : name.substring(0, 1).toUpperCase(),
          style: TextStyle(color: scheme.onPrimaryContainer),
        ),
      ),
      title: Text(name),
      subtitle: Text(subtitle),
      trailing: id.isEmpty ? null : const Icon(Icons.chevron_right_rounded),
      onTap: id.isEmpty ? null : () => widget.onOpenPerson(id),
    );
  }

  @override
  Widget build(BuildContext context) {
    final slug = _spaceSlug;
    final identity = widget.id + ':' + (slug ?? 'personal');
    return Scaffold(
      appBar: AppBar(
        title: const Text('Personnes et responsabilités'),
        actions: [
          IconButton(
            tooltip: 'Actualiser',
            onPressed: _refreshing ? null : _refresh,
            icon: const Icon(Icons.refresh_rounded),
          ),
        ],
      ),
      body: StreamBuilder<OwnerSourceState>(
        key: ValueKey('people-owner:' + identity),
        stream: widget.repository.watchSource(
          ObjectiveDepth.dossier,
          widget.id,
          spaceSlug: slug,
        ),
        initialData: OwnerSourceState.unknown,
        builder: (context, sourceSnapshot) {
          final source = sourceSnapshot.data ?? OwnerSourceState.unknown;
          if (source.invalidated) {
            return const Center(
              child: Text('Ce Dossier n’est plus accessible dans ce contexte.'),
            );
          }
          return StreamBuilder<StoredProjection?>(
            key: ValueKey('people-detail:' + identity),
            stream: widget.repository.watch(
              ObjectiveDepth.dossier,
              widget.id,
              spaceSlug: slug,
            ),
            builder: (context, snapshot) {
              final data = snapshot.data?.payload;
              if (data == null) {
                return Center(
                  child: _refreshing
                      ? const CircularProgressIndicator.adaptive()
                      : const Text('Aucune donnée locale disponible.'),
                );
              }
              final assignments = _items(data['assignments']);
              final mandates = _items(data['mandates']);
              final owner = _object(data['owner']);
              final title =
                  _object(data['objective'])['title']?.toString() ?? '';
              return RefreshIndicator(
                onRefresh: _refresh,
                child: ListView(
                  physics: const AlwaysScrollableScrollPhysics(),
                  padding: const EdgeInsets.fromLTRB(16, 14, 16, 36),
                  children: [
                    Text(
                      title,
                      style: Theme.of(context).textTheme.titleLarge
                          ?.copyWith(fontWeight: FontWeight.w800),
                    ),
                    const SizedBox(height: 12),
                    ListTile(
                      leading: Icon(
                        owner['kind'] == 'space'
                            ? Icons.groups_outlined
                            : Icons.person_outline_rounded,
                      ),
                      title: const Text('Porteur du Dossier'),
                      subtitle: Text(
                        owner['label']?.toString() ?? 'Non précisé',
                      ),
                    ),
                    if (source.lastErrorCode != null || _refreshFailed)
                      const Padding(
                        padding: EdgeInsets.all(8),
                        child: Text(
                          'Données enregistrées : actualisation indisponible.',
                        ),
                      ),
                    const SizedBox(height: 12),
                    Text(
                      'Coordination',
                      style: Theme.of(context).textTheme.titleMedium
                          ?.copyWith(fontWeight: FontWeight.w800),
                    ),
                    if (assignments.isEmpty)
                      const ListTile(
                        title: Text('Aucune responsabilité visible'),
                      )
                    else
                      for (final item in assignments)
                        _personTile(
                          item,
                          'label',
                          'Responsabilité opérationnelle',
                        ),
                    const SizedBox(height: 14),
                    Text(
                      'Autorisations',
                      style: Theme.of(context).textTheme.titleMedium
                          ?.copyWith(fontWeight: FontWeight.w800),
                    ),
                    if (mandates.isEmpty)
                      const ListTile(
                        title: Text('Aucun mandat visible dans ce contexte'),
                      )
                    else
                      for (final item in mandates)
                        _personTile(
                          item,
                          'profile',
                          'Mandat · ' +
                              (item['role']?.toString() ?? 'Rôle non précisé'),
                        ),
                    const SizedBox(height: 12),
                    Text(
                      'Une responsabilité opérationnelle ne donne pas '
                      'automatiquement le droit de gérer ce Dossier.',
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                  ],
                ),
              );
            },
          );
        },
      ),
    );
  }
}
