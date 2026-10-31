import 'dart:async';

import 'package:flutter/material.dart';

import '../../app/runtime/app_runtime.dart';
import '../../design/makolo_theme.dart';
import 'subscription_actions_panel.dart';

/// Private subscription read model supplied by the canonical Subscriptions API.
/// No absent or stale local record is interpreted as "no subscription".
class BillingScreen extends StatefulWidget {
  const BillingScreen({super.key, required this.runtime});

  final AppRuntime runtime;

  @override
  State<BillingScreen> createState() => _BillingScreenState();
}

class _BillingScreenState extends State<BillingScreen> {
  Map<String, dynamic>? _data;
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    unawaited(_load());
  }

  Future<void> _load() async {
    final api = widget.runtime.api;
    if (api == null) {
      if (mounted) {
        setState(() {
          _loading = false;
          _error = 'La consultation de votre abonnement nécessite une connexion.';
        });
      }
      return;
    }
    if (mounted) setState(() { _loading = true; _error = null; });
    try {
      final response = await api.get('api/v1/subscriptions/me/');
      if (mounted) setState(() => _data = response.jsonObject());
    } on Object {
      if (mounted) {
        setState(() => _error = 'Impossible de vérifier votre abonnement. '
            'Les dernières informations affichées peuvent avoir changé.');
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Map<String, dynamic>? _object(Object? value) =>
      value is Map ? value.map((key, item) => MapEntry(key.toString(), item)) : null;

  String _text(Object? value, {String fallback = 'Non renseigné'}) =>
      value is String && value.trim().isNotEmpty ? value.trim() : fallback;

  Widget _heading(String title) => Padding(
    padding: const EdgeInsets.only(
      top: MakoloSpacing.lg, bottom: MakoloSpacing.sm,
    ),
    child: Text(title, style: Theme.of(context).textTheme.titleMedium),
  );

  Widget _content() {
    final subscription = _object(_data?['subscription']);
    if (subscription == null) {
      return const ListTile(
        contentPadding: EdgeInsets.zero,
        title: Text('Aucun abonnement personnel actif ou enregistré.'),
        subtitle: Text('Cette information provient du serveur Makolo.'),
      );
    }

    final status = _object(subscription['status']);
    final current = _object(subscription['current_base']);
    final addons = subscription['active_addons'] is List
        ? subscription['active_addons'] as List : const [];
    final billing = _object(_data?['billing']);
    final obligations = billing?['items'] is List
        ? billing!['items'] as List : const [];
    final transition = _object(_data?['transition']);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        _heading('Mon abonnement'),
        ListTile(
          contentPadding: EdgeInsets.zero,
          leading: const Icon(Icons.verified_outlined),
          title: Text(_text(status?['label'], fallback: 'État à vérifier')),
          subtitle: Text(_text(status?['explanation'], fallback: 'État de l’abonnement')),
        ),
        if (current != null)
          ListTile(
            contentPadding: EdgeInsets.zero,
            title: Text(_text(current['name'])),
            subtitle: Text(_text(current['description'], fallback: 'Formule actuelle')),
          ),
        if (addons.isNotEmpty) ...[
          _heading('Options actives'),
          for (final row in addons)
            if (_object(row) != null)
              ListTile(
                contentPadding: EdgeInsets.zero,
                title: Text(_text(_object(row)?['name'])),
                subtitle: Text(_text(_object(row)?['description'],
                    fallback: 'Option supplémentaire')),
              ),
        ],
        if (transition != null) ...[
          _heading('Changement en cours'),
          ListTile(
            contentPadding: EdgeInsets.zero,
            title: Text(_text(transition['target_name'])),
            subtitle: Text(_text(transition['status_explanation'],
                fallback: _text(transition['status_label']))),
          ),
        ],
        _heading('Facturation'),
        if (obligations.isEmpty)
          const ListTile(
            contentPadding: EdgeInsets.zero,
            title: Text('Aucune obligation de facturation dans cette sélection.'),
          ),
        for (final row in obligations)
          if (_object(row) != null)
            ListTile(
              contentPadding: EdgeInsets.zero,
              leading: const Icon(Icons.receipt_long_outlined),
              title: Text(_text(_object(row)?['label'], fallback: 'Paiement')),
              subtitle: Text(
                _text(_object(row)?['amount'], fallback: '—') + ' ' +
                _text(_object(row)?['currency'], fallback: '') + ' · ' +
                _text(_object(row)?['status'], fallback: 'État à vérifier'),
              ),
            ),
        _heading('Gérer mon abonnement'),
        SubscriptionActionsPanel(
          runtime: widget.runtime,
          snapshot: _data!,
          onUpdated: _load,
        ),
        if (billing?['next_offset'] != null)
          const Padding(
            padding: EdgeInsets.only(top: MakoloSpacing.md),
            child: Text('D’autres éléments de facturation sont disponibles.'),
          ),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Abonnement & facturation')),
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
                      child: Text(_error!, style: TextStyle(
                        color: Theme.of(context).colorScheme.error)),
                    ),
                  if (_data == null)
                    const Text('Aucune information fiable n’est disponible pour le moment.')
                  else
                    _content(),
                ],
              ),
            ),
    );
  }
}
