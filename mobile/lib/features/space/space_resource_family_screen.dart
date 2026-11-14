import 'dart:async';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../app/runtime/actor_context.dart';
import '../../app/runtime/app_runtime.dart';
import '../../data/local/profile_store.dart';
import '../../design/makolo_theme.dart';
import '../../sync/owner_source_state.dart';
import '../resources/resource_presentation.dart';

class SpaceResourceFamilyScreen extends StatefulWidget {
  const SpaceResourceFamilyScreen({
    super.key,
    required this.runtime,
    required this.slug,
    required this.kind,
  });

  final AppRuntime runtime;
  final String slug;
  final String kind;

  @override
  State<SpaceResourceFamilyScreen> createState() =>
      _SpaceResourceFamilyScreenState();
}

class _SpaceResourceFamilyScreenState extends State<SpaceResourceFamilyScreen> {
  final _search = TextEditingController();
  bool _refreshing = false;

  static const _labels = <String, (String, IconData)>{
    'asset': ('Nos médias', Icons.photo_library_outlined),
    'template': ('Nos modèles', Icons.content_copy_outlined),
    'theme': ('Nos thèmes', Icons.palette_outlined),
    'credential': ('Titres émis', Icons.workspace_premium_outlined),
    'received_title': ('Titres reçus', Icons.verified_outlined),
  };

  SpaceActorContext? get _actor {
    final actor = widget.runtime.actorContext?.value;
    return actor is SpaceActorContext && actor.space.slug == widget.slug
        ? actor
        : null;
  }

  bool get _supported => _labels.containsKey(widget.kind);

  @override
  void initState() {
    super.initState();
    widget.runtime.actorContext?.addListener(_actorChanged);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) unawaited(_ensure());
    });
  }

  @override
  void dispose() {
    widget.runtime.actorContext?.removeListener(_actorChanged);
    _search.dispose();
    super.dispose();
  }

  void _actorChanged() {
    if (!mounted) return;
    setState(() {});
    unawaited(_ensure());
  }

  Future<void> _ensure() async {
    final actor = _actor;
    final repository = widget.runtime.space;
    if (!_supported ||
        actor == null ||
        repository == null ||
        repository.sync == null) {
      return;
    }
    try {
      await repository.ensureResourceFamily(actor.space, widget.kind);
    } on Object {
      // Local-first: a previously acquired family remains readable.
    }
  }

  Future<void> _refresh() async {
    if (_refreshing) return;
    final actor = _actor;
    final repository = widget.runtime.space;
    if (!_supported ||
        actor == null ||
        repository == null ||
        repository.sync == null) {
      return;
    }
    final expected = actor.space.id;
    setState(() => _refreshing = true);
    try {
      await repository.refreshResourceFamily(actor.space, widget.kind);
    } on Object {
      // Keep the last acquired projection.
    } finally {
      if (mounted && _actor?.space.id == expected) {
        setState(() => _refreshing = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final descriptor = _labels[widget.kind];
    final actor = _actor;
    final repository = widget.runtime.space;
    if (descriptor == null || actor == null || repository == null) {
      return _scaffold(
        title: descriptor?.$1 ?? 'Ressources',
        count: null,
        children: const [
          Padding(
            padding: EdgeInsets.symmetric(vertical: MakoloSpacing.xl),
            child: Center(child: Text('Cette ressource n’est pas disponible.')),
          ),
        ],
      );
    }

    final source = repository.resourceFamilySource(actor.space, widget.kind);
    return StreamBuilder<OwnerSourceState>(
      stream: repository.watchSource(source),
      initialData: OwnerSourceState.unknown,
      builder: (context, sourceSnapshot) {
        final state = sourceSnapshot.data ?? OwnerSourceState.unknown;
        return StreamBuilder<StoredProjection?>(
          stream: repository.watchResourceFamily(actor.space, widget.kind),
          builder: (context, projectionSnapshot) {
            final payload = projectionSnapshot.data?.payload;
            final rows = _rows(payload?['items']);
            final count = payload?['count'] is num
                ? (payload!['count'] as num).toInt()
                : null;

            if (state.invalidated) {
              return _scaffold(
                title: descriptor.$1,
                count: null,
                children: const [
                  Padding(
                    padding: EdgeInsets.symmetric(vertical: MakoloSpacing.xl),
                    child: Center(
                      child: Text(
                        'Cette ressource n’est plus accessible dans ce contexte.',
                      ),
                    ),
                  ),
                ],
              );
            }

            final children = <Widget>[
              if (payload == null && state.lastSuccessAt == null)
                const Padding(
                  padding: EdgeInsets.symmetric(vertical: MakoloSpacing.xl),
                  child: Center(child: CircularProgressIndicator.adaptive()),
                )
              else if (rows.isEmpty)
                Padding(
                  padding: const EdgeInsets.symmetric(
                    vertical: MakoloSpacing.xl,
                  ),
                  child: Center(child: Text(_emptyLabel(widget.kind))),
                )
              else
                for (final row in rows)
                  Padding(
                    padding: const EdgeInsets.only(bottom: MakoloSpacing.sm),
                    child: Card(
                      child: ListTile(
                        leading: Icon(
                          descriptor.$2,
                          color: Theme.of(context).colorScheme.primary,
                        ),
                        title: Text(_text(row['title']) ?? 'Ressource'),
                        subtitle: _text(row['detail']) == null
                            ? null
                            : Text(_text(row['detail'])!),
                        trailing: _documentId(row) == null
                            ? null
                            : const Icon(Icons.chevron_right_rounded),
                        onTap: _documentId(row) == null
                            ? null
                            : () => context.push(
                                '/space/${widget.slug}/us/documents/'
                                '${_documentId(row)!}',
                              ),
                      ),
                    ),
                  ),
              if (payload?['has_more'] == true)
                Padding(
                  padding: const EdgeInsets.only(top: MakoloSpacing.sm),
                  child: Text(
                    'D’autres éléments existent. La suite sera chargée dans cette collection.',
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
                    ),
                  ),
                ),
            ];

            return _scaffold(
              title: descriptor.$1,
              count: state.lastErrorCode == null ? count : null,
              children: children,
            );
          },
        );
      },
    );
  }

  Widget _scaffold({
    required String title,
    required int? count,
    required List<Widget> children,
  }) => ResourceCollectionScaffold(
    title: title,
    count: count,
    searching: false,
    searchEnabled: false,
    searchController: _search,
    searchHint: '',
    onSearchChanged: (_) {},
    onOpenSearch: () {},
    onCloseSearch: () {},
    onRefresh: _refresh,
    refreshing: _refreshing,
    storageKey: PageStorageKey<String>(
      'space-resource-family:${_actor?.space.id ?? widget.slug}:${widget.kind}',
    ),
    children: children,
  );

  static List<Map<String, dynamic>> _rows(Object? value) {
    if (value is! List) return const [];
    return [
      for (final item in value)
        if (item is Map)
          item.map((key, value) => MapEntry(key.toString(), value)),
    ];
  }

  static String? _text(Object? value) {
    final text = value?.toString().trim();
    return text == null || text.isEmpty ? null : text;
  }

  static String? _documentId(Map<String, dynamic> row) {
    if (row['owner'] != 'space_assets') return null;
    final id = _text(row['id']);
    return id != null && RegExp(r'^[0-9a-fA-F-]{36}$').hasMatch(id) ? id : null;
  }

  static String _emptyLabel(String kind) => switch (kind) {
    'asset' => 'Aucun média pour le moment.',
    'template' => 'Aucun modèle pour le moment.',
    'theme' => 'Aucun thème pour le moment.',
    'credential' => 'Aucun titre émis pour le moment.',
    'received_title' => 'Aucun titre reçu pour le moment.',
    _ => 'Aucune ressource pour le moment.',
  };
}
