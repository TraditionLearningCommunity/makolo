import 'dart:async';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../app/runtime/actor_context.dart';
import '../../app/runtime/app_runtime.dart';
import '../../design/makolo_theme.dart';
import '../../network/api_error.dart';
import 'subscription_actions_panel.dart';
import 'subscription_billing_format.dart';

/// Private subscription read model supplied by the canonical Subscriptions API.
/// No absent or stale local record is interpreted as "no subscription".
class BillingScreen extends StatefulWidget {
  const BillingScreen({
    super.key,
    required this.runtime,
    this.spaceSlug,
    this.expectedSpaceId,
    this.fromTeam = false,
  });

  final AppRuntime runtime;
  final String? spaceSlug;
  final String? expectedSpaceId;
  final bool fromTeam;

  @override
  State<BillingScreen> createState() => _BillingScreenState();
}

class _BillingScreenState extends State<BillingScreen> {
  Map<String, dynamic>? _data;
  bool _loading = true;
  String? _error;
  int _requestRevision = 0;
  String _section = 'overview';

  bool get _spaceMode => widget.spaceSlug != null;

  SpaceActorContext? get _currentSpace {
    final actor = widget.runtime.actorContext?.value;
    if (actor is! SpaceActorContext ||
        actor.space.slug != widget.spaceSlug ||
        actor.space.id != widget.expectedSpaceId) {
      return null;
    }
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
    if (_spaceMode) {
      widget.runtime.actorContext?.removeListener(_onActorChanged);
    }
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
    if (isCurrent()) {
      setState(() {
        _loading = true;
        _error = null;
      });
    }
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
            _error =
                'Vous n’avez plus accès à l’abonnement de cet Espace. '
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
      top: MakoloSpacing.md,
      bottom: MakoloSpacing.sm,
    ),
    child: Text(title, style: Theme.of(context).textTheme.titleMedium),
  );

  Widget _benefits(Object? source, {bool compact = false}) {
    if (source is! List || source.isEmpty) return const SizedBox.shrink();
    final rows = source.map(_object).whereType<Map<String, dynamic>>().toList();
    if (rows.isEmpty) return const SizedBox.shrink();
    final visible = compact ? rows.take(2).toList() : rows;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        for (final item in visible)
          Padding(
            padding: const EdgeInsets.only(top: 5),
            child: Text(
              _text(item['title'], fallback: 'Avantage inclus'),
              style: Theme.of(context).textTheme.bodyMedium,
            ),
          ),
        if (compact && rows.length > 2)
          ExpansionTile(
            tilePadding: EdgeInsets.zero,
            title: Text('Autres avantages (${rows.length - 2})'),
            children: [
              for (final item in rows.skip(2))
                ListTile(
                  dense: true,
                  contentPadding: EdgeInsets.zero,
                  title: Text(
                    _text(item['title'], fallback: 'Avantage inclus'),
                  ),
                  subtitle: item['description'] == null
                      ? null
                      : Text(item['description'].toString()),
                ),
            ],
          ),
      ],
    );
  }

  Widget _capabilityTile(Map<String, dynamic> row) {
    final value = num.tryParse(row['value']?.toString() ?? '');
    final used = num.tryParse(row['usage']?.toString() ?? '');
    final progress = value != null && value > 0 && used != null
        ? (used / value).clamp(0.0, 1.0).toDouble()
        : null;
    final allowed = row['allowed'] == true;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 10),
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
          const SizedBox(height: 3),
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
          if (progress != null) ...[
            const SizedBox(height: 8),
            LinearProgressIndicator(value: progress),
          ],
          if (row['over_limit'] == true)
            const Padding(
              padding: EdgeInsets.only(top: 6),
              child: Text(
                'Limite dépassée : les éléments existants sont conservés, '
                'mais de nouvelles opérations peuvent être bloquées.',
              ),
            ),
        ],
      ),
    );
  }

  Widget _sectionLink(String label, String target) => ListTile(
    dense: true,
    contentPadding: const EdgeInsets.symmetric(horizontal: 12),
    title: Text(label),
    trailing: const Icon(Icons.chevron_right_rounded, size: 20),
    onTap: () => setState(() => _section = target),
  );

  Widget _content() {
    final subscription = _object(_data?['subscription']);
    if (subscription == null) {
      return const Padding(
        padding: EdgeInsets.symmetric(vertical: 12),
        child: Text('Aucune information d’abonnement disponible actuellement.'),
      );
    }

    if (_section != 'overview') {
      return SubscriptionActionsPanel(
        runtime: widget.runtime,
        snapshot: _data!,
        onUpdated: _load,
        section: _section,
        spaceSlug: widget.spaceSlug,
        expectedSpaceId: widget.expectedSpaceId,
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
    final outline = Theme.of(context).colorScheme.outlineVariant;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        if (_spaceMode) ...[
          Text(
            _text(
              _object(_data?['space'])?['name'],
              fallback: 'Espace sélectionné',
            ),
            style: Theme.of(context).textTheme.titleMedium,
          ),
          if (subscription['can_manage'] != true)
            Text(
              'Consultation uniquement',
              style: Theme.of(context).textTheme.bodySmall,
            ),
          const SizedBox(height: 12),
        ],
        if (_spaceMode && widget.fromTeam && _currentSpace != null)
          ListTile(
            contentPadding: EdgeInsets.zero,
            title: const Text('Revenir à l’équipe'),
            subtitle: const Text(
              'Changer de formule ne confirme pas l’ajout d’un collaborateur.',
            ),
            trailing: const Icon(Icons.chevron_right_rounded),
            onTap: () {
              if (_currentSpace == null) return;
              if (context.canPop()) {
                context.pop();
              } else {
                context.go(
                  '/space/${Uri.encodeComponent(widget.spaceSlug!)}/us/team',
                );
              }
            },
          ),
        Container(
          decoration: BoxDecoration(
            border: Border.all(color: outline),
            borderRadius: BorderRadius.circular(20),
            color: Theme.of(context).colorScheme.surface,
          ),
          padding: const EdgeInsets.all(MakoloSpacing.md),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(
                    child: Text(
                      current == null
                          ? 'Aucune formule principale active'
                          : _text(current['name']),
                      style: Theme.of(context).textTheme.titleLarge,
                    ),
                  ),
                  const SizedBox(width: 8),
                  Text(
                    _text(status?['label'], fallback: 'À vérifier'),
                    style: Theme.of(context).textTheme.labelMedium,
                  ),
                ],
              ),
              if (current != null) ...[
                const SizedBox(height: 6),
                Text(
                  subscriptionPriceLabel(current['billing_terms']),
                  style: Theme.of(context).textTheme.titleSmall,
                ),
                if (current['benefits'] is List &&
                    (current['benefits'] as List).isNotEmpty) ...[
                  const SizedBox(height: 8),
                  _benefits(current['benefits'], compact: true),
                ] else if (current['description'] != null) ...[
                  const SizedBox(height: 8),
                  Text(
                    _text(current['description']),
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                ],
              ] else
                const Padding(
                  padding: EdgeInsets.only(top: 6),
                  child: Text(
                    'Les droits déjà accordés restent vérifiés séparément.',
                  ),
                ),
              if (_text(status?['explanation'], fallback: '').isNotEmpty)
                Padding(
                  padding: const EdgeInsets.only(top: 8),
                  child: Text(
                    _text(status?['explanation']),
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                ),
              if (subscriptionDateLabel(status?['grace_until']).isNotEmpty)
                Padding(
                  padding: const EdgeInsets.only(top: 6),
                  child: Text(
                    'Fin du délai de grâce : ${subscriptionDateLabel(status?['grace_until'])}',
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                ),
            ],
          ),
        ),
        if (addons.isNotEmpty) ...[
          _heading('Options actives'),
          for (final row in addons)
            if (_object(row) case final addon?)
              ListTile(
                contentPadding: EdgeInsets.zero,
                dense: true,
                title: Text(_text(addon['name'])),
                subtitle: Text(subscriptionPriceLabel(addon['billing_terms'])),
              ),
        ],
        if (transition != null && transition['open'] == true) ...[
          _heading('Changement en cours'),
          Text(
            _text(transition['target_name']),
            style: Theme.of(context).textTheme.titleSmall,
          ),
          const SizedBox(height: 3),
          Text(
            _text(
              transition['status_explanation'],
              fallback: _text(transition['status_label']),
            ),
          ),
          if (transition['next_action'] == 'pay' &&
              _text(
                transition['payment_obligation_id'],
                fallback: '',
              ).isNotEmpty)
            Align(
              alignment: Alignment.centerLeft,
              child: TextButton(
                onPressed: () async {
                  await context.push(
                    '/payments/obligations/${Uri.encodeComponent(transition['payment_obligation_id'].toString())}',
                  );
                  if (mounted) await _load();
                },
                child: const Text('Reprendre le paiement'),
              ),
            )
          else if (transition['next_action'] == 'finance_access_required')
            const Text(
              'Le règlement nécessite une personne autorisée pour cet Espace.',
            ),
          if (transition['total_conditions'] is int &&
              (transition['total_conditions'] as int) > 0)
            Text(
              'Conditions remplies : ${transition['completed_conditions']} / ${transition['total_conditions']}',
              style: Theme.of(context).textTheme.bodySmall,
            ),
          if (transition['conditions'] is List &&
              (transition['conditions'] as List).isNotEmpty)
            ExpansionTile(
              tilePadding: EdgeInsets.zero,
              title: const Text('Conditions du changement'),
              children: [
                for (final condition in transition['conditions'] as List)
                  if (_object(condition) case final item?)
                    ListTile(
                      dense: true,
                      title: Text(_text(item['label'])),
                      subtitle: Text(
                        subscriptionConditionStatusLabel(item['state']) +
                            (item['detail'] == null
                                ? ''
                                : ' · ${item['detail']}'),
                      ),
                    ),
              ],
            ),
        ],
        if (conditions.isNotEmpty)
          ExpansionTile(
            tilePadding: EdgeInsets.zero,
            title: const Text('Conditions à suivre'),
            children: [
              for (final row in conditions)
                if (_object(row) case final item?)
                  ListTile(
                    dense: true,
                    title: Text(_text(item['label'])),
                    subtitle: Text(
                      subscriptionConditionStatusLabel(item['state']) +
                          (item['detail'] == null
                              ? ''
                              : ' · ${item['detail']}'),
                    ),
                  ),
            ],
          ),
        if (capacities.isNotEmpty)
          ExpansionTile(
            tilePadding: EdgeInsets.zero,
            title: Text(
              _spaceMode ? 'Capacités de cet Espace' : 'Capacités et limites',
            ),
            children: [
              for (final row in capacities)
                if (_object(row) case final item?) _capabilityTile(item),
            ],
          ),
        if (transition != null && transition['open'] == true)
          SubscriptionActionsPanel(
            runtime: widget.runtime,
            snapshot: _data!,
            onUpdated: _load,
            section: _section,
            spaceSlug: widget.spaceSlug,
            expectedSpaceId: widget.expectedSpaceId,
          ),
        _heading('Gérer l’abonnement'),
        Container(
          decoration: BoxDecoration(
            border: Border.all(color: outline),
            borderRadius: BorderRadius.circular(18),
          ),
          child: Column(
            children: [
              _sectionLink('Changer de formule', 'plans'),
              Divider(height: 1, color: outline),
              _sectionLink('Mes options', 'options'),
              Divider(height: 1, color: outline),
              _sectionLink('Facturation', 'billing'),
              Divider(height: 1, color: outline),
              _sectionLink('Historique', 'history'),
            ],
          ),
        ),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    return PopScope(
      canPop: _section == 'overview',
      onPopInvokedWithResult: (didPop, result) {
        if (!didPop && _section != 'overview' && mounted) {
          setState(() => _section = 'overview');
        }
      },
      child: Scaffold(
        appBar: AppBar(
          leading: _section == 'overview'
              ? null
              : IconButton(
                  tooltip: 'Retour à l’abonnement',
                  icon: const Icon(Icons.arrow_back_rounded),
                  onPressed: () => setState(() => _section = 'overview'),
                ),
          title: Text(
            _section == 'overview'
                ? (_spaceMode
                      ? 'Abonnement de l’Espace'
                      : 'Abonnement & facturation')
                : ({
                        'plans': 'Changer de formule',
                        'options': 'Mes options',
                        'billing': 'Facturation',
                        'history': 'Historique',
                      }[_section] ??
                      'Abonnement & facturation'),
          ),
        ),
        body: _loading && _data == null
            ? const Center(child: CircularProgressIndicator())
            : RefreshIndicator(
                onRefresh: _load,
                child: ListView(
                  physics: const AlwaysScrollableScrollPhysics(),
                  padding: const EdgeInsets.fromLTRB(
                    MakoloSpacing.inner,
                    8,
                    MakoloSpacing.inner,
                    24,
                  ),
                  children: [
                    if (_loading) const LinearProgressIndicator(),
                    if (_error != null)
                      Padding(
                        padding: const EdgeInsets.only(
                          bottom: MakoloSpacing.md,
                        ),
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
      ),
    );
  }
}
