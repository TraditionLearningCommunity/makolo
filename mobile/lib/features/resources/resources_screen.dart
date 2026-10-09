import 'dart:async';

import 'package:flutter/material.dart';

import '../../data/local/profile_store.dart';
import '../../design/makolo_components.dart';
import '../../design/makolo_theme.dart';
import '../../sync/freshness.dart';
import 'resource_repository.dart';

class ResourcesScreen extends StatefulWidget {
  const ResourcesScreen({
    super.key,
    required this.repository,
    required this.onOpenResource,
  });

  final ResourceRepository repository;
  final ValueChanged<String> onOpenResource;

  @override
  State<ResourcesScreen> createState() => _ResourcesScreenState();
}

class _ResourcesScreenState extends State<ResourcesScreen> {
  final _search = TextEditingController();
  String _query = '';
  bool _refreshing = false;
  bool _loadingMore = false;

  @override
  void initState() {
    super.initState();
    unawaited(_ensureFirstPage());
  }

  @override
  void dispose() {
    _search.dispose();
    super.dispose();
  }

  Future<void> _ensureFirstPage() async {
    final cached = await widget.repository.readCollectionPage(
      query: _query,
      offset: 0,
    );
    if (cached == null && mounted) await _refreshFirst();
  }

  Future<void> _refreshFirst() async {
    if (_refreshing) return;
    setState(() => _refreshing = true);
    try {
      await widget.repository.refreshCollectionPage(query: _query, offset: 0);
    } on Object {
      // Existing local metadata remains useful when the owner is unreachable.
    } finally {
      if (mounted) setState(() => _refreshing = false);
    }
  }

  Future<void> _loadMore(_ResourcesView view) async {
    if (_loadingMore || !view.hasMore) return;
    setState(() => _loadingMore = true);
    try {
      await widget.repository.refreshCollectionPage(
        query: _query,
        offset: view.nextOffset,
      );
    } on Object {
      // Keep already acquired pages visible.
    } finally {
      if (mounted) setState(() => _loadingMore = false);
    }
  }

  void _submitSearch(String value) {
    final next = value.trim();
    if (next == _query) {
      unawaited(_refreshFirst());
      return;
    }
    setState(() => _query = next);
    unawaited(_ensureFirstPage());
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Mes ressources'),
        actions: [
          IconButton(
            tooltip: 'Actualiser',
            onPressed: _refreshing ? null : _refreshFirst,
            icon: const Icon(Icons.refresh_rounded),
          ),
        ],
      ),
      body: StreamBuilder<List<StoredProjection>>(
        stream: widget.repository.watchCollectionPages(),
        initialData: const [],
        builder: (context, pagesSnapshot) {
          final view = _ResourcesView.fromPages(
            pagesSnapshot.data ?? const [],
            query: _query,
          );
          return StreamBuilder<ResourceSourceState>(
            stream: widget.repository.watchCollectionSource(query: _query),
            initialData: ResourceSourceState.unknown,
            builder: (context, sourceSnapshot) {
              final source = sourceSnapshot.data ?? ResourceSourceState.unknown;
              return RefreshIndicator(
                onRefresh: _refreshFirst,
                child: ListView(
                  key: PageStorageKey<String>('resources:' + _query),
                  physics: const AlwaysScrollableScrollPhysics(),
                  padding: const EdgeInsets.all(MakoloSpacing.inner),
                  children: [
                    TextField(
                      controller: _search,
                      onSubmitted: _submitSearch,
                      textInputAction: TextInputAction.search,
                      decoration: InputDecoration(
                        labelText: 'Rechercher dans mes documents',
                        suffixIcon: IconButton(
                          tooltip: 'Rechercher',
                          onPressed: () => _submitSearch(_search.text),
                          icon: const Icon(Icons.search_rounded),
                        ),
                      ),
                    ),
                    if (source.reachability == ReachabilityState.unreachable &&
                        view.hasAnyContent) ...[
                      const SizedBox(height: MakoloSpacing.md),
                      Text(
                        'Métadonnées connues sur cet appareil. '
                        'La disponibilité des fichiers n’est pas supposée.',
                        style: Theme.of(context).textTheme.bodySmall?.copyWith(
                          color: Theme.of(context).colorScheme.onSurfaceVariant,
                        ),
                      ),
                    ],
                    const SizedBox(height: MakoloSpacing.lg),
                    _SectionTitle(
                      title: 'Bibliothèque',
                      subtitle: _query.isEmpty
                          ? 'Documents personnels contrôlés'
                          : 'Résultats dans les titres',
                    ),
                    if (view.documents.isEmpty)
                      Padding(
                        padding: const EdgeInsets.symmetric(
                          vertical: MakoloSpacing.lg,
                        ),
                        child: Text(
                          _query.isEmpty
                              ? 'Aucune ressource enregistrée pour le moment.'
                              : 'Aucun document correspondant.',
                        ),
                      )
                    else
                      for (final document in view.documents)
                        _ResourceRow(
                          icon: Icons.description_outlined,
                          title: document.title,
                          subtitle: [
                            document.kindLabel,
                            if (document.validityLabel != null)
                              document.validityLabel!,
                            if (document.sensitivityLabel != null)
                              document.sensitivityLabel!,
                          ].join(' · '),
                          onTap: () => widget.onOpenResource(document.id),
                        ),
                    if (view.hasMore) ...[
                      const SizedBox(height: MakoloSpacing.sm),
                      OutlinedButton(
                        onPressed: _loadingMore ? null : () => _loadMore(view),
                        child: Text(
                          _loadingMore ? 'Chargement…' : 'Afficher la suite',
                        ),
                      ),
                    ],
                    if (_query.isEmpty) ...[
                      const SizedBox(height: MakoloSpacing.xl),
                      const _SectionTitle(
                        title: 'Proofs',
                        subtitle: 'Faits établis, distincts des fichiers',
                      ),
                      if (view.proofs.isEmpty)
                        const Text('Aucune Proof disponible.')
                      else
                        for (final proof in view.proofs)
                          _ResourceRow(
                            icon: Icons.verified_outlined,
                            title: proof.title,
                            subtitle: proof.subtitle,
                          ),
                      const SizedBox(height: MakoloSpacing.xl),
                      const _SectionTitle(
                        title: 'Credentials',
                        subtitle: 'Titres émis par un owner Trust',
                      ),
                      if (view.credentials.isEmpty)
                        const Text('Aucun titre délivré pour le moment.')
                      else
                        for (final credential in view.credentials)
                          _ResourceRow(
                            icon: Icons.workspace_premium_outlined,
                            title: credential.title,
                            subtitle: credential.subtitle,
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

class _SectionTitle extends StatelessWidget {
  const _SectionTitle({required this.title, required this.subtitle});

  final String title;
  final String subtitle;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(bottom: MakoloSpacing.sm),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(title, style: Theme.of(context).textTheme.titleLarge),
        const SizedBox(height: MakoloSpacing.xs),
        Text(
          subtitle,
          style: Theme.of(context).textTheme.bodySmall
              ?.copyWith(color: Theme.of(context).colorScheme.onSurfaceVariant),
        ),
      ],
    ),
  );
}

class _ResourceRow extends StatelessWidget {
  const _ResourceRow({
    required this.icon,
    required this.title,
    required this.subtitle,
    this.onTap,
  });

  final IconData icon;
  final String title;
  final String subtitle;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) => MakoloCard(
    onTap: onTap,
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(icon),
        const SizedBox(width: MakoloSpacing.md),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(title, style: Theme.of(context).textTheme.titleMedium),
              const SizedBox(height: MakoloSpacing.xs),
              Text(
                subtitle,
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color: Theme.of(context).colorScheme.onSurfaceVariant,
                ),
              ),
            ],
          ),
        ),
        if (onTap != null) const Icon(Icons.chevron_right_rounded),
      ],
    ),
  );
}

class _ResourcesView {
  const _ResourcesView({
    required this.documents,
    required this.proofs,
    required this.credentials,
    required this.hasMore,
    required this.nextOffset,
  });

  final List<_DocumentItem> documents;
  final List<_SimpleItem> proofs;
  final List<_SimpleItem> credentials;
  final bool hasMore;
  final int nextOffset;

  bool get hasAnyContent =>
      documents.isNotEmpty || proofs.isNotEmpty || credentials.isNotEmpty;

  factory _ResourcesView.fromPages(
    List<StoredProjection> pages, {
    required String query,
  }) {
    final encoded = Uri.encodeComponent(query.trim());
    final prefix = encoded + ':';
    final selected =
        pages
            .where(
              (page) =>
                  page.kind == ResourceRepository.collectionProjectionKind &&
                  page.resourceKey.startsWith(prefix),
            )
            .toList()
          ..sort((a, b) => _offset(a).compareTo(_offset(b)));

    if (selected.isEmpty) {
      return const _ResourcesView(
        documents: [],
        proofs: [],
        credentials: [],
        hasMore: false,
        nextOffset: 0,
      );
    }

    final documents = <_DocumentItem>[];
    final seen = <String>{};
    for (final page in selected) {
      final section = _map(page.payload['documents']);
      final rows = section['items'];
      if (rows is! List) continue;
      for (final raw in rows) {
        final row = _map(raw);
        final id = _string(row['id']);
        final title = _string(row['title']);
        if (id == null || title == null || !seen.add(id)) continue;
        final current = _map(row['current_version']);
        final validity = _map(current['validity']);
        documents.add(
          _DocumentItem(
            id: id,
            title: title,
            kindLabel: _string(row['asset_kind_label']) ?? 'Document',
            sensitivityLabel: _string(row['sensitivity_label']),
            validityLabel: _validity(validity),
          ),
        );
      }
    }

    final first = selected.first.payload;
    final proofs = _simpleItems(
      _map(first['proofs'])['items'],
      fallback: 'Proof',
      typeKeys: const ['proof_type_label', 'proof_type'],
      statusKey: 'status_label',
    );
    final credentials = _simpleItems(
      _map(first['credentials'])['items'],
      fallback: 'Credential',
      typeKeys: const ['title', 'credential_type_label'],
      statusKey: 'status_label',
    );

    final lastPage = _map(selected.last.payload['documents']);
    final page = _map(lastPage['page']);
    final offset = page['offset'] is num
        ? (page['offset'] as num).toInt()
        : _offset(selected.last);
    final limit = page['limit'] is num
        ? (page['limit'] as num).toInt()
        : ResourceRepository.defaultLimit;

    return _ResourcesView(
      documents: List.unmodifiable(documents),
      proofs: List.unmodifiable(proofs),
      credentials: List.unmodifiable(credentials),
      hasMore: page['has_more'] == true || lastPage['has_more'] == true,
      nextOffset: offset + limit,
    );
  }

  static int _offset(StoredProjection page) {
    final parts = page.resourceKey.split(':');
    if (parts.length >= 3) return int.tryParse(parts[parts.length - 2]) ?? 0;
    return 0;
  }
}

class _DocumentItem {
  const _DocumentItem({
    required this.id,
    required this.title,
    required this.kindLabel,
    this.sensitivityLabel,
    this.validityLabel,
  });

  final String id;
  final String title;
  final String kindLabel;
  final String? sensitivityLabel;
  final String? validityLabel;
}

class _SimpleItem {
  const _SimpleItem({required this.title, required this.subtitle});

  final String title;
  final String subtitle;
}

List<_SimpleItem> _simpleItems(
  Object? raw, {
  required String fallback,
  required List<String> typeKeys,
  required String statusKey,
}) {
  if (raw is! List) return const [];
  final result = <_SimpleItem>[];
  for (final item in raw) {
    final row = _map(item);
    String? title;
    for (final key in typeKeys) {
      title ??= _string(row[key]);
    }
    title ??= fallback;
    final status = _string(row[statusKey]);
    result.add(
      _SimpleItem(
        title: title,
        subtitle: status == null ? fallback : fallback + ' · ' + status,
      ),
    );
  }
  return result;
}

String? _validity(Map<String, dynamic> validity) {
  final state = _string(validity['state']);
  return switch (state) {
    'current' => 'valide',
    'expired' => 'expiré',
    'not_yet_issued' => 'pas encore émis',
    'unknown' || null => 'validité inconnue',
    _ => state,
  };
}

Map<String, dynamic> _map(Object? value) {
  if (value is Map<String, dynamic>) return value;
  if (value is Map) {
    return value.map((key, item) => MapEntry(key.toString(), item));
  }
  return const {};
}

String? _string(Object? value) {
  final text = value?.toString().trim();
  return text == null || text.isEmpty ? null : text;
}
