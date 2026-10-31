import 'dart:async';

import 'package:flutter/material.dart';

import '../../app/runtime/actor_context.dart';
import '../../app/runtime/app_runtime.dart';
import '../../design/makolo_theme.dart';
import '../../network/api_error.dart';
import 'subscription_actions_panel.dart';
import 'subscription_billing_format.dart';

/// Private subscription read model supplied by the canonical Subscriptions API.
/// No absent or stale local record is interpreted as "no subscription".
class BillingScreen extends StatefulWidget {
  const BillingScreen({super.key, required this.runtime, this.spaceSlug, this.expectedSpaceId});

  final AppRuntime runtime;
  final String? spaceSlug;
  final String? expectedSpaceId;

  @override
  State<BillingScreen> createState() => _BillingScreenState();
}

class _BillingScreenState extends State<BillingScreen> {
  Map<String, dynamic>? _data;
  bool _loading = true;
  String? _error;
  int _requestRevision = 0;

  bool get _spaceMode => widget.spaceSlug != null;

  SpaceActorContext? get _currentSpace {
    final actor = widget.runtime.actorContext?.value;
    if (actor is! SpaceActorContext ||
        actor.space.slug != widget.spaceSlug ||
        actor.space.id != widget.expectedSpaceId) return null;
    return actor;
  }

  void _onActorChanged() {
    if (!_spaceMode || !mounted) return;
    _requestRevision++;
    setState(() {
      _data = null;
      _error = null;
      _loading = _currentSpace != null;
    });
    if (_currentSpace != null) unawaited(_load());
  }

  @override
  void initState() {
    super.initState();
    if (_spaceMode) widget.runtime.actorContext?.addListener(_onActorChanged);
    unawaited(_load());
  }

  @override
  void dispose() {
    if (_spaceMode) widget.runtime.actorContext?.removeListener(_onActorChanged);
    super.dispose();
  }

  @override
  void didUpdateWidget(covariant BillingScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.runtime.actorContext != widget.runtime.actorContext ||
        oldWidget.spaceSlug != widget.spaceSlug) {
      if (oldWidget.spaceSlug != null) {
        oldWidget.runtime.actorContext?.removeListener(_onActorChanged);
      }
      if (_spaceMode) widget.runtime.actorContext?.addListener(_onActorChanged);
    }
    if (oldWidget.runtime != widget.runtime ||
        oldWidget.spaceSlug != widget.spaceSlug ||
        oldWidget.expectedSpaceId != widget.expectedSpaceId ||
        oldWidget.runtime.session?.profileId !=
            widget.runtime.session?.profileId) {
      _requestRevision++;
      _data = null;
      _error = null;
      _loading = true;
      unawaited(_load());
    }
  }

  Future<void> _load() async {
    final api = widget.runtime.api;
    final requestRevision = ++_requestRevision;
    final expectedSpaceId = widget.expectedSpaceId;
    final expectedSlug = widget.spaceSlug;
    bool isCurrent() =>
        mounted &&
        requestRevision == _requestRevision &&
        identical(widget.runtime.api, api) &&
        (!_spaceMode ||
          (_currentSpace != null &&
           widget.expectedSpaceId == expectedSpaceId &&
           widget.spaceSlug == expectedSlug));
    if (_spaceMode && _currentSpace == null) {
      if (mounted && requestRevision == _requestRevision) {
        setState(() {
          _data = null;
          _loading = false;
          _error = 'Sélectionnez cet Espace dans « Agir comme » pour consulter son abonnement.';
        });
      }
      return;
    }
    if (api == null) {
      if (isCurrent()) {
        setState(() {
          _loading = false;
          _error =
              'La consultation de votre abonnement nécessite une connexion.';
        });
      }
      return;
    }
    if (isCurrent())
      setState(() {
        _loading = true;
        _error = null;
      });
    try {
      final path = _spaceMode
          ? 'api/v1/subscriptions/spaces/${Uri.encodeComponent(expectedSlug!)}/'
          : 'api/v1/subscriptions/me/';
      final response = await api.get(path);
      final payload = response.jsonObject();
      if (_spaceMode) {
        final space = _object(payload['space']);
        final subscription = _object(payload['subscription']);
        if (space?['id']?.toString() != expectedSpaceId ||
            space?['slug']?.toString() != expectedSlug ||
            subscription?['subject_type'] != 'space') {
          throw const FormatException('Space Subscription identity mismatch');
        }
      }
      if (isCurrent()) setState(() => _data = payload);
    } on MakoloApiError catch (error) {
      if (isCurrent()) {
        setState(() {
          if (_spaceMode &&
              (error.statusCode == 401 ||
               error.statusCode == 403 ||
               error.statusCode == 404)) {
            _data = null;
            _error = 'Vous n’avez plus accès à l’abonnement de cet Espace. '
                'Vérifiez votre Mandate ou sélectionnez un autre Espace.';
          } else {
            _error = 'Impossible d’actualiser cet abonnement. Réessayez.';
          }
        });
      }
    } on Object {
      if (isCurrent()) {
        setState(
          () => _error =
              'Impossible de vérifier votre abonnement. '
              'Les dernières informations affichées peuvent avoir changé.',
        );
      }
    } finally {
      if (isCurrent()) setState(() => _loading = false);
    }
  }

  Map<String, dynamic>? _object(Object? value) => value is Map
      ? value.map((key, item) => MapEntry(key.toString(), item))
      : null;

  String _text(Object? value, {String fallback = 'Non renseigné'}) =>
      value is String && value.trim().isNotEmpty ? value.trim() : fallback;

  Widget _heading(String title) => Padding(
    padding: const EdgeInsets.only(
      top: MakoloSpacing.lg,
      bottom: MakoloSpacing.sm,
    ),
    child: Text(title, style: Theme.of(context).textTheme.titleMedium),
  );

  Widget _benefits(Object? source) {
    if (source is! List || source.isEmpty) return const SizedBox.shrink();
    return Padding(
      padding: const EdgeInsets.only(top: 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          for (final benefit in source)
            if (_object(benefit) case final item?)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 3),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Icon(Icons.check_circle_outline, size: 18),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            _text(item['title'], fallback: 'Avantage inclus'),
                          ),
                          if (item['description'] case final description?)
                            Text(
                              description.toString(),
                              style: Theme.of(context).textTheme.bodySmall,
                            ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
        ],
      ),
    );
  }

  Widget _capabilityTile(Map<String, dynamic> row) {
    final value = num.tryParse(row['value']?.toString() ?? '');
    final used = num.tryParse(row['usage']?.toString() ?? '');
    final limitProgress = value != null && value > 0 && used != null
        ? (used / value).clamp(0.0, 1.0).toDouble()
        : null;
    final allowed = row['allowed'] == true;
    final overLimit = row['over_limit'] == true;
    return Card(
      margin: const EdgeInsets.only(bottom: MakoloSpacing.sm),
      child: Padding(
        padding: const EdgeInsets.all(MakoloSpacing.md),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    _text(row['name']),
                    style: Theme.of(context).textTheme.titleSmall,
                  ),
                ),
                Text(_text(row['value_label'], fallback: 'À vérifier')),
              ],
            ),
            const SizedBox(height: 4),
            Text(
              _text(
                row['usage_label'],
                fallback: _text(
                  row['description'],
                  fallback: allowed ? 'Disponible' : 'Capacité limitée',
                ),
              ),
              style: Theme.of(context).textTheme.bodySmall,
            ),
            if (limitProgress != null) ...[
              const SizedBox(height: 9),
              LinearProgressIndicator(value: limitProgress),
            ],
            if (overLimit)
              const Padding(
                padding: EdgeInsets.only(top: 8),
                child: Text(
                  'Limite dépassée : l’existant est préservé, '
                  'de nouvelles opérations peuvent être bloquées.',
                ),
              )
            else if (!allowed)
              const Padding(
                padding: EdgeInsets.only(top: 8),
                child: Text(
                  'Cette capacité n’est pas utilisable actuellement.',
                ),
              ),
          ],
        ),
      ),
    );
  }

  Widget _content() {
    final subscription = _object(_data?['subscription']);
    if (subscription == null) {
      return const ListTile(
        contentPadding: EdgeInsets.zero,
        title: Text('Aucun abonnement actif ou enregistré pour ce sujet.'),
        subtitle: Text('Cette information provient du serveur Makolo.'),
      );
    }

    final status = _object(subscription['status']);
    final current = _object(subscription['current_base']);
    final addons = subscription['active_addons'] is List
        ? subscription['active_addons'] as List
        : const [];
    final capacities = _data?['capabilities'] is List
        ? _data!['capabilities'] as List
        : const [];
    final conditions = _data?['ongoing_conditions'] is List
        ? _data!['ongoing_conditions'] as List
        : const [];
    final transition = _object(_data?['transition']);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        _heading(_spaceMode ? 'Abonnement de cet Espace' : 'Mon abonnement'),
        if (_spaceMode) ...[
          Text(
            _text(_object(_data?['space'])?['name'], fallback: 'Espace sélectionné'),
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: 6),
          Text(
            subscription['can_manage'] == true
                ? 'Consultation et gestion autorisées pour cet Espace.'
                : 'Consultation uniquement : votre Mandate ne permet pas de modifier cet abonnement.',
          ),
          const SizedBox(height: 6),
          Text(
            'Les capacités de cet Espace ne deviennent pas des capacités personnelles.',
            style: Theme.of(context).textTheme.bodySmall,
          ),
        ],
        ListTile(
          contentPadding: EdgeInsets.zero,
          leading: const Icon(Icons.verified_outlined),
          title: Text(_text(status?['label'], fallback: 'État à vérifier')),
          subtitle: Text(
            _text(status?['explanation'], fallback: 'État de l’abonnement') +
                (subscriptionDateLabel(status?['grace_until']).isNotEmpty
                    ? ' · Échéance ' +
                          subscriptionDateLabel(status?['grace_until'])
                    : ''),
          ),
        ),
        if (current != null)
          Card(
            margin: EdgeInsets.zero,
            child: Padding(
              padding: const EdgeInsets.all(MakoloSpacing.md),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    _text(current['name']),
                    style: Theme.of(context).textTheme.titleLarge,
                  ),
                  const SizedBox(height: 6),
                  Text(subscriptionPriceLabel(current['billing_terms'])),
                  if (current['description'] != null)
                    Padding(
                      padding: const EdgeInsets.only(top: 6),
                      child: Text(_text(current['description'])),
                    ),
                  _benefits(current['benefits']),
                ],
              ),
            ),
          )
        else
          const Text(
            'Aucune formule de base active n’est associée à cet abonnement.',
          ),
        if (addons.isNotEmpty) ...[
          _heading('Options actives'),
          for (final row in addons)
            if (_object(row) != null)
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(MakoloSpacing.md),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        _text(_object(row)?['name']),
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
                      const SizedBox(height: 6),
                      Text(
                        subscriptionPriceLabel(_object(row)?['billing_terms']),
                      ),
                      if (_object(row)?['description'] != null)
                        Text(_text(_object(row)?['description'])),
                      _benefits(_object(row)?['benefits']),
                    ],
                  ),
                ),
              ),
        ],
        if (transition != null) ...[
          _heading('Changement en cours'),
          ListTile(
            contentPadding: EdgeInsets.zero,
            title: Text(_text(transition['target_name'])),
            subtitle: Text(
              _text(
                transition['status_explanation'],
                fallback: _text(transition['status_label']),
              ),
            ),
          ),
          if (transition['total_conditions'] is int &&
              (transition['total_conditions'] as int) > 0)
            Text(
              'Conditions remplies : ${transition['completed_conditions']} '
              '/ ${transition['total_conditions']}',
            ),
          if (transition['conditions'] is List)
            for (final condition in transition['conditions'] as List)
              if (_object(condition) case final item?)
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  leading: const Icon(Icons.fact_check_outlined),
                  title: Text(_text(item['label'])),
                  subtitle: Text(
                    subscriptionConditionStatusLabel(item['state']) +
                        (item['detail'] == null ? '' : ' · ${item['detail']}'),
                  ),
                ),
        ],
        if (conditions.isNotEmpty) ...[
          _heading('Conditions à suivre'),
          for (final row in conditions)
            if (_object(row) != null)
              ListTile(
                contentPadding: EdgeInsets.zero,
                title: Text(_text(_object(row)?['label'])),
                subtitle: Text(
                  subscriptionConditionStatusLabel(_object(row)?['state']) +
                      ' · ' +
                      _text(
                        _object(row)?['detail'],
                        fallback: 'Vérification en attente',
                      ),
                ),
              ),
        ],
        if (capacities.isNotEmpty) ...[
          _heading(_spaceMode ? 'Capacités de cet Espace' : 'Capacités de ma formule'),
          for (final row in capacities)
            if (_object(row) != null) _capabilityTile(_object(row)!),
        ],
        _heading(_spaceMode ? 'Abonnement de l’Espace' : 'Gérer mon abonnement'),
        SubscriptionActionsPanel(
          runtime: widget.runtime,
          snapshot: _data!,
          onUpdated: _load,
          spaceSlug: widget.spaceSlug,
          expectedSpaceId: widget.expectedSpaceId,
        ),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(
        _spaceMode ? 'Abonnement de l’Espace' : 'Abonnement & facturation',
      )),
      body: _loading && _data == null
          ? const Center(child: CircularProgressIndicator())
          : RefreshIndicator(
              onRefresh: _load,
              child: ListView(
                physics: const AlwaysScrollableScrollPhysics(),
                padding: const EdgeInsets.all(MakoloSpacing.inner),
                children: [
                  if (_loading) const LinearProgressIndicator(),
                  if (_error != null)
                    Padding(
                      padding: const EdgeInsets.only(bottom: MakoloSpacing.md),
                      child: Text(
                        _error!,
                        style: TextStyle(
                          color: Theme.of(context).colorScheme.error,
                        ),
                      ),
                    ),
                  if (_error != null)
                    Align(
                      alignment: Alignment.centerLeft,
                      child: TextButton.icon(
                        onPressed: _loading ? null : _load,
                        icon: const Icon(Icons.refresh_rounded),
                        label: const Text('Réessayer'),
                      ),
                    ),
                  if (_data == null)
                    const Text(
                      'Aucune information fiable n’est disponible pour le moment.',
                    )
                  else
                    _content(),
                ],
              ),
            ),
    );
  }
}
