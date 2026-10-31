import 'dart:async';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../app/runtime/app_runtime.dart';

/// A context-specific Obtention entry. The owner API selects the published
/// modes, creates the Journey, and revalidates permissions and requirements.
class ObtentionChooseScreen extends StatefulWidget {
  const ObtentionChooseScreen({
    super.key,
    required this.runtime,
    required this.obtentionId,
  });

  final AppRuntime runtime;
  final String obtentionId;

  @override
  State<ObtentionChooseScreen> createState() => _ObtentionChooseScreenState();
}

class _ObtentionChooseScreenState extends State<ObtentionChooseScreen> {
  Map<String, dynamic>? _obtention;
  List<Map<String, dynamic>> _modes = const [];
  List<Map<String, dynamic>> _existing = const [];
  String? _selectedMode;
  bool _loading = true;
  bool _submitting = false;
  bool _attempted = false;
  String? _error;
  String? _journeyId;

  @override
  void initState() {
    super.initState();
    unawaited(_load());
  }

  Map<String, dynamic>? get _existingForSelection {
    for (final journey in _existing) {
      if (journey['mode'] == _selectedMode && journey['id'] is String) {
        return journey;
      }
    }
    return null;
  }

  Future<void> _readExisting() async {
    if (!widget.runtime.isAuthenticated) return;
    try {
      final id = Uri.encodeComponent(widget.obtentionId);
      final result = (await widget.runtime.api!.get(
        'api/v1/obtention/$id/journeys/',
      )).jsonObject();
      final list = result['existing_journeys'];
      if (list is List && mounted) {
        setState(() {
          _existing = list
              .whereType<Map>()
              .map((row) => Map<String, dynamic>.from(row))
              .toList(growable: false);
        });
      }
    } on Object {
      // Never invent an existing Journey when the owner read fails.
    }
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final api = widget.runtime.api;
      if (api == null) throw StateError('API unavailable');
      final id = Uri.encodeComponent(widget.obtentionId);
      final response = await api.publicGet('api/v1/obtention/$id/');
      final data = response.jsonObject();
      if (data['id'] != widget.obtentionId) {
        throw const FormatException('Obtention identity mismatch');
      }
      final config = data['configuration'];
      if (config is! Map || config['modes'] is! List) {
        throw const FormatException('Missing published modes');
      }
      final modes = (config['modes'] as List)
          .whereType<Map>()
          .map((mode) => Map<String, dynamic>.from(mode))
          .where((mode) => mode['code'] is String)
          .toList(growable: false);
      if (!mounted) return;
      setState(() {
        _obtention = data;
        _modes = modes;
        _selectedMode = modes.isEmpty ? null : modes.first['code'] as String;
        _loading = false;
      });
      await _readExisting();
    } on Object {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = 'Cette possibilité n’est pas disponible.';
      });
    }
  }

  Future<void> _begin() async {
    if (_submitting || _selectedMode == null) return;
    if (!widget.runtime.isAuthenticated) {
      widget.runtime.recovery.requireAuthentication(
        '/obtention/${widget.obtentionId}/choose',
      );
      context.push('/login');
      return;
    }
    final existing = _existingForSelection;
    if (existing != null && existing['id'] is String) {
      context.push(
        '/journeys/${Uri.encodeComponent(existing['id'] as String)}',
      );
      return;
    }
    setState(() {
      _submitting = true;
      _attempted = true;
      _error = null;
    });
    try {
      final id = Uri.encodeComponent(widget.obtentionId);
      final response = await widget.runtime.api!.post(
        'api/v1/obtention/$id/journeys/',
        body: {'mode': _selectedMode},
      );
      final journey = response.jsonObject();
      if (journey['id'] is! String || journey['id'].toString().isEmpty) {
        throw const FormatException('Journey identity missing');
      }
      if (!mounted) return;
      setState(() => _journeyId = journey['id'] as String);
      context.push('/journeys/${Uri.encodeComponent(_journeyId!)}');
    } on Object {
      await _readExisting();
      if (!mounted) return;
      final existing = _existingForSelection;
      if (existing != null && existing['id'] is String) {
        context.push(
          '/journeys/${Uri.encodeComponent(existing['id'] as String)}',
        );
        return;
      }
      setState(() {
        _attempted = false;
        _error =
            'Démarrage à vérifier. Réessayez si aucune démarche n’apparaît.';
      });
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final obtention = _obtention;
    final config = obtention?['configuration'];
    final configuration = config is Map ? config : const {};
    return Scaffold(
      appBar: AppBar(title: const Text('Obtenir')),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          if (_loading)
            const Center(child: CircularProgressIndicator())
          else if (obtention == null)
            OutlinedButton(onPressed: _load, child: const Text('Réessayer'))
          else ...[
            Text(
              (obtention['activity'] is Map
                          ? (obtention['activity'] as Map)['title']
                          : null)
                      ?.toString() ??
                  'Obtention',
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            if ((configuration['result_label'] ?? '')
                .toString()
                .isNotEmpty) ...[
              const SizedBox(height: 12),
              Text(configuration['result_label'].toString()),
            ],
            const SizedBox(height: 20),
            if (_modes.isEmpty)
              const Text('Aucun mode disponible.')
            else ...[
              Text(
                'Comment souhaitez-vous l’obtenir ?',
                style: Theme.of(context).textTheme.titleMedium,
              ),
              const SizedBox(height: 8),
              RadioGroup<String>(
                groupValue: _selectedMode,
                onChanged: (code) {
                  if (!_attempted) setState(() => _selectedMode = code);
                },
                child: Column(
                  children: [
                    for (final mode in _modes)
                      RadioListTile<String>(
                        value: mode['code'] as String,
                        title: Text(
                          mode['label']?.toString() ?? mode['code'].toString(),
                        ),
                      ),
                  ],
                ),
              ),
              const SizedBox(height: 20),
              FilledButton.icon(
                onPressed: _submitting ? null : _begin,
                icon: const Icon(Icons.play_arrow_rounded),
                label: Text(
                  _submitting
                      ? 'Ouverture en cours…'
                      : _existingForSelection != null
                      ? 'Continuer ma démarche'
                      : widget.runtime.isAuthenticated
                      ? 'Ouvrir ma démarche'
                      : 'Se connecter pour continuer',
                ),
              ),
              if (_journeyId case final id?) ...[
                const SizedBox(height: 12),
                OutlinedButton(
                  onPressed: () =>
                      context.push('/journeys/${Uri.encodeComponent(id)}'),
                  child: const Text('Voir ma démarche'),
                ),
              ],
            ],
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
