import 'dart:async';
import 'dart:math';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../app/runtime/app_runtime.dart';

/// Native Services owner handoff. The server owns eligibility, idempotence
/// and the actual Journey; Discovery only provides the typed Service identity.
class ServiceStartScreen extends StatefulWidget {
  const ServiceStartScreen({
    super.key,
    required this.runtime,
    required this.serviceId,
  });

  final AppRuntime runtime;
  final String serviceId;

  @override
  State<ServiceStartScreen> createState() => _ServiceStartScreenState();
}

class _ServiceStartScreenState extends State<ServiceStartScreen> {
  final _objective = TextEditingController();
  bool _loading = true;
  bool _submitting = false;
  bool _attempted = false;
  String? _error;
  Map<String, dynamic>? _requirements;
  late String _operationKey = _newOperationKey();

  static String _newOperationKey() {
    const chars = 'abcdefghijklmnopqrstuvwxyz0123456789';
    final random = Random.secure();
    return List.generate(
      32,
      (_) => chars[random.nextInt(chars.length)],
    ).join();
  }

  @override
  void initState() {
    super.initState();
    unawaited(_prevalidate());
  }

  @override
  void dispose() {
    _objective.dispose();
    super.dispose();
  }

  Future<void> _prevalidate() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final api = widget.runtime.api;
      if (api == null) throw StateError('Session unavailable');
      final response = await api.get(
        'api/v1/services/${Uri.encodeComponent(widget.serviceId)}/start/',
      );
      final body = response.jsonObject();
      final requirements = body['requirements'];
      final service = body['service'];
      final capabilities = body['capabilities'];
      if (requirements is! Map ||
          service is! Map ||
          service['id'] != widget.serviceId ||
          capabilities is! List ||
          !capabilities.contains('start')) {
        throw const FormatException('Service prevalidation invalid');
      }
      if (!mounted) return;
      setState(() {
        _requirements = Map<String, dynamic>.from(requirements);
        _loading = false;
      });
    } on Object {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = 'Impossible de vérifier les conditions de ce Service.';
      });
    }
  }

  Future<void> _start() async {
    if (_loading || _submitting || _requirements == null) return;
    if (_requirements!['opportunity_required'] == true) return;
    setState(() {
      _submitting = true;
      _error = null;
      _attempted = true;
    });
    try {
      final api = widget.runtime.api;
      if (api == null) throw StateError('Session unavailable');
      final response = await api.post(
        'api/v1/services/${Uri.encodeComponent(widget.serviceId)}/start/',
        headers: {'Idempotency-Key': _operationKey},
        body: {'objective': _objective.text.trim()},
      );
      final data = response.jsonObject();
      final journey = data['journey'];
      if (journey is! Map ||
          journey['kind'] != 'journey' ||
          journey['id'] is! String) {
        throw const FormatException('Service start response invalid');
      }
      if (!mounted) return;
      context.push('/journeys/${journey['id']}');
    } on Object {
      if (!mounted) return;
      setState(() {
        _error =
            'Le démarrage n’a pas été confirmé. Réessayez sans changer la demande.';
      });
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final needsOpportunity = _requirements?['opportunity_required'] == true;
    return Scaffold(
      appBar: AppBar(title: const Text('Commencer un Service')),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          if (_loading)
            const Center(child: CircularProgressIndicator())
          else if (_requirements == null)
            OutlinedButton.icon(
              onPressed: _prevalidate,
              icon: const Icon(Icons.refresh_rounded),
              label: const Text('Réessayer'),
            )
          else ...[
            Text('Votre objectif',
                style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 12),
            TextField(
              controller: _objective,
              maxLength: 1000,
              enabled: !_attempted,
              maxLines: 5,
              decoration: const InputDecoration(
                hintText: 'Quel résultat souhaitez-vous obtenir ?',
                border: OutlineInputBorder(),
              ),
            ),
            if (needsOpportunity)
              const Text(
                'Ce Service nécessite une Opportunity choisie. '
                'Le démarrage direct n’est pas disponible dans ce parcours.',
              ),
            const SizedBox(height: 16),
            FilledButton.icon(
              onPressed: _submitting || needsOpportunity ? null : _start,
              icon: const Icon(Icons.play_arrow_rounded),
              label: Text(_submitting ? 'Démarrage…' : 'Commencer'),
            ),
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
