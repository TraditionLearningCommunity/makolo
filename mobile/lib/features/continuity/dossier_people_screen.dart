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
    this.onOpenMyPassport,
    this.actorContext,
  });

  final String id;
  final ObjectiveRepository repository;
  final ValueChanged<String> onOpenPerson;
  final VoidCallback? onOpenMyPassport;
  final ActorContextController? actorContext;

  @override
  State<DossierPeopleScreen> createState() => _DossierPeopleScreenState();
}

class _DossierPeopleScreenState extends State<DossierPeopleScreen> {
  bool _refreshing = false;
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
    });
    try {
      await widget.repository.refresh(
        ObjectiveDepth.dossier,
        widget.id,
        spaceSlug: slug,
      );
    } on Object {
      // Retain usable local data; automatic network errors remain silent.
    } finally {
      if (mounted && revision == _revision) {
        setState(() => _refreshing = false);
      }
    }
  }

  Widget _personTile(Map<String, dynamic> row, String key, String subtitle) {
    final name = (row[key]?.toString() ?? '').trim();
    final id = row['profile_id']?.toString() ?? '';
    // A visible Assignment or Mandate does not open a private Profile.
    // Older cached projections lacking this owner-backed link stay read-only.
    final isSelf = row['profile_view'] == 'self';
    final canOpen =
        id.isNotEmpty &&
        (row['profile_url']?.toString() ?? '').isNotEmpty &&
        (!isSelf || widget.onOpenMyPassport != null);
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
      trailing: canOpen ? const Icon(Icons.chevron_right_rounded) : null,
      onTap: !canOpen
          ? null
          : isSelf
          ? widget.onOpenMyPassport
          : () => widget.onOpenPerson(id),
    );
  }

  @override
  Widget build(BuildContext context) {
    final slug = _spaceSlug;
    final identity = '${widget.id}:${slug ?? 'personal'}';
    return Scaffold(
      appBar: AppBar(title: const Text('Personnes et responsabilités')),
      body: StreamBuilder<OwnerSourceState>(
        key: ValueKey('people-owner:$identity'),
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
            key: ValueKey('people-detail:$identity'),
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
                    if (title.isNotEmpty)
                      Padding(
                        padding: const EdgeInsets.only(bottom: 10),
                        child: Text(
                          title,
                          style: Theme.of(context).textTheme.titleMedium
                              ?.copyWith(fontWeight: FontWeight.w800),
                        ),
                      ),
                    if ((owner['label']?.toString() ?? '').isNotEmpty)
                      ListTile(
                        dense: true,
                        contentPadding: EdgeInsets.zero,
                        leading: Icon(
                          owner['kind'] == 'space'
                              ? Icons.groups_outlined
                              : Icons.person_outline_rounded,
                        ),
                        title: Text(owner['label']!.toString()),
                        subtitle: const Text('Porteur du Dossier'),
                      ),
                    if (assignments.isEmpty && mandates.isEmpty)
                      const Padding(
                        padding: EdgeInsets.symmetric(vertical: 20),
                        child: Text('Aucune personne visible pour ce Dossier.'),
                      ),
                    if (assignments.isNotEmpty) ...[
                      const SizedBox(height: 10),
                      Text(
                        'Coordination',
                        style: Theme.of(context).textTheme.titleMedium
                            ?.copyWith(fontWeight: FontWeight.w800),
                      ),
                      for (final item in assignments)
                        _personTile(
                          item,
                          'label',
                          'Responsabilité opérationnelle',
                        ),
                    ],
                    if (mandates.isNotEmpty) ...[
                      const SizedBox(height: 12),
                      Text(
                        'Autorisations',
                        style: Theme.of(context).textTheme.titleMedium
                            ?.copyWith(fontWeight: FontWeight.w800),
                      ),
                      for (final item in mandates)
                        _personTile(
                          item,
                          'profile',
                          'Mandat · ${item['role']?.toString() ?? 'Rôle non précisé'}',
                        ),
                    ],
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
