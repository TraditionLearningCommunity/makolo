import 'dart:async';

import 'package:flutter/material.dart';

import '../../data/local/profile_store.dart';
import '../../design/action_controls.dart';
import '../../design/makolo_components.dart';
import '../../design/makolo_theme.dart';
import '../../sync/freshness.dart';
import 'resource_repository.dart';
import 'trust_resource_repository.dart';

class ResourcesScreen extends StatefulWidget {
  const ResourcesScreen({
    super.key,
    required this.repository,
    required this.onOpenDocuments,
    this.trustRepository,
    this.onOpenProofs,
    this.onOpenTitles,
  });

  final ResourceRepository repository;
  final TrustResourceRepository? trustRepository;
  final VoidCallback onOpenDocuments;
  final VoidCallback? onOpenProofs;
  final VoidCallback? onOpenTitles;

  @override
  State<ResourcesScreen> createState() => _ResourcesScreenState();
}

class _ResourcesScreenState extends State<ResourcesScreen> {
  bool _refreshing = false;
  late Stream<List<StoredProjection>> _pages;
  late Stream<List<StoredProjection>> _proofPages;
  late Stream<List<StoredProjection>> _titlePages;
  late Stream<ResourceSourceState> _source;

  @override
  void initState() {
    super.initState();
    _pages = widget.repository.watchCollectionPages();
    _proofPages = widget.repository.store.watchProjections('personal.proofs');
    _titlePages = widget.repository.store.watchProjections('personal.titles');
    _source = widget.repository.watchCollectionSource(query: '', offset: 0);
    unawaited(_ensure());
  }

  @override
  void didUpdateWidget(covariant ResourcesScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.repository != widget.repository) {
      _pages = widget.repository.watchCollectionPages();
      _proofPages = widget.repository.store.watchProjections('personal.proofs');
      _titlePages = widget.repository.store.watchProjections('personal.titles');
      _source = widget.repository.watchCollectionSource(query: '', offset: 0);
      unawaited(_ensure());
    }
  }

  Future<void> _ensure() async {
    await _refreshOwners(ensureOnly: true);
  }

  Future<void> _refreshOwners({required bool ensureOnly}) async {
    final tasks = <Future<void>>[
      ensureOnly
          ? widget.repository.ensureCollectionPage(query: '', offset: 0)
          : widget.repository.refreshCollectionPage(query: '', offset: 0),
    ];
    final trust = widget.trustRepository;
    if (trust != null) {
      for (final family in TrustResourceFamily.values) {
        tasks.add(
          ensureOnly
              ? trust.ensureCollectionPage(family: family, query: '', offset: 0)
              : trust.refreshCollectionPage(
                  family: family,
                  query: '',
                  offset: 0,
                ),
        );
      }
    }
    for (final task in tasks) {
      try {
        await task;
      } on Object {
        // Each owner remains independent; one failure must not block the hub.
      }
    }
    try {
      await widget.repository.sync?.refreshPersonalMe();
    } on Object {
      // Moi keeps its last acquired projection if the root refresh is unavailable.
    }
  }

  Future<void> _refresh() async {
    if (_refreshing) return;
    setState(() => _refreshing = true);
    try {
      await _refreshOwners(ensureOnly: false);
    } finally {
      if (mounted) setState(() => _refreshing = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Mes ressources'),
        actions: [
          MakoloIconActionButton(
            tooltip: 'Actualiser',
            icon: Icons.refresh_rounded,
            onPressed: _refreshing ? null : _refresh,
          ),
        ],
      ),
      body: StreamBuilder<List<StoredProjection>>(
        stream: _pages,
        initialData: const [],
        builder: (context, documentSnapshot) {
          return StreamBuilder<List<StoredProjection>>(
            stream: _proofPages,
            initialData: const [],
            builder: (context, proofSnapshot) {
              return StreamBuilder<List<StoredProjection>>(
                stream: _titlePages,
                initialData: const [],
                builder: (context, titleSnapshot) {
                  final counts = _ResourceCounts.fromPages(
                    documentSnapshot.data ?? const [],
                    proofPages: proofSnapshot.data ?? const [],
                    titlePages: titleSnapshot.data ?? const [],
                  );
                  return StreamBuilder<ResourceSourceState>(
                    stream: _source,
                    initialData: ResourceSourceState.unknown,
                    builder: (context, sourceSnapshot) {
                      final source =
                          sourceSnapshot.data ?? ResourceSourceState.unknown;
                      return RefreshIndicator(
                        onRefresh: _refresh,
                        child: Center(
                          child: ConstrainedBox(
                            constraints: const BoxConstraints(maxWidth: 860),
                            child: ListView(
                              physics: const AlwaysScrollableScrollPhysics(),
                              padding: const EdgeInsets.all(
                                MakoloSpacing.inner,
                              ),
                              children: [
                                if (source.reachability ==
                                        ReachabilityState.unreachable ||
                                    source.invalidated) ...[
                                  Semantics(
                                    liveRegion: true,
                                    child: Text(
                                      source.ownerDenied
                                          ? 'Les compteurs de ressources ne sont plus disponibles.'
                                          : 'Les compteurs ne peuvent pas être actualisés pour le moment.',
                                      style: Theme.of(context)
                                          .textTheme
                                          .bodySmall
                                          ?.copyWith(
                                            color: Theme.of(context)
                                                .colorScheme
                                                .onSurfaceVariant,
                                          ),
                                    ),
                                  ),
                                  const SizedBox(height: MakoloSpacing.md),
                                ],
                                _ResourceEntry(
                                  icon: Icons.folder_copy_outlined,
                                  title: 'Mes documents',
                                  subtitle: 'Fichiers et pièces personnelles',
                                  count: counts.documents,
                                  onTap: widget.onOpenDocuments,
                                ),
                                const SizedBox(height: MakoloSpacing.md),
                                _ResourceEntry(
                                  icon: Icons.verified_outlined,
                                  title: 'Mes preuves',
                                  subtitle: 'Participations et faits attestés',
                                  count: counts.proofs,
                                  onTap: widget.onOpenProofs,
                                ),
                                const SizedBox(height: MakoloSpacing.md),
                                _ResourceEntry(
                                  icon: Icons.workspace_premium_outlined,
                                  title: 'Mes titres',
                                  subtitle:
                                      'Attestations et certificats délivrés',
                                  count: counts.titles,
                                  onTap: widget.onOpenTitles,
                                ),
                              ],
                            ),
                          ),
                        ),
                      );
                    },
                  );
                },
              );
            },
          );
        },
      ),
    );
  }
}

class _ResourceEntry extends StatelessWidget {
  const _ResourceEntry({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.count,
    required this.onTap,
  });

  final IconData icon;
  final String title;
  final String subtitle;
  final int? count;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) => MakoloCard(
    onTap: onTap,
    child: Row(
      children: [
        Container(
          width: 52,
          height: 52,
          alignment: Alignment.center,
          decoration: BoxDecoration(
            color: Theme.of(context).colorScheme.primary.withValues(alpha: .10),
            borderRadius: BorderRadius.circular(16),
          ),
          child: Icon(icon, color: Theme.of(context).colorScheme.primary),
        ),
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
        if (count != null && count! > 0) ...[
          const SizedBox(width: MakoloSpacing.sm),
          Text(
            '$count',
            style: Theme.of(context).textTheme.labelLarge
                ?.copyWith(color: Theme.of(context).colorScheme.primary),
          ),
        ],
        if (onTap != null) ...[
          const SizedBox(width: MakoloSpacing.xs),
          const Icon(Icons.chevron_right_rounded),
        ],
      ],
    ),
  );
}

class _ResourceCounts {
  const _ResourceCounts({this.documents, this.proofs, this.titles});

  final int? documents;
  final int? proofs;
  final int? titles;

  factory _ResourceCounts.fromPages(
    List<StoredProjection> pages, {
    List<StoredProjection> proofPages = const [],
    List<StoredProjection> titlePages = const [],
  }) {
    for (final page in pages.reversed) {
      if (page.kind != ResourceRepository.collectionProjectionKind) continue;
      final documents = _map(page.payload['documents']);
      if ((_string(documents['view']) ?? 'current') != 'current') continue;
      if ((_string(documents['query']) ?? '').isNotEmpty) continue;
      if ((_string(documents['sort']) ?? 'recent') != 'recent') continue;
      final filters = _map(documents['filters']);
      if ((_string(filters['kind']) ?? '').isNotEmpty ||
          (_string(filters['sensitivity']) ?? '').isNotEmpty) {
        continue;
      }
      final documentCount = _int(documents['count']);
      final proofs = _map(page.payload['proofs']);
      final credentials = _map(page.payload['credentials']);
      return _ResourceCounts(
        documents: documentCount,
        proofs:
            _trustOwnerCount(
              proofPages,
              projectionKind: 'personal.proofs',
              typeKey: 'proof_type',
            ) ??
            _int(proofs['count']),
        titles:
            _trustOwnerCount(
              titlePages,
              projectionKind: 'personal.titles',
              typeKey: 'credential_type',
            ) ??
            _int(credentials['count']),
      );
    }
    return const _ResourceCounts();
  }
}

int? _trustOwnerCount(
  List<StoredProjection> pages, {
  required String projectionKind,
  required String typeKey,
}) {
  StoredProjection? latest;
  for (final page in pages) {
    if (page.kind != projectionKind) continue;
    final payload = page.payload;
    if ((_string(payload['query']) ?? '').isNotEmpty) continue;
    if ((_string(payload['status']) ?? 'all') != 'all') continue;
    if ((_string(payload[typeKey]) ?? '').isNotEmpty) continue;
    if ((_string(payload['sort']) ?? 'recent') != 'recent') continue;
    final pageMeta = _map(payload['page']);
    if ((_int(pageMeta['offset']) ?? 0) != 0) continue;
    if (latest == null || page.receivedAt.isAfter(latest.receivedAt)) {
      latest = page;
    }
  }
  return latest == null ? null : _int(latest.payload['count']);
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

int? _int(Object? value) =>
    value is num ? value.toInt() : int.tryParse('$value');
