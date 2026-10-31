import 'dart:math';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../app/runtime/actor_context.dart';
import '../../app/runtime/app_runtime.dart';
import '../../network/api_error.dart';
import 'subscription_billing_format.dart';

Map<String, dynamic>? _object(Object? raw) {
  if (raw is! Map) return null;
  return raw.map((key, value) => MapEntry(key.toString(), value));
}

List<Map<String, dynamic>> _objects(Object? raw) {
  if (raw is! List) return const [];
  return raw.map(_object).whereType<Map<String, dynamic>>().toList();
}

String _value(Object? raw, [String fallback = '']) {
  final value = raw?.toString().trim() ?? '';
  return value.isEmpty ? fallback : value;
}

String _actionError(Object error) {
  if (error is MakoloApiError) {
    if (error.statusCode == 401) return 'Votre session doit être renouvelée.';
    if (error.statusCode == 403 || error.statusCode == 404) {
      return 'Cette action n’est plus accessible.';
    }
    if (error.statusCode == 400) return error.message;
  }
  return 'La demande n’a pas pu être confirmée. Vérifiez son état avant de réessayer.';
}

String _uniqueIntent() {
  final random = Random.secure();
  return List.generate(
    24,
    (_) => random.nextInt(256).toRadixString(16).padLeft(2, '0'),
  ).join();
}

/// Self-service controls are projections of the server catalog and transitions.
/// No capability, quote, or payment state is computed here.
class SubscriptionActionsPanel extends StatefulWidget {
  const SubscriptionActionsPanel({
    super.key,
    required this.runtime,
    required this.snapshot,
    required this.onUpdated,
    this.spaceSlug,
    this.expectedSpaceId,
  });

  final AppRuntime runtime;
  final Map<String, dynamic> snapshot;
  final Future<void> Function() onUpdated;
  final String? spaceSlug;
  final String? expectedSpaceId;

  @override
  State<SubscriptionActionsPanel> createState() =>
      _SubscriptionActionsPanelState();
}

class _SubscriptionActionsPanelState extends State<SubscriptionActionsPanel> {
  bool _busy = false;
  bool _loadingMore = false;
  String? _error;
  final List<Map<String, dynamic>> _extraBills = [];
  final List<Map<String, dynamic>> _extraHistory = [];
  int? _offset;
  int? _historyOffset;
  bool _loadingHistory = false;

  String get subscriptionPath => widget.spaceSlug == null
      ? 'api/v1/subscriptions/me/'
      : 'api/v1/subscriptions/spaces/${Uri.encodeComponent(widget.spaceSlug!)}/';

  bool get canManage =>
      _object(widget.snapshot['subscription'])?['can_manage'] != false;

  bool _sameSubject(AppRuntime runtime, String? profileId) {
    if (!mounted || !identical(widget.runtime, runtime) ||
        runtime.session?.profileId != profileId) return false;
    if (widget.spaceSlug == null) return true;
    final actor = runtime.actorContext?.value;
    return actor is SpaceActorContext &&
        actor.space.slug == widget.spaceSlug &&
        actor.space.id == widget.expectedSpaceId &&
        _object(widget.snapshot['space'])?['id']?.toString() ==
            widget.expectedSpaceId;
  }

  @override
  void initState() {
    super.initState();
    _offset = _object(widget.snapshot['billing'])?['next_offset'] as int?;
    _historyOffset =
        _object(widget.snapshot['history'])?['next_offset'] as int?;
  }

  @override
  void didUpdateWidget(covariant SubscriptionActionsPanel oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.runtime != oldWidget.runtime ||
        widget.snapshot != oldWidget.snapshot ||
        widget.spaceSlug != oldWidget.spaceSlug ||
        widget.expectedSpaceId != oldWidget.expectedSpaceId) {
      _extraBills.clear();
      _extraHistory.clear();
      _offset = _object(widget.snapshot['billing'])?['next_offset'] as int?;
      _historyOffset =
          _object(widget.snapshot['history'])?['next_offset'] as int?;
      _error = null;
    }
  }

  Widget _list(String title, Object? source) {
    if (source is! List || source.isEmpty) return const SizedBox.shrink();
    return Padding(
      padding: const EdgeInsets.only(top: 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: const TextStyle(fontWeight: FontWeight.w700)),
          for (final row in source)
            Padding(
              padding: const EdgeInsets.only(top: 6),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    '• ' +
                        _value(
                          _object(row)?['label'] ?? _object(row)?['title'],
                          _value(row),
                        ),
                  ),
                  if (_object(row) case final detail?)
                    if (_value(
                      detail['detail'],
                      _value(detail['description']),
                    ).isNotEmpty)
                      Padding(
                        padding: const EdgeInsets.only(left: 16),
                        child: Text(
                          _value(
                                detail['detail'],
                                _value(detail['description']),
                              ) +
                              (detail['state'] == null
                                  ? ''
                                  : ' · ' +
                                        subscriptionConditionStatusLabel(
                                          detail['state'],
                                        )),
                          style: Theme.of(context).textTheme.bodySmall,
                        ),
                      ),
                ],
              ),
            ),
        ],
      ),
    );
  }

  Future<void> _preview(String endpoint, String title) async {
    final api = widget.runtime.api;
    final sourceRuntime = widget.runtime;
    final profileId = sourceRuntime.session?.profileId;
    if (api == null || _busy) {
      setState(() => _error = 'Cette action nécessite une connexion active.');
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
    });
    late final Map<String, dynamic> preview;
    try {
      preview = (await api.get(endpoint)).jsonObject();
    } on Object catch (error) {
      if (mounted) {
        setState(() {
          _busy = false;
          _error = _actionError(error);
        });
      }
      return;
    }
    if (!_sameSubject(sourceRuntime, profileId) || widget.runtime.api != api)
      return;
    setState(() => _busy = false);
    final intent = _uniqueIntent();
    var confirming = false;
    String? failed;
    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (sheetContext) => StatefulBuilder(
        builder: (sheetContext, setSheet) => SafeArea(
          child: Padding(
            padding: EdgeInsets.fromLTRB(
              20,
              8,
              20,
              MediaQuery.viewInsetsOf(sheetContext).bottom + 20,
            ),
            child: SingleChildScrollView(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(
                    title,
                    style: Theme.of(sheetContext).textTheme.headlineSmall,
                  ),
                  const SizedBox(height: 10),
                  Text(_value(preview['target_name'], title)),
                  if (_object(preview['billing_terms']) != null) ...[
                    const SizedBox(height: 8),
                    Text(subscriptionPriceLabel(preview['billing_terms'])),
                  ],
                  if (_value(preview['current_name']).isNotEmpty)
                    Text('Depuis : ' + _value(preview['current_name'])),
                  if (_value(preview['eligibility']).isNotEmpty)
                    Text('Disponibilité : ' + _value(preview['eligibility'])),
                  _list('Capacités obtenues', preview['features_gained']),
                  _list('Capacités retirées', preview['features_lost']),
                  _list('Conditions', preview['requirements']),
                  _list('À savoir', preview['warnings']),
                  for (final quota in _objects(preview['quota_changes'])) ...[
                    const SizedBox(height: 8),
                    Text(
                      _value(quota['label']) +
                          ' : ' +
                          _value(quota['current_value'], '—') +
                          ' → ' +
                          _value(quota['target_value'], '—'),
                    ),
                  ],
                  if (preview['quota_changes'] is List &&
                      (preview['quota_changes'] as List).isNotEmpty)
                    const Padding(
                      padding: EdgeInsets.only(top: 6),
                      child: Text(
                        'Les limites sont calculées selon votre usage actuel.',
                      ),
                    ),
                  if (preview['has_payment_requirement'] == true) ...[
                    const SizedBox(height: 12),
                    const Text(
                      'Cette demande comporte une condition de paiement.',
                    ),
                  ],
                  const SizedBox(height: 12),
                  const Text(
                    'La confirmation est soumise aux vérifications du serveur.',
                  ),
                  if (failed != null) ...[
                    const SizedBox(height: 10),
                    Text(
                      failed!,
                      style: TextStyle(
                        color: Theme.of(sheetContext).colorScheme.error,
                      ),
                    ),
                  ],
                  const SizedBox(height: 18),
                  Row(
                    children: [
                      Expanded(
                        child: OutlinedButton(
                          onPressed: confirming
                              ? null
                              : () => Navigator.pop(sheetContext),
                          child: const Text('Retour'),
                        ),
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: FilledButton(
                          onPressed: confirming || !canManage ||
                                  preview['can_confirm'] == false
                              ? null
                              : () async {
                                  setSheet(() {
                                    confirming = true;
                                    failed = null;
                                  });
                                  try {
                                    await api.post(
                                      endpoint,
                                      body: {'idempotency_key': intent},
                                    );
                                    if (!_sameSubject(
                                          sourceRuntime,
                                          profileId,
                                        ) ||
                                        widget.runtime.api != api)
                                      return;
                                    await widget.onUpdated();
                                    if (sheetContext.mounted)
                                      Navigator.pop(sheetContext);
                                  } on Object catch (error) {
                                    // The intent key is unchanged, including after a lost response.
                                    if (_sameSubject(
                                          sourceRuntime,
                                          profileId,
                                        ) &&
                                        widget.runtime.api == api) {
                                      await widget.onUpdated();
                                    }
                                    if (sheetContext.mounted) {
                                      setSheet(() {
                                        failed = _actionError(error);
                                        confirming = false;
                                      });
                                    }
                                  }
                                },
                          child: Text(
                            canManage && preview['can_confirm'] != false
                                ? (confirming ? 'Confirmation…' : 'Confirmer')
                                : 'Consultation uniquement',
                          ),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  Future<void> _transition(String id, String action) async {
    final api = widget.runtime.api;
    final sourceRuntime = widget.runtime;
    final profileId = sourceRuntime.session?.profileId;
    if (_busy || api == null) return;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: Text(
          action == 'complete'
              ? 'Finaliser le changement ?'
              : 'Annuler la demande ?',
        ),
        content: const Text(
          'Makolo vérifiera à nouveau vos droits et les conditions.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, false),
            child: const Text('Retour'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(dialogContext, true),
            child: const Text('Confirmer'),
          ),
        ],
      ),
    );
    if (confirmed != true ||
        !_sameSubject(sourceRuntime, profileId) ||
        widget.runtime.api != api)
      return;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await api.post(
        subscriptionPath + 'transitions/' +
            Uri.encodeComponent(id) +
            '/' +
            action +
            '/',
      );
      if (_sameSubject(sourceRuntime, profileId) && widget.runtime.api == api) {
        await widget.onUpdated();
      }
    } on Object catch (error) {
      if (_sameSubject(sourceRuntime, profileId) && widget.runtime.api == api) {
        await widget.onUpdated();
        if (mounted) setState(() => _error = _actionError(error));
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _more() async {
    final api = widget.runtime.api;
    final sourceRuntime = widget.runtime;
    final profileId = sourceRuntime.session?.profileId;
    final snapshot = widget.snapshot;
    final offset = _offset;
    if (_loadingMore || api == null || offset == null) return;
    setState(() => _loadingMore = true);
    try {
      final result = (await api.get(
        subscriptionPath + 'obligations/?offset=' + offset.toString(),
      )).jsonObject();
      if (!_sameSubject(sourceRuntime, profileId) ||
          widget.runtime.api != api ||
          widget.snapshot != snapshot)
        return;
      final previous = {
        ..._objects(_object(widget.snapshot['billing'])?['items']),
        ..._extraBills,
      }.map((row) => _value(row['id'])).toSet();
      final next = _objects(result['items']);
      setState(() {
        _extraBills.addAll(
          next.where((row) => previous.add(_value(row['id']))),
        );
        _offset = result['next_offset'] as int?;
      });
    } on Object catch (error) {
      if (mounted) setState(() => _error = _actionError(error));
    } finally {
      if (mounted) setState(() => _loadingMore = false);
    }
  }

  Future<void> _moreHistory() async {
    final api = widget.runtime.api;
    final offset = _historyOffset;
    final runtime = widget.runtime;
    final profileId = runtime.session?.profileId;
    final snapshot = widget.snapshot;
    if (api == null || offset == null || _loadingHistory) return;
    setState(() => _loadingHistory = true);
    try {
      final result = (await api.get(
        subscriptionPath + 'transitions/?offset=' + offset.toString(),
      )).jsonObject();
      if (!_sameSubject(runtime, profileId) ||
          widget.runtime.api != api ||
          widget.snapshot != snapshot)
        return;
      final seen = {
        ..._objects(_object(widget.snapshot['history'])?['items']),
        ..._extraHistory,
      }.map((item) => _value(item['id'])).toSet();
      setState(() {
        _extraHistory.addAll(
          _objects(result['items'])
              .where((item) => seen.add(_value(item['id']))),
        );
        _historyOffset = result['next_offset'] as int?;
      });
    } on Object catch (error) {
      if (_sameSubject(runtime, profileId)) {
        setState(() => _error = _actionError(error));
      }
    } finally {
      if (mounted) setState(() => _loadingHistory = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final subscription = _object(widget.snapshot['subscription']);
    if (subscription == null) return const SizedBox.shrink();
    final catalog = _objects(widget.snapshot['catalog']);
    final addons = _objects(subscription['active_addons']);
    final transition = _object(widget.snapshot['transition']);
    final hasOpenTransition = transition?['open'] == true;
    final billingRestricted =
        _object(widget.snapshot['billing'])?['visibility'] == 'restricted';
    final bills = [
      ..._objects(_object(widget.snapshot['billing'])?['items']),
      ..._extraBills,
    ];
    final history = [
      ..._objects(_object(widget.snapshot['history'])?['items']),
      ..._extraHistory,
    ];
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        if (_error != null)
          Padding(
            padding: const EdgeInsets.only(bottom: 12),
            child: Text(
              _error!,
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
          ),
        if (canManage) for (final row in addons)
          OutlinedButton(
            onPressed: _busy || hasOpenTransition
                ? null
                : () => _preview(
                    subscriptionPath + 'addons/' +
                        Uri.encodeComponent(_value(row['item_id'])) +
                        '/remove/',
                    'Retirer ' + _value(row['name'], 'cette option'),
                  ),
            child: Text(
              'Examiner le retrait de ' + _value(row['name'], 'l’option'),
            ),
          ),
        if (canManage && transition != null && transition['open'] == true) ...[
          const SizedBox(height: 8),
          if (transition['status'] == 'ready')
            FilledButton(
              onPressed: _busy
                  ? null
                  : () => _transition(_value(transition['id']), 'complete'),
              child: const Text('Finaliser le changement prêt'),
            ),
          OutlinedButton(
            onPressed: _busy
                ? null
                : () => _transition(_value(transition['id']), 'cancel'),
            child: const Text('Annuler la demande'),
          ),
        ],
        const SizedBox(height: 18),
        Text(widget.spaceSlug == null ? 'Mes changements' : 'Changements de l’Espace',
          style: Theme.of(context).textTheme.titleMedium),
        const SizedBox(height: 8),
        if (history.isEmpty)
          const Text('Aucune demande de changement enregistrée.'),
        for (final event in history)
          ListTile(
            contentPadding: EdgeInsets.zero,
            leading: const Icon(Icons.history_rounded),
            title: Text(_value(event['target_name'], 'Changement')),
            subtitle: Text(
              _value(event['kind_label']) +
                  ' · ' +
                  _value(event['status_label'], 'À vérifier') +
                  (subscriptionDateLabel(event['requested_at']).isEmpty
                      ? ''
                      : ' · ' + subscriptionDateLabel(event['requested_at'])),
            ),
          ),
        if (_historyOffset != null)
          TextButton(
            onPressed: _loadingHistory ? null : _moreHistory,
            child: Text(
              _loadingHistory ? 'Chargement…' : 'Voir les demandes précédentes',
            ),
          ),
        const SizedBox(height: 16),
        Text(
          'Formules disponibles',
          style: Theme.of(context).textTheme.titleMedium,
        ),
        const SizedBox(height: 8),
        if (hasOpenTransition)
          const Text(
            'Terminez ou annulez la demande en cours avant de lancer un autre changement.',
          ),

        if (catalog.isEmpty)
          const Text('Aucune autre formule proposée actuellement.'),
        for (final option in catalog) ...[
          Card(
            child: Padding(
              padding: const EdgeInsets.all(14),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    option['plan_type'] == 'addon' ? 'Option' : 'Formule',
                    style: Theme.of(context).textTheme.labelSmall,
                  ),
                  const SizedBox(height: 3),
                  Text(
                    _value(option['name']),
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                  const SizedBox(height: 6),
                  Text(subscriptionPriceLabel(option['billing_terms'])),
                  if (_value(option['description']).isNotEmpty)
                    Text(_value(option['description'])),
                  _list('Ce que comprend cette formule', option['benefits']),
                  const SizedBox(height: 6),
                  Text(
                    option['current'] == true
                        ? 'Déjà inclus dans votre abonnement'
                        : _value(
                            option['eligibility_label'],
                            'Disponibilité à confirmer',
                          ),
                  ),
                  if (_value(option['eligibility_explanation']).isNotEmpty)
                    Padding(
                      padding: const EdgeInsets.only(top: 4),
                      child: Text(
                        _value(option['eligibility_explanation']),
                        style: Theme.of(context).textTheme.bodySmall,
                      ),
                    ),
                  _list('Conditions à satisfaire', option['requirements']),
                  if ((option['can_request'] == true || option['can_preview'] == true) &&
                      !hasOpenTransition)
                    Padding(
                      padding: const EdgeInsets.only(top: 10),
                      child: FilledButton(
                        onPressed: _busy
                            ? null
                            : () => _preview(
                                subscriptionPath + 'plans/' +
                                    Uri.encodeComponent(
                                      _value(option['plan_version_id']),
                                    ) +
                                    '/',
                                'Examiner cette formule',
                              ),
                        child: const Text('Examiner le changement'),
                      ),
                    ),
                ],
              ),
            ),
          ),
        ],
        const SizedBox(height: 18),
        Text(
          widget.spaceSlug == null
              ? 'Facturation de mon abonnement'
              : 'Facturation de l’Espace',
          style: Theme.of(context).textTheme.titleMedium,
        ),
        const SizedBox(height: 8),
        if (billingRestricted)
          const Text('Les obligations financières sont réservées aux personnes '
              'autorisées à consulter les finances de cet Espace.')
        else if (bills.isEmpty)
          const Text('Aucune obligation financière liée à cet abonnement.'),
        for (final obligation in bills)
          Card(
            child: ListTile(
              title: Text(_value(obligation['label'], 'Facturation')),
              subtitle: Text(
                _value(obligation['amount']) +
                    ' ' +
                    _value(obligation['currency']) +
                    ' · ' +
                    subscriptionObligationStatusLabel(obligation['status']) +
                    (subscriptionDateLabel(obligation['due_at']).isEmpty
                        ? ''
                        : ' · Échéance ' +
                              subscriptionDateLabel(obligation['due_at'])),
              ),
              trailing: const Icon(Icons.chevron_right_rounded),
              onTap: _value(obligation['id']).isEmpty ||
                      (widget.spaceSlug != null && obligation['can_open_detail'] != true)
                  ? null
                  : () async {
                      final sourceRuntime = widget.runtime;
                      final profileId = sourceRuntime.session?.profileId;
                      await context.push(
                        '/payments/obligations/' +
                            Uri.encodeComponent(_value(obligation['id'])),
                      );
                      if (_sameSubject(sourceRuntime, profileId)) {
                        await widget.onUpdated();
                      }
                    },
            ),
          ),
        if (_offset != null)
          TextButton(
            onPressed: _loadingMore ? null : _more,
            child: Text(
              _loadingMore
                  ? 'Chargement…'
                  : 'Voir les autres éléments de facturation',
            ),
          ),
        const SizedBox(height: 8),
        Text(
          'Les montants et les droits restent ceux du serveur. '
          'Aucun paiement ou changement ne peut être confirmé hors ligne.',
          style: Theme.of(context).textTheme.bodySmall,
        ),
      ],
    );
  }
}
