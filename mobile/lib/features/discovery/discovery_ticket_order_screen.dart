import 'dart:async';
import 'dart:convert';
import 'dart:math';

import 'package:flutter/material.dart';

import '../../app/runtime/app_runtime.dart';

/// Private owner read; never expose ticket QR secrets or infer payment status.
class DiscoveryTicketOrderScreen extends StatefulWidget {
  const DiscoveryTicketOrderScreen({
    super.key,
    required this.runtime,
    required this.orderId,
  });

  final AppRuntime runtime;
  final String orderId;

  @override
  State<DiscoveryTicketOrderScreen> createState() =>
      _DiscoveryTicketOrderScreenState();
}

class _DiscoveryTicketOrderScreenState
    extends State<DiscoveryTicketOrderScreen> {
  bool _loading = true;
  String? _error;
  Map<String, dynamic>? _order;
  Map<String, dynamic>? _payment;
  bool _sandboxAvailable = false;
  bool _paying = false;
  String? _paymentError;
  final String _paymentKey = _newPaymentKey();

  static String _newPaymentKey() {
    final random = Random.secure();
    return List.generate(
      32,
      (_) => random.nextInt(16).toRadixString(16),
    ).join();
  }

  Future<void> _paySandbox() async {
    if (_paying || !_sandboxAvailable || _order == null) return;
    setState(() {
      _paying = true;
      _paymentError = null;
    });
    try {
      final api = widget.runtime.api!;
      var payment = _payment;
      if (payment == null) {
        final response = await api.post(
          'api/v1/payments/payments/',
          body: {
            'order_id': widget.orderId,
            'provider': 'sandbox',
            'method': 'card',
            'idempotency_key': _paymentKey,
          },
        );
        payment = response.jsonObject();
        if (payment['id'] is! String) {
          throw const FormatException('Payment identity missing');
        }
        _payment = payment;
      }
      if (payment['status'] != 'succeeded') {
        final id = Uri.encodeComponent(payment['id'] as String);
        final response = await api.post(
          'api/v1/payments/payments/$id/sandbox-complete/',
        );
        payment = response.jsonObject();
        _payment = payment;
      }
      if (!mounted) return;
      if (payment['status'] != 'succeeded') {
        setState(() => _paymentError = 'Paiement à vérifier.');
      }
      await _load();
    } on Object {
      // Payment initiation may have committed despite a lost response.
      await _load();
      if (mounted && _payment?['status'] != 'succeeded') {
        setState(
          () => _paymentError =
              'Paiement à vérifier. Actualisez avant de réessayer.',
        );
      }
    } finally {
      if (mounted) setState(() => _paying = false);
    }
  }

  @override
  void initState() {
    super.initState();
    unawaited(_load());
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final response = await widget.runtime.api!.get(
        'api/v1/tickets/orders/${Uri.encodeComponent(widget.orderId)}/',
      );
      final order = response.jsonObject();
      var sandbox = false;
      try {
        final config = await widget.runtime.api!.get(
          'api/v1/payments/configuration/',
        );
        sandbox = config.jsonObject()['sandbox_enabled'] == true;
      } on Object {
        // Failed configuration cannot enable sandbox.
      }
      if (order['id'] != widget.orderId) {
        throw const FormatException('Order identity mismatch');
      }
      Map<String, dynamic>? currentPayment;
      final reference = order['reference'];
      if (reference is String && reference.isNotEmpty) {
        try {
          final query = Uri.encodeQueryComponent(reference);
          final paymentsResponse = await widget.runtime.api!.get(
            'api/v1/payments/payments/?order=$query',
          );
          final decoded = jsonDecode(paymentsResponse.body);
          final rows = decoded is List
              ? decoded
              : decoded is Map
              ? decoded['results']
              : null;
          if (rows is List) {
            for (final raw in rows.whereType<Map>()) {
              final relatedOrder = raw['order'];
              if (relatedOrder is! Map ||
                  relatedOrder['id'] != widget.orderId ||
                  raw['id'] is! String) {
                continue;
              }
              final candidate = Map<String, dynamic>.from(raw);
              if (currentPayment == null ||
                  candidate['status'] == 'succeeded') {
                currentPayment = candidate;
              }
              if (candidate['status'] == 'succeeded') break;
            }
          }
        } on Object {
          // The authorized owner order still remains usable for inspection.
        }
      }
      if (!mounted) return;
      setState(() {
        _order = order;
        _payment = currentPayment;
        _sandboxAvailable = sandbox;
        _loading = false;
      });
    } on Object {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = 'Cette commande n’est pas accessible dans ce compte.';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final order = _order;
    return Scaffold(
      appBar: AppBar(
        title: const Text('Commande de billets'),
        actions: [
          IconButton(
            tooltip: 'Actualiser',
            onPressed: _loading ? null : _load,
            icon: const Icon(Icons.refresh_rounded),
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          if (_loading)
            const Center(child: CircularProgressIndicator())
          else if (_error != null) ...[
            Text(
              _error!,
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
            TextButton(onPressed: _load, child: const Text('Réessayer')),
          ] else if (order != null) ...[
            Text(
              'Commande ${order['reference'] ?? ''}',
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            const SizedBox(height: 16),
            Text('État : ${order['status'] ?? 'À vérifier'}'),
            Text(
              'Montant : ${order['total_amount'] ?? ''} ${order['currency'] ?? ''}',
            ),
            const SizedBox(height: 12),
            if (_sandboxAvailable &&
                _payment?['status'] != 'succeeded' &&
                !{
                  'paid',
                  'confirmed',
                  'cancelled',
                  'expired',
                }.contains(order['status']?.toString().toLowerCase())) ...[
              const SizedBox(height: 16),
              FilledButton.icon(
                onPressed: _paying ? null : _paySandbox,
                icon: const Icon(Icons.credit_card_rounded),
                label: Text(
                  _paying ? 'Paiement en cours…' : 'Payer en sandbox',
                ),
              ),
            ],
            if (_payment != null)
              Text('Paiement : ${_payment!['status'] ?? 'À vérifier'}'),
            if (_paymentError != null)
              Text(
                _paymentError!,
                style: TextStyle(color: Theme.of(context).colorScheme.error),
              ),
          ],
        ],
      ),
    );
  }
}
