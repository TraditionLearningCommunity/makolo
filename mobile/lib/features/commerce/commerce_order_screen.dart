import 'dart:async';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../app/runtime/app_runtime.dart';

/// Private read of the Commerce owner truth; never interpret an order as paid.
class CommerceOrderScreen extends StatefulWidget {
  const CommerceOrderScreen({
    super.key,
    required this.runtime,
    required this.orderId,
  });

  final AppRuntime runtime;
  final String orderId;

  @override
  State<CommerceOrderScreen> createState() => _CommerceOrderScreenState();
}

class _CommerceOrderScreenState extends State<CommerceOrderScreen> {
  Map<String, dynamic>? _order;
  bool _loading = true;
  String? _error;

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
      final id = Uri.encodeComponent(widget.orderId);
      final response = await widget.runtime.api!.get('api/v1/me/orders/$id/');
      final order = response.jsonObject();
      if (order['kind'] != 'commerce_order' || order['id'] != widget.orderId) {
        throw const FormatException('Commerce order identity mismatch');
      }
      if (!mounted) return;
      setState(() {
        _order = order;
        _loading = false;
      });
    } on Object {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = 'Cette commande ne peut pas être consultée pour le moment.';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final checkout = _order?['checkout'];
    final details = checkout is Map ? checkout : const {};
    final obligationId = details['payment_obligation_id'];
    final hasObligation = obligationId is String && obligationId.isNotEmpty;
    final items = _order?['items'];
    return Scaffold(
      appBar: AppBar(
        title: const Text('Ma commande'),
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
          if (_loading) const Center(child: CircularProgressIndicator()),
          if (_order != null) ...[
            Text(
              'Commande ${_order!['reference'] ?? ''}',
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            const SizedBox(height: 12),
            Text(
              'État : ${switch (_order!['status']) {
                'confirmed' => 'Confirmée',
                'pending' => 'En attente',
                'cancelled' => 'Annulée',
                'expired' => 'Expirée',
                'refunded' => 'Remboursée',
                _ => 'À vérifier',
              }}',
            ),
            Text(
              'Montant : ${details['total'] ?? 'À vérifier'} '
              '${details['currency'] ?? ''}',
            ),
            if (items is List) ...[
              const SizedBox(height: 20),
              for (final entry in items.whereType<Map>())
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  title: Text(entry['label']?.toString() ?? 'Offre'),
                  subtitle: Text('Quantité : ${entry['quantity'] ?? ''}'),
                  trailing: Text(entry['line_total']?.toString() ?? ''),
                ),
            ],
            if (hasObligation) ...[
              const SizedBox(height: 20),
              Text(
                'Paiement : ${details['payment_obligation_status'] ?? 'À vérifier'}',
              ),
              const SizedBox(height: 12),
              FilledButton.icon(
                onPressed: () => context.push(
                  '/payments/obligations/${Uri.encodeComponent(obligationId)}',
                ),
                icon: const Icon(Icons.payments_outlined),
                label: const Text('Consulter le paiement'),
              ),
            ] else ...[
              const SizedBox(height: 12),
              Text(switch (details['payment_mode']) {
                'none' => 'Aucun paiement requis pour cette commande.',
                'on_site' => 'Paiement prévu sur place. Aucun règlement confirmé dans Makolo.',
                'later' => 'Paiement différé. Aucun règlement confirmé.',
                _ => 'L’état financier doit être vérifié auprès de Makolo.',
              }),
            ],
          ],
          if (_error != null) ...[
            Text(
              _error!,
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
            TextButton(onPressed: _load, child: const Text('Réessayer')),
          ],
        ],
      ),
    );
  }
}
