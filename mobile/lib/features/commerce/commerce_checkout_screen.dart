import 'dart:async';
import 'dart:math';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../app/runtime/app_runtime.dart';

/// Commerce checkout for an Activity or its already-existing personal Journey.
/// The client never computes prices, claims capacity, or creates payment truth.
class CommerceCheckoutScreen extends StatefulWidget {
  const CommerceCheckoutScreen({
    super.key,
    required this.runtime,
    this.journeyId,
    this.activityId,
  }) : assert((journeyId == null) != (activityId == null));

  final AppRuntime runtime;
  final String? journeyId;
  final String? activityId;

  @override
  State<CommerceCheckoutScreen> createState() => _CommerceCheckoutScreenState();
}

class _CommerceCheckoutScreenState extends State<CommerceCheckoutScreen> {
  Map<String, dynamic>? _checkout;
  String? _offerId;
  String? _occurrenceId;
  String? _paymentMode;
  int _quantity = 1;
  bool _loading = true;
  bool _submitting = false;
  bool _attempted = false;
  String? _error;
  String _operationKey = _newKey();

  static String _newKey() {
    final random = Random.secure();
    return List.generate(
      32,
      (_) => random.nextInt(16).toRadixString(16),
    ).join();
  }

  String get _endpoint => widget.journeyId != null
      ? 'api/v1/commerce/journeys/${Uri.encodeComponent(widget.journeyId!)}/checkout/'
      : 'api/v1/commerce/activities/${Uri.encodeComponent(widget.activityId!)}/checkout/';

  String _choiceId(Map<String, dynamic> row) =>
      '${row['id']}|${row['occurrence_id'] ?? ''}';

  String? get _selectedChoice =>
      _offerId == null ? null : '$_offerId|${_occurrenceId ?? ''}';

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
      if (offer['id'] == _offerId && offer['occurrence_id'] == _occurrenceId) {
        return offer;
      }
    }
    return null;
  }

  List<String> get _modes {
    final raw = _selected?['payment_modes'];
    return raw is List ? raw.whereType<String>().toList() : const [];
  }

  String get _interactionId =>
      'commerce.checkout:${widget.runtime.session?.profileId ?? 'guest'}:'
      '${widget.journeyId ?? widget.activityId}';

  Future<void> _initialize() async {
    final store = widget.runtime.interactions;
    if (widget.runtime.isAuthenticated && store != null) {
      try {
        final saved = await store.read(_interactionId);
        final key = saved['idempotency_key'];
        if (key is String && key.isNotEmpty) {
          _operationKey = key;
          _offerId = saved['offer_id'] as String?;
          _occurrenceId = saved['occurrence_id'] as String?;
          _paymentMode = saved['payment_mode'] as String?;
          _quantity = saved['quantity'] is int ? saved['quantity'] as int : 1;
          _attempted = true;
        }
      } on Object {
        // The owner GET will still prevent duplicate active orders.
      }
    }
    if (mounted) await _load();
  }

  @override
  void initState() {
    super.initState();
    unawaited(_initialize());
  }

  Future<Map<String, dynamic>?> _refreshOwner() async {
    final api = widget.runtime.api;
    if (api == null) throw StateError('Session unavailable');
    final response = widget.runtime.isAuthenticated
        ? await api.get(_endpoint)
        : await api.publicGet(_endpoint);
    final result = response.jsonObject();
    if (widget.journeyId != null) {
      if (result['journey_id'] != widget.journeyId) {
        throw const FormatException('Commerce Journey identity mismatch');
      }
    } else {
      final activity = result['activity'];
      if (activity is! Map || activity['id'] != widget.activityId) {
        throw const FormatException('Commerce Activity identity mismatch');
      }
    }
    if (!mounted) return null;
    setState(() {
      _checkout = result;
      final offers = _offers;
      final selectionAvailable = offers.any(
        (row) => row['id'] == _offerId && row['occurrence_id'] == _occurrenceId,
      );
      // Never silently replace the subject of a previously submitted key:
      // it might already have committed despite a lost response.
      if (!selectionAvailable && !_attempted) {
        _offerId = offers.isEmpty ? null : offers.first['id'] as String?;
        _occurrenceId = offers.isEmpty
            ? null
            : offers.first['occurrence_id'] as String?;
        final choice = _selected;
        _paymentMode = choice?['default_payment_mode'] as String?;
        _quantity = (choice?['min_quantity'] as int?) ?? 1;
      }
    });
    return result;
  }

  void _openOrder(String id) {
    if (!mounted) return;
    final store = widget.runtime.interactions;
    if (store != null) {
      unawaited(store.clear(_interactionId).catchError((Object _) {}));
    }
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
        _error = 'Impossible de vérifier les offres disponibles.';
      });
    }
  }

  Future<void> _reviseChoice() async {
    if (_loading || _submitting || !_attempted) return;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      // Confirm owner state before abandoning the previously attempted key.
      final result = await _refreshOwner();
      if (!mounted) return;
      final existing = result?['existing_order'];
      if (existing is Map && existing['id'] is String) {
        _openOrder(existing['id'] as String);
        return;
      }
      final store = widget.runtime.interactions;
      if (store != null) await store.clear(_interactionId);
      if (!mounted) return;
      setState(() {
        _operationKey = _newKey();
        _attempted = false;
        _offerId = null;
        _occurrenceId = null;
        _paymentMode = null;
        _quantity = 1;
      });
      await _refreshOwner();
    } on Object {
      if (mounted) {
        setState(
          () => _error =
              'Impossible de vérifier la commande. Réessayez plus tard.',
        );
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  void _chooseOffer(String? choiceId) {
    if (_attempted || choiceId == null) return;
    final choice = _offers.where((row) => _choiceId(row) == choiceId);
    if (choice.isEmpty) return;
    setState(() {
      _offerId = choice.first['id'] as String?;
      _occurrenceId = choice.first['occurrence_id'] as String?;
      _paymentMode = _selected?['default_payment_mode'] as String?;
      _quantity = (_selected?['min_quantity'] as int?) ?? 1;
    });
  }

  Future<void> _createOrder() async {
    if (_loading || _submitting || _offerId == null || _paymentMode == null) {
      return;
    }
    if (!widget.runtime.isAuthenticated) {
      widget.runtime.recovery.requireAuthentication(
        widget.journeyId != null
            ? '/commerce/journeys/${widget.journeyId}/checkout'
            : '/commerce/activities/${widget.activityId}/checkout',
      );
      context.push('/login');
      return;
    }
    setState(() {
      _submitting = true;
      _attempted = true;
      _error = null;
    });
    final store = widget.runtime.interactions;
    if (store != null) {
      try {
        await store.save(_interactionId, {
          'idempotency_key': _operationKey,
          'offer_id': _offerId,
          'occurrence_id': _occurrenceId,
          'payment_mode': _paymentMode,
          'quantity': _quantity,
        });
      } on Object {
        // The server still guarantees idempotence on this Journey/Activity.
      }
    }
    try {
      final response = await widget.runtime.api!.post(
        _endpoint,
        body: {
          'offer_id': _offerId,
          if (_occurrenceId != null) 'occurrence_id': _occurrenceId,
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
    final selectedModeAvailable = _modes.contains(_paymentMode);
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
              child: Text(
                'Aucune nouvelle commande disponible pour cette démarche.',
              ),
            ),
          if (canOrder) ...[
            const SizedBox(height: 20),
            Text(
              'Offres disponibles',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 8),
            RadioGroup<String>(
              groupValue: _selectedChoice,
              onChanged: (choice) {
                if (!_attempted) _chooseOffer(choice);
              },
              child: Column(
                children: [
                  for (final option in _offers)
                    RadioListTile<String>(
                      value: _choiceId(option),
                      title: Text(option['label']?.toString() ?? 'Offre'),
                      subtitle: Text(
                        [
                          if ((option['occurrence_label'] ?? '')
                              .toString()
                              .isNotEmpty)
                            option['occurrence_label'].toString(),
                          '${option['unit_price']} ${option['currency']}',
                        ].join(' · '),
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
              Text(
                'Mode de paiement',
                style: Theme.of(context).textTheme.titleSmall,
              ),
              RadioGroup<String>(
                groupValue: _paymentMode,
                onChanged: (mode) {
                  if (!_attempted) setState(() => _paymentMode = mode);
                },
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
                onPressed: _submitting || !selectedModeAvailable
                    ? null
                    : _createOrder,
                icon: const Icon(Icons.shopping_bag_outlined),
                label: Text(
                  _submitting
                      ? 'Vérification…'
                      : !widget.runtime.isAuthenticated
                      ? 'Se connecter pour continuer'
                      : _attempted
                      ? 'Revérifier la commande'
                      : 'Créer la commande',
                ),
              ),
            ],
            if (_attempted) ...[
              const SizedBox(height: 8),
              TextButton(
                onPressed: _loading || _submitting ? null : _reviseChoice,
                child: const Text('Modifier mon choix'),
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
