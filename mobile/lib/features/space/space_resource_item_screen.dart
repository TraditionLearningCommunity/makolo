import 'dart:async';

import 'package:flutter/material.dart';

import '../../app/runtime/actor_context.dart';
import '../../app/runtime/app_runtime.dart';
import '../../data/local/profile_store.dart';
import '../../design/makolo_theme.dart';
import '../../sync/owner_source_state.dart';
import '../resources/resource_presentation.dart';

class SpaceResourceItemScreen extends StatefulWidget {
  const SpaceResourceItemScreen({
    super.key,
    required this.runtime,
    required this.slug,
    required this.kind,
    required this.id,
  });
  final AppRuntime runtime;
  final String slug;
  final String kind;
  final String id;
  @override
  State<SpaceResourceItemScreen> createState() =>
      _SpaceResourceItemScreenState();
}

class _SpaceResourceItemScreenState extends State<SpaceResourceItemScreen> {
  bool _refreshing = false;

  SpaceActorContext? get _actor {
    final actor = widget.runtime.actorContext?.value;
    return actor is SpaceActorContext && actor.space.slug == widget.slug
        ? actor
        : null;
  }

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) unawaited(_ensure());
    });
  }

  Future<void> _ensure() async {
    final actor = _actor;
    final repository = widget.runtime.space;
    if (actor == null || repository == null || repository.sync == null) return;
    try {
      await repository.ensureResourceFamily(actor.space, widget.kind);
    } on Object {}
  }

  Future<void> _refresh() async {
    if (_refreshing) return;
    final actor = _actor;
    final repository = widget.runtime.space;
    if (actor == null || repository == null || repository.sync == null) return;
    final expected = actor.space.id;
    setState(() => _refreshing = true);
    try {
      await repository.refreshResourceFamily(actor.space, widget.kind);
    } on Object {
    } finally {
      if (mounted && _actor?.space.id == expected)
        setState(() => _refreshing = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final actor = _actor;
    final repository = widget.runtime.space;
    if (actor == null || repository == null) {
      return const Scaffold(
        body: Center(child: Text('Cette ressource n’est plus disponible.')),
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
            final item = _findItem(payload?['items'], widget.id);
            final title = _text(item?['title']) ?? _titleFor(widget.kind);
            final detail = _text(item?['detail']);
            final metadata = _map(item?['metadata']);
            final rows = item == null
                ? const <(String, String)>[]
                : _detailRows(widget.kind, item, metadata);
            return Scaffold(
              appBar: AppBar(
                title: Text(_titleFor(widget.kind)),
                actions: [
                  IconButton(
                    tooltip: 'Actualiser',
                    onPressed: _refreshing ? null : _refresh,
                    icon: _refreshing
                        ? const SizedBox.square(
                            dimension: 18,
                            child: CircularProgressIndicator.adaptive(
                              strokeWidth: 2,
                            ),
                          )
                        : const Icon(Icons.refresh_rounded),
                  ),
                ],
              ),
              body: state.invalidated
                  ? const Center(
                      child: Text(
                        'Cette ressource n’est plus accessible dans ce contexte.',
                        textAlign: TextAlign.center,
                      ),
                    )
                  : item == null
                  ? const Center(child: Text('Ressource indisponible.'))
                  : ListView(
                      padding: const EdgeInsets.all(MakoloSpacing.inner),
                      children: [
                        ResourceDocumentHeader(
                          title: title,
                          subtitle: detail ?? _subtitleFor(widget.kind),
                        ),
                        const SizedBox(height: MakoloSpacing.lg),
                        Card(
                          child: Padding(
                            padding: const EdgeInsets.all(MakoloSpacing.inner),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                for (
                                  var index = 0;
                                  index < rows.length;
                                  index++
                                ) ...[
                                  _DetailRow(
                                    label: rows[index].$1,
                                    value: rows[index].$2,
                                  ),
                                  if (index < rows.length - 1)
                                    const Divider(height: MakoloSpacing.lg),
                                ],
                              ],
                            ),
                          ),
                        ),
                        if (state.lastErrorCode != null &&
                            !state.invalidated) ...[
                          const SizedBox(height: MakoloSpacing.md),
                          Text(
                            'Dernières informations disponibles sur cet appareil.',
                            style: Theme.of(context).textTheme.bodySmall
                                ?.copyWith(
                                  color: Theme.of(context)
                                      .colorScheme
                                      .onSurfaceVariant,
                                ),
                          ),
                        ],
                      ],
                    ),
            );
          },
        );
      },
    );
  }
}

class _DetailRow extends StatelessWidget {
  const _DetailRow({required this.label, required this.value});
  final String label;
  final String value;
  @override
  Widget build(BuildContext context) => Row(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      SizedBox(
        width: 112,
        child: Text(
          label,
          style: Theme.of(context).textTheme.bodySmall
              ?.copyWith(color: Theme.of(context).colorScheme.onSurfaceVariant),
        ),
      ),
      Expanded(
        child: Text(value, style: Theme.of(context).textTheme.bodyMedium),
      ),
    ],
  );
}

Map<String, dynamic>? _findItem(Object? value, String id) {
  if (value is! List) return null;
  for (final raw in value) {
    final item = _map(raw);
    if (_text(item['id']) == id) return item;
  }
  return null;
}

Map<String, dynamic> _map(Object? value) {
  if (value is Map<String, dynamic>) return value;
  if (value is Map)
    return value.map((key, value) => MapEntry(key.toString(), value));
  return const {};
}

String? _text(Object? value) {
  final text = value?.toString().trim();
  return text == null || text.isEmpty ? null : text;
}

String _titleFor(String kind) => switch (kind) {
  'asset' => 'Média',
  'template' => 'Modèle',
  'theme' => 'Thème',
  'credential' => 'Titre émis',
  _ => 'Ressource',
};

String _subtitleFor(String kind) => switch (kind) {
  'asset' => 'Média de présentation de cet Espace',
  'template' => 'Modèle de présentation de cet Espace',
  'theme' => 'Thème de présentation de cet Espace',
  'credential' => 'Titre institutionnel émis par cet Espace',
  _ => 'Ressource de cet Espace',
};

List<(String, String)> _detailRows(
  String kind,
  Map<String, dynamic> item,
  Map<String, dynamic> metadata,
) {
  final rows = <(String, String)>[];
  final owner = _text(item['owner']);
  if (owner != null)
    rows.add(('Propriétaire', owner == 'trust' ? 'Confiance' : 'Présentation'));
  void add(String label, Object? value) {
    final text = _text(value);
    if (text != null) rows.add((label, text));
  }

  switch (kind) {
    case 'asset':
      add('Format', metadata['mime_type']);
      final size = metadata['size'];
      if (size is num) rows.add(('Taille', _formatBytes(size.toInt())));
      add('Ajouté le', _displayDate(metadata['created_at']));
      break;
    case 'template':
    case 'theme':
      add('Version', metadata['version_number']);
      add('État', metadata['status']);
      add('Visibilité', metadata['visibility']);
      add('Origine', metadata['provenance']);
      break;
    case 'credential':
      add('Type', metadata['credential_type']);
      add('État', metadata['status']);
      add('Émis le', _displayDate(metadata['issued_at']));
      add('Révoqué le', _displayDate(metadata['revoked_at']));
      break;
  }
  return rows.isEmpty ? [('Type', _subtitleFor(kind))] : rows;
}

String? _displayDate(Object? value) {
  final text = _text(value);
  if (text == null) return null;
  final parsed = DateTime.tryParse(text);
  if (parsed == null) return text;
  final local = parsed.toLocal();
  final day = local.day.toString().padLeft(2, '0');
  final month = local.month.toString().padLeft(2, '0');
  return day + '/' + month + '/' + local.year.toString();
}

String _formatBytes(int bytes) {
  if (bytes < 1024) return bytes.toString() + ' o';
  final kb = bytes / 1024;
  if (kb < 1024) return kb.toStringAsFixed(kb >= 10 ? 0 : 1) + ' Ko';
  final mb = kb / 1024;
  return mb.toStringAsFixed(mb >= 10 ? 0 : 1) + ' Mo';
}
