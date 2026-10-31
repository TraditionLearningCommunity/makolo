import 'dart:async';
import 'dart:math';

import 'package:flutter/material.dart';

import '../../app/runtime/app_runtime.dart';

/// Native payment depth backed by the canonical PaymentObligation and Payment
/// services. A success screen is shown only after the owner confirms it.
class PaymentObligationScreen extends StatefulWidget {
  const PaymentObligationScreen({
    super.key,
    required this.runtime,
    required this.obligationId,
  });

  final AppRuntime runtime;
  final String obligationId;

  @override
  State<PaymentObligationScreen> createState() =>
      _PaymentObligationScreenState();
}

class _PaymentObligationScreenState extends State<PaymentObligationScreen> {
  Map<String, dynamic>? _obligation;
  Map<String, dynamic>? _payment;
  bool _loading = true;
  bool _paying = false;
  bool _sandboxAvailable = false;
  String? _error;
  final String _idempotencyKey = _newKey();

  static String _newKey() {
    final random = Random.secure();
    return List.generate(
      32,
      (_) => random.nextInt(16).toRadixString(16),
    ).join();
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
      final api = widget.runtime.api!;
      final id = Uri.encodeComponent(widget.obligationId);
      final response = await api.get('api/v1/payments/obligations/$id/');
      final obligation = response.jsonObject();
      if (obligation['id'] != widget.obligationId) {
        throw const FormatException('Obligation identity mismatch');
      }
      var sandbox = false;
      try {
        final config = await api.get('api/v1/payments/configuration/');
        sandbox = config.jsonObject()['sandbox_enabled'] == true;
      } on Object {
        // Unknown provider availability is not permission to pay.
      }
      if (!mounted) return;
      setState(() {
        _obligation = obligation;
        _payment = obligation['active_payment'] is Map
            ? Map<String, dynamic>.from(obligation['active_payment'] as Map)
            : null;
        _sandboxAvailable = sandbox;
        _loading = false;
      });
    } on Object {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = 'Paiement indisponible.';
      });
    }
  }

  Future<void> _pay() async {
    final obligation = _obligation;
    if (_paying ||
        obligation == null ||
        !_sandboxAvailable ||
        obligation['processing_mode'] != 'makolo_provider' ||
        !(obligation['capabilities'] is List &&
            (obligation['capabilities'] as List).contains('pay'))) {
      return;
    }
    setState(() {
      _paying = true;
      _error = null;
    });
    try {
      final api = widget.runtime.api!;
      var payment = _payment;
      if (payment == null ||
          payment['provider'] != 'sandbox' ||
          payment['status'] == 'failed' ||
          payment['status'] == 'cancelled') {
        final id = Uri.encodeComponent(widget.obligationId);
        final response = await api.post(
          'api/v1/payments/obligations/$id/',
          body: {
            'provider': 'sandbox',
            'method': 'card',
            'idempotency_key': _idempotencyKey,
          },
        );
        payment = response.jsonObject();
        if (payment['id'] is! String) {
          throw const FormatException('Payment identity missing');
        }
        _payment = payment;
      }
      if (payment['status'] != 'succeeded') {
        final paymentId = Uri.encodeComponent(payment['id'] as String);
        final response = await api.post(
          'api/v1/payments/payments/$paymentId/sandbox-complete/',
        );
        payment = response.jsonObject();
        _payment = payment;
      }
      if (!mounted) return;
      await _load();
      if (mounted && payment['status'] != 'succeeded') {
        setState(() => _error = 'Paiement à vérifier.');
      }
    } on Object {
      // The request may have succeeded while its response was lost.
      // Resolve the owner state before showing a failure or replaying.
      await _load();
      if (mounted && _obligation?['status'] != 'satisfied') {
        setState(
          () => _error = 'Paiement à vérifier. Actualisez avant de réessayer.',
        );
      }
    } finally {
      if (mounted) setState(() => _paying = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final obligation = _obligation;
    final status = obligation?['status']?.toString() ?? '';
    final canPay =
        obligation?['capabilities'] is List &&
        (obligation!['capabilities'] as List).contains('pay');
    final terminal = {
      'satisfied',
      'waived',
      'expired',
      'cancelled',
      'refunded',
    }.contains(status);
    return Scaffold(
      appBar: AppBar(
        title: const Text('Paiement'),
        actions: [
          IconButton(
            onPressed: _loading || _paying ? null : _load,
            tooltip: 'Actualiser',
            icon: const Icon(Icons.refresh_rounded),
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          if (_loading)
            const Center(child: CircularProgressIndicator())
          else if (obligation == null)
            OutlinedButton(onPressed: _load, child: const Text('Réessayer'))
          else ...[
            Text(
              obligation['label']?.toString() ?? 'Paiement',
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            const SizedBox(height: 16),
            Text(
              'Montant : ${obligation['amount']?.toString() ?? ''} ${obligation['currency']?.toString() ?? ''}',
            ),
            const SizedBox(height: 12),
            Text('État : $status'),
            if (status == 'satisfied') ...[
              const SizedBox(height: 16),
              const Row(
                children: [
                  Icon(Icons.check_circle_outline_rounded),
                  SizedBox(width: 8),
                  Text('Paiement confirmé'),
                ],
              ),
            ] else if (canPay &&
                !terminal &&
                _payment?['status'] != 'succeeded') ...[
              const SizedBox(height: 20),
              if (_sandboxAvailable)
                FilledButton.icon(
                  onPressed: _paying || _loading ? null : _pay,
                  icon: const Icon(Icons.credit_card_rounded),
                  label: Text(
                    _paying ? 'Paiement en cours…' : 'Payer en sandbox',
                  ),
                )
              else
                const Text('Aucun moyen de paiement disponible.'),
            ],
            if (_payment != null)
              Text(
                'Transaction : ${_payment!['status']?.toString() ?? 'À vérifier'}',
              ),
          ],
          if (_error case final error?) ...[
            const SizedBox(height: 12),
            Text(
              error,
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
          ],
        ],
      ),
    );
  }
}
