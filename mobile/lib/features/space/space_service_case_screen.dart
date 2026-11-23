import 'dart:async';

import 'package:flutter/material.dart';

import '../../design/action_controls.dart';

import 'package:go_router/go_router.dart';

import '../../app/runtime/actor_context.dart';
import '../../app/runtime/app_runtime.dart';
import '../../presentation/contracts/space_presentation.dart';

/// MT4 operator dossier. Read and commands revalidate the current Space,
/// Mandate, Services role and Journey owner on the server every time.
class SpaceServiceCaseScreen extends StatefulWidget {
  const SpaceServiceCaseScreen({
    super.key,
    required this.runtime,
    required this.actor,
    required this.journeyId,
  });

  final AppRuntime runtime;
  final SpaceActorContext actor;
  final String journeyId;

  @override
  State<SpaceServiceCaseScreen> createState() => _SpaceServiceCaseScreenState();
}

class _SpaceServiceCaseScreenState extends State<SpaceServiceCaseScreen> {
  Map<String, dynamic>? _owner;
  bool _loading = true;
  bool _busy = false;
  bool _mustVerify = false;
  String? _error;
  int _epoch = 0;
  int _stepsOffset = 0;
  int _blockersOffset = 0;

  bool get _actorValid => widget.runtime.actorContext?.value == widget.actor;

  String get _path {
    final perspective = widget.actor.perspective;
    return Uri(
      path:
          'api/v1/organizations/workspaces/'
          '${Uri.encodeComponent(widget.actor.space.slug)}/work/'
          'service-cases/${Uri.encodeComponent(widget.journeyId)}/',
      queryParameters: {
        if (!perspective.isAll) 'responsibility': perspective.id!,
        if (_stepsOffset > 0) 'steps_offset': '$_stepsOffset',
        if (_blockersOffset > 0) 'blockers_offset': '$_blockersOffset',
      },
    ).toString();
  }

  @override
  void initState() {
    super.initState();
    widget.runtime.actorContext?.addListener(_onActorChanged);
    unawaited(_load());
  }

  @override
  void didUpdateWidget(covariant SpaceServiceCaseScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.runtime.actorContext != widget.runtime.actorContext) {
      oldWidget.runtime.actorContext?.removeListener(_onActorChanged);
      widget.runtime.actorContext?.addListener(_onActorChanged);
    }
    if (oldWidget.runtime != widget.runtime ||
        oldWidget.actor != widget.actor ||
        oldWidget.journeyId != widget.journeyId) {
      _onActorChanged();
    }
  }

  @override
  void dispose() {
    ++_epoch;
    widget.runtime.actorContext?.removeListener(_onActorChanged);
    super.dispose();
  }

  void _onActorChanged() {
    ++_epoch;
    if (!mounted) return;
    setState(() {
      _owner = null;
      _loading = _actorValid;
      _busy = false;
      _mustVerify = false;
      _stepsOffset = 0;
      _blockersOffset = 0;
      _error = null;
    });
    if (_actorValid) unawaited(_load());
  }

  Future<void> _load() async {
    if (!_actorValid) return;
    final epoch = ++_epoch;
    setState(() {
      _loading = true;
      _owner = null;
      _error = null;
    });
    try {
      final api = widget.runtime.api;
      if (api == null) throw StateError('API indisponible');
      final response = await api.get(_path);
      if (response.statusCode != 200) {
        throw StateError('Propriétaire indisponible');
      }
      final data = response.jsonObject();
      if (!_matches(data)) {
        throw const FormatException('Mauvais propriétaire ou Mandate');
      }
      if (!mounted || !_actorValid || epoch != _epoch) return;
      setState(() {
        _owner = data;
        _mustVerify = false;
      });
    } on Object {
      if (!mounted || !_actorValid || epoch != _epoch) return;
      setState(() {
        _owner = null;
        _error =
            'Ce dossier n’est pas accessible actuellement. '
            'Vérifiez votre connexion ou vos autorisations.';
      });
    } finally {
      if (mounted && epoch == _epoch) setState(() => _loading = false);
    }
  }

  void _changePage({required bool steps, required int offset}) {
    if (!_actorValid || _busy || _loading || offset < 0 || offset > 10000) {
      return;
    }
    setState(() {
      if (steps) {
        _stepsOffset = offset;
      } else {
        _blockersOffset = offset;
      }
    });
    unawaited(_load());
  }

  bool _matches(Map<String, dynamic> data) {
    final space = spaceMap(data['space']);
    final owner = spaceMap(data['owner']);
    return space?['id'] == widget.actor.space.id &&
        space?['slug'] == widget.actor.space.slug &&
        data['responsibility'] == (widget.actor.perspective.id ?? 'all') &&
        owner?['kind'] == 'journey' &&
        owner?['id'] == widget.journeyId;
  }

  Future<void> _command(String action, String id) async {
    if (!_actorValid || _owner == null || _busy || _mustVerify) return;
    final title = switch (action) {
      'start_step' => 'Démarrer cette étape ?',
      'complete_step' => 'Terminer cette étape ?',
      _ => 'Résoudre ce blocage ?',
    };
    final yes = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: Text(title),
        content: const Text(
          'Cette action modifie le dossier réel. '
          'Le serveur vérifiera votre droit et son état actuel.',
        ),
        actions: [
          MakoloActionButton(
            appearance: MakoloActionAppearance.quiet,
            onPressed: () => Navigator.of(dialogContext).pop(false),
            label: 'Annuler',
          ),
          MakoloActionButton(
            appearance: MakoloActionAppearance.primary,
            onPressed: () => Navigator.of(dialogContext).pop(true),
            label: 'Confirmer',
          ),
        ],
      ),
    );
    if (yes != true || !_actorValid || !mounted) return;
    setState(() {
      _busy = true;
      _error = null;
      _mustVerify = true;
    });
    final epoch = _epoch;
    try {
      final api = widget.runtime.api;
      if (api == null) throw StateError('API indisponible');
      final response = await api.post(
        _path,
        body: {'action': action, 'id': id},
      );
      if (response.statusCode != 200) {
        throw StateError('Action non confirmée');
      }
      final confirmed = response.jsonObject();
      if (confirmed['confirmed_by_owner'] != true || !_matches(confirmed)) {
        throw const FormatException(
          'Réponse non confirmée par le propriétaire',
        );
      }
      if (!mounted || !_actorValid || epoch != _epoch) return;
      // Reload instead of pretending a local button changed the Journey.
      await _load();
    } on Object {
      if (!mounted || !_actorValid || epoch != _epoch) return;
      setState(() {
        _error =
            'Résultat de l’action non confirmé. Actualisez le dossier '
            'avant d’envisager une nouvelle action.';
      });
    } finally {
      if (mounted && epoch == _epoch) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final data = _owner;
    final activity = spaceMap(data?['activity']);
    final conditions = spaceMap(data?['conditions']);
    final steps = data?['steps'] is List ? data!['steps'] as List : const [];
    final blockers = data?['blockers'] is List
        ? data!['blockers'] as List
        : const [];
    return Scaffold(
      appBar: AppBar(title: const Text('Dossier de prestation')),
      body: !_actorValid
          ? const Center(child: Text('Choisissez votre Espace autorisé.'))
          : RefreshIndicator(
              onRefresh: _load,
              child: ListView(
                padding: const EdgeInsets.all(20),
                children: [
                  if (_loading) const LinearProgressIndicator(),
                  if (_error != null)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 16),
                      child: Text(
                        _error!,
                        style: TextStyle(
                          color: Theme.of(context).colorScheme.error,
                        ),
                      ),
                    ),
                  if (data == null)
                    MakoloActionButton(
                      appearance: MakoloActionAppearance.quiet,
                      onPressed: _loading ? null : _load,
                      label: 'Vérifier les droits et actualiser',
                    ),
                  if (data != null) ...[
                    Text(
                      spaceText(activity?['title']) ?? 'Prestation',
                      style: Theme.of(context).textTheme.headlineSmall,
                    ),
                    if (spaceText(data['objective'])
                        case final String objective)
                      Padding(
                        padding: const EdgeInsets.only(top: 8),
                        child: Text(objective),
                      ),
                    const SizedBox(height: 12),
                    Text(
                      'État : ${spaceStateLabel(spaceText(data['status']) ?? 'unknown')}',
                    ),
                    if (spaceText(data['outcome']) case final String outcome)
                      Text('Résultat déclaré : ${spaceStateLabel(outcome)}'),
                    if (conditions != null &&
                        conditions['total'] is int &&
                        conditions['total'] > 0) ...[
                      const SizedBox(height: 20),
                      Text(
                        'Conditions évaluées',
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
                      Text(
                        '${conditions['satisfied']} satisfaites · '
                        '${conditions['awaiting']} en attente · '
                        '${conditions['unsatisfied']} à revoir',
                      ),
                    ],
                    const SizedBox(height: 24),
                    Text(
                      'Étapes de la démarche',
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    if (steps.isEmpty)
                      const Text('Aucune étape établie pour ce dossier.'),
                    for (final raw in steps)
                      if (spaceMap(raw) case final Map<String, dynamic> step)
                        ListTile(
                          contentPadding: EdgeInsets.zero,
                          title: Text(spaceText(step['title']) ?? 'Étape'),
                          subtitle: Text(
                            spaceStateLabel(
                              spaceText(step['status']) ?? 'unknown',
                            ),
                          ),
                          trailing:
                              step['can_start'] == true &&
                                  !_mustVerify &&
                                  !_busy
                              ? MakoloActionButton(
                                  appearance: MakoloActionAppearance.quiet,
                                  onPressed: () => _command(
                                    'start_step',
                                    step['id'] as String,
                                  ),
                                  label: 'Démarrer',
                                )
                              : step['can_complete'] == true &&
                                    !_mustVerify &&
                                    !_busy
                              ? MakoloActionButton(
                                  appearance: MakoloActionAppearance.quiet,
                                  onPressed: () => _command(
                                    'complete_step',
                                    step['id'] as String,
                                  ),
                                  label: 'Terminer',
                                )
                              : null,
                        ),
                    if (_stepsOffset > 0 || data['steps_has_more'] == true)
                      Wrap(
                        spacing: 8,
                        children: [
                          if (_stepsOffset > 0)
                            MakoloActionButton(
                              appearance: MakoloActionAppearance.secondary,
                              onPressed: () => _changePage(
                                steps: true,
                                offset: _stepsOffset > 50
                                    ? _stepsOffset - 50
                                    : 0,
                              ),
                              label: 'Étapes précédentes',
                            ),
                          if (data['steps_has_more'] == true)
                            MakoloActionButton(
                              appearance: MakoloActionAppearance.secondary,
                              onPressed: () => _changePage(
                                steps: true,
                                offset: _stepsOffset + 50,
                              ),
                              label: 'Étapes suivantes',
                            ),
                        ],
                      ),
                    const SizedBox(height: 24),
                    Text(
                      'Blocages actifs',
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    if (blockers.isEmpty)
                      const Text('Aucun blocage actif déclaré.'),
                    for (final raw in blockers)
                      if (spaceMap(raw) case final Map<String, dynamic> blocker)
                        ListTile(
                          contentPadding: EdgeInsets.zero,
                          title: Text(spaceText(blocker['title']) ?? 'Blocage'),
                          subtitle: Text(
                            'Sévérité : ${spaceText(blocker['severity']) ?? 'inconnue'}',
                          ),
                          trailing:
                              blocker['can_resolve'] == true &&
                                  !_mustVerify &&
                                  !_busy
                              ? MakoloActionButton(
                                  appearance: MakoloActionAppearance.quiet,
                                  onPressed: () => _command(
                                    'resolve_blocker',
                                    blocker['id'] as String,
                                  ),
                                  label: 'Résoudre',
                                )
                              : null,
                        ),
                    if (_blockersOffset > 0 ||
                        data['blockers_has_more'] == true)
                      Wrap(
                        spacing: 8,
                        children: [
                          if (_blockersOffset > 0)
                            MakoloActionButton(
                              appearance: MakoloActionAppearance.secondary,
                              onPressed: () => _changePage(
                                steps: false,
                                offset: _blockersOffset > 50
                                    ? _blockersOffset - 50
                                    : 0,
                              ),
                              label: 'Blocages précédents',
                            ),
                          if (data['blockers_has_more'] == true)
                            MakoloActionButton(
                              appearance: MakoloActionAppearance.secondary,
                              onPressed: () => _changePage(
                                steps: false,
                                offset: _blockersOffset + 50,
                              ),
                              label: 'Blocages suivants',
                            ),
                        ],
                      ),
                    const SizedBox(height: 20),
                    MakoloActionButton(
                      appearance: MakoloActionAppearance.secondary,
                      onPressed: _loading ? null : _load,
                      label: 'Actualiser le dossier',
                    ),
                    MakoloActionButton(
                      appearance: MakoloActionAppearance.secondary,
                      onPressed: () => context.pop(),
                      label: 'Retour à la prestation',
                    ),
                  ],
                ],
              ),
            ),
    );
  }
}
