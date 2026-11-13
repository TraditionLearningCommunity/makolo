import 'dart:async';
import 'dart:io';

import 'package:flutter/material.dart';

import '../../data/local/profile_store.dart';
import '../../design/action_controls.dart';
import '../../design/makolo_components.dart';
import '../../design/makolo_theme.dart';
import '../../platform/downloads/device_downloads.dart';
import '../../platform/sharing/share_gateway.dart';
import '../../repositories/personal_repository.dart';
import '../../sync/freshness.dart';
import 'resource_file_viewer.dart';
import 'resource_presentation.dart';
import 'resource_repository.dart';

class ResourceDetailScreen extends StatefulWidget {
  const ResourceDetailScreen({
    super.key,
    required this.assetId,
    required this.repository,
    required this.personal,
    required this.onOpenJourney,
    required this.onAddVersion,
    required this.onArchived,
    this.sharing = const SystemShareGateway(),
  });

  final String assetId;
  final ResourceRepository repository;
  final PersonalRepository personal;
  final ValueChanged<String> onOpenJourney;
  final VoidCallback onAddVersion;
  final VoidCallback onArchived;
  final ShareGateway sharing;

  @override
  State<ResourceDetailScreen> createState() => _ResourceDetailScreenState();
}

class _ResourceDetailScreenState extends State<ResourceDetailScreen> {
  bool _refreshing = false;
  bool _downloading = false;
  bool _sharing = false;
  bool _archiving = false;
  double? _downloadProgress;
  _ResourceDetail? _cachedSummary;
  final GlobalKey _versionsKey = GlobalKey();
  late Stream<StoredProjection?> _detail;
  late Stream<ResourceSourceState> _source;

  @override
  void initState() {
    super.initState();
    _bind();
  }

  @override
  void didUpdateWidget(covariant ResourceDetailScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.repository != widget.repository ||
        oldWidget.assetId != widget.assetId) {
      _cachedSummary = null;
      _bind();
    }
  }

  void _bind() {
    _detail = widget.repository.watchDetail(widget.assetId);
    _source = widget.repository.watchDetailSource(widget.assetId);
    unawaited(_loadKnownSummary());
    unawaited(_ensureFresh());
  }

  Future<void> _loadKnownSummary() async {
    final assetId = widget.assetId;
    final repository = widget.repository;
    try {
      final pages = await repository.store.readProjections(
        ResourceRepository.collectionProjectionKind,
      );
      final known = _ResourceDetail.fromKnownCollection(pages, assetId);
      if (mounted &&
          widget.assetId == assetId &&
          identical(widget.repository, repository)) {
        setState(() => _cachedSummary = known);
      }
    } on Object {
      // A list row remains a summary, never a permission grant.
    }
  }

  Future<void> _ensureFresh() async {
    if (_refreshing) return;
    try {
      if (!await widget.repository.shouldRefreshDetail(widget.assetId)) return;
      if (mounted) setState(() => _refreshing = true);
      await widget.repository.refreshDetail(widget.assetId);
    } on Object {
      // Keep already acquired metadata visible.
    } finally {
      if (mounted) setState(() => _refreshing = false);
    }
  }

  Future<void> _refresh() async {
    if (_refreshing) return;
    setState(() => _refreshing = true);
    try {
      await widget.repository.refreshDetail(widget.assetId);
    } on Object {
      // Keep already acquired metadata visible.
    } finally {
      if (mounted) setState(() => _refreshing = false);
    }
  }

  Future<void> _download(
    _ResourceDetail detail,
    _ResourceVersion version,
  ) async {
    final path = version.downloadPath;
    if (path == null || _downloading || _sharing) return;
    setState(() {
      _downloading = true;
      _downloadProgress = null;
    });
    try {
      const retainOfflineCopy = false;
      final pathOnDevice = await widget.repository
          .downloadVersionForExplicitExport(
            path: path,
            assetId: widget.assetId,
            title: detail.title,
            versionNumber: version.number,
            retainOfflineCopy: retainOfflineCopy,
            fileExtension: _extensionForMime(version.mimeType),
            onProgress: (transferred, total) {
              if (!mounted || total <= 0) return;
              setState(() => _downloadProgress = transferred / total);
            },
          );
      final exportedFile = File(pathOnDevice);
      try {
        final extension = _extensionForMime(version.mimeType);
        final exportedName = await const AndroidDeviceDownloads().save(
          source: exportedFile,
          fileName: makoloDownloadName(
            '${detail.title}-v${version.number}',
            extension,
          ),
          mimeType: version.mimeType ?? 'application/octet-stream',
        );
        if (!mounted) return;
        _message('Enregistré : $exportedName');
      } finally {
        if (await exportedFile.exists()) {
          await exportedFile.delete();
        }
        final parent = exportedFile.parent;
        if (await parent.exists()) {
          try {
            await parent.delete();
          } on FileSystemException {
            // Best-effort staging cleanup after explicit OS export.
          }
        }
      }
    } on Object {
      if (mounted) _message('Téléchargement impossible.');
    } finally {
      if (mounted) {
        setState(() {
          _downloading = false;
          _downloadProgress = null;
        });
      }
    }
  }

  Future<void> _share(_ResourceDetail detail, _ResourceVersion version) async {
    final path = version.downloadPath;
    if (path == null || _sharing || _downloading) return;
    setState(() {
      _sharing = true;
      _downloadProgress = null;
    });
    String? temporaryPath;
    try {
      temporaryPath = await widget.repository.downloadVersionForExplicitExport(
        path: path,
        assetId: widget.assetId,
        title: detail.title,
        versionNumber: version.number,
        retainOfflineCopy: false,
        fileExtension: _extensionForMime(version.mimeType),
        onProgress: (transferred, total) {
          if (!mounted || total <= 0) return;
          setState(() => _downloadProgress = transferred / total);
        },
      );
      await widget.sharing.shareFiles(
        paths: [temporaryPath],
        text: detail.title,
      );
    } on Object {
      if (mounted) _message('Partage impossible.');
    } finally {
      if (temporaryPath != null) {
        final temporary = File(temporaryPath);
        if (await temporary.exists()) {
          try {
            await temporary.delete();
            final parent = temporary.parent;
            if (await parent.exists()) await parent.delete();
          } on Object {
            // Staging cleanup is best-effort and never changes owner truth.
          }
        }
      }
      if (mounted) {
        setState(() {
          _sharing = false;
          _downloadProgress = null;
        });
      }
    }
  }

  Future<void> _openCurrentFile(
    _ResourceDetail detail,
    _ResourceVersion version,
  ) async {
    final path = version.downloadPath;
    if (path == null) return;
    await Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (context) => ResourceFileViewer(
          repository: widget.repository,
          assetId: widget.assetId,
          title: detail.title,
          versionNumber: version.number,
          mimeType: version.mimeType,
          downloadPath: path,
        ),
      ),
    );
  }

  void _scrollToVersions() {
    final target = _versionsKey.currentContext;
    if (target == null) return;
    Scrollable.ensureVisible(
      target,
      duration: const Duration(milliseconds: 240),
      curve: Curves.easeOut,
      alignment: 0.05,
    );
  }

  Future<void> _reuse(_ResourceDetail detail) async {
    final reusePath = detail.reusePath;
    if (reusePath == null || detail.currentVersion == null) return;
    final journey = await showModalBottomSheet<_JourneyChoice>(
      context: context,
      isScrollControlled: true,
      builder: (context) => _JourneyChooser(personal: widget.personal),
    );
    if (journey == null || !mounted) return;

    try {
      final result = await widget.repository.reuseVersion(
        path: reusePath,
        journeyId: journey.id,
      );
      if (!mounted) return;
      _message('Ajouté à la démarche.');
      widget.onOpenJourney(result.journeyId);
    } on Object {
      if (mounted) _message('Action impossible.');
    }
  }

  Future<void> _archive(_ResourceDetail detail) async {
    final path = detail.archivePath;
    if (path == null || _archiving) return;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Archiver ce document ?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(false),
            child: const Text('Annuler'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(dialogContext).pop(true),
            child: const Text('Archiver'),
          ),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;

    setState(() => _archiving = true);
    try {
      await widget.repository.archiveDocument(path: path);
      try {
        await widget.repository.refreshDetail(widget.assetId);
      } on Object {
        // The archive is already confirmed by the owner.
      }
      if (!mounted) return;
      _message('Document archivé.');
      widget.onArchived();
    } on Object {
      if (mounted) _message('Archivage impossible.');
    } finally {
      if (mounted) setState(() => _archiving = false);
    }
  }

  void _message(String value) {
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(value)));
  }

  @override
  Widget build(BuildContext context) {
    return StreamBuilder<ResourceSourceState>(
      stream: _source,
      initialData: ResourceSourceState.unknown,
      builder: (context, sourceSnapshot) {
        final source = sourceSnapshot.data ?? ResourceSourceState.unknown;
        return StreamBuilder<StoredProjection?>(
          stream: _detail,
          builder: (context, snapshot) {
            final projection = snapshot.data;
            final detail = projection != null
                ? _ResourceDetail.fromPayload(projection.payload)
                : _cachedSummary;
            final ownerAvailable = !source.invalidated && !source.ownerDenied;
            final networkAvailable =
                source.reachability == ReachabilityState.reachable;
            final canUseNetworkActions = ownerAvailable && networkAvailable;
            final canDownload = canUseNetworkActions;

            return Scaffold(
              appBar: AppBar(
                title: const Text('Document'),
                actions: [
                  if (detail != null && detail.versions.length > 1)
                    MakoloIconActionButton(
                      tooltip: 'Historique des versions',
                      icon: Icons.history_rounded,
                      onPressed: _scrollToVersions,
                    ),
                  if (detail?.currentVersion?.downloadPath != null &&
                      ownerAvailable)
                    MakoloIconActionButton(
                      tooltip:
                          detail!.currentVersion!.mimeType == 'application/pdf'
                          ? 'Télécharger le PDF'
                          : 'Télécharger',
                      icon: detail.currentVersion!.mimeType == 'application/pdf'
                          ? Icons.picture_as_pdf_outlined
                          : Icons.download_rounded,
                      onPressed: !canDownload || _downloading || _sharing
                          ? null
                          : () => _download(detail, detail.currentVersion!),
                    ),
                  if (detail?.currentVersion?.downloadPath != null &&
                      ownerAvailable)
                    MakoloIconActionButton(
                      tooltip: 'Partager',
                      icon: Icons.share_outlined,
                      onPressed:
                          !canUseNetworkActions || _sharing || _downloading
                          ? null
                          : () => _share(detail!, detail.currentVersion!),
                    ),
                  if (detail != null)
                    PopupMenuButton<String>(
                      tooltip: 'Plus',
                      onSelected: (value) {
                        if (value == 'reuse') {
                          _reuse(detail);
                        } else if (value == 'archive') {
                          _archive(detail);
                        } else if (value == 'refresh') {
                          _refresh();
                        }
                      },
                      itemBuilder: (context) => [
                        if (detail.reusePath != null && ownerAvailable)
                          PopupMenuItem(
                            value: 'reuse',
                            enabled: canUseNetworkActions,
                            child: const ListTile(
                              leading: Icon(Icons.drive_file_move_outline),
                              title: Text('Utiliser dans une démarche'),
                              contentPadding: EdgeInsets.zero,
                            ),
                          ),
                        if (detail.archivePath != null && ownerAvailable)
                          PopupMenuItem(
                            value: 'archive',
                            enabled: canUseNetworkActions && !_archiving,
                            child: const ListTile(
                              leading: Icon(Icons.archive_outlined),
                              title: Text('Archiver'),
                              contentPadding: EdgeInsets.zero,
                            ),
                          ),
                        PopupMenuItem(
                          value: 'refresh',
                          enabled: !_refreshing,
                          child: const ListTile(
                            leading: Icon(Icons.refresh_rounded),
                            title: Text('Actualiser'),
                            contentPadding: EdgeInsets.zero,
                          ),
                        ),
                      ],
                    ),
                ],
              ),
              body: detail == null
                  ? Center(
                      child: _refreshing
                          ? const CircularProgressIndicator.adaptive()
                          : Column(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                const Text('Document indisponible'),
                                const SizedBox(height: MakoloSpacing.md),
                                MakoloActionButton(
                                  label: 'Réessayer',
                                  appearance: MakoloActionAppearance.quiet,
                                  onPressed: _refresh,
                                ),
                              ],
                            ),
                    )
                  : source.invalidated
                  ? Center(
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          const Text('Document indisponible'),
                          const SizedBox(height: MakoloSpacing.md),
                          MakoloActionButton(
                            label: 'Réessayer',
                            appearance: MakoloActionAppearance.quiet,
                            onPressed: _refresh,
                          ),
                        ],
                      ),
                    )
                  : RefreshIndicator(
                      onRefresh: _refresh,
                      child: Center(
                        child: ConstrainedBox(
                          constraints: const BoxConstraints(maxWidth: 760),
                          child: ListView(
                            physics: const AlwaysScrollableScrollPhysics(),
                            padding: const EdgeInsets.all(MakoloSpacing.inner),
                            children: [
                              ResourceDocumentHeader(
                                title: detail.title,
                                subtitle: [
                                  detail.kindLabel,
                                  if (detail.archived) 'Archivé',
                                ].join(' · '),
                              ),
                              if (source.reachability ==
                                  ReachabilityState.unreachable) ...[
                                const SizedBox(height: MakoloSpacing.sm),
                                Semantics(
                                  liveRegion: true,
                                  child: const Row(
                                    crossAxisAlignment:
                                        CrossAxisAlignment.start,
                                    children: [
                                      Icon(Icons.cloud_off_outlined, size: 18),
                                      SizedBox(width: MakoloSpacing.xs),
                                      Expanded(
                                        child: Text(
                                          'Données enregistrées sur cet appareil. '
                                          'Mise à jour indisponible.',
                                        ),
                                      ),
                                    ],
                                  ),
                                ),
                              ],
                              if ((_downloading || _sharing) &&
                                  _downloadProgress != null) ...[
                                const SizedBox(height: MakoloSpacing.md),
                                LinearProgressIndicator(
                                  value: _downloadProgress,
                                ),
                              ],
                              const SizedBox(height: MakoloSpacing.lg),
                              if (detail.currentVersion != null)
                                ResourceVersionCard(
                                  leading: _fileIconForMime(
                                    detail.currentVersion!.mimeType,
                                  ),
                                  title:
                                      'Version ${detail.currentVersion!.number}',
                                  subtitle: [
                                    detail.currentVersion!.validityLabel,
                                    'Provenance : '
                                        '${detail.currentVersion!.provenanceLabel}',
                                  ].join(' · '),
                                  onTap:
                                      detail.currentVersion!.downloadPath !=
                                              null &&
                                          canUseNetworkActions
                                      ? () => _openCurrentFile(
                                          detail,
                                          detail.currentVersion!,
                                        )
                                      : null,
                                ),
                              if (detail.addVersionPath != null &&
                                  ownerAvailable) ...[
                                const SizedBox(height: MakoloSpacing.md),
                                Align(
                                  alignment: Alignment.centerLeft,
                                  child: MakoloActionButton(
                                    label: 'Nouvelle version',
                                    icon: Icons.add_rounded,
                                    appearance: MakoloActionAppearance.quiet,
                                    onPressed: canUseNetworkActions
                                        ? widget.onAddVersion
                                        : null,
                                  ),
                                ),
                              ],
                              if (detail.versions.length > 1) ...[
                                const SizedBox(height: MakoloSpacing.xl),
                                ResourceSectionHeader(
                                  key: _versionsKey,
                                  title: 'Versions précédentes',
                                  count: detail.versions
                                      .where((version) => !version.current)
                                      .length,
                                ),
                                const SizedBox(height: MakoloSpacing.sm),
                                for (final version in detail.versions)
                                  if (!version.current)
                                    Padding(
                                      padding: const EdgeInsets.only(
                                        bottom: MakoloSpacing.sm,
                                      ),
                                      child: ResourceVersionCard(
                                        title: 'v${version.number}',
                                        subtitle: [
                                          version.validityLabel,
                                          version.provenanceLabel,
                                        ].join(' · '),
                                        actions: [
                                          if (version.downloadPath != null &&
                                              canDownload)
                                            MakoloIconActionButton(
                                              tooltip: 'Télécharger',
                                              icon: Icons.download_rounded,
                                              onPressed:
                                                  _downloading || _sharing
                                                  ? null
                                                  : () => _download(
                                                      detail,
                                                      version,
                                                    ),
                                            ),
                                        ],
                                      ),
                                    ),
                              ],
                            ],
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

class _JourneyChooser extends StatelessWidget {
  const _JourneyChooser({required this.personal});

  final PersonalRepository personal;

  @override
  Widget build(BuildContext context) => SafeArea(
    child: StreamBuilder<StoredProjection?>(
      stream: personal.watchOngoing(),
      builder: (context, snapshot) {
        final choices = _journeys(snapshot.data?.payload);
        return FractionallySizedBox(
          heightFactor: 0.72,
          child: Padding(
            padding: const EdgeInsets.all(MakoloSpacing.inner),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text(
                  'Choisir une démarche',
                  style: Theme.of(context).textTheme.titleLarge,
                ),
                const SizedBox(height: MakoloSpacing.md),
                Expanded(
                  child: choices.isEmpty
                      ? const Center(child: Text('Aucune démarche disponible'))
                      : ListView.builder(
                          itemCount: choices.length,
                          itemBuilder: (context, index) {
                            final choice = choices[index];
                            return ListTile(
                              title: Text(choice.title),
                              trailing: const Icon(Icons.chevron_right_rounded),
                              onTap: () => Navigator.of(context).pop(choice),
                            );
                          },
                        ),
                ),
              ],
            ),
          ),
        );
      },
    ),
  );
}

class _JourneyChoice {
  const _JourneyChoice({required this.id, required this.title});

  final String id;
  final String title;
}

List<_JourneyChoice> _journeys(Map<String, dynamic>? payload) {
  if (payload == null) return const [];
  final rows = payload['items'];
  if (rows is! List) return const [];
  final result = <_JourneyChoice>[];
  final seen = <String>{};
  for (final raw in rows) {
    final row = _map(raw);
    if (_string(row['kind'])?.toLowerCase() != 'journey') continue;
    final source = _map(row['source']);
    if ((_string(source['kind']) ?? '').toLowerCase() != 'journey') continue;
    final id = _string(source['id']);
    final title = _string(row['title']);
    if (id == null || title == null || !seen.add(id)) continue;
    result.add(_JourneyChoice(id: id, title: title));
  }
  return result;
}

class _ResourceDetail {
  const _ResourceDetail({
    required this.title,
    required this.kindLabel,
    required this.sensitivity,
    required this.sensitivityLabel,
    required this.archived,
    required this.currentVersion,
    required this.versions,
    required this.reusePath,
    required this.addVersionPath,
    required this.archivePath,
  });

  final String title;
  final String kindLabel;
  final String sensitivity;
  final String sensitivityLabel;
  final bool archived;
  final _ResourceVersion? currentVersion;
  final List<_ResourceVersion> versions;
  final String? reusePath;
  final String? addVersionPath;
  final String? archivePath;

  static _ResourceDetail? fromKnownCollection(
    Iterable<StoredProjection> pages,
    String assetId,
  ) {
    for (final page in pages) {
      if (page.kind != ResourceRepository.collectionProjectionKind) continue;
      final rows = _map(page.payload['documents'])['items'];
      if (rows is! List) continue;
      for (final raw in rows) {
        final row = _map(raw);
        if (_string(row['id']) != assetId) continue;
        return _ResourceDetail(
          title: _string(row['title']) ?? 'Document',
          kindLabel: _string(row['asset_kind_label']) ?? 'Document',
          sensitivity: _string(row['sensitivity']) ?? 'unknown',
          sensitivityLabel:
              _string(row['sensitivity_label']) ?? 'Confidentialité inconnue',
          archived: _string(row['status']) == 'archived',
          currentVersion: null,
          versions: const [],
          reusePath: null,
          addVersionPath: null,
          archivePath: null,
        );
      }
    }
    return null;
  }

  factory _ResourceDetail.fromPayload(Map<String, dynamic> payload) {
    final currentRaw = _map(payload['current_version']);
    final current = currentRaw.isEmpty
        ? null
        : _ResourceVersion.fromPayload(currentRaw);
    final versionsRaw = _map(payload['versions'])['items'];
    final versions = <_ResourceVersion>[];
    if (versionsRaw is List) {
      for (final raw in versionsRaw) {
        final version = _map(raw);
        if (version.isNotEmpty) {
          versions.add(_ResourceVersion.fromPayload(version));
        }
      }
    }
    final links = _map(payload['links']);
    return _ResourceDetail(
      title: _string(payload['title']) ?? 'Document',
      kindLabel: _string(payload['asset_kind_label']) ?? 'Document',
      sensitivity: _string(payload['sensitivity']) ?? 'normal',
      sensitivityLabel:
          _string(payload['sensitivity_label']) ?? 'Confidentialité inconnue',
      archived: _string(payload['status']) == 'archived',
      currentVersion: current,
      versions: List.unmodifiable(versions),
      reusePath: _string(links['reuse_in_journey']),
      addVersionPath: _string(links['add_version']),
      archivePath: _string(links['archive']),
    );
  }
}

class _ResourceVersion {
  const _ResourceVersion({
    required this.number,
    required this.current,
    required this.validityLabel,
    required this.provenanceLabel,
    required this.mimeType,
    required this.downloadPath,
  });

  final int number;
  final bool current;
  final String validityLabel;
  final String provenanceLabel;
  final String? mimeType;
  final String? downloadPath;

  factory _ResourceVersion.fromPayload(Map<String, dynamic> payload) {
    final validity = _map(payload['validity']);
    final provenance = _map(payload['provenance']);
    final links = _map(payload['links']);
    return _ResourceVersion(
      number: payload['version'] is num
          ? (payload['version'] as num).toInt()
          : 0,
      current: payload['current'] == true,
      validityLabel: _validityLabel(
        _string(validity['state']),
        expiresAt: _string(validity['expires_at']),
      ),
      provenanceLabel: _string(provenance['kind']) == 'journey_artifact'
          ? 'Démarche'
          : 'Inconnue',
      mimeType: _string(payload['mime_type']),
      downloadPath: _string(links['download']),
    );
  }
}

String _validityLabel(String? state, {String? expiresAt}) {
  final expiry = _displayIsoDate(expiresAt);
  return switch (state) {
    'current' when expiry != null => 'Jusqu’au $expiry',
    'current' => 'Valide',
    'expired' when expiry != null => 'Expiré · $expiry',
    'expired' => 'Expiré',
    'not_yet_issued' => 'À venir',
    _ => 'Validité inconnue',
  };
}

String? _displayIsoDate(String? value) {
  if (value == null) return null;
  final date = DateTime.tryParse(value);
  if (date == null) return value;
  final day = date.day.toString().padLeft(2, '0');
  final month = date.month.toString().padLeft(2, '0');
  return '$day/$month/${date.year}';
}

IconData _fileIconForMime(String? mimeType) => switch (mimeType) {
  'application/pdf' => Icons.picture_as_pdf_outlined,
  'image/jpeg' ||
  'image/png' ||
  'image/webp' ||
  'image/gif' => Icons.image_outlined,
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document' =>
    Icons.article_outlined,
  'text/plain' => Icons.notes_outlined,
  _ => Icons.description_outlined,
};

String _extensionForMime(String? mimeType) => switch (mimeType) {
  'application/pdf' => 'pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document' =>
    'docx',
  'application/msword' => 'doc',
  'text/plain' => 'txt',
  'image/jpeg' => 'jpg',
  'image/png' => 'png',
  _ => 'bin',
};

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
