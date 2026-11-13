import 'dart:async';

import 'package:flutter/material.dart';

import '../../app/runtime/actor_context.dart';
import '../../app/runtime/app_runtime.dart';
import '../../data/local/profile_store.dart';
import '../../network/api_error.dart';
import 'journey_artifact_repository.dart';
import 'journey_artifact_screen.dart';

/// Published owner Preparation, not a synthetic Space document library.
class SpaceBeneficiaryResourcesScreen extends StatefulWidget {
  const SpaceBeneficiaryResourcesScreen({
    super.key,
    required this.runtime,
    required this.space,
    required this.journeyId,
  });

  final AppRuntime runtime;
  final SpaceActorIdentity space;
  final String journeyId;

  @override
  State<SpaceBeneficiaryResourcesScreen> createState() =>
      _SpaceBeneficiaryResourcesScreenState();
}

class _SpaceBeneficiaryResourcesScreenState
    extends State<SpaceBeneficiaryResourcesScreen> {
  late SpaceBeneficiaryResourcesRepository _repository;
  bool _loading = false;
  bool _denied = false;
  String? _error;
  int _epoch = 0;

  bool get _actorValid {
    final actor = widget.runtime.actorContext?.value;
    return actor is SpaceActorContext && actor.space == widget.space;
  }

  @override
  void initState() {
    super.initState();
    _repository = SpaceBeneficiaryResourcesRepository(
      database: widget.runtime.database!,
      store: widget.runtime.store!,
      profileId: widget.runtime.session!.profileId,
      sync: widget.runtime.sync,
    );
    widget.runtime.actorContext?.addListener(_actorChanged);
    unawaited(_refresh());
  }

  void _actorChanged() {
    if (!mounted) return;
    setState(() {
      _denied = !_actorValid;
      _error = null;
    });
    if (_actorValid) unawaited(_refresh());
  }

  @override
  void dispose() {
    _epoch++;
    widget.runtime.actorContext?.removeListener(_actorChanged);
    super.dispose();
  }

  Future<void> _refresh() async {
    if (_loading || !_actorValid) return;
    final revision = ++_epoch;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      await _repository.refresh(widget.space, widget.journeyId);
      if (mounted && revision == _epoch) setState(() => _denied = false);
    } on MakoloApiError catch (error) {
      if (!mounted || revision != _epoch) return;
      if (error.statusCode == 403 || error.statusCode == 404) {
        await _repository.store.deleteProjection(
          SpaceBeneficiaryResourcesRepository.projectionKind,
          resourceKey: SpaceBeneficiaryResourcesRepository.resourceKey(
            widget.space, widget.journeyId,
          ),
        );
        if (mounted) setState(() => _denied = true);
      } else {
        setState(() => _error = 'Impossible de récupérer les ressources récentes.');
      }
    } on Object {
      if (mounted && revision == _epoch) {
        setState(() => _error = 'La connexion est indisponible. Les ressources locales restent lisibles.');
      }
    } finally {
      if (mounted && revision == _epoch) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Ressources de préparation'),
      actions: [
        IconButton(
          icon: const Icon(Icons.refresh_rounded),
          tooltip: 'Actualiser',
          onPressed: _loading || !_actorValid ? null : _refresh,
        ),
      ],
    ),
    body: !_actorValid || _denied
        ? const Center(child: Text('Ressources non accessibles pour cet Espace.'))
        : StreamBuilder<StoredProjection?>(
            stream: _repository.watch(widget.space, widget.journeyId),
            builder: (context, snapshot) {
              final raw = snapshot.data?.payload['resources'];
              final resources = raw is List ? raw.whereType<Map>().toList() : <Map>[];
              return ListView(
                padding: const EdgeInsets.all(20),
                children: [
                  if (_loading) const LinearProgressIndicator(),
                  if (_error != null) Text(_error!),
                  if (snapshot.data == null && !_loading)
                    const Text('Les ressources ne sont pas encore disponibles localement.'),
                  if (snapshot.data != null && resources.isEmpty)
                    const Text('Aucune ressource publiée pour cette démarche.'),
                  for (final resource in resources)
                    Card(
                      child: ListTile(
                        title: Text(resource['title']?.toString() ?? 'Ressource'),
                        subtitle: Text(resource['description']?.toString() ?? ''),
                        trailing: resource['kind'] == 'file'
                            ? const Icon(Icons.insert_drive_file_outlined)
                            : null,
                        onTap: () {
                          final path = resource['download_url'];
                          if (resource['kind'] == 'text') {
                            _showText(resource['title']?.toString() ?? 'Ressource',
                                resource['text']?.toString() ?? '');
                          } else if (resource['kind'] == 'file' &&
                              path is String && path.isNotEmpty &&
                              widget.runtime.api != null) {
                            Navigator.of(context).push(
                              MaterialPageRoute<void>(
                                builder: (_) => JourneyOwnerFileReader(
                                  api: widget.runtime.api!,
                                  profileId: _repository.profileId,
                                  path: path,
                                  title: resource['title']?.toString() ?? 'Ressource',
                                  mime: resource['mime_type']?.toString() ?? '',
                                ),
                              ),
                            );
                          } else if (resource['kind'] == 'url') {
                            _showText(
                              'Source externe',
                              resource['external_url']?.toString() ?? '',
                            );
                          }
                        },
                      ),
                    ),
                ],
              );
            },
          ),
  );

  void _showText(String title, String text) {
    showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(title),
        content: SingleChildScrollView(child: SelectableText(text)),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(),
            child: const Text('Fermer'),
          ),
        ],
      ),
    );
  }
}
