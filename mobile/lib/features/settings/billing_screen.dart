import 'dart:math';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../app/runtime/app_runtime.dart';
import '../../design/behavior_states.dart';
import '../../network/api_error.dart';

Map<String, dynamic>? _billingMap(Object? raw) {
  if (raw is Map<String, dynamic>) return raw;
  if (raw is Map) {
    return raw.map((key, value) => MapEntry(key.toString(), value));
  }
  return null;
}

List<Map<String, dynamic>> _billingRows(Object? value) {
  if (value is! List) return const [];
  return value.map(_billingMap).whereType<Map<String, dynamic>>().toList();
}

String _billingString(Object? value, [String fallback = '']) {
  final text = value?.toString().trim() ?? '';
  return text.isEmpty ? fallback : text;
}

/// The absence of a commercial term is NOT evidence that a plan is free.
String subscriptionPriceLabel(Object? value) {
  final terms = _billingMap(value);
  if (terms == null) return 'Tarif non communiqué';
  final amount = _billingString(terms['amount']);
  final currency = _billingString(terms['currency']);
  if (amount.isEmpty || currency.isEmpty) return 'Tarif non communiqué';
  if (num.tryParse(amount) == 0) return 'Gratuit';
  const periods = {
    'day': 'jour',
    'week': 'semaine',
    'month': 'mois',
    'year': 'an',
  };
  final unit = periods[terms['period_unit']] ?? 'période';
  final count = terms['period_count'] is int
      ? terms['period_count'] as int
      : int.tryParse(_billingString(terms['period_count'])) ?? 1;
  return currency + ' ' + amount + ' / ' +
      (count > 1 ? count.toString() + ' ' : '') + unit +
      (count > 1 && unit != 'mois' ? 's' : '');
}

String _billingDate(Object? raw) {
  final value = DateTime.tryParse(_billingString(raw));
  if (value == null) return '';
  final local = value.toLocal();
  return local.day.toString().padLeft(2, '0') + '/' +
      local.month.toString().padLeft(2, '0') + '/' +
      local.year.toString();
}

String _billingError(Object error) {
  if (error is MakoloApiError) {
    if (error.statusCode == 401) return 'Votre session doit être renouvelée.';
    if (error.statusCode == 403 || error.statusCode == 404) {
      return 'Cette information ou cette action n’est plus accessible.';
    }
    if (error.statusCode == 400) return error.message;
  }
  if (error is MakoloTransportError) {
    return 'Connexion indisponible. Aucune modification n’a été confirmée.';
  }
  return 'Impossible de joindre les informations de facturation.';
}

String _confirmationKey() {
  final random = Random.secure();
  return List.generate(24, (_) => random.nextInt(256).toRadixString(16).padLeft(2, '0')).join();
}

class BillingScreen extends StatefulWidget {
  const BillingScreen({super.key, required this.runtime});

  final AppRuntime runtime;

  @override
  State<BillingScreen> createState() => _BillingScreenState();
}

class _BillingScreenState extends State<BillingScreen> {
  Map<String, dynamic>? _data;
  String? _error;
  String? _notice;
  bool _loading = true;
  bool _busy = false;
  bool _loadingMore = false;
  int? _nextOffset;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void didUpdateWidget(covariant BillingScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.runtime != widget.runtime ||
        oldWidget.runtime.session?.profileId != widget.runtime.session?.profileId) {
      _data = null;
      _notice = null;
      _nextOffset = null;
      _load();
    }
  }

  Future<void> _load() async {
    final api = widget.runtime.api;
    if (api == null) {
      if (mounted) {
        setState(() {
          _loading = false;
          _error = 'Connexion au serveur indisponible.';
        });
      }
      return;
    }
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final payload = (await api.get('api/v1/subscriptions/me/')).jsonObject();
      if (!mounted) return;
      setState(() {
        _data = payload;
        _nextOffset = _billingMap(payload['billing'])?['next_offset'] as int?;
        _loading = false;
      });
    } on Object catch (error) {
      if (!mounted) return;
      setState(() {
        _error = _billingError(error);
        _loading = false;
      });
    }
  }

  void _apply(Map<String, dynamic> data, String message) {
    if (!mounted) return;
    setState(() {
      _data = data;
      _nextOffset = _billingMap(data['billing'])?['next_offset'] as int?;
      _notice = message;
      _error = null;
    });
  }

  Future<void> _moreBilling() async {
    final offset = _nextOffset;
    final api = widget.runtime.api;
    if (offset == null || api == null || _loadingMore) return;
    setState(() => _loadingMore = true);
    try {
      final data = (await api.get('api/v1/subscriptions/me/obligations/?offset=' + offset.toString())).jsonObject();
      if (!mounted || _data == null) return;
      final oldPage = _billingMap(_data!['billing']) ?? {};
      final existing = _billingRows(oldPage['items']);
      final newer = _billingRows(data['items']);
      final seen = existing.map((item) => _billingString(item['id'])).toSet();
      final combined = [...existing, ...newer.where((row) => seen.add(_billingString(row['id'])))];
      setState(() {
        _data = {
          ..._data!,
          'billing': {...oldPage, 'items': combined, 'next_offset': data['next_offset']},
        };
        _nextOffset = data['next_offset'] as int?;
      });
    } on Object catch (error) {
      if (mounted) setState(() => _error = _billingError(error));
    } finally {
      if (mounted) setState(() => _loadingMore = false);
    }
  }

  Future<void> _preview(String endpoint, String title) async {
    final api = widget.runtime.api;
    if (api == null || _busy) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    Map<String, dynamic> preview;
    try {
      preview = (await api.get(endpoint)).jsonObject();
    } on Object catch (error) {
      if (mounted) {
        setState(() {
          _error = _billingError(error);
          _busy = false;
        });
      }
      return;
    }
    if (!mounted) return;
    setState(() => _busy = false);
    final key = _confirmationKey(); // Held for the lifetime of this intent.
    var submitting = false;
    String? submitError;
    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (sheetContext) => StatefulBuilder(
        builder: (sheetContext, updateSheet) => SafeArea(
          child: Padding(
            padding: EdgeInsets.fromLTRB(
              20, 8, 20, MediaQuery.viewInsetsOf(sheetContext).bottom + 24,
            ),
            child: SingleChildScrollView(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(title, style: Theme.of(sheetContext).textTheme.headlineSmall),
                  const SizedBox(height: 12),
                  Text(_billingString(preview['target_name'], title)),
                  if (_billingMap(preview['billing_terms']) != null) ...[
                    const SizedBox(height: 8),
                    Text(subscriptionPriceLabel(preview['billing_terms'])),
                  ],
                  const SizedBox(height: 12),
                  _previewList('Capacités ajoutées', preview['features_gained']),
                  _previewList('Capacités retirées', preview['features_lost']),
                  _previewList('Conditions à vérifier', preview['requirements']),
                  _previewList('Points d’attention', preview['warnings']),
                  for (final quota in _billingRows(preview['quota_changes'])) ...[
                    const SizedBox(height: 8),
                    Text(
                      _billingString(quota['label']) + ' : ' +
                      _billingString(quota['current_value'], '—') + ' → ' +
                      _billingString(quota['target_value'], '—'),
                    ),
                  ],
                  if (preview['has_payment_requirement'] == true) ...[
                    const SizedBox(height: 12),
                    const Text('Un règlement peut être requis pour cette formule.'),
                  ],
                  const SizedBox(height: 16),
                  const Text('Les changements et paiements éventuels restent soumis à confirmation du serveur.'),
                  if (submitError != null) ...[
                    const SizedBox(height: 12),
                    Text(submitError!, style: TextStyle(color: Theme.of(sheetContext).colorScheme.error)),
                  ],
                  const SizedBox(height: 20),
                  Row(
                    children: [
                      Expanded(
                        child: OutlinedButton(
                          onPressed: submitting ? null : () => Navigator.of(sheetContext).pop(),
                          child: const Text('Retour'),
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: FilledButton(
                          onPressed: submitting ? null : () async {
                            updateSheet(() {
                              submitting = true;
                              submitError = null;
                            });
                            try {
                              final result = (await api.post(
                                endpoint, body: {'idempotency_key': key},
                              )).jsonObject();
                              _apply(result, 'Votre demande a été enregistrée.');
                              if (sheetContext.mounted) Navigator.of(sheetContext).pop();
                            } on Object catch (error) {
                              // A lost response might follow a successful write.
                              await _load();
                              if (sheetContext.mounted) {
                                updateSheet(() {
                                  submitError = _billingError(error) +
                                    ' Vérifiez l’état actualisé avant toute nouvelle confirmation.';
                                  submitting = false;
                                });
                              }
                            }
                          },
                          child: Text(submitting ? 'Confirmation…' : 'Confirmer'),
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

  Widget _previewList(String title, Object? raw) {
    if (raw is! List || raw.isEmpty) return const SizedBox.shrink();
    return Padding(
      padding: const EdgeInsets.only(top: 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: const TextStyle(fontWeight: FontWeight.w700)),
          for (final entry in raw)
            Padding(
              padding: const EdgeInsets.only(top: 5),
              child: Text('• ' + (_billingMap(entry)?['label']?.toString() ?? _billingString(entry))),
            ),
        ],
      ),
    );
  }

  Future<void> _transitionAction(String id, String operation) async {
    if (_busy || widget.runtime.api == null) return;
    final actionLabel = operation == 'complete' ? 'Finaliser' : 'Annuler';
    final confirm = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: Text(actionLabel + ' cette demande ?'),
        content: const Text('Makolo vérifiera de nouveau les conditions et votre autorité.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(dialogContext, false), child: const Text('Retour')),
          FilledButton(onPressed: () => Navigator.pop(dialogContext, true), child: Text(actionLabel)),
        ],
      ),
    );
    if (confirm != true || !mounted) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final payload = (await widget.runtime.api!.post(
        'api/v1/subscriptions/me/transitions/' + Uri.encodeComponent(id) + '/' + operation + '/',
      )).jsonObject();
      _apply(payload, operation == 'cancel' ? 'Demande annulée.' : 'Changement finalisé.');
    } on Object catch (error) {
      await _load();
      if (mounted) setState(() => _error = _billingError(error));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Widget _section(String title, List<Widget> children) => Padding(
    padding: const EdgeInsets.only(bottom: 26),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(title, style: Theme.of(context).textTheme.titleLarge),
        const SizedBox(height: 12),
        ...children,
      ],
    ),
  );

  Widget _panel(Widget child) => Card(
    margin: const EdgeInsets.only(bottom: 10),
    child: Padding(padding: const EdgeInsets.all(16), child: child),
  );

  Widget _plan(Map<String, dynamic> plan, {bool removable = false}) => _panel(
    Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(_billingString(plan['name'], 'Formule'), style: Theme.of(context).textTheme.titleMedium),
        const SizedBox(height: 6),
        Text(subscriptionPriceLabel(plan['billing_terms'])),
        if (_billingString(plan['description']).isNotEmpty) ...[
          const SizedBox(height: 6),
          Text(_billingString(plan['description'])),
        ],
        for (final benefit in _billingRows(plan['benefits']))
          Padding(
            padding: const EdgeInsets.only(top: 6),
            child: Text('✓ ' + _billingString(benefit['title'])),
          ),
        if (removable) ...[
          const SizedBox(height: 12),
          OutlinedButton(
            onPressed: _busy ? null : () => _preview(
              'api/v1/subscriptions/me/addons/' +
              Uri.encodeComponent(_billingString(plan['item_id'])) + '/remove/',
              'Retirer cette option',
            ),
            child: const Text('Examiner le retrait'),
          ),
        ],
      ],
    ),
  );

  @override
  Widget build(BuildContext context) {
    final subscription = _billingMap(_data?['subscription']);
    final state = _billingMap(subscription?['status']);
    final transition = _billingMap(_data?['transition']);
    final billing = _billingMap(_data?['billing']);
    final obligations = _billingRows(billing?['items']);
    final addons = _billingRows(subscription?['active_addons']);
    final catalog = _billingRows(_data?['catalog']);
    final capabilities = _billingRows(_data?['capabilities']);
    final ongoingConditions = _billingRows(_data?['ongoing_conditions']);
    return Scaffold(
      appBar: AppBar(
        title: const Text('Abonnement & facturation'),
        actions: [
          IconButton(
            tooltip: 'Actualiser',
            onPressed: _loading || _busy ? null : _load,
            icon: const Icon(Icons.refresh_rounded),
          ),
        ],
      ),
      body: _loading && _data == null
          ? const MakoloLoadingState()
          : _error != null && _data == null
              ? MakoloErrorState(message: _error!, onRetry: _load)
              : subscription == null
                  ? const MakoloEmptyState(
                      title: 'Aucun abonnement personnel disponible.',
                      body: 'Votre compte ne possède pas encore d’abonnement connu du serveur.',
                      icon: Icons.receipt_long_outlined,
                    )
                  : RefreshIndicator(
                      onRefresh: _load,
                      child: ListView(
                        physics: const AlwaysScrollableScrollPhysics(),
                        padding: const EdgeInsets.fromLTRB(20, 16, 20, 36),
                        children: [
                          if (_error != null)
                            _panel(Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error))),
                          if (_notice != null) _panel(Text(_notice!)),
                          Text(
                            _billingString(subscription['subject_label'], 'Mon abonnement'),
                            style: Theme.of(context).textTheme.headlineSmall,
                          ),
                          const SizedBox(height: 8),
                          Text(
                            _billingString(state?['label']) + ' · ' +
                            _billingString(state?['explanation']),
                          ),
                          if (state?['grace_until'] != null)
                            Text('À régulariser avant le ' + _billingDate(state?['grace_until'])),
                          const SizedBox(height: 24),
                          _section('Ma formule', [
                            if (_billingMap(subscription['current_base']) case final base?)
                              _plan(base)
                            else
                              const Text('Aucune formule de base active.'),
                          ]),
                          if (addons.isNotEmpty)
                            _section('Mes options', [
                              for (final addon in addons) _plan(addon, removable: true),
                            ]),
                          if (transition != null)
                            _section('Demande de changement', [
                              _panel(Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    _billingString(transition['target_name']),
                                    style: Theme.of(context).textTheme.titleMedium,
                                  ),
                                  const SizedBox(height: 6),
                                  Text(_billingString(transition['status_label'])),
                                  Text(_billingString(transition['status_explanation'])),
                                  if (transition['total_conditions'] is int &&
                                      (transition['total_conditions'] as int) > 0)
                                    Text('Conditions vérifiées : ' +
                                      _billingString(transition['completed_conditions']) +
                                      ' / ' + _billingString(transition['total_conditions'])),
                                  _previewList('Conditions', transition['conditions']),
                                  if (transition['open'] == true) ...[
                                    const SizedBox(height: 12),
                                    Wrap(
                                      spacing: 8,
                                      children: [
                                        if (transition['status'] == 'ready')
                                          FilledButton(
                                            onPressed: _busy ? null : () => _transitionAction(
                                              _billingString(transition['id']), 'complete',
                                            ),
                                            child: const Text('Finaliser'),
                                          ),
                                        OutlinedButton(
                                          onPressed: _busy ? null : () => _transitionAction(
                                            _billingString(transition['id']), 'cancel',
                                          ),
                                          child: const Text('Annuler la demande'),
                                        ),
                                      ],
                                    ),
                                  ],
                                ],
                              )),
                            ]),
                          if (ongoingConditions.isNotEmpty)
                            _section('Conditions à suivre', [
                              for (final condition in ongoingConditions)
                                ListTile(
                                  contentPadding: EdgeInsets.zero,
                                  leading: const Icon(Icons.info_outline_rounded),
                                  title: Text(_billingString(condition['label'])),
                                  subtitle: Text(_billingString(condition['detail'], 'Vérification nécessaire')),
                                ),
                            ]),
                          if (capabilities.isNotEmpty)
                            _section('Ce que ma formule permet', [
                              for (final cap in capabilities)
                                ListTile(
                                  contentPadding: EdgeInsets.zero,
                                  title: Text(_billingString(cap['name'])),
                                  subtitle: _billingString(cap['description']).isEmpty
                                      ? null : Text(_billingString(cap['description'])),
                                  trailing: Text(_billingString(cap['value_label'])),
                                ),
                            ]),
                          _section('Formules disponibles', [
                            if (catalog.isEmpty)
                              const Text('Aucune autre formule proposée actuellement.'),
                            for (final plan in catalog)
                              _panel(Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(_billingString(plan['name']), style: Theme.of(context).textTheme.titleMedium),
                                  const SizedBox(height: 6),
                                  Text(subscriptionPriceLabel(plan['billing_terms'])),
                                  if (_billingString(plan['description']).isNotEmpty)
                                    Padding(
                                      padding: const EdgeInsets.only(top: 6),
                                      child: Text(_billingString(plan['description'])),
                                    ),
                                  const SizedBox(height: 6),
                                  Text(plan['current'] == true
                                      ? 'Formule actuelle'
                                      : _billingString(plan['eligibility_label'], 'Disponibilité à confirmer')),
                                  if (_billingString(plan['eligibility_explanation']).isNotEmpty)
                                    Text(_billingString(plan['eligibility_explanation'])),
                                  _previewList('Conditions', plan['requirements']),
                                  if (plan['can_request'] == true) ...[
                                    const SizedBox(height: 12),
                                    FilledButton(
                                      onPressed: _busy ? null : () => _preview(
                                        'api/v1/subscriptions/me/plans/' +
                                        Uri.encodeComponent(_billingString(plan['plan_version_id'])) + '/',
                                        'Examiner cette formule',
                                      ),
                                      child: const Text('Examiner le changement'),
                                    ),
                                  ],
                                ],
                              )),
                          ]),
                          _section('Facturation', [
                            if (obligations.isEmpty)
                              const Text('Aucune obligation de facturation liée à cet abonnement.'),
                            for (final obligation in obligations)
                              _panel(ListTile(
                                contentPadding: EdgeInsets.zero,
                                title: Text(_billingString(obligation['label'], 'Facturation')),
                                subtitle: Text(
                                  _billingString(obligation['status']) +
                                  (_billingDate(obligation['due_at']).isNotEmpty
                                      ? ' · Échéance ' + _billingDate(obligation['due_at'])
                                      : ''),
                                ),
                                trailing: const Icon(Icons.chevron_right),
                                onTap: () => context.push(
                                  '/payments/obligations/' +
                                  Uri.encodeComponent(_billingString(obligation['id'])),
                                ),
                              )),
                            if (_nextOffset != null)
                              TextButton(
                                onPressed: _loadingMore ? null : _moreBilling,
                                child: Text(_loadingMore ? 'Chargement…' : 'Voir les autres éléments'),
                              ),
                          ]),
                          const SizedBox(height: 12),
                          Text(
                            'Les montants et statuts affichés proviennent du serveur. '
                            'Aucun paiement ni changement n’est confirmé hors connexion.',
                            style: Theme.of(context).textTheme.bodySmall,
                          ),
                        ],
                      ),
                    ),
    );
  }
}
