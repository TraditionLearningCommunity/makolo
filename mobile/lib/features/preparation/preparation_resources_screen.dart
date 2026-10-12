import 'dart:async';

import 'package:flutter/material.dart';

import '../../data/local/profile_store.dart';
import '../../design/behavior_primitives.dart';
import '../../design/behavior_states.dart';
import '../../design/makolo_components.dart';
import '../../design/makolo_patterns.dart';
import '../../design/makolo_theme.dart';
import '../../design/surface_states.dart';
import '../../presentation/projection_surface_adapter.dart';
import '../../selectors/projection_selector.dart';
import '../../sync/freshness.dart';
import '../../sync/owner_source_state.dart';
import 'preparation_repository.dart';

class PreparationResourcesScreen extends StatefulWidget {
  const PreparationResourcesScreen({
    super.key,
    required this.journeyId,
    required this.repository,
    required this.onOpenExternal,
    this.resourcesPath,
    this.onOpenDownloadedFile,
  });

  final String journeyId;
  final PreparationResourcesRepository repository;
  final Future<bool> Function(String url) onOpenExternal;
  final String? resourcesPath;
  final Future<void> Function(String path, String? mimeType, String title)?
  onOpenDownloadedFile;

  @override
  State<PreparationResourcesScreen> createState() =>
      _PreparationResourcesScreenState();
}

class _PreparationResourcesScreenState
    extends State<PreparationResourcesScreen> {
  static const _surfaceAdapter = ProjectionSurfaceAdapter();
  bool _refreshing = false;
  bool _requestedInitialRefresh = false;
  final Set<String> _downloading = <String>{};
  final Map<String, String> _downloaded = <String, String>{};

  @override
  void initState() {
    super.initState();
    unawaited(_acquireOrRefresh());
  }

  Future<void> _acquireOrRefresh() async {
    if (_requestedInitialRefresh) return;
    _requestedInitialRefresh = true;
    final local = await widget.repository.readResources(widget.journeyId);
    final source = await widget.repository.readSource(widget.journeyId);
    if (!mounted) return;
    if (local == null) {
      await _refresh();
      return;
    }
    final freshness = PreparationResourcesRepository.freshnessPolicy.evaluate(
      local,
      now: DateTime.now(),
      invalidated: source.invalidated,
    );
    if (freshness != FreshnessState.fresh) await _refresh();
  }

  Future<void> _refresh() async {
    if (_refreshing) return;
    setState(() => _refreshing = true);
    try {
      await widget.repository.refresh(
        journeyId: widget.journeyId,
        resourcesPath: widget.resourcesPath,
      );
    } on Object {
      // SyncSource records the failure and preserves usable local content.
    } finally {
      if (mounted) setState(() => _refreshing = false);
    }
  }

  Future<void> _download(_PreparationResource resource) async {
    final downloadUrl = resource.downloadUrl;
    if (downloadUrl == null || _downloading.contains(resource.id)) return;
    setState(() => _downloading.add(resource.id));
    try {
      final file = await widget.repository.downloadResource(
        resourceId: resource.id,
        downloadPath: downloadUrl,
        title: resource.title,
        mimeType: resource.mimeType,
      );
      if (!mounted) return;
      setState(() => _downloaded[resource.id] = file.path);
      await widget.onOpenDownloadedFile?.call(
        file.path,
        resource.mimeType,
        resource.title,
      );
    } on Object {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
            'Le document n’a pas pu être téléchargé. Les autres ressources restent disponibles.',
          ),
        ),
      );
    } finally {
      if (mounted) setState(() => _downloading.remove(resource.id));
    }
  }

  Future<void> _openFile(_PreparationResource resource) async {
    final localPath = _downloaded[resource.id];
    if (localPath == null) {
      await _download(resource);
      return;
    }
    await widget.onOpenDownloadedFile?.call(
      localPath,
      resource.mimeType,
      resource.title,
    );
  }

  @override
  Widget build(BuildContext context) {
    return StreamBuilder<StoredProjection?>(
      stream: widget.repository.watchResources(widget.journeyId),
      builder: (context, projectionSnapshot) {
        return StreamBuilder<OwnerSourceState>(
          stream: widget.repository.watchSource(widget.journeyId),
          initialData: OwnerSourceState.unknown,
          builder: (context, sourceSnapshot) {
            final projection = projectionSnapshot.data;
            final source = sourceSnapshot.data ?? OwnerSourceState.unknown;
            final items = _PreparationResource.fromProjection(projection);
            final freshness = projection == null
                ? null
                : PreparationResourcesRepository.freshnessPolicy.evaluate(
                    projection,
                    now: DateTime.now(),
                    invalidated: source.invalidated,
                  );
            final available = projection != null;
            final surface = _surfaceAdapter.adapt(
              projection: ProjectionPresentationModel(
                available: available,
                payload: projection?.payload,
                freshness: freshness,
                resources: const [],
                drafts: const [],
                pendingOperations: const [],
              ),
              availability: available
                  ? items.isEmpty
                        ? MakoloAvailabilityCue.empty
                        : MakoloAvailabilityCue.content
                  : _refreshing
                  ? MakoloAvailabilityCue.loading
                  : MakoloAvailabilityCue.initial,
              reachability: source.reachability,
              failure:
                  !available &&
                      (source.invalidated ||
                          source.reachability ==
                              ReachabilityState.unreachable) &&
                      !_refreshing
                  ? MakoloFailureCue.blocking
                  : source.lastErrorCode != null && available
                  ? MakoloFailureCue.recoverable
                  : MakoloFailureCue.none,
              refreshing: _refreshing && available,
            );

            return Scaffold(
              appBar: AppBar(
                title: const Text('Documents et instructions'),
                actions: [
                  IconButton(
                    tooltip: 'Actualiser',
                    onPressed: _refreshing ? null : _refresh,
                    icon: const Icon(Icons.refresh_rounded),
                  ),
                ],
              ),
              body: MakoloNetworkContextFrame(
                child: MakoloSurfaceStateView(
                  state: surface,
                  empty: const MakoloEmptyState(
                    title: 'Rien à préparer ici',
                    body: 'Aucun document ou instruction partagé n’est disponible pour cette démarche.',
                  ),
                  initialLoading: const MakoloLoadingState(
                    label: 'Chargement des ressources de préparation…',
                  ),
                  blockingErrorMessage: 'Ces ressources ne sont pas disponibles dans votre contexte actuel.',
                  onRetry: _refresh,
                  content: ListView.separated(
                    key: const Key('preparation-resources-content'),
                    padding: const EdgeInsets.all(MakoloSpacing.inner),
                    itemCount: items.length,
                    separatorBuilder: (_, _) =>
                        const SizedBox(height: MakoloSpacing.sm),
                    itemBuilder: (context, index) => _PreparationResourceCard(
                      resource: items[index],
                      onOpenExternal: widget.onOpenExternal,
                      downloading: _downloading.contains(items[index].id),
                      downloaded: _downloaded.containsKey(items[index].id),
                      onOpenFile: () => _openFile(items[index]),
                    ),
                  ),
                ),
              ),
            );
          },
        );
      },
    );
  }
}

class _PreparationResourceCard extends StatelessWidget {
  const _PreparationResourceCard({
    required this.resource,
    required this.onOpenExternal,
    required this.downloading,
    required this.downloaded,
    required this.onOpenFile,
  });

  final _PreparationResource resource;
  final Future<bool> Function(String url) onOpenExternal;
  final bool downloading;
  final bool downloaded;
  final VoidCallback onOpenFile;

  @override
  Widget build(BuildContext context) {
    return MakoloCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          MakoloStatusMetadataAction(
            title: resource.title,
            subtitle: resource.description,
            status: MakoloStatus(label: resource.kindLabel),
            metadata: [
              if (resource.version > 1)
                MakoloMetadataItem('Version ${resource.version}'),
              if (resource.occurrenceId != null)
                const MakoloMetadataItem(
                  'Liée à une occurrence',
                  icon: Icons.event_outlined,
                ),
            ],
          ),
          if (resource.text != null) ...[
            const SizedBox(height: MakoloSpacing.md),
            Text(resource.text!),
          ],
          if (resource.externalUrl != null) ...[
            const SizedBox(height: MakoloSpacing.md),
            OutlinedButton.icon(
              onPressed: () async {
                final opened = await onOpenExternal(resource.externalUrl!);
                if (!opened && context.mounted) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(
                      content: Text(
                        'Ce lien externe n’est pas disponible pour le moment.',
                      ),
                    ),
                  );
                }
              },
              icon: const Icon(Icons.open_in_new_rounded),
              label: const Text('Ouvrir le site externe'),
            ),
          ],
          if (resource.downloadUrl != null) ...[
            const SizedBox(height: MakoloSpacing.md),
            FilledButton.tonalIcon(
              onPressed: downloading ? null : onOpenFile,
              icon: downloading
                  ? const SizedBox.square(
                      dimension: 18,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : Icon(
                      downloaded
                          ? Icons.description_outlined
                          : Icons.download_rounded,
                    ),
              label: Text(
                downloading
                    ? 'Téléchargement…'
                    : downloaded
                    ? 'Ouvrir le document'
                    : 'Télécharger le document',
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class _PreparationResource {
  const _PreparationResource({
    required this.id,
    required this.title,
    required this.kindLabel,
    required this.version,
    this.description,
    this.occurrenceId,
    this.text,
    this.externalUrl,
    this.downloadUrl,
    this.mimeType,
    this.size,
  });

  final String id;
  final String title;
  final String kindLabel;
  final int version;
  final String? description;
  final String? occurrenceId;
  final String? text;
  final String? externalUrl;
  final String? downloadUrl;
  final String? mimeType;
  final int? size;

  static List<_PreparationResource> fromProjection(
    StoredProjection? projection,
  ) {
    if (projection == null) return const [];
    final raw = projection.payload['items'];
    if (raw is! List) return const [];
    return raw
        .map((value) {
          final row = value is Map<String, dynamic>
              ? value
              : value is Map
              ? value.map((key, item) => MapEntry(key.toString(), item))
              : const <String, dynamic>{};
          final kind = _string(row['kind']) ?? 'resource';
          return _PreparationResource(
            id: _string(row['id']) ?? '',
            title: _string(row['title']) ?? 'Ressource',
            description: _string(row['description']),
            kindLabel: switch (kind) {
              'text' => 'Instruction',
              'url' => 'Lien',
              'file' => 'Fichier',
              _ => 'Ressource',
            },
            version: row['version'] is num
                ? (row['version'] as num).toInt()
                : int.tryParse(row['version']?.toString() ?? '') ?? 1,
            occurrenceId: _string(row['occurrence_id']),
            text: _string(row['text']),
            externalUrl: _string(row['external_url']),
            downloadUrl: _string(row['download_url']),
            mimeType: _string(row['mime_type']),
            size: row['size'] is num
                ? (row['size'] as num).toInt()
                : int.tryParse(row['size']?.toString() ?? ''),
          );
        })
        .where((item) => item.id.isNotEmpty && item.title.isNotEmpty)
        .toList(growable: false);
  }
}

String? _string(Object? value) {
  final text = value?.toString().trim();
  return text == null || text.isEmpty ? null : text;
}
