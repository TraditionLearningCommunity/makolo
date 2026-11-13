import 'dart:async';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../app/runtime/actor_context.dart';
import '../../app/runtime/app_runtime.dart';
import '../../data/local/profile_store.dart';
import '../../design/action_controls.dart';
import '../../network/api_error.dart';
import 'journey_artifact_repository.dart';

/// Readable continuation of applicant Space Journeys, never provider cases.
class SpaceBeneficiaryJourneysScreen extends StatefulWidget {
  const SpaceBeneficiaryJourneysScreen({
    super.key,
    required this.runtime,
    required this.space,
  });

  final AppRuntime runtime;
  final SpaceActorIdentity space;

  @override
  State<SpaceBeneficiaryJourneysScreen> createState() =>
      _SpaceBeneficiaryJourneysScreenState();
}

class _SpaceBeneficiaryJourneysScreenState
    extends State<SpaceBeneficiaryJourneysScreen> {
  late SpaceBeneficiaryJourneyListRepository _repository;
  bool _refreshing = false;
  bool _loadingMore = false;
  bool _denied = false;
  String? _message;
  int _epoch = 0;

  bool get _actorValid {
    final active = widget.runtime.actorContext?.value;
    return active is SpaceActorContext && active.space == widget.space;
  }

  @override
  void initState() {
    super.initState();
    _repository = SpaceBeneficiaryJourneyListRepository(
      database: widget.runtime.database!,
      store: widget.runtime.store!,
      profileId: widget.runtime.session!.profileId,
      sync: widget.runtime.sync,
    );
    widget.runtime.actorContext?.addListener(_changed);
    unawaited(_refresh());
  }

  void _changed() {
    if (!mounted) return;
    setState(() {
      _denied = !_actorValid;
      _message = null;
    });
    if (_actorValid) unawaited(_refresh());
  }

  @override
  void dispose() {
    _epoch++;
    widget.runtime.actorContext?.removeListener(_changed);
    super.dispose();
  }

  Future<void> _refresh() async {
    if (_refreshing || !_actorValid) return;
    final epoch = ++_epoch;
    setState(() {
      _refreshing = true;
      _message = null;
    });
    try {
      await _repository.refresh(widget.space);
      if (mounted && epoch == _epoch) setState(() => _denied = false);
    } on MakoloApiError catch (error) {
      if (!mounted || epoch != _epoch) return;
      if (error.statusCode == 403 || error.statusCode == 404) {
        await _repository.store.deleteProjection(
          SpaceBeneficiaryJourneyListRepository.projectionKind,
          resourceKey: widget.space.id,
        );
        if (mounted) setState(() => _denied = true);
      } else {
        setState(
          () => _message = 'Connexion indisponible. Les demandes déjà connues restent visibles.',
        );
      }
    } on Object {
      if (mounted && epoch == _epoch) {
        setState(() => _message = 'Actualisation impossible pour le moment.');
      }
    } finally {
      if (mounted && epoch == _epoch) setState(() => _refreshing = false);
    }
  }

  Future<void> _more() async {
    if (_loadingMore || !_actorValid || _denied || _refreshing) return;
    final previous = await _repository.store.readProjection(
      SpaceBeneficiaryJourneyListRepository.projectionKind,
      resourceKey: widget.space.id,
    );
    final offset = previous?.payload['next_offset'];
    if (offset is! int || offset < 1) return;
    setState(() => _loadingMore = true);
    try {
      final response = await widget.runtime.api!.get(
        'api/v1/organizations/workspaces/${Uri.encodeComponent(widget.space.slug)}/beneficiary/journeys/?offset=$offset',
      );
      final page = response.jsonObject();
      final scope = page['space'];
      if (scope is! Map ||
          scope['id'] != widget.space.id ||
          page['journeys'] is! List ||
          !_actorValid) {
        throw const FormatException('Mismatched Space continuation page');
      }
      final seen = <String>{};
      final combined = <Map<String, dynamic>>[];
      for (final source in [previous?.payload['journeys'], page['journeys']]) {
        if (source is! List) continue;
        for (final value in source) {
          if (value is! Map) continue;
          final row = Map<String, dynamic>.from(value);
          final id = row['id'];
          if (id is String && seen.add(id)) combined.add(row);
        }
      }
      final next = <String, dynamic>{
        ...?previous?.payload,
        'journeys': combined,
        'has_more': page['has_more'] == true,
        'next_offset': page['next_offset'],
      };
      await _repository.store.putProjection(
        kind: SpaceBeneficiaryJourneyListRepository.projectionKind,
        resourceKey: widget.space.id,
        schemaVersion: 1,
        payload: next,
      );
    } on MakoloApiError catch (error) {
      if (error.statusCode == 401 ||
          error.statusCode == 403 ||
          error.statusCode == 404) {
        await _repository.store.deleteProjection(
          SpaceBeneficiaryJourneyListRepository.projectionKind,
          resourceKey: widget.space.id,
        );
        if (mounted) setState(() => _denied = true);
      } else if (mounted) {
        setState(
          () => _message =
              'Les demandes suivantes sont momentanément indisponibles.',
        );
      }
    } on Object {
      if (mounted) {
        setState(
          () => _message = 'Les demandes suivantes n’ont pas été récupérées.',
        );
      }
    } finally {
      if (mounted) setState(() => _loadingMore = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Demandes de cet Espace'),
      actions: [
        IconButton(
          tooltip: 'Actualiser',
          onPressed: !_actorValid || _refreshing ? null : _refresh,
          icon: const Icon(Icons.refresh_rounded),
        ),
      ],
    ),
    body: !_actorValid || _denied
        ? const Center(
            child: Text(
              'Les demandes ne sont pas accessibles pour cet Espace.',
            ),
          )
        : StreamBuilder<StoredProjection?>(
            stream: _repository.watch(widget.space),
            builder: (context, snapshot) {
              final raw = snapshot.data?.payload['journeys'];
              final journeys = raw is List
                  ? raw.whereType<Map>().toList(growable: false)
                  : <Map>[];
              return ListView(
                padding: const EdgeInsets.all(20),
                children: [
                  if (_refreshing) const LinearProgressIndicator(),
                  if (_message != null) Text(_message!),
                  if (snapshot.data == null && !_refreshing)
                    const Text('Aucune liste locale disponible actuellement.'),
                  if (snapshot.data != null && journeys.isEmpty)
                    const Text(
                      'Cet Espace n’a pas encore de demande Services.',
                    ),
                  for (final journey in journeys)
                    Card(
                      child: ListTile(
                        title: Text(journey['title']?.toString() ?? 'Demande'),
                        subtitle: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            if (journey['objective'] is String)
                              Text(journey['objective'] as String),
                            Text(journey['status']?.toString() ?? ''),
                          ],
                        ),
                        trailing: const Icon(Icons.chevron_right_rounded),
                        onTap: () {
                          final id = journey['id'];
                          if (id is String && id.isNotEmpty) {
                            context.push(
                              '/space/${Uri.encodeComponent(widget.space.slug)}/beneficiary/journeys/$id',
                            );
                          }
                        },
                      ),
                    ),
                  if (snapshot.data?.payload['has_more'] == true)
                    Padding(
                      padding: const EdgeInsets.only(top: 16),
                      child: MakoloActionButton(
                        label: 'Afficher plus de demandes',
                        icon: Icons.expand_more_rounded,
                        busy: _loadingMore,
                        onPressed: _loadingMore ? null : _more,
                      ),
                    ),
                ],
              );
            },
          ),
  );
}
