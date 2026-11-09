import 'dart:async';
import 'dart:io';

import 'package:flutter/material.dart';

import '../../data/local/profile_store.dart';
import '../../design/behavior_primitives.dart';
import '../../platform/downloads/device_downloads.dart';
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
  int _identityRevision = 0;
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
    final revision = _identityRevision;
    final id = widget.journeyId;
    final repository = widget.repository;
    final local = await repository.readResources(id);
    final source = await repository.readSource(id);
    if (!_sameOwner(revision, repository, id)) return;
    await _restoreLocalFiles(local);
    if (!_sameOwner(revision, repository, id)) return;
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

  bool _sameOwner(
    int revision,
    PreparationResourcesRepository repository,
    String id,
  ) =>
      mounted &&
      revision == _identityRevision &&
      identical(repository, widget.repository) &&
      id == widget.journeyId;

  Future<void> _restoreLocalFiles(StoredProjection? projection) async {
    final revision = _identityRevision;
    final repository = widget.repository;
    final resources = _PreparationResource.fromProjection(projection);
    final paths = <String, String>{};
    for (final item in resources) {
      if (item.downloadUrl == null) continue;
      final stored = await repository.readLocalResourceFile(
        item.id,
        version: item.version,
      );
      if (stored != null) paths[item.id] = stored.path;
    }
    if (!mounted ||
        revision != _identityRevision ||
        !identical(repository, widget.repository))
      return;
    setState(() {
      _downloaded
        ..clear()
        ..addAll(paths);
    });
  }

  @override
  void didUpdateWidget(covariant PreparationResourcesScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.journeyId != widget.journeyId ||
        oldWidget.repository != widget.repository) {
      _identityRevision++;
      _requestedInitialRefresh = false;
      _refreshing = false;
      _downloading.clear();
      _downloaded.clear();
      unawaited(_acquireOrRefresh());
    }
  }

  Future<void> _refresh() async {
    if (_refreshing) return;
    final revision = _identityRevision;
    final id = widget.journeyId;
    final repository = widget.repository;
    setState(() => _refreshing = true);
    try {
      await repository.refresh(
        journeyId: id,
        resourcesPath: widget.resourcesPath,
      );
      if (!_sameOwner(revision, repository, id)) return;
      final acquired = await repository.readResources(id);
      if (_sameOwner(revision, repository, id)) {
        await _restoreLocalFiles(acquired);
      }
    } on Object {
      // Owner facts already acquired remain in this Profile's database.
    } finally {
      if (_sameOwner(revision, repository, id)) {
        setState(() => _refreshing = false);
      }
    }
  }

  Future<void> _download(_PreparationResource resource) async {
    final downloadUrl = resource.downloadUrl;
    if (downloadUrl == null || _downloading.contains(resource.id)) return;
    final revision = _identityRevision;
    final id = widget.journeyId;
    final repository = widget.repository;
    setState(() => _downloading.add(resource.id));
    try {
      final file = await repository.downloadResource(
        resourceId: resource.id,
        version: resource.version,
        downloadPath: downloadUrl,
        title: resource.title,
        mimeType: resource.mimeType,
      );
      // Only this explicit action exports to public Downloads; opening a
      // private copy stays inside the current Profile.
      if (!_sameOwner(revision, repository, id)) return;
      setState(() => _downloaded[resource.id] = file.path);
      final mime = resource.mimeType ?? 'application/octet-stream';
      final extension = switch (mime.toLowerCase()) {
        'application/pdf' => 'pdf',
        'text/plain' => 'txt',
        'image/png' => 'png',
        'image/jpeg' => 'jpg',
        'text/csv' => 'csv',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document' =>
          'docx',
        _ => 'bin',
      };
      final saved = await const AndroidDeviceDownloads().save(
        source: File(file.path),
        fileName: makoloDownloadName(resource.title, extension),
        mimeType: mime,
      );
      if (!_sameOwner(revision, repository, id)) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Enregistré dans Téléchargements : $saved')),
      );
    } on Object {
      if (!_sameOwner(revision, repository, id)) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
            'Le document n’a pas pu être téléchargé. Les autres ressources restent disponibles.',
          ),
        ),
      );
    } finally {
      if (_sameOwner(revision, repository, id)) {
        setState(() => _downloading.remove(resource.id));
      }
    }
  }

  Future<void> _openFile(_PreparationResource resource) async {
    if (_downloading.contains(resource.id)) return;
    final revision = _identityRevision;
    final id = widget.journeyId;
    final repository = widget.repository;
    setState(() => _downloading.add(resource.id));
    try {
      var local = await repository.readLocalResourceFile(
        resource.id,
        version: resource.version,
      );
      if (local == null && resource.downloadUrl != null) {
        local = await repository.downloadResource(
          resourceId: resource.id,
          version: resource.version,
          downloadPath: resource.downloadUrl!,
          title: resource.title,
          mimeType: resource.mimeType,
        );
      }
      final localPath = local?.path;
      if (localPath == null) return;
      if (!_sameOwner(revision, repository, id)) return;
      setState(() => _downloaded[resource.id] = localPath);
      await widget.onOpenDownloadedFile?.call(
        localPath,
        resource.mimeType,
        resource.title,
      );
    } on Object {
      if (_sameOwner(revision, repository, id)) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text(
              'Ce document ne peut pas être ouvert pour le moment.',
            ),
          ),
        );
      }
    } finally {
      if (_sameOwner(revision, repository, id)) {
        setState(() => _downloading.remove(resource.id));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return StreamBuilder<StoredProjection?>(
      key: ValueKey(
        'resources:${widget.repository.profileId}:${widget.journeyId}',
      ),
      stream: widget.repository.watchResources(widget.journeyId),
      builder: (context, projectionSnapshot) {
        return StreamBuilder<OwnerSourceState>(
          stream: widget.repository.watchSource(widget.journeyId),
          initialData: OwnerSourceState.unknown,
          builder: (context, sourceSnapshot) {
            final source = sourceSnapshot.data ?? OwnerSourceState.unknown;
            final ownerDenied =
                source.invalidated &&
                const {
                  'permission_denied',
                  'not_found',
                }.contains(source.lastErrorCode);
            final projection = ownerDenied ? null : projectionSnapshot.data;
            final items = _PreparationResource.fromProjection(projection);
            final freshness = projection == null
                ? null
                : PreparationResourcesRepository.freshnessPolicy.evaluate(
                    projection,
                    now: DateTime.now(),
                    invalidated: source.invalidated,
                  );
            final available = projection != null;
            // Only an explicit owner denial withdraws this local depth.

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
                  : _refreshing ||
                        projectionSnapshot.connectionState ==
                            ConnectionState.waiting
                  ? MakoloAvailabilityCue.loading
                  : MakoloAvailabilityCue.empty,
              reachability: source.reachability,
              failure: ownerDenied
                  ? MakoloFailureCue.permissionDenied
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
                    title: 'Aucun document à afficher',
                    body: 'Les documents et instructions apparaîtront ici lorsqu’ils seront disponibles.',
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
                      onExportFile: () => _download(items[index]),
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
    required this.onExportFile,
  });

  final _PreparationResource resource;
  final Future<bool> Function(String url) onOpenExternal;
  final bool downloading;
  final bool downloaded;
  final VoidCallback onOpenFile;
  final VoidCallback onExportFile;

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
              label: Text(downloading ? 'Ouverture…' : 'Ouvrir le document'),
            ),
            const SizedBox(height: MakoloSpacing.sm),
            TextButton.icon(
              onPressed: downloading ? null : onExportFile,
              icon: const Icon(Icons.download_outlined),
              label: const Text('Enregistrer une copie'),
            ),
            const SizedBox(height: MakoloSpacing.sm),
            Text(
              downloaded ? 'Document disponible' : 'Document à ouvrir',
              style: Theme.of(context).textTheme.bodySmall,
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
