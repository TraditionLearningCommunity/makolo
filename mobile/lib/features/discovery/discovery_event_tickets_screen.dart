import 'dart:async';
import 'dart:convert';
import 'dart:math';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../app/runtime/app_runtime.dart';

/// Event Tickets owner API: browse public ticket types and submit a real order.
/// No local allocation, Access or Payment state is manufactured by this view.
class DiscoveryEventTicketsScreen extends StatefulWidget {
  const DiscoveryEventTicketsScreen({
    super.key,
    required this.runtime,
    required this.eventSlug,
  });

  final AppRuntime runtime;
  final String eventSlug;

  @override
  State<DiscoveryEventTicketsScreen> createState() =>
      _DiscoveryEventTicketsScreenState();
}

class _DiscoveryEventTicketsScreenState
    extends State<DiscoveryEventTicketsScreen> {
  final _name = TextEditingController();
  final _email = TextEditingController();
  bool _loading = true;
  bool _submitting = false;
  bool _joiningWaitlist = false;
  String? _waitlistNotice;
  String? _error;
  String? _eventId;
  String _eventTitle = '';
  List<Map<String, dynamic>> _types = const [];
  String? _ticketTypeId;
  int _quantity = 1;
  late final String _idempotencyKey = _newKey();

  static String _newKey() {
    final random = Random.secure();
    final hex = List.generate(
      32,
      (_) => random.nextInt(16).toRadixString(16),
    ).join();
    return '${hex.substring(0, 8)}-${hex.substring(8, 12)}-4'
        '${hex.substring(13, 16)}-a${hex.substring(17, 20)}-'
        '${hex.substring(20, 32)}';
  }

  @override
  void initState() {
    super.initState();
    unawaited(_load());
  }

  @override
  void dispose() {
    _name.dispose();
    _email.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final api = widget.runtime.api;
      if (api == null) throw StateError('API unavailable');
      final slug = Uri.encodeComponent(widget.eventSlug);
      final detail = (await api.publicGet('api/v1/events/discover/$slug/'))
          .jsonObject();
      final ticketResponse = await api.publicGet(
        'api/v1/events/$slug/ticket-types/',
      );
      final decoded = jsonDecode(ticketResponse.body);
      final collection = decoded is Map ? decoded['results'] : decoded;
      if (detail['id'] is! String || collection is! List) {
        throw const FormatException('Unexpected Event Ticket owner response');
      }
      if (!mounted) return;
      setState(() {
        _eventId = detail['id'] as String;
        _eventTitle = detail['title']?.toString() ?? 'Billets';
        _types = collection
            .whereType<Map>()
            .map((value) => Map<String, dynamic>.from(value))
            .toList(growable: false);
        _loading = false;
      });
    } on Object {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = 'Impossible de consulter les billets de cet événement.';
      });
    }
  }

  Future<void> _order() async {
    if (_submitting || _eventId == null || _ticketTypeId == null) return;
    if (!widget.runtime.isAuthenticated) {
      widget.runtime.recovery.requireAuthentication(
        '/events/${widget.eventSlug}/tickets',
      );
      context.push('/login');
      return;
    }
    if (_name.text.trim().isEmpty || !_email.text.contains('@')) {
      setState(() => _error = 'Indiquez un nom et une adresse e-mail valides.');
      return;
    }
    setState(() {
      _submitting = true;
      _error = null;
    });
    try {
      final response = await widget.runtime.api!.post(
        'api/v1/tickets/orders/',
        body: {
          'idempotency_key': _idempotencyKey,
          'event_id': _eventId,
          'customer_name': _name.text.trim(),
          'customer_email': _email.text.trim(),
          'items': [
            {'ticket_type_id': _ticketTypeId, 'quantity': _quantity},
          ],
        },
      );
      final payload = response.jsonObject();
      final orderId = payload['id'];
      if (orderId is! String || orderId.isEmpty) {
        throw const FormatException('Unconfirmed Ticket order');
      }
      if (!mounted) return;
      context.push('/tickets/orders/$orderId');
    } on Object {
      if (!mounted) return;
      setState(() {
        _error =
            'La commande n’a pas été confirmée. '
            'Réessayez avec la même demande pour préserver l’idempotence.';
      });
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  Future<void> _joinWaitlist(String ticketTypeId) async {
    if (_joiningWaitlist) return;
    if (!widget.runtime.isAuthenticated) {
      widget.runtime.recovery.requireAuthentication(
        '/events/${widget.eventSlug}/tickets',
      );
      context.push('/login');
      return;
    }
    setState(() {
      _joiningWaitlist = true;
      _error = null;
      _waitlistNotice = null;
    });
    try {
      final response = await widget.runtime.api!.post(
        'api/v1/tickets/waitlist/',
        body: {'ticket_type_id': ticketTypeId, 'quantity': 1},
      );
      final entry = response.jsonObject();
      if (entry['id'] is! String) {
        throw const FormatException('Waitlist entry missing');
      }
      if (!mounted) return;
      setState(
        () => _waitlistNotice = 'Inscription sur liste d’attente enregistrée.',
      );
    } on Object {
      if (!mounted) return;
      setState(() => _error = 'Liste d’attente indisponible.');
    } finally {
      if (mounted) setState(() => _joiningWaitlist = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final chosen = _types.where(
      (type) => type['id']?.toString() == _ticketTypeId,
    );
    final selected = chosen.isEmpty ? null : chosen.first;
    final minimum = int.tryParse('${selected?['min_per_order'] ?? 1}') ?? 1;
    final maximum = int.tryParse('${selected?['max_per_order'] ?? 10}') ?? 10;
    final allowed = selected?['is_on_sale'] == true;
    return Scaffold(
      appBar: AppBar(
        title: Text(_eventTitle.isEmpty ? 'Billets' : _eventTitle),
      ),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          if (_loading)
            const Center(child: CircularProgressIndicator())
          else if (_eventId == null)
            OutlinedButton(onPressed: _load, child: const Text('Réessayer'))
          else ...[
            Text(
              'Billets disponibles',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 12),
            if (_types.isEmpty)
              const Text('Aucun type de billet n’est publié actuellement.'),
            RadioGroup<String>(
              groupValue: _ticketTypeId,
              onChanged: (value) {
                final matching = _types.where(
                  (ticket) => ticket['id']?.toString() == value,
                );
                if (matching.isEmpty || matching.first['is_on_sale'] != true) {
                  return;
                }
                setState(() {
                  _ticketTypeId = value;
                  _quantity =
                      int.tryParse('${matching.first['min_per_order'] ?? 1}') ??
                      1;
                });
              },
              child: Column(
                children: [
                  for (final ticket in _types)
                    RadioListTile<String>(
                      value: ticket['id']?.toString() ?? '',
                      enabled: ticket['is_on_sale'] == true,
                      title: Text(ticket['name']?.toString() ?? 'Billet'),
                      subtitle: Text(
                        '${ticket['price'] ?? ''} ${ticket['currency'] ?? ''}'
                        '${ticket['is_on_sale'] == true ? '' : ' · Non disponible'}',
                      ),
                      secondary:
                          ticket['is_on_sale'] != true &&
                              ticket['available_quantity'] == 0 &&
                              ticket['is_active'] == true &&
                              ticket['is_public'] == true
                          ? TextButton(
                              onPressed: _joiningWaitlist
                                  ? null
                                  : () => _joinWaitlist(
                                      ticket['id']?.toString() ?? '',
                                    ),
                              child: const Text('Attendre une place'),
                            )
                          : null,
                    ),
                ],
              ),
            ),
            if (selected != null) ...[
              const SizedBox(height: 16),
              Row(
                children: [
                  const Text('Quantité'),
                  const Spacer(),
                  IconButton(
                    onPressed: _quantity > minimum
                        ? () => setState(() => _quantity--)
                        : null,
                    icon: const Icon(Icons.remove),
                  ),
                  Text('$_quantity'),
                  IconButton(
                    onPressed: _quantity < maximum
                        ? () => setState(() => _quantity++)
                        : null,
                    icon: const Icon(Icons.add),
                  ),
                ],
              ),
              const SizedBox(height: 16),
              TextField(
                controller: _name,
                enabled: !_submitting,
                decoration: const InputDecoration(
                  labelText: 'Nom du bénéficiaire',
                ),
              ),
              TextField(
                controller: _email,
                enabled: !_submitting,
                keyboardType: TextInputType.emailAddress,
                decoration: const InputDecoration(labelText: 'Adresse e-mail'),
              ),
              const SizedBox(height: 16),
              FilledButton.icon(
                onPressed: allowed && !_submitting ? _order : null,
                icon: const Icon(Icons.confirmation_number_outlined),
                label: Text(
                  _submitting
                      ? 'Demande en cours…'
                      : widget.runtime.isAuthenticated
                      ? 'Passer commande'
                      : 'Se connecter pour commander',
                ),
              ),
            ],
          ],
          if (_waitlistNotice != null) ...[
            const SizedBox(height: 12),
            Text(_waitlistNotice!),
          ],
          if (_error != null) ...[
            const SizedBox(height: 12),
            Text(
              _error!,
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
          ],
        ],
      ),
    );
  }
}
