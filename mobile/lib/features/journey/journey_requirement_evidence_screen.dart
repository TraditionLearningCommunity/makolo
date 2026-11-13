import 'dart:async';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../app/runtime/actor_context.dart';
import '../../app/runtime/app_runtime.dart';
import '../../data/local/profile_store.dart';
import '../../design/action_controls.dart';
import '../../network/api_error.dart';
import 'journey_artifact_repository.dart';

/// Explicit evidence submission. An artifact exists independently of a
/// Requirement; owner review alone determines whether the condition is met.
class JourneyRequirementEvidenceScreen extends StatefulWidget {
  const JourneyRequirementEvidenceScreen({
    super.key,
    required this.runtime,
    required this.journeyId,
    required this.assessmentId,
    this.space,
  });

  final AppRuntime runtime;
  final String journeyId;
  final String assessmentId;
  final SpaceActorIdentity? space;

  @override
  State<JourneyRequirementEvidenceScreen> createState() =>
      _JourneyRequirementEvidenceScreenState();
}

class _JourneyRequirementEvidenceScreenState
    extends State<JourneyRequirementEvidenceScreen> {
  late JourneyArtifactRepository _repository;
  bool _loading = false;
  bool _sending = false;
  bool _denied = false;
  String? _message;

  bool get _actorValid {
    if (widget.space == null) return true;
    final actor = widget.runtime.actorContext?.value;
    return actor is SpaceActorContext && actor.space == widget.space;
  }

  String get _evidencePath => widget.space == null
      ? 'api/v1/me/journeys/${widget.journeyId}/requirements/${widget.assessmentId}/evidence/'
      : 'api/v1/organizations/workspaces/${Uri.encodeComponent(widget.space!.slug)}/beneficiary/journeys/${widget.journeyId}/requirements/${widget.assessmentId}/evidence/';

  String get _artifactsRoute => widget.space == null
      ? '/journeys/${widget.journeyId}/artifacts'
      : '/space/${Uri.encodeComponent(widget.space!.slug)}/beneficiary/journeys/${widget.journeyId}/artifacts';

  @override
  void initState() {
    super.initState();
    _repository = JourneyArtifactRepository(
      database: widget.runtime.database!,
      store: widget.runtime.store!,
      profileId: widget.runtime.session!.profileId!,
      sync: widget.runtime.sync,
    );
    widget.runtime.actorContext?.addListener(_onActor);
    unawaited(_refresh());
  }

  @override
  void dispose() {
    widget.runtime.actorContext?.removeListener(_onActor);
    super.dispose();
  }

  void _onActor() {
    if (!mounted) return;
    setState(() => _denied = !_actorValid);
    if (_actorValid) unawaited(_refresh());
  }

  Future<void> _refresh() async {
    if (_loading || !_actorValid) return;
    setState(() {
      _loading = true;
      _message = null;
    });
    try {
      await _repository.refresh(widget.journeyId, space: widget.space);
    } on MakoloApiError catch (error) {
      if (!mounted) return;
      if (error.statusCode == 401 ||
          error.statusCode == 403 ||
          error.statusCode == 404) {
        await _repository.store.deleteProjection(
          JourneyArtifactRepository.projectionKind,
          resourceKey: JourneyArtifactRepository.resourceKey(
            widget.journeyId,
            space: widget.space,
          ),
        );
        if (mounted) setState(() => _denied = true);
      } else {
        setState(() {
          _message = 'La connexion est indisponible. Les pièces locales restent consultables.';
        });
      }
    } on Object {
      if (mounted) {
        setState(
          () => _message = 'Les pièces connues restent affichées hors réseau.',
        );
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _propose(Map<String, dynamic> artifact) async {
    if (_sending || !_actorValid || _denied) return;
    final id = artifact['id'];
    if (id is! String || id.isEmpty) return;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Proposer cette pièce comme preuve ?'),
        content: Text(
          '« ${artifact['title'] ?? 'Pièce'} » sera présentée pour examen. '
          'Cela ne valide pas automatiquement la condition.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Annuler'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('Proposer la pièce'),
          ),
        ],
      ),
    );
    if (!mounted || confirmed != true || !_actorValid) return;
    setState(() {
      _sending = true;
      _message = null;
    });
    try {
      final response = await widget.runtime.api!.post(
        _evidencePath,
        body: {'artifact_id': id},
      );
      final payload = response.jsonObject();
      final evidence = payload['evidence'];
      if (evidence is! Map ||
          evidence['artifact_id'] != id ||
          evidence['assessment_id'] != widget.assessmentId) {
        throw const FormatException('Unconfirmed Requirement evidence');
      }
      if (mounted) {
        setState(() {
          _message = 'Pièce proposée pour examen. La condition n’est pas automatiquement satisfaite.';
        });
      }
    } on MakoloApiError catch (error) {
      if (mounted) {
        setState(() {
          _message = error.statusCode == 403 || error.statusCode == 404
              ? 'Votre mandat ou cette condition n’est plus accessible.'
              : 'La transmission n’a pas été confirmée. Réessayez sans créer de nouvelle preuve.';
        });
      }
    } on Object {
      if (mounted) {
        setState(() {
          _message = 'Aucune confirmation reçue. Vérifiez la démarche avant de recommencer.';
        });
      }
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Proposer une pièce'),
        actions: [
          IconButton(
            tooltip: 'Actualiser',
            icon: const Icon(Icons.refresh_rounded),
            onPressed: _loading || !_actorValid ? null : _refresh,
          ),
        ],
      ),
      body: !_actorValid || _denied
          ? const Center(
              child: Text(
                'Cette condition n’est plus accessible dans ce contexte.',
              ),
            )
          : StreamBuilder<StoredProjection?>(
              stream: _repository.watch(widget.journeyId, space: widget.space),
              builder: (context, snapshot) {
                final payload = snapshot.data?.payload;
                final raw = payload?['artifacts'];
                final pieces = raw is List
                    ? raw.whereType<Map>().toList()
                    : <Map>[];
                final eligible = pieces
                    .where((item) => item['status'] != 'superseded')
                    .toList();
                return ListView(
                  padding: const EdgeInsets.all(20),
                  children: [
                    if (_loading) const LinearProgressIndicator(),
                    if (_message != null)
                      Padding(
                        padding: const EdgeInsets.only(bottom: 12),
                        child: Text(_message!),
                      ),
                    const Text(
                      'Choisissez une pièce déjà présente dans la démarche. '
                      'Un examen reste nécessaire avant de satisfaire la condition.',
                    ),
                    const SizedBox(height: 16),
                    for (final artifact in eligible)
                      Card(
                        child: ListTile(
                          title: Text(artifact['title']?.toString() ?? 'Pièce'),
                          subtitle: Text('Version ${artifact['version']}'),
                          trailing: _sending
                              ? const SizedBox.shrink()
                              : const Icon(Icons.send_outlined),
                          onTap: _sending
                              ? null
                              : () => _propose(
                                  Map<String, dynamic>.from(artifact),
                                ),
                        ),
                      ),
                    if (eligible.isEmpty)
                      const Padding(
                        padding: EdgeInsets.only(bottom: 12),
                        child: Text('Aucune pièce à proposer pour le moment.'),
                      ),
                    const SizedBox(height: 12),
                    MakoloActionButton(
                      label: 'Ajouter une nouvelle pièce',
                      icon: Icons.attach_file_rounded,
                      appearance: MakoloActionAppearance.secondary,
                      onPressed: _sending
                          ? null
                          : () async {
                              await context.push(_artifactsRoute);
                              if (mounted) await _refresh();
                            },
                    ),
                  ],
                );
              },
            ),
    );
  }
}
