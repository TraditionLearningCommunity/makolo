import 'dart:async';

import 'package:flutter/material.dart';

import '../../app/runtime/actor_context.dart';
import '../../app/runtime/app_runtime.dart';
import '../../design/behavior_states.dart';
import '../../design/makolo_components.dart';
import '../../design/makolo_theme.dart';

/// Online-only JourneyRequest owner depth for an authenticated Space actor.
/// Now cannot decide on a cached capability or claim a local optimistic result.
class SpaceRequestScreen extends StatefulWidget {
  const SpaceRequestScreen({
    super.key,
    required this.runtime,
    required this.actor,
    required this.requestId,
  });

  final AppRuntime runtime;
  final SpaceActorContext actor;
  final String requestId;

  @override
  State<SpaceRequestScreen> createState() => _SpaceRequestScreenState();
}

class _SpaceRequestScreenState extends State<SpaceRequestScreen> {
  Map<String, dynamic>? _owner;
  String? _error;
  bool _loading = true;
  bool _sending = false;
  int _epoch = 0;

  bool get _actorValid => widget.runtime.actorContext?.value == widget.actor;

  String get _path {
    final slug = Uri.encodeComponent(widget.actor.space.slug);
    final requestId = Uri.encodeComponent(widget.requestId);
    final perspective = widget.actor.perspective;
    final uri = Uri(
      path: 'api/v1/organizations/workspaces/$slug/requests/$requestId/',
      queryParameters: perspective.isAll
          ? null
          : {'responsibility': perspective.id!},
    );
    return uri.toString();
  }

  Map<String, dynamic>? _map(Object? value) {
    if (value is Map<String, dynamic>) return value;
    if (value is Map) {
      return value.map((key, value) => MapEntry(key.toString(), value));
    }
    return null;
  }

  @override
  void initState() {
    super.initState();
    widget.runtime.actorContext?.addListener(_contextChanged);
    unawaited(_load());
  }

  @override
  void didUpdateWidget(covariant SpaceRequestScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.runtime.actorContext != widget.runtime.actorContext) {
      oldWidget.runtime.actorContext?.removeListener(_contextChanged);
      widget.runtime.actorContext?.addListener(_contextChanged);
    }
    if (oldWidget.actor != widget.actor ||
        oldWidget.requestId != widget.requestId ||
        oldWidget.runtime != widget.runtime) {
      _contextChanged();
    }
  }

  @override
  void dispose() {
    _epoch++;
    widget.runtime.actorContext?.removeListener(_contextChanged);
    super.dispose();
  }

  void _contextChanged() {
    _epoch++;
    if (!mounted) return;
    setState(() {
      _owner = null;
      _error = null;
      _sending = false;
      _loading = _actorValid;
    });
    if (_actorValid) unawaited(_load());
  }

  Future<void> _load() async {
    if (!_actorValid) return;
    final epoch = ++_epoch;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final api = widget.runtime.api;
      if (api == null) throw StateError('API indisponible');
      final response = await api.get(_path);
      if (response.statusCode != 200) throw StateError('Lecture non confirmée');
      final data = response.jsonObject();
      final space = _map(data['space']);
      final owner = _map(data['request']);
      final expectedPerspective = widget.actor.perspective.id ?? 'all';
      if (space?['id'] != widget.actor.space.id ||
          owner?['id'] != widget.requestId ||
          data['responsibility'] != expectedPerspective) {
        throw const FormatException('Contexte propriétaire incohérent');
      }
      if (!mounted || epoch != _epoch || !_actorValid) return;
      setState(() => _owner = data);
    } on Object {
      if (!mounted || epoch != _epoch || !_actorValid) return;
      setState(() {
        _owner = null;
        _error = 'Le propriétaire ne rend plus cette demande accessible '
            'dans ce contexte. Vérifiez la connexion ou vos droits.';
      });
    } finally {
      if (mounted && epoch == _epoch) setState(() => _loading = false);
    }
  }

  Future<void> _decide(String decision) async {
    final owner = _owner;
    if (owner == null ||
        !_actorValid ||
        _sending ||
        _map(owner['capabilities'])?['decide'] != true) {
      return;
    }
    final label = decision == 'approve' ? 'approuver' : 'refuser';
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Confirmer votre décision'),
        content: Text(
          'Voulez-vous $label cette demande ? '
          'Le propriétaire vérifiera à nouveau votre autorité et son état.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(false),
            child: const Text('Annuler'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(dialogContext).pop(true),
            child: const Text('Confirmer'),
          ),
        ],
      ),
    );
    if (confirmed != true || !mounted || !_actorValid) return;
    final epoch = _epoch;
    setState(() {
      _sending = true;
      _error = null;
    });
    try {
      final api = widget.runtime.api;
      if (api == null) throw StateError('API indisponible');
      final response = await api.post(
        _path,
        body: {'decision': decision},
      );
      if (response.statusCode != 200) {
        throw StateError('Le propriétaire n’a pas confirmé cette décision.');
      }
      final result = response.jsonObject();
      final request = _map(result['request']);
      final space = _map(result['space']);
      if (result['confirmed_by_owner'] != true ||
          space?['id'] != widget.actor.space.id ||
          request?['id'] != widget.requestId ||
          request?['status'] !=
              (decision == 'approve' ? 'approved' : 'rejected')) {
        throw const FormatException('Confirmation propriétaire incomplète');
      }
      if (!mounted || !_actorValid || epoch != _epoch) return;
      // Re-read the owner after its authoritative mutation. Never requeue
      // the command just because the subsequent observation is unavailable.
      await _load();
      if (!mounted || !_actorValid) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Décision confirmée par le propriétaire.')),
      );
    } on Object {
      if (!mounted || !_actorValid || epoch != _epoch) return;
      setState(() {
        _owner = null;
        _error = 'La décision n’est pas confirmée ici. '
            'Actualisez la demande avant toute nouvelle tentative.';
      });
    } finally {
      if (mounted && _actorValid) setState(() => _sending = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final request = _map(_owner?['request']);
    final activity = _map(request?['activity']);
    final capabilities = _map(_owner?['capabilities']);
    final canDecide =
        _actorValid && !_loading && !_sending && capabilities?['decide'] == true;
    return Scaffold(
      appBar: AppBar(
        title: const Text('Demande de cet Espace'),
        actions: [
          IconButton(
            tooltip: 'Actualiser',
            onPressed: _sending || !_actorValid ? null : _load,
            icon: const Icon(Icons.refresh_rounded),
          ),
        ],
      ),
      body: !_actorValid
          ? const MakoloEmptyState(
              title: 'Le contexte de cet Espace a changé.',
              body: 'Revenez dans l’Espace autorisé pour consulter la demande.',
              icon: Icons.lock_outline,
            )
          : _loading
          ? const Center(child: CircularProgressIndicator.adaptive())
          : _error != null
          ? MakoloErrorState(message: _error!, onRetry: _load)
          : request == null
          ? MakoloErrorState(
              message: 'Cette demande n’est pas disponible.',
              onRetry: _load,
            )
          : ListView(
              padding: const EdgeInsets.all(MakoloSpacing.lg),
              children: [
                Semantics(
                  header: true,
                  child: Text(
                    (activity?['title'] as String?) ?? 'Demande',
                    style: Theme.of(context).textTheme.headlineMedium,
                  ),
                ),
                const SizedBox(height: MakoloSpacing.lg),
                MakoloSection(
                  title: 'État établi',
                  child: MakoloCard(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        MakoloStatus(
                          label: request['status'] == 'pending'
                              ? 'En attente de décision'
                              : request['status'] == 'approved'
                              ? 'Approuvée'
                              : request['status'] == 'rejected'
                              ? 'Refusée'
                              : 'Statut modifié dans le métier',
                        ),
                        const SizedBox(height: MakoloSpacing.md),
                        const Text(
                          'La demande appartient au domaine Démarche. '
                          'Les autorisations sont revérifiées par le serveur.',
                        ),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: MakoloSpacing.lg),
                if (canDecide) ...[
                  FilledButton.icon(
                    onPressed: () => unawaited(_decide('approve')),
                    icon: const Icon(Icons.check_circle_outline_rounded),
                    label: const Text('Approuver'),
                  ),
                  const SizedBox(height: MakoloSpacing.sm),
                  OutlinedButton.icon(
                    onPressed: () => unawaited(_decide('reject')),
                    icon: const Icon(Icons.cancel_outlined),
                    label: const Text('Refuser'),
                  ),
                ] else if (request['status'] == 'pending')
                  const Text(
                    'Aucune décision n’est autorisée dans votre contexte actuel.',
                  ),
              ],
            ),
    );
  }
}
