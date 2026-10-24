import 'dart:async';

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
      if (order['id'] != widget.orderId) {
        throw const FormatException('Order identity mismatch');
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
            const Text(
              'Une commande créée ne signifie pas qu’un paiement ou '
              'un droit d’accès est confirmé. Son état est vérifié sur Makolo.',
            ),
          ],
        ],
      ),
    );
  }
}
