import 'dart:async';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../app/runtime/app_runtime.dart';
import '../../network/api_error.dart';
import '../journey/journey_repository.dart';

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
    unawaited(_prepare());
  }

  /// Display the Profile's acquired Commerce fact from an authorized Journey.
  /// The Commerce owner is still responsible for confirmation and actions.
  Future<void> _prepare() async {
    final store = widget.runtime.store;
    if (store != null) {
      try {
        final journeys = await store.readProjections(
          JourneyRepository.projectionKind,
        );
        for (final local in journeys) {
          final source = await widget.runtime.journeys?.readSource(
            local.resourceKey,
          );
          if (source?.invalidated == true &&
              const {
                'permission_denied',
                'not_found',
              }.contains(source?.lastErrorCode)) {
            continue;
          }
          final payment = local.payload['payment'];
          if (payment is! Map) continue;
          final order = payment['order'];
          if (order is! Map || order['id'] != widget.orderId) continue;
          if (!mounted) return;
          setState(
            () => _order = {
              'id': widget.orderId,
              'kind': 'commerce_order',
              'status': order['state'],
              'checkout': {
                'total': order['total'],
                'currency': order['currency'],
                'payment_mode': order['payment_mode'],
              },
            },
          );
          break;
        }
      } on Object {
        // A missing local summary does not invalidate another owner fact.
      }
    }
    if (mounted) unawaited(_load());
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
    } on MakoloApiError catch (error) {
      if (!mounted) return;
      final denied = error.statusCode == 403 || error.statusCode == 404;
      setState(() {
        _loading = false;
        if (denied) _order = null;
        _error = _order == null
            ? 'Cette commande ne peut pas être consultée pour le moment.'
            : null;
      });
    } on Object {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = _order == null
            ? 'Cette commande ne peut pas être consultée pour le moment.'
            : null;
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
          if (_loading && _order == null)
            const Center(child: CircularProgressIndicator()),
          if (_loading && _order != null) const LinearProgressIndicator(),
          if (_order != null) ...[
            Text(
              _order!['reference'] == null
                  ? 'Ma commande'
                  : 'Commande ${_order!['reference']}',
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
                _ => 'Statut du paiement à vérifier.',
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
