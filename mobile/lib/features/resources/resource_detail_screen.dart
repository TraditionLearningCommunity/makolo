
import 'dart:async';
import 'package:flutter/material.dart';
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';

import '../../data/local/profile_store.dart';
import '../../design/makolo_components.dart';
import '../../design/makolo_theme.dart';
import '../../repositories/personal_repository.dart';
import '../../sync/freshness.dart';
import 'resource_repository.dart';

class ResourceDetailScreen extends StatefulWidget {
  const ResourceDetailScreen({
    super.key,
    required this.assetId,
    required this.repository,
    required this.personal,
    required this.onOpenJourney,
  });

  final String assetId;
  final ResourceRepository repository;
  final PersonalRepository personal;
  final ValueChanged<String> onOpenJourney;

  @override
  State<ResourceDetailScreen> createState() => _ResourceDetailScreenState();
}

class _ResourceDetailScreenState extends State<ResourceDetailScreen> {
  bool _refreshing = false;
  bool _downloading = false;
  double? _downloadProgress;

  @override
  void initState() {
    super.initState();
    unawaited(_refresh());
  }

  Future<void> _refresh() async {
    if (_refreshing) return;
    setState(() => _refreshing = true);
    try {
      await widget.repository.refreshDetail(widget.assetId);
    } on Object {
      // Keep the locally known metadata.
    } finally {
      if (mounted) setState(() => _refreshing = false);
    }
  }

  Future<void> _download(_ResourceDetail detail) async {
    final path = detail.downloadPath;
    final version = detail.currentVersion;
    if (path == null || version == null || _downloading) return;
    if (detail.sensitivity != 'normal') {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
            'Ce document sensible n’est pas conservé localement sans '
            'politique de stockage protégée explicite.',
          ),
        ),
      );
      return;
    }

    setState(() {
      _downloading = true;
      _downloadProgress = null;
    });
    try {
      final directory = await getApplicationDocumentsDirectory();
      final safeTitle = detail.title
          .replaceAll(RegExp(r'[^A-Za-z0-9._-]+'), '-')
          .replaceAll(RegExp(r'-+'), '-');
      final destination = p.join(
        directory.path,
        'makolo',
        'resources',
        widget.repository.profileId,
        widget.assetId,
        (safeTitle.isEmpty ? 'document' : safeTitle) +
            '-v' +
            version.number.toString(),
      );
      await widget.repository.downloadVersion(
        path: path,
        destinationPath: destination,
        onProgress: (transferred, total) {
          if (!mounted || total <= 0) return;
          setState(() => _downloadProgress = transferred / total);
        },
      );
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Fichier disponible sur cet appareil.')),
      );
    } on Object {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Téléchargement impossible pour le moment.')),
      );
    } finally {
      if (mounted) {
        setState(() {
          _downloading = false;
          _downloadProgress = null;
        });
      }
    }
  }

  Future<void> _reuse(_ResourceDetail detail) async {
    final reusePath = detail.reusePath;
    final version = detail.currentVersion;
    if (reusePath == null || version == null) return;

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
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
            'Document ajouté à la démarche. '
            'La satisfaction des exigences reste décidée par son owner.',
          ),
        ),
      );
      widget.onOpenJourney(result.journeyId);
    } on Object {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Ce document ne peut pas être réutilisé ici pour le moment.'),
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Ressource'),
        actions: [
          IconButton(
            tooltip: 'Actualiser',
            onPressed: _refreshing ? null : _refresh,
            icon: const Icon(Icons.refresh_rounded),
          ),
        ],
      ),
      body: StreamBuilder<StoredProjection?>(
        stream: widget.repository.watchDetail(widget.assetId),
        builder: (context, snapshot) {
          final projection = snapshot.data;
          if (projection == null) {
            return Center(
              child: _refreshing
                  ? const CircularProgressIndicator.adaptive()
                  : const Text('Cette ressource n’est pas disponible ici.'),
            );
          }
          final detail = _ResourceDetail.fromPayload(projection.payload);
          return StreamBuilder<ResourceSourceState>(
            stream: widget.repository.watchDetailSource(widget.assetId),
            initialData: ResourceSourceState.unknown,
            builder: (context, sourceSnapshot) {
              final source = sourceSnapshot.data ?? ResourceSourceState.unknown;
              return RefreshIndicator(
                onRefresh: _refresh,
                child: ListView(
                  physics: const AlwaysScrollableScrollPhysics(),
                  padding: const EdgeInsets.all(MakoloSpacing.inner),
                  children: [
                    Text(
                      detail.title,
                      style: Theme.of(context).textTheme.headlineMedium,
                    ),
                    const SizedBox(height: MakoloSpacing.xs),
                    Text(
                      [
                        detail.kindLabel,
                        detail.sensitivityLabel,
                        if (detail.archived) 'Archivé',
                      ].join(' · '),
                      style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                        color: Theme.of(context).colorScheme.onSurfaceVariant,
                      ),
                    ),
                    if (source.reachability == ReachabilityState.unreachable) ...[
                      const SizedBox(height: MakoloSpacing.md),
                      Text(
                        'Dernières métadonnées connues. '
                        'Les actions sensibles nécessitent le owner courant.',
                        style: Theme.of(context).textTheme.bodySmall?.copyWith(
                          color: Theme.of(context).colorScheme.onSurfaceVariant,
                        ),
                      ),
                    ],
                    const SizedBox(height: MakoloSpacing.lg),
                    if (detail.currentVersion != null)
                      _VersionSummary(version: detail.currentVersion!),
                    const SizedBox(height: MakoloSpacing.lg),
                    if (!detail.archived) ...[
                      Wrap(
                        spacing: MakoloSpacing.sm,
                        runSpacing: MakoloSpacing.sm,
                        children: [
                          if (detail.downloadPath != null)
                            FilledButton.icon(
                              onPressed: _downloading
                                  ? null
                                  : () => _download(detail),
                              icon: const Icon(Icons.download_rounded),
                              label: const Text('Télécharger'),
                            ),
                          if (detail.reusePath != null)
                            OutlinedButton.icon(
                              onPressed: () => _reuse(detail),
                              icon: const Icon(Icons.redo_rounded),
                              label: const Text(
                                'Réutiliser dans une démarche',
                              ),
                            ),
                        ],
                      ),
                      if (_downloading && _downloadProgress != null) ...[
                        const SizedBox(height: MakoloSpacing.sm),
                        LinearProgressIndicator(value: _downloadProgress),
                      ],
                    ] else ...[
                      Text(
                        'Cette ressource a été retirée de vos ressources '
                        'courantes. Les versions historiques restent lisibles.',
                        style: Theme.of(context).textTheme.bodyMedium,
                      ),
                    ],
                    const SizedBox(height: MakoloSpacing.xl),
                    Text(
                      'Versions',
                      style: Theme.of(context).textTheme.titleLarge,
                    ),
                    const SizedBox(height: MakoloSpacing.sm),
                    for (final version in detail.versions)
                      _VersionRow(version: version),
                    const SizedBox(height: MakoloSpacing.xl),
                    Text(
                      'Présence dans la Bibliothèque ≠ exigence satisfaite.',
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: Theme.of(context).colorScheme.onSurfaceVariant,
                      ),
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

class _VersionSummary extends StatelessWidget {
  const _VersionSummary({required this.version});

  final _ResourceVersion version;

  @override
  Widget build(BuildContext context) => MakoloCard(
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'Version courante ' + version.number.toString(),
          style: Theme.of(context).textTheme.titleMedium,
        ),
        const SizedBox(height: MakoloSpacing.xs),
        Text('Validité : ' + version.validityLabel),
        Text('Provenance : ' + version.provenanceLabel),
      ],
    ),
  );
}

class _VersionRow extends StatelessWidget {
  const _VersionRow({required this.version});

  final _ResourceVersion version;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(bottom: MakoloSpacing.sm),
    child: MakoloCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Version ' +
                version.number.toString() +
                (version.current ? ' · courante' : ''),
            style: Theme.of(context).textTheme.titleSmall,
          ),
          const SizedBox(height: MakoloSpacing.xs),
          Text(
            version.validityLabel + ' · provenance ' + version.provenanceLabel,
            style: Theme.of(context).textTheme.bodySmall,
          ),
        ],
      ),
    ),
  );
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
        return Padding(
          padding: const EdgeInsets.all(MakoloSpacing.inner),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(
                'Choisir une démarche',
                style: Theme.of(context).textTheme.titleLarge,
              ),
              const SizedBox(height: MakoloSpacing.xs),
              Text(
                'Seules les démarches déjà visibles dans En cours sont '
                'proposées. Le serveur revalide l’accès avant la copie.',
                style: Theme.of(context).textTheme.bodySmall,
              ),
              const SizedBox(height: MakoloSpacing.md),
              if (choices.isEmpty)
                const Padding(
                  padding: EdgeInsets.symmetric(vertical: MakoloSpacing.lg),
                  child: Text('Aucune démarche admissible connue ici.'),
                )
              else
                for (final choice in choices)
                  ListTile(
                    title: Text(choice.title),
                    subtitle: const Text('Démarche'),
                    onTap: () => Navigator.of(context).pop(choice),
                  ),
            ],
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
    required this.downloadPath,
    required this.reusePath,
  });

  final String title;
  final String kindLabel;
  final String sensitivity;
  final String sensitivityLabel;
  final bool archived;
  final _ResourceVersion? currentVersion;
  final List<_ResourceVersion> versions;
  final String? downloadPath;
  final String? reusePath;

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
      title: _string(payload['title']) ?? 'Ressource',
      kindLabel: _string(payload['asset_kind_label']) ?? 'Document',
      sensitivity: _string(payload['sensitivity']) ?? 'normal',
      sensitivityLabel:
          _string(payload['sensitivity_label']) ?? 'Sensibilité inconnue',
      archived: _string(payload['status']) == 'archived',
      currentVersion: current,
      versions: List.unmodifiable(versions),
      downloadPath: _string(links['download']),
      reusePath: _string(links['reuse_in_journey']),
    );
  }
}

class _ResourceVersion {
  const _ResourceVersion({
    required this.number,
    required this.current,
    required this.validityLabel,
    required this.provenanceLabel,
  });

  final int number;
  final bool current;
  final String validityLabel;
  final String provenanceLabel;

  factory _ResourceVersion.fromPayload(Map<String, dynamic> payload) {
    final validity = _map(payload['validity']);
    final provenance = _map(payload['provenance']);
    return _ResourceVersion(
      number: payload['version'] is num
          ? (payload['version'] as num).toInt()
          : 0,
      current: payload['current'] == true,
      validityLabel: _validityLabel(_string(validity['state'])),
      provenanceLabel:
          _string(provenance['kind']) == 'journey_artifact'
          ? 'pièce de démarche'
          : 'inconnue',
    );
  }
}

String _validityLabel(String? state) => switch (state) {
  'current' => 'valide',
  'expired' => 'expirée',
  'not_yet_issued' => 'pas encore émise',
  _ => 'inconnue',
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
