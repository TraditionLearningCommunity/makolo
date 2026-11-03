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
  final _opportunitySearch = TextEditingController();
  List<Map<String, dynamic>> _opportunities = const [];
  String? _selectedOpportunity;
  bool _searchingOpportunities = false;
  bool _loading = true;
  bool _submitting = false;
  bool _attempted = false;
  String? _error;
  Map<String, dynamic>? _requirements;
  String _operationKey = _newOperationKey();

  String get _interactionId =>
      'services.start:${widget.runtime.session?.profileId ?? 'guest'}:'
      '${widget.serviceId}';

  Future<void> _initialize() async {
    if (widget.runtime.isAuthenticated && widget.runtime.interactions != null) {
      try {
        final previous = await widget.runtime.interactions!.read(
          _interactionId,
        );
        final key = previous['idempotency_key'];
        if (key is String && key.isNotEmpty) {
          _operationKey = key;
          _objective.text = previous['objective'] is String
              ? previous['objective'] as String
              : '';
          _selectedOpportunity = previous['opportunity'] as String?;
          _attempted = true;
        }
      } on Object {
        // Idempotence is still enforced by the owner when a retry is possible.
      }
    }
    if (mounted) await _prevalidate();
  }

  static String _newOperationKey() {
    const chars = 'abcdefghijklmnopqrstuvwxyz0123456789';
    final random = Random.secure();
    return List.generate(32, (_) => chars[random.nextInt(chars.length)]).join();
  }

  @override
  void initState() {
    super.initState();
    unawaited(_initialize());
  }

  @override
  void dispose() {
    _objective.dispose();
    _opportunitySearch.dispose();
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
      final choices = body['opportunities'];
      final results = choices is Map ? choices['results'] : null;
      setState(() {
        _requirements = Map<String, dynamic>.from(requirements);
        _opportunities = results is List
            ? results
                  .whereType<Map>()
                  .map((value) => Map<String, dynamic>.from(value))
                  .toList(growable: false)
            : const [];
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

  Future<void> _searchOpportunities() async {
    if (_searchingOpportunities || _attempted) return;
    setState(() => _searchingOpportunities = true);
    try {
      final query = Uri.encodeQueryComponent(_opportunitySearch.text.trim());
      final response = await widget.runtime.api!.get(
        'api/v1/services/${Uri.encodeComponent(widget.serviceId)}/start/?q=$query',
      );
      final choices = response.jsonObject()['opportunities'];
      final results = choices is Map ? choices['results'] : null;
      if (results is! List) throw const FormatException('Invalid choices');
      if (!mounted) return;
      setState(() {
        _opportunities = results
            .whereType<Map>()
            .map((value) => Map<String, dynamic>.from(value))
            .toList(growable: false);
        _selectedOpportunity = null;
      });
    } on Object {
      if (mounted) {
        setState(
          () => _error =
              'Impossible de rechercher les Opportunities disponibles.',
        );
      }
    } finally {
      if (mounted) setState(() => _searchingOpportunities = false);
    }
  }

  Future<void> _start() async {
    if (_loading || _submitting || _requirements == null) return;
    if (_requirements!['opportunity_required'] == true &&
        _selectedOpportunity == null) {
      return;
    }
    setState(() {
      _submitting = true;
      _error = null;
      _attempted = true;
    });
    try {
      final store = widget.runtime.interactions;
      if (store != null) {
        await store.save(_interactionId, {
          'idempotency_key': _operationKey,
          'objective': _objective.text.trim(),
          'opportunity': _selectedOpportunity,
        });
      }
      final api = widget.runtime.api;
      if (api == null) throw StateError('Session unavailable');
      final response = await api.post(
        'api/v1/services/${Uri.encodeComponent(widget.serviceId)}/start/',
        headers: {'Idempotency-Key': _operationKey},
        body: {
          'objective': _objective.text.trim(),
          if (_selectedOpportunity != null) 'opportunity': _selectedOpportunity,
        },
      );
      final data = response.jsonObject();
      final journey = data['journey'];
      if (journey is! Map ||
          journey['kind'] != 'journey' ||
          journey['id'] is! String) {
        throw const FormatException('Service start response invalid');
      }
      if (!mounted) return;
      if (store != null) {
        unawaited(store.clear(_interactionId).catchError((Object _) {}));
      }
      context.push('/journeys/${journey['id']}');
    } on Object {
      if (!mounted) return;
      setState(() {
        _error = 'Le démarrage n’a pas été confirmé. Réessayez sans changer la demande.';
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
            Text(
              'Votre objectif',
              style: Theme.of(context).textTheme.titleMedium,
            ),
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
            if (_requirements?['opportunity_policy'] != 'none') ...[
              const SizedBox(height: 12),
              TextField(
                controller: _opportunitySearch,
                enabled: !_attempted,
                decoration: InputDecoration(
                  labelText: 'Rechercher une Opportunity',
                  suffixIcon: IconButton(
                    tooltip: 'Rechercher',
                    onPressed: _searchingOpportunities || _attempted
                        ? null
                        : _searchOpportunities,
                    icon: const Icon(Icons.search),
                  ),
                ),
                onSubmitted: (_) => _searchOpportunities(),
              ),
              DropdownButtonFormField<String>(
                initialValue: _selectedOpportunity,
                isExpanded: true,
                decoration: InputDecoration(
                  labelText: needsOpportunity
                      ? 'Opportunity requise'
                      : 'Opportunity (facultatif)',
                ),
                items: [
                  if (_selectedOpportunity != null &&
                      !_opportunities.any(
                        (row) => row['id'] == _selectedOpportunity,
                      ))
                    DropdownMenuItem<String>(
                      value: _selectedOpportunity,
                      child: const Text('Choix précédent'),
                    ),
                  if (!needsOpportunity)
                    const DropdownMenuItem<String>(
                      value: '',
                      child: Text('Sans Opportunity'),
                    ),
                  for (final opportunity in _opportunities)
                    DropdownMenuItem<String>(
                      value: opportunity['id']?.toString() ?? '',
                      child: Text(
                        opportunity['title']?.toString() ?? 'Opportunity',
                      ),
                    ),
                ],
                onChanged: _attempted
                    ? null
                    : (value) => setState(
                        () => _selectedOpportunity =
                            value == null || value.isEmpty ? null : value,
                      ),
              ),
            ],
            const SizedBox(height: 16),
            FilledButton.icon(
              onPressed:
                  _submitting ||
                      (needsOpportunity && _selectedOpportunity == null)
                  ? null
                  : _start,
              icon: const Icon(Icons.play_arrow_rounded),
              label: Text(
                _submitting
                    ? 'Démarrage…'
                    : _attempted
                    ? 'Reprendre la demande'
                    : 'Commencer',
              ),
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
