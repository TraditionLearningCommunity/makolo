import 'dart:async';
import 'dart:math';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../app/runtime/app_runtime.dart';

/// Checkout of an existing personal Journey through the Commerce owner API.
/// The client never computes prices, claims capacity, or creates payment truth.
class CommerceCheckoutScreen extends StatefulWidget {
  const CommerceCheckoutScreen({
    super.key,
    required this.runtime,
    required this.journeyId,
  });

  final AppRuntime runtime;
  final String journeyId;

  @override
  State<CommerceCheckoutScreen> createState() => _CommerceCheckoutScreenState();
}

class _CommerceCheckoutScreenState extends State<CommerceCheckoutScreen> {
  Map<String, dynamic>? _checkout;
  String? _offerId;
  String? _paymentMode;
  int _quantity = 1;
  bool _loading = true;
  bool _submitting = false;
  bool _attempted = false;
  String? _error;
  late final String _operationKey = _newKey();

  static String _newKey() {
    final random = Random.secure();
    return List.generate(
      32,
      (_) => random.nextInt(16).toRadixString(16),
    ).join();
  }

  String get _endpoint =>
      'api/v1/commerce/journeys/${Uri.encodeComponent(widget.journeyId)}/checkout/';

  List<Map<String, dynamic>> get _offers {
    final raw = _checkout?['offers'];
    if (raw is! List) return const [];
    return raw
        .whereType<Map>()
        .map((row) => Map<String, dynamic>.from(row))
        .toList(growable: false);
  }

  Map<String, dynamic>? get _selected {
    for (final offer in _offers) {
      if (offer['id'] == _offerId) return offer;
    }
    return null;
  }

  List<String> get _modes {
    final raw = _selected?['payment_modes'];
    return raw is List ? raw.whereType<String>().toList() : const [];
  }

  @override
  void initState() {
    super.initState();
    unawaited(_load());
  }

  Future<Map<String, dynamic>?> _refreshOwner() async {
    final api = widget.runtime.api;
    if (api == null) throw StateError('Session unavailable');
    final result = (await api.get(_endpoint)).jsonObject();
    if (result['journey_id'] != widget.journeyId) {
      throw const FormatException('Commerce Journey identity mismatch');
    }
    if (!mounted) return null;
    setState(() {
      _checkout = result;
      final offers = _offers;
      if (_offerId == null || !offers.any((row) => row['id'] == _offerId)) {
        _offerId = offers.isEmpty ? null : offers.first['id'] as String?;
        final choice = _selected;
        _paymentMode = choice?['default_payment_mode'] as String?;
        _quantity = (choice?['min_quantity'] as int?) ?? 1;
      }
    });
    return result;
  }

  void _openOrder(String id) {
    if (!mounted) return;
    context.push('/commerce/orders/${Uri.encodeComponent(id)}');
  }

  Future<void> _load() async {
    if (_submitting) return;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final data = await _refreshOwner();
      if (!mounted) return;
      setState(() => _loading = false);
      final existing = data?['existing_order'];
      if (existing is Map && existing['id'] is String) {
        _openOrder(existing['id'] as String);
      }
    } on Object {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = 'Impossible de vérifier les offres pour cette démarche.';
      });
    }
  }

  void _chooseOffer(String? offerId) {
    if (_attempted || offerId == null) return;
    setState(() {
      _offerId = offerId;
      _paymentMode = _selected?['default_payment_mode'] as String?;
      _quantity = (_selected?['min_quantity'] as int?) ?? 1;
    });
  }

  Future<void> _createOrder() async {
    if (_loading || _submitting || _offerId == null || _paymentMode == null) {
      return;
    }
    setState(() {
      _submitting = true;
      _attempted = true;
      _error = null;
    });
    try {
      final response = await widget.runtime.api!.post(
        _endpoint,
        body: {
          'offer_id': _offerId,
          'quantity': _quantity,
          'payment_mode': _paymentMode,
          'idempotency_key': _operationKey,
        },
      );
      final order = response.jsonObject();
      if (order['kind'] != 'commerce_order' || order['id'] is! String) {
        throw const FormatException('Commerce order not confirmed');
      }
      _openOrder(order['id'] as String);
    } on Object {
      // An HTTP response can be lost after a successful order creation.
      // Read the owner before allowing an idempotent replay.
      try {
        final data = await _refreshOwner();
        final existing = data?['existing_order'];
        if (existing is Map && existing['id'] is String) {
          _openOrder(existing['id'] as String);
          return;
        }
      } on Object {
        // Unknown server outcome: the next attempt keeps the same key.
      }
      if (mounted) {
        setState(() {
          _error = 'Commande non confirmée. Vérifiez puis réessayez.';
        });
      }
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final offer = _selected;
    final min = (offer?['min_quantity'] as int?) ?? 1;
    final max = (offer?['max_quantity'] as int?) ?? 10000;
    final canOrder = _checkout?['can_order'] == true;
    return Scaffold(
      appBar: AppBar(
        title: const Text('Choisir une offre'),
        actions: [
          IconButton(
            tooltip: 'Actualiser',
            onPressed: _loading || _submitting ? null : _load,
            icon: const Icon(Icons.refresh_rounded),
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          if (_loading) const Center(child: CircularProgressIndicator()),
          if (_checkout?['activity'] case final Map activity)
            Text(
              activity['title']?.toString() ?? 'Cette possibilité',
              style: Theme.of(context).textTheme.titleLarge,
            ),
          if (_checkout != null && !canOrder)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 16),
              child: Text('Aucune nouvelle commande disponible pour cette démarche.'),
            ),
          if (canOrder) ...[
            const SizedBox(height: 20),
            Text('Offres disponibles', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 8),
            RadioGroup<String>(
              groupValue: _offerId,
              onChanged: _attempted ? null : _chooseOffer,
              child: Column(
                children: [
                  for (final option in _offers)
                    RadioListTile<String>(
                      value: option['id'] as String,
                      title: Text(option['label']?.toString() ?? 'Offre'),
                      subtitle: Text(
                        '${option['unit_price']} ${option['currency']}'
                      ),
                    ),
                ],
              ),
            ),
            if (offer != null) ...[
              const SizedBox(height: 12),
              Text('Quantité', style: Theme.of(context).textTheme.titleSmall),
              Row(
                children: [
                  IconButton(
                    tooltip: 'Diminuer',
                    onPressed: _attempted || _quantity <= min
                        ? null
                        : () => setState(() => _quantity--),
                    icon: const Icon(Icons.remove_circle_outline),
                  ),
                  Text('$_quantity'),
                  IconButton(
                    tooltip: 'Augmenter',
                    onPressed: _attempted || _quantity >= max
                        ? null
                        : () => setState(() => _quantity++),
                    icon: const Icon(Icons.add_circle_outline),
                  ),
                ],
              ),
              Text('Mode de paiement', style: Theme.of(context).textTheme.titleSmall),
              RadioGroup<String>(
                groupValue: _paymentMode,
                onChanged: _attempted
                    ? null
                    : (mode) => setState(() => _paymentMode = mode),
                child: Column(
                  children: [
                    for (final mode in _modes)
                      RadioListTile<String>(
                        value: mode,
                        title: Text(switch (mode) {
                          'none' => 'Sans paiement',
                          'upfront' => 'Payer avant confirmation',
                          'after_approval' => 'Payer après approbation',
                          'on_site' => 'Payer sur place',
                          'later' => 'Payer plus tard',
                          _ => mode,
                        }),
                      ),
                  ],
                ),
              ),
              const SizedBox(height: 16),
              FilledButton.icon(
                onPressed: _submitting ? null : _createOrder,
                icon: const Icon(Icons.shopping_bag_outlined),
                label: Text(_submitting
                    ? 'Vérification…'
                    : _attempted
                        ? 'Revérifier la commande'
                        : 'Créer la commande'),
              ),
            ],
          ],
          if (_error != null) ...[
            const SizedBox(height: 16),
            Text(
              _error!,
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
            TextButton(
              onPressed: _submitting ? null : _load,
              child: const Text('Actualiser'),
            ),
          ],
        ],
      ),
    );
  }
}
